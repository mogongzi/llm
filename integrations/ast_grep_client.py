"""
ast-grep Client Integration.

Provides integration with ast-grep for structural code search
and pattern matching in Ruby/Rails codebases.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Union


class AstGrepClient:
    """
    ast-grep client for structural code search.

    Provides AST-based pattern matching and code search capabilities
    using the ast-grep tool for precise structural analysis.
    """

    def __init__(self, project_root: str = "."):
        """
        Initialize ast-grep client.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root).resolve()
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if ast-grep is available."""
        try:
            result = subprocess.run(
                ["ast-grep", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def is_available(self) -> bool:
        """Check if ast-grep is available for use."""
        return self.available

    def search_pattern(self, pattern: str, language: str = "ruby", paths: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search for AST pattern in codebase.

        Args:
            pattern: ast-grep pattern to search for
            language: Programming language (default: ruby)
            paths: Optional list of specific paths to search

        Returns:
            List of matches with location and context
        """
        if not self.available:
            return []

        try:
            # Build ast-grep command
            cmd = [
                "ast-grep",
                "--json",
                "--lang", language,
                pattern
            ]

            # Add paths if specified
            if paths:
                cmd.extend(paths)
            else:
                cmd.append(str(self.project_root))

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_root
            )

            if result.returncode == 0 and result.stdout.strip():
                matches = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        try:
                            match = json.loads(line)
                            matches.append(self._process_match(match))
                        except json.JSONDecodeError:
                            continue
                return matches

        except Exception as e:
            print(f"ast-grep error: {e}")

        return []

    def _process_match(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """Process raw ast-grep match into standardized format."""
        return {
            "file": match.get("file", ""),
            "line": match.get("line", 0),
            "column": match.get("column", 0),
            "text": match.get("text", ""),
            "kind": match.get("kind", ""),
            "range": match.get("range", {}),
            "source": "ast-grep"
        }

    def find_class_definitions(self, class_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find class definitions.

        Args:
            class_name: Specific class name to find (None for all classes)

        Returns:
            List of class definitions
        """
        if class_name:
            pattern = f"class {class_name}"
        else:
            pattern = "class $CLASS"

        return self.search_pattern(pattern)

    def find_method_definitions(self, method_name: Optional[str] = None, class_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find method definitions.

        Args:
            method_name: Specific method name to find (None for all methods)
            class_name: Limit search to specific class

        Returns:
            List of method definitions
        """
        if method_name:
            pattern = f"def {method_name}"
        else:
            pattern = "def $METHOD"

        matches = self.search_pattern(pattern)

        # Filter by class if specified
        if class_name:
            # This would require more sophisticated pattern matching
            # For now, return all matches
            pass

        return matches

    def find_rails_associations(self, association_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find Rails associations.

        Args:
            association_type: Type of association (has_many, belongs_to, etc.)

        Returns:
            List of association definitions
        """
        if association_type:
            pattern = f"{association_type} :$ASSOCIATION"
        else:
            # Find any Rails association
            patterns = [
                "has_many :$ASSOCIATION",
                "has_one :$ASSOCIATION",
                "belongs_to :$ASSOCIATION",
                "has_and_belongs_to_many :$ASSOCIATION"
            ]

            all_matches = []
            for pattern in patterns:
                matches = self.search_pattern(pattern)
                all_matches.extend(matches)
            return all_matches

        return self.search_pattern(pattern)

    def find_method_calls(self, method_name: str, receiver: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find method calls.

        Args:
            method_name: Name of method being called
            receiver: Optional receiver object/class

        Returns:
            List of method call locations
        """
        if receiver:
            pattern = f"{receiver}.{method_name}"
        else:
            pattern = f"$OBJ.{method_name}"

        return self.search_pattern(pattern)

    def find_sql_queries(self) -> List[Dict[str, Any]]:
        """
        Find SQL queries in Ruby code.

        Returns:
            List of SQL query locations
        """
        # Common patterns for SQL in Rails
        patterns = [
            'find_by_sql("$SQL")',
            "find_by_sql('$SQL')",
            'execute("$SQL")',
            "execute('$SQL')",
            'select_all("$SQL")',
            "select_all('$SQL')"
        ]

        all_matches = []
        for pattern in patterns:
            matches = self.search_pattern(pattern)
            all_matches.extend(matches)

        return all_matches

    def find_activerecord_queries(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find ActiveRecord query methods.

        Args:
            table_name: Optional table/model name to filter by

        Returns:
            List of ActiveRecord query locations
        """
        patterns = [
            "$MODEL.where($CONDITION)",
            "$MODEL.find($ID)",
            "$MODEL.find_by($CONDITION)",
            "$MODEL.joins($TABLES)",
            "$MODEL.includes($ASSOCIATIONS)",
            "$MODEL.select($COLUMNS)"
        ]

        all_matches = []
        for pattern in patterns:
            matches = self.search_pattern(pattern)

            # Filter by model name if specified
            if table_name:
                model_name = self._table_to_model_name(table_name)
                matches = [m for m in matches if model_name in m.get("text", "")]

            all_matches.extend(matches)

        return all_matches

    def find_controller_actions(self, controller_name: Optional[str] = None, action_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find Rails controller actions.

        Args:
            controller_name: Specific controller name
            action_name: Specific action name

        Returns:
            List of controller action definitions
        """
        # Search in controller files
        controller_paths = []
        if controller_name:
            # Look for specific controller file
            controller_file = f"**/controllers/**/{controller_name.lower()}_controller.rb"
            controller_paths.append(controller_file)
        else:
            # Search all controller files
            controller_paths.append("**/controllers/**/*_controller.rb")

        if action_name:
            pattern = f"def {action_name}"
        else:
            pattern = "def $ACTION"

        # Use paths parameter to limit search to controllers
        return self.search_pattern(pattern, paths=controller_paths)

    def find_rails_routes(self) -> List[Dict[str, Any]]:
        """
        Find Rails route definitions.

        Returns:
            List of route definitions
        """
        routes_file = self.project_root / "config" / "routes.rb"
        if not routes_file.exists():
            return []

        patterns = [
            "resources :$RESOURCE",
            "resource :$RESOURCE",
            "get '$PATH', to: '$ACTION'",
            "post '$PATH', to: '$ACTION'",
            "put '$PATH', to: '$ACTION'",
            "patch '$PATH', to: '$ACTION'",
            "delete '$PATH', to: '$ACTION'"
        ]

        all_matches = []
        for pattern in patterns:
            matches = self.search_pattern(pattern, paths=[str(routes_file)])
            all_matches.extend(matches)

        return all_matches

    def find_migrations(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find Rails migration files and operations.

        Args:
            table_name: Optional table name to filter by

        Returns:
            List of migration operations
        """
        migration_paths = [str(self.project_root / "db" / "migrate" / "*.rb")]

        patterns = [
            "create_table :$TABLE",
            "drop_table :$TABLE",
            "add_column :$TABLE, :$COLUMN",
            "remove_column :$TABLE, :$COLUMN",
            "add_index :$TABLE, :$COLUMN"
        ]

        all_matches = []
        for pattern in patterns:
            matches = self.search_pattern(pattern, paths=migration_paths)

            # Filter by table name if specified
            if table_name:
                matches = [m for m in matches if table_name in m.get("text", "")]

            all_matches.extend(matches)

        return all_matches

    def _table_to_model_name(self, table_name: str) -> str:
        """Convert table name to Rails model class name."""
        # Basic Rails conventions
        # shopping_carts -> ShoppingCart
        singular = table_name.rstrip('s')  # Simple singularization
        words = singular.split('_')
        return ''.join(word.capitalize() for word in words)

    def search_custom_pattern(self, pattern: str, file_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search for custom ast-grep pattern.

        Args:
            pattern: Custom ast-grep pattern
            file_types: Optional file type extensions to search

        Returns:
            List of matches
        """
        search_paths = []

        if file_types:
            for file_type in file_types:
                search_paths.append(f"**/*.{file_type}")
        else:
            search_paths = [str(self.project_root)]

        return self.search_pattern(pattern, paths=search_paths)

    def analyze_rails_structure(self) -> Dict[str, Any]:
        """
        Comprehensive Rails structure analysis using ast-grep.

        Returns:
            Complete Rails structure information
        """
        if not self.available:
            return {"available": False}

        analysis = {
            "available": True,
            "models": {
                "classes": self.find_class_definitions(),
                "associations": self.find_rails_associations()
            },
            "controllers": {
                "classes": self.search_pattern("class $CONTROLLER < ApplicationController"),
                "actions": self.find_controller_actions()
            },
            "routes": self.find_rails_routes(),
            "migrations": self.find_migrations(),
            "queries": {
                "sql": self.find_sql_queries(),
                "activerecord": self.find_activerecord_queries()
            }
        }

        return analysis

    def find_code_for_sql(self, sql_query: str) -> List[Dict[str, Any]]:
        """
        Find Ruby code related to SQL query using structural search.

        Args:
            sql_query: SQL query to find related code for

        Returns:
            List of related code locations
        """
        results = []

        # Extract table names from SQL
        table_names = self._extract_table_names_from_sql(sql_query)

        for table_name in table_names:
            # Find model class
            model_name = self._table_to_model_name(table_name)
            model_classes = self.find_class_definitions(model_name)
            results.extend(model_classes)

            # Find ActiveRecord queries for this table
            ar_queries = self.find_activerecord_queries(table_name)
            results.extend(ar_queries)

            # Find controller actions that might use this model
            controller_name = f"{model_name}s"  # Pluralize for controller
            controller_actions = self.find_controller_actions(controller_name)
            results.extend(controller_actions)

        # Look for exact SQL string matches
        exact_matches = self.search_custom_pattern(f'"{sql_query}"')
        results.extend(exact_matches)

        return results

    def _extract_table_names_from_sql(self, sql: str) -> List[str]:
        """Extract table names from SQL query."""
        import re

        patterns = [
            r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'UPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        ]

        table_names = []
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            table_names.extend(matches)

        return list(set(table_names))