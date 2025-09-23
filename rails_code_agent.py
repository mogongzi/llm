#!/usr/bin/env python3
"""
Rails Code Analysis Agent

A specialized agent for analyzing Ruby on Rails codebases with intelligent
SQL query to source code mapping, Rails convention understanding, and
multi-modal code search capabilities.

Features:
- SQL query parsing and table-to-model mapping
- Rails convention-based code discovery
- Multi-tier search (Symbol → Structural → Semantic)
- Integration with tree-sitter, Solargraph, and other Ruby tools
- Separate from naive RAG for code-specific intelligence

Usage:
    agent = RailsCodeAgent()
    agent.enable()
    results = agent.analyze_query("SELECT * FROM shopping_cart WHERE user_id = ?")
"""

from __future__ import annotations

import os
import re
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
try:
    from rich.console import Console
    console = Console()
except ImportError:
    # Fallback console for environments without rich
    class SimpleConsole:
        def print(self, text, style=None):
            print(text)
    console = SimpleConsole()


@dataclass
class CodeResult:
    """Represents a code search result with metadata."""
    file_path: str
    line_number: int
    code_snippet: str
    context_lines: List[str] = field(default_factory=list)
    relevance_score: float = 0.0
    result_type: str = "unknown"  # 'exact_match', 'model_def', 'controller', 'related'
    description: str = ""


@dataclass
class SQLQuery:
    """Parsed SQL query structure."""
    original: str
    tables: List[str] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    query_type: str = "SELECT"  # SELECT, INSERT, UPDATE, DELETE


class RailsCodeAgent:
    """
    Main Rails code analysis agent.

    Provides intelligent code discovery for Rails applications by combining:
    - SQL query parsing
    - Rails naming conventions
    - Multi-tool code search
    - Semantic code understanding
    """

    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize the Rails code agent.

        Args:
            project_root: Root directory of the Rails project (None by default)
        """
        self.enabled = False
        self.project_root = Path(project_root) if project_root else None
        self.console = console

        # Cache directories
        self.cache_dir = Path("cache")
        self.symbols_cache = self.cache_dir / "symbols"
        self.embeddings_cache = self.cache_dir / "embeddings"

        # Initialize caches
        self._ensure_cache_dirs()

        # Tool availability flags (will be set during initialization)
        self.has_tree_sitter = False
        self.has_solargraph = False
        self.has_ast_grep = False
        self.has_ctags = False

        # Rails-specific paths (only set if project_root is provided)
        if self.project_root:
            self.models_path = self.project_root / "app" / "models"
            self.controllers_path = self.project_root / "app" / "controllers"
            self.views_path = self.project_root / "app" / "views"
            self.migrations_path = self.project_root / "db" / "migrate"
            self.schema_path = self.project_root / "db" / "schema.rb"
            self.routes_path = self.project_root / "config" / "routes.rb"
        else:
            self.models_path = None
            self.controllers_path = None
            self.views_path = None
            self.migrations_path = None
            self.schema_path = None
            self.routes_path = None

        # Internal state
        self._schema_cache: Optional[Dict] = None
        self._routes_cache: Optional[Dict] = None

    def _ensure_cache_dirs(self) -> None:
        """Create cache directories if they don't exist."""
        for cache_dir in [self.cache_dir, self.symbols_cache, self.embeddings_cache]:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _check_tool_availability(self) -> Dict[str, bool]:
        """Check which external tools are available."""
        tools_config = {
            "tree-sitter-cli": {"command": "tree-sitter", "args": ["--version"]},
            "solargraph": {"command": "solargraph", "args": ["--version"]},
            "ast-grep": {"command": "ast-grep", "args": ["--version"]},
            "ctags": {"command": "ctags", "args": ["--version"]},
            "rg": {"command": "rg", "args": ["--version"]}
        }

        availability = {}
        for tool_name, config in tools_config.items():
            try:
                command = config["command"]
                args = config["args"]
                result = subprocess.run([command] + args,
                                      capture_output=True, text=True, timeout=5)
                availability[tool_name] = result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError):
                availability[tool_name] = False

        return availability

    def get_tool_usage_info(self) -> Dict[str, str]:
        """Get information about how each tool is used in practice."""
        return {
            "tree-sitter-cli": "Parse Ruby AST: tree-sitter parse file.rb",
            "solargraph": "Language server: solargraph stdio (for symbol resolution)",
            "ast-grep": "Code pattern search: ast-grep -p 'class $NAME' *.rb",
            "ctags": "Symbol indexing: ctags -R --languages=ruby .",
            "rg": "Text search: rg 'pattern' --type ruby"
        }

    def check_required_tools(self, required_tools: list = None, strict: bool = False) -> Dict[str, any]:
        """
        Check required tools and optionally throw errors if missing.

        Args:
            required_tools: List of required tool names. If None, uses default minimum set.
            strict: If True, raises exception when required tools are missing.

        Returns:
            Dict with 'available', 'missing', 'all_satisfied' keys

        Raises:
            RuntimeError: If strict=True and required tools are missing
        """
        if required_tools is None:
            # Minimum required tools for basic functionality
            required_tools = ["rg"]  # ripgrep is essential for basic search

        availability = self._check_tool_availability()

        missing_tools = []
        available_tools = []

        for tool in required_tools:
            if availability.get(tool, False):
                available_tools.append(tool)
            else:
                missing_tools.append(tool)

        all_satisfied = len(missing_tools) == 0

        result = {
            'available': available_tools,
            'missing': missing_tools,
            'all_satisfied': all_satisfied,
            'all_tools': availability
        }

        if strict and not all_satisfied:
            self.console.print(f"[red]Error: Missing required tools: {', '.join(missing_tools)}[/red]")
            self.console.print("[dim]Install missing tools:[/dim]")
            for tool in missing_tools:
                if tool == "rg":
                    self.console.print("  [yellow]ripgrep:[/yellow] brew install ripgrep (macOS) | apt install ripgrep (Ubuntu)")
                elif tool == "tree-sitter-cli":
                    self.console.print("  [yellow]tree-sitter CLI:[/yellow] brew install tree-sitter (macOS) | apt install tree-sitter-cli (Ubuntu)")
                elif tool == "solargraph":
                    self.console.print("  [yellow]solargraph:[/yellow] gem install solargraph")
                elif tool == "ast-grep":
                    self.console.print("  [yellow]ast-grep:[/yellow] brew install ast-grep (macOS) | cargo install ast-grep")
                elif tool == "ctags":
                    self.console.print("  [yellow]ctags:[/yellow] brew install universal-ctags (macOS) | apt install universal-ctags (Ubuntu)")

            raise RuntimeError(f"Missing required tools: {', '.join(missing_tools)}")

        return result

    def enable(self) -> None:
        """Enable the Rails agent and initialize tools."""
        self.enabled = True
        self.console.print("[green]Rails Code Agent enabled[/green]")

        # Check tool availability
        availability = self._check_tool_availability()
        self.has_tree_sitter = availability.get("tree-sitter-cli", False)
        self.has_solargraph = availability.get("solargraph", False)
        self.has_ast_grep = availability.get("ast-grep", False)
        self.has_ctags = availability.get("ctags", False)

        # Report available tools
        enabled_tools = [tool for tool, available in availability.items() if available]
        if enabled_tools:
            self.console.print(f"[cyan]Available tools:[/cyan] {', '.join(enabled_tools)}")
        else:
            self.console.print("[yellow]Warning: No external tools detected[/yellow]")

        # Initialize Rails project analysis
        self._initialize_project_analysis()

    def disable(self) -> None:
        """Disable the Rails agent."""
        self.enabled = False
        self.console.print("[dim]Rails Code Agent disabled[/dim]")

    def _initialize_project_analysis(self) -> None:
        """Initialize Rails project analysis by parsing schema and routes."""
        if not self.project_root:
            self.console.print("[yellow]Warning: No Rails project root specified[/yellow]")
            return

        if not self.project_root.exists():
            self.console.print(f"[yellow]Warning: Project root not found: {self.project_root}[/yellow]")
            return

        # Parse Rails schema for table information
        if self.schema_path and self.schema_path.exists():
            self._parse_schema()
        else:
            self.console.print("[yellow]Warning: db/schema.rb not found[/yellow]")

        # Parse routes for controller mappings
        if self.routes_path and self.routes_path.exists():
            self._parse_routes()
        else:
            self.console.print("[yellow]Warning: config/routes.rb not found[/yellow]")

    def _parse_schema(self) -> None:
        """Parse Rails schema.rb to extract table information."""
        try:
            schema_content = self.schema_path.read_text(encoding='utf-8')

            # Simple regex-based parsing (could be enhanced with tree-sitter)
            table_pattern = r'create_table\s+"([^"]+)"'
            tables = re.findall(table_pattern, schema_content)

            self._schema_cache = {
                "tables": tables,
                "parsed_at": str(self.schema_path.stat().st_mtime)
            }

            self.console.print(f"[dim]Parsed schema: {len(tables)} tables[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error parsing schema: {e}[/red]")

    def _parse_routes(self) -> None:
        """Parse Rails routes.rb to extract controller mappings."""
        try:
            routes_content = self.routes_path.read_text(encoding='utf-8')

            # Basic routes parsing (can be enhanced)
            resource_pattern = r'resources?\s+:(\w+)'
            resources = re.findall(resource_pattern, routes_content)

            self._routes_cache = {
                "resources": resources,
                "parsed_at": str(self.routes_path.stat().st_mtime)
            }

            self.console.print(f"[dim]Parsed routes: {len(resources)} resources[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error parsing routes: {e}[/red]")

    def parse_sql_query(self, sql: str) -> SQLQuery:
        """
        Parse SQL query to extract tables, columns, and conditions.

        Args:
            sql: SQL query string

        Returns:
            SQLQuery object with parsed components
        """
        sql = sql.strip()

        # Determine query type
        query_type = "SELECT"
        if sql.upper().startswith("INSERT"):
            query_type = "INSERT"
        elif sql.upper().startswith("UPDATE"):
            query_type = "UPDATE"
        elif sql.upper().startswith("DELETE"):
            query_type = "DELETE"

        # Extract table names (simple regex approach)
        table_patterns = [
            r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)',  # SELECT ... FROM table
            r'INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)',  # INSERT INTO table
            r'UPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)', # UPDATE table
            r'DELETE\s+FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', # DELETE FROM table
        ]

        tables = []
        for pattern in table_patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.extend(matches)

        # Extract columns (basic implementation)
        columns = []
        if query_type == "SELECT":
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
            if select_match:
                columns_str = select_match.group(1).strip()
                if columns_str == "*":
                    columns = ["*"]
                else:
                    # Split by comma and clean up
                    columns = [col.strip() for col in columns_str.split(",")]

        # Extract WHERE conditions (basic implementation)
        conditions = []
        where_match = re.search(r'WHERE\s+(.*?)(?:ORDER|GROUP|LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1).strip()
            # Split by AND/OR and clean up
            condition_parts = re.split(r'\s+(?:AND|OR)\s+', where_clause, flags=re.IGNORECASE)
            conditions = [cond.strip() for cond in condition_parts]

        return SQLQuery(
            original=sql,
            tables=tables,
            columns=columns,
            conditions=conditions,
            query_type=query_type
        )

    def table_to_model_name(self, table_name: str) -> str:
        """
        Convert Rails table name to model name using Rails conventions.

        Args:
            table_name: Database table name (e.g., 'shopping_carts')

        Returns:
            Model class name (e.g., 'ShoppingCart')
        """
        # Rails conventions: pluralized table names -> singular class names
        # shopping_carts -> ShoppingCart
        # users -> User

        # Simple singularization (could use inflection library for accuracy)
        singular = table_name
        if table_name.endswith('ies'):
            singular = table_name[:-3] + 'y'  # categories -> category
        elif table_name.endswith('es'):
            singular = table_name[:-2]        # boxes -> box
        elif table_name.endswith('s'):
            singular = table_name[:-1]        # users -> user

        # Convert to CamelCase
        parts = singular.split('_')
        return ''.join(word.capitalize() for word in parts)

    def find_model_file(self, model_name: str) -> Optional[Path]:
        """
        Find the model file for a given model name.

        Args:
            model_name: Model class name (e.g., 'ShoppingCart')

        Returns:
            Path to model file if found, None otherwise
        """
        if not self.models_path:
            return None

        # Convert CamelCase to snake_case for file name
        # ShoppingCart -> shopping_cart.rb
        snake_case = re.sub(r'([A-Z])', r'_\1', model_name).lower().lstrip('_')
        model_file = self.models_path / f"{snake_case}.rb"

        return model_file if model_file.exists() else None

    def analyze_query(self, user_query: str) -> List[CodeResult]:
        """
        Main entry point for analyzing user queries about code.

        Args:
            user_query: User's query (SQL or natural language)

        Returns:
            List of relevant code results
        """
        if not self.enabled:
            return []

        # Try to detect query type
        sql_indicators = ['select', 'insert', 'update', 'delete', 'from', 'where']
        lifecycle_indicators = ['before', 'after', 'around', 'callback', 'hook', 'invoked', 'called', 'methods']

        is_sql = any(indicator in user_query.lower() for indicator in sql_indicators)
        is_lifecycle = any(indicator in user_query.lower() for indicator in lifecycle_indicators)

        if is_lifecycle:
            return self._analyze_rails_lifecycle_query(user_query)
        elif is_sql:
            return self._analyze_sql_query(user_query)
        else:
            return self._analyze_natural_language_query(user_query)

    def _analyze_sql_query(self, sql: str) -> List[CodeResult]:
        """Analyze SQL query and find related code."""
        results = []

        # Parse the SQL query
        parsed_sql = self.parse_sql_query(sql)

        for table_name in parsed_sql.tables:
            # Find related model
            model_name = self.table_to_model_name(table_name)
            model_file = self.find_model_file(model_name)

            if model_file:
                # Read model file and create result
                try:
                    content = model_file.read_text(encoding='utf-8')
                    lines = content.split('\n')

                    # Find class definition line
                    class_line = 1
                    for i, line in enumerate(lines):
                        if f"class {model_name}" in line:
                            class_line = i + 1
                            break

                    result = CodeResult(
                        file_path=str(model_file.relative_to(self.project_root)),
                        line_number=class_line,
                        code_snippet=lines[class_line-1] if class_line <= len(lines) else "",
                        context_lines=lines[max(0, class_line-3):class_line+5],
                        relevance_score=0.9,
                        result_type="model_def",
                        description=f"Model definition for table '{table_name}'"
                    )
                    results.append(result)

                except Exception as e:
                    self.console.print(f"[red]Error reading model file {model_file}: {e}[/red]")

            # Search for exact SQL usage with ripgrep if available
            if hasattr(self, 'has_rg') and self.has_rg:
                rg_results = self._search_with_ripgrep(sql)
                results.extend(rg_results)

        return results

    def _analyze_natural_language_query(self, query: str) -> List[CodeResult]:
        """Analyze natural language query about code."""
        # Placeholder for future semantic search implementation
        return []

    def _analyze_rails_lifecycle_query(self, query: str) -> List[CodeResult]:
        """
        Analyze Rails lifecycle queries like 'list all methods invoked before order.create'.

        Args:
            query: Natural language query about Rails lifecycles

        Returns:
            List of CodeResult objects with lifecycle information
        """
        results = []

        if not self.project_root:
            return results

        # Extract the model and operation from the query
        model_info = self._extract_model_from_lifecycle_query(query)
        if not model_info:
            return results

        model_name = model_info['model']
        operation = model_info['operation']
        stage = model_info['stage']  # 'before', 'after', 'around'

        self.console.print(f"[dim]Analyzing {stage} {operation} lifecycle for {model_name}...[/dim]")

        # Find the model file
        model_results = self._find_model_lifecycle_hooks(model_name, operation, stage)
        results.extend(model_results)

        # Find controller actions that might trigger this
        controller_results = self._find_controller_lifecycle_triggers(model_name, operation)
        results.extend(controller_results)

        # Find application-wide callbacks
        app_results = self._find_application_lifecycle_hooks(model_name, operation, stage)
        results.extend(app_results)

        return results

    def _extract_model_from_lifecycle_query(self, query: str) -> dict:
        """Extract model, operation, and stage from lifecycle query."""
        import re

        # Pattern to match queries like "methods invoked before order.create"
        patterns = [
            r'(?:methods|callbacks|hooks).*?(before|after|around).*?(\w+)\.(\w+)',
            r'(before|after|around).*?(\w+)\.(\w+)',
            r'(\w+)\.(\w+).*?(before|after|around)',
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    if groups[0] in ['before', 'after', 'around']:
                        stage, model, operation = groups
                    else:
                        stage = groups[2]
                        model, operation = groups[0], groups[1]

                    return {
                        'model': model.capitalize(),
                        'operation': operation,
                        'stage': stage
                    }

        return None

    def _find_model_lifecycle_hooks(self, model_name: str, operation: str, stage: str) -> List[CodeResult]:
        """Find lifecycle hooks in the model file."""
        results = []

        model_file = self.project_root / "app" / "models" / f"{model_name.lower()}.rb"
        if not model_file.exists():
            return results

        try:
            content = model_file.read_text(encoding='utf-8')
            lines = content.split('\n')

            # Search for Rails callbacks
            callback_patterns = [
                rf'{stage}_{operation}',
                rf'{stage}_save',
                rf'{stage}_create',
                rf'{stage}_update',
                rf'{stage}_destroy',
                rf'{stage}_validation',
                rf'{stage}_commit',
                f'validates',
                f'validate'
            ]

            for i, line in enumerate(lines, 1):
                for pattern in callback_patterns:
                    if pattern in line.lower():
                        result = CodeResult(
                            file_path=f"app/models/{model_name.lower()}.rb",
                            line_number=i,
                            code_snippet=line.strip(),
                            relevance_score=0.95,
                            result_type="lifecycle_hook",
                            description=f"Rails {stage} {operation} callback in {model_name} model"
                        )
                        results.append(result)

        except Exception as e:
            self.console.print(f"[red]Error reading model file: {e}[/red]")

        return results

    def _find_controller_lifecycle_triggers(self, model_name: str, operation: str) -> List[CodeResult]:
        """Find controller actions that trigger the lifecycle."""
        results = []

        # Search for controller actions that call the operation
        search_patterns = [
            f"{model_name}.{operation}",
            f"{model_name}.create",
            f"@{model_name.lower()}.{operation}",
            f"@{model_name.lower()}.save"
        ]

        for pattern in search_patterns:
            rg_results = self._search_with_ripgrep(pattern)
            for result in rg_results:
                if 'controller' in result.file_path.lower():
                    result.description = f"Controller action triggering {model_name}.{operation}"
                    result.result_type = "lifecycle_trigger"
                    result.relevance_score = 0.85
                    results.append(result)

        return results

    def _find_application_lifecycle_hooks(self, model_name: str, operation: str, stage: str) -> List[CodeResult]:
        """Find application-wide lifecycle hooks."""
        results = []

        # Search in concerns, observers, and application files
        search_paths = [
            "app/models/concerns",
            "app/observers",
            "config/initializers",
            "lib"
        ]

        for search_path in search_paths:
            path = self.project_root / search_path
            if path.exists():
                # Search for callback-related code
                try:
                    cmd = ["rg", "--line-number", "--with-filename",
                           f"{stage}.*{operation}", str(path)]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

                    if result.returncode == 0:
                        for line in result.stdout.strip().split('\n'):
                            if ':' in line:
                                parts = line.split(':', 2)
                                if len(parts) >= 3:
                                    file_path = parts[0]
                                    line_number = int(parts[1])
                                    code_snippet = parts[2]

                                    try:
                                        rel_path = Path(file_path).relative_to(self.project_root)
                                    except ValueError:
                                        rel_path = Path(file_path)

                                    hook_result = CodeResult(
                                        file_path=str(rel_path),
                                        line_number=line_number,
                                        code_snippet=code_snippet.strip(),
                                        relevance_score=0.75,
                                        result_type="app_lifecycle_hook",
                                        description=f"Application-wide {stage} {operation} hook"
                                    )
                                    results.append(hook_result)

                except Exception as e:
                    continue

        return results

    def _search_with_ripgrep(self, pattern: str) -> List[CodeResult]:
        """Search for exact string matches using ripgrep."""
        results = []

        if not self.project_root:
            return results

        try:
            # Use ripgrep to find exact matches
            cmd = ["rg", "--line-number", "--with-filename", pattern, str(self.project_root)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        parts = line.split(':', 2)
                        if len(parts) >= 3:
                            file_path = parts[0]
                            line_number = int(parts[1])
                            code_snippet = parts[2]

                            # Make path relative to project root
                            try:
                                rel_path = Path(file_path).relative_to(self.project_root)
                            except ValueError:
                                rel_path = Path(file_path)

                            result = CodeResult(
                                file_path=str(rel_path),
                                line_number=line_number,
                                code_snippet=code_snippet.strip(),
                                relevance_score=0.8,
                                result_type="exact_match",
                                description="Exact SQL string match"
                            )
                            results.append(result)

        except Exception as e:
            self.console.print(f"[red]Error with ripgrep search: {e}[/red]")

        return results

    def status(self) -> Dict[str, Any]:
        """Get current agent status and statistics."""
        return {
            "enabled": self.enabled,
            "project_root": str(self.project_root) if self.project_root else None,
            "tools": {
                "tree_sitter": self.has_tree_sitter,
                "solargraph": self.has_solargraph,
                "ast_grep": self.has_ast_grep,
                "ctags": self.has_ctags,
            },
            "rails_paths": {
                "models": self.models_path.exists() if self.models_path else False,
                "controllers": self.controllers_path.exists() if self.controllers_path else False,
                "views": self.views_path.exists() if self.views_path else False,
                "schema": self.schema_path.exists() if self.schema_path else False,
                "routes": self.routes_path.exists() if self.routes_path else False,
            },
            "cache": {
                "schema": self._schema_cache is not None,
                "routes": self._routes_cache is not None,
            }
        }


# Global agent instance
_rails_agent = None

def get_rails_agent() -> RailsCodeAgent:
    """Get or create the global Rails agent instance."""
    global _rails_agent
    if _rails_agent is None:
        _rails_agent = RailsCodeAgent(project_root=None)
    return _rails_agent


def build_rails_index(project_root: str) -> None:
    """Build Rails code index for the specified project."""
    try:
        from rag.rails_rag.manager import RailsRAGManager

        console.print(f"[cyan]Building Rails code index for:[/cyan] {project_root}")

        rails_rag = RailsRAGManager(
            project_root=project_root,
            enabled=True
        )

        console.print("[dim]Indexing Rails project structure...[/dim]")
        metadata = rails_rag.index_project(force_rebuild=True)

        build_time = metadata.get('build_time', 0)
        console.print(f"[green]✓ Rails index built successfully[/green] ({build_time:.2f}s)")

        # Show index statistics
        stats = rails_rag.status()
        if stats.get('index_info'):
            index_info = stats['index_info']
            console.print(f"[dim]Index version:[/dim] {index_info.get('version', 'unknown')}")

        if stats.get('statistics'):
            statistics = stats['statistics']
            console.print("[dim]Components indexed:[/dim]")
            for component, data in statistics.items():
                files = data.get('files', 0)
                entries = data.get('entries', 0)
                console.print(f"  {component}: {files} files, {entries} entries")

        console.print(f"[green]Index saved to:[/green] cache/rails_rag_index.json")

    except Exception as e:
        console.print(f"[red]Error building Rails index:[/red] {e}")
        raise


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="rails_code_agent",
        description="Rails Code Analysis Agent - Intelligent code discovery for Rails applications"
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="Build Rails code index for the current project"
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Root directory of the Rails project (required for most operations)"
    )
    parser.add_argument(
        "--analyze",
        metavar="QUERY",
        help="Analyze SQL query or code pattern"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show Rails agent status"
    )
    parser.add_argument(
        "--check-tools",
        action="store_true",
        help="Check availability of required external tools"
    )
    parser.add_argument(
        "--strict-tools",
        action="store_true",
        help="Require all recommended tools (use with --check-tools)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed tool usage information (use with --check-tools)"
    )

    args = parser.parse_args()

    # Create agent instance
    agent = RailsCodeAgent(project_root=args.project_root)

    if args.check_tools:
        # Check tool availability
        console.print("[bold cyan]Rails Code Agent - Tool Check[/bold cyan]")

        if args.strict_tools:
            # Require all recommended tools
            required_tools = ["rg", "tree-sitter-cli", "solargraph", "ast-grep", "ctags"]
            console.print("[dim]Checking all recommended tools...[/dim]")
        else:
            # Only check essential tools
            required_tools = ["rg"]
            console.print("[dim]Checking essential tools...[/dim]")

        try:
            result = agent.check_required_tools(required_tools=required_tools, strict=True)
            console.print(f"[green]✓ All required tools available:[/green] {', '.join(result['available'])}")

            # Show optional tools status
            all_tools = result['all_tools']
            optional_tools = [tool for tool in all_tools.keys() if tool not in required_tools]
            if optional_tools:
                console.print("[dim]Optional tools:[/dim]")
                for tool in optional_tools:
                    status = "✓" if all_tools[tool] else "✗"
                    color = "green" if all_tools[tool] else "red"
                    console.print(f"  [{color}]{status} {tool}[/{color}]")

            # Show tool usage information if verbose
            if args.verbose:
                console.print("\n[dim]Tool usage in Rails analysis:[/dim]")
                usage_info = agent.get_tool_usage_info()
                for tool, usage in usage_info.items():
                    available = all_tools.get(tool, False)
                    status = "✓" if available else "✗"
                    color = "green" if available else "red"
                    console.print(f"  [{color}]{status} {tool}:[/{color}] {usage}")

        except RuntimeError as e:
            sys.exit(1)

    elif args.index:
        # Build Rails code index
        console.print("[bold cyan]Rails Code Agent - Index Builder[/bold cyan]")
        if not args.project_root:
            console.print("[red]Error: --project-root is required for indexing[/red]")
            console.print("[dim]Example: python rails_code_agent.py --index --project-root /path/to/rails/app[/dim]")
            sys.exit(1)

        # Check essential tools before indexing
        try:
            console.print("[dim]Checking required tools...[/dim]")
            agent.check_required_tools(required_tools=["rg"], strict=True)
        except RuntimeError:
            sys.exit(1)

        build_rails_index(args.project_root)

    elif args.analyze:
        # Analyze query
        console.print("[bold cyan]Rails Code Agent - Code Analysis[/bold cyan]")

        if not args.project_root:
            console.print("[yellow]Warning: No project root specified. Limited analysis available.[/yellow]")

        # Check essential tools before analysis
        try:
            console.print("[dim]Checking required tools...[/dim]")
            agent.check_required_tools(required_tools=["rg"], strict=True)
        except RuntimeError:
            sys.exit(1)

        agent.enable()

        console.print(f"[cyan]Analyzing:[/cyan] {args.analyze}")
        results = agent.analyze_query(args.analyze)

        if not results:
            console.print("[yellow]No results found[/yellow]")
            if args.project_root:
                console.print("[dim]Tip: Try building the index first with --index[/dim]")
            else:
                console.print("[dim]Tip: Specify --project-root for better analysis[/dim]")
        else:
            console.print(f"[green]Found {len(results)} results:[/green]")
            for i, result in enumerate(results, 1):
                score_display = f"({result.relevance_score:.2f})" if result.relevance_score > 0 else ""
                console.print(f"\n{i}. [green]{result.file_path}:{result.line_number}[/green] {score_display}")
                console.print(f"   [dim]{result.description}[/dim]")
                if result.code_snippet:
                    console.print(f"   [white]{result.code_snippet}[/white]")

    elif args.status:
        # Show agent status
        console.print("[bold cyan]Rails Code Agent - Status[/bold cyan]")
        agent.enable()
        status = agent.status()

        console.print(f"[cyan]Project root:[/cyan] {status['project_root']}")
        console.print(f"[cyan]Agent enabled:[/cyan] {status['enabled']}")

        # Show tool availability
        tools = status.get('tools', {})
        available_tools = [name for name, available in tools.items() if available]
        console.print(f"[cyan]Available tools:[/cyan] {', '.join(available_tools) if available_tools else 'none'}")

        # Show Rails paths
        paths = status.get('rails_paths', {})
        valid_paths = [name for name, exists in paths.items() if exists]
        console.print(f"[cyan]Rails paths found:[/cyan] {', '.join(valid_paths) if valid_paths else 'none'}")

        # Show cache status
        cache = status.get('cache', {})
        cached_items = [name for name, exists in cache.items() if exists]
        console.print(f"[cyan]Cached data:[/cyan] {', '.join(cached_items) if cached_items else 'none'}")

        # Check if Rails RAG index exists
        try:
            from rag.rails_rag.manager import RailsRAGManager
            rails_rag = RailsRAGManager(project_root=args.project_root)
            rag_status = rails_rag.status()
            console.print(f"[cyan]Rails index:[/cyan] {'exists' if rag_status['index_exists'] else 'not found'}")
        except Exception:
            console.print("[yellow]Rails RAG system not available[/yellow]")

    else:
        # Default: show help and run a simple test
        parser.print_help()
        console.print("\n[bold cyan]Rails Code Agent - Quick Test[/bold cyan]")

        agent.enable()

        # Test with sample SQL
        test_sql = "SELECT * FROM shopping_cart WHERE user_id = ?"
        results = agent.analyze_query(test_sql)

        console.print(f"\n[cyan]Test Query:[/cyan] {test_sql}")
        console.print(f"[cyan]Results found:[/cyan] {len(results)}")

        if results:
            for result in results:
                console.print(f"\n[green]{result.file_path}:{result.line_number}[/green]")
                console.print(f"[dim]{result.description}[/dim]")
                console.print(f"[white]{result.code_snippet}[/white]")
        else:
            console.print("[dim]No results found. Try building the index first:[/dim]")
            console.print("[dim]  python rails_code_agent.py --index[/dim]")