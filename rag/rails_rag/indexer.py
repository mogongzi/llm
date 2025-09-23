"""
Rails Code Indexer - Multi-modal indexing for Rails codebases.

Provides multiple indexing strategies:
1. Structural Index: AST-based code structure analysis
2. Symbol Index: Definitions, references, and relationships
3. Convention Index: Rails-specific patterns and conventions
4. Semantic Index: Code embeddings for similarity search
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import json


class RailsCodeIndexer:
    """
    Multi-modal indexer for Rails codebases.

    Builds different types of indexes to support various search strategies:
    - Structural: File/class/method hierarchy
    - Symbol: Definitions and cross-references
    - Convention: Rails-specific patterns
    - Semantic: Code embeddings (if available)
    """

    def __init__(self, project_root: str = ".", max_file_size: int = 1024 * 1024):
        """
        Initialize the Rails code indexer.

        Args:
            project_root: Root directory of Rails project
            max_file_size: Maximum file size to index (bytes)
        """
        self.project_root = Path(project_root).resolve()
        self.max_file_size = max_file_size

        # Rails-specific paths
        self.rails_paths = {
            "models": self.project_root / "app" / "models",
            "controllers": self.project_root / "app" / "controllers",
            "views": self.project_root / "app" / "views",
            "helpers": self.project_root / "app" / "helpers",
            "mailers": self.project_root / "app" / "mailers",
            "jobs": self.project_root / "app" / "jobs",
            "lib": self.project_root / "lib",
            "config": self.project_root / "config",
            "db": self.project_root / "db",
        }

        # File patterns to include/exclude
        self.include_patterns = {
            "*.rb", "*.erb", "*.yml", "*.yaml", "*.json"
        }
        self.exclude_patterns = {
            "*/tmp/*", "*/log/*", "*/vendor/*", "*/.git/*",
            "*/node_modules/*", "*/coverage/*", "*/.bundle/*"
        }

    def _should_index_file(self, file_path: Path) -> bool:
        """Check if file should be included in index."""
        # Size check
        if file_path.stat().st_size > self.max_file_size:
            return False

        # Pattern checks
        path_str = str(file_path)

        # Exclude patterns
        for pattern in self.exclude_patterns:
            if pattern.replace("*", "") in path_str:
                return False

        # Include patterns
        for pattern in self.include_patterns:
            if file_path.suffix in pattern or pattern.replace("*", "") in file_path.suffix:
                return True

        return False

    def _find_ruby_files(self) -> List[Path]:
        """Find all Ruby files to index."""
        ruby_files = []

        for rails_path in self.rails_paths.values():
            if rails_path.exists():
                for file_path in rails_path.rglob("*.rb"):
                    if self._should_index_file(file_path):
                        ruby_files.append(file_path)

        return ruby_files

    def build_structural_index(self) -> Dict[str, Any]:
        """
        Build structural index using file system hierarchy and basic parsing.

        Returns:
            Structural index with files, classes, and methods
        """
        print("    Building structural index...")

        structural_index = {
            "files": [],
            "classes": [],
            "methods": [],
            "modules": [],
        }

        ruby_files = self._find_ruby_files()

        for file_path in ruby_files:
            try:
                rel_path = file_path.relative_to(self.project_root)
                content = file_path.read_text(encoding='utf-8')

                file_entry = {
                    "path": str(rel_path),
                    "size": len(content),
                    "lines": len(content.split('\n')),
                    "type": self._classify_rails_file(file_path),
                }

                # Extract classes and modules with basic regex
                classes = self._extract_classes(content, str(rel_path))
                methods = self._extract_methods(content, str(rel_path))
                modules = self._extract_modules(content, str(rel_path))

                file_entry["classes"] = len(classes)
                file_entry["methods"] = len(methods)
                file_entry["modules"] = len(modules)

                structural_index["files"].append(file_entry)
                structural_index["classes"].extend(classes)
                structural_index["methods"].extend(methods)
                structural_index["modules"].extend(modules)

            except Exception as e:
                print(f"    Error indexing {file_path}: {e}")

        print(f"    Structural index: {len(structural_index['files'])} files, "
              f"{len(structural_index['classes'])} classes, "
              f"{len(structural_index['methods'])} methods")

        return structural_index

    def _classify_rails_file(self, file_path: Path) -> str:
        """Classify Rails file type based on path."""
        path_str = str(file_path)

        if "/models/" in path_str:
            return "model"
        elif "/controllers/" in path_str:
            return "controller"
        elif "/views/" in path_str:
            return "view"
        elif "/helpers/" in path_str:
            return "helper"
        elif "/mailers/" in path_str:
            return "mailer"
        elif "/jobs/" in path_str:
            return "job"
        elif "/lib/" in path_str:
            return "library"
        elif "/config/" in path_str:
            return "config"
        elif "/db/" in path_str:
            if "migrate" in path_str:
                return "migration"
            elif "schema" in path_str:
                return "schema"
            else:
                return "database"
        else:
            return "other"

    def _extract_classes(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract class definitions from Ruby content."""
        classes = []
        lines = content.split('\n')

        class_pattern = re.compile(r'^\s*class\s+([A-Z][a-zA-Z0-9_]*)')

        for line_num, line in enumerate(lines, 1):
            match = class_pattern.match(line)
            if match:
                class_name = match.group(1)
                classes.append({
                    "name": class_name,
                    "file": file_path,
                    "line": line_num,
                    "definition": line.strip(),
                })

        return classes

    def _extract_methods(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract method definitions from Ruby content."""
        methods = []
        lines = content.split('\n')

        # Match both def method_name and def self.method_name
        method_pattern = re.compile(r'^\s*def\s+(self\.)?([a-zA-Z_][a-zA-Z0-9_]*[!?]?)')

        for line_num, line in enumerate(lines, 1):
            match = method_pattern.match(line)
            if match:
                is_class_method = match.group(1) is not None
                method_name = match.group(2)

                methods.append({
                    "name": method_name,
                    "file": file_path,
                    "line": line_num,
                    "is_class_method": is_class_method,
                    "definition": line.strip(),
                })

        return methods

    def _extract_modules(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract module definitions from Ruby content."""
        modules = []
        lines = content.split('\n')

        module_pattern = re.compile(r'^\s*module\s+([A-Z][a-zA-Z0-9_]*)')

        for line_num, line in enumerate(lines, 1):
            match = module_pattern.match(line)
            if match:
                module_name = match.group(1)
                modules.append({
                    "name": module_name,
                    "file": file_path,
                    "line": line_num,
                    "definition": line.strip(),
                })

        return modules

    def build_symbol_index(self) -> Dict[str, Any]:
        """
        Build symbol index using ctags if available.

        Returns:
            Symbol index with definitions and references
        """
        print("    Building symbol index...")

        symbol_index = {
            "definitions": [],
            "references": [],
            "generated_with": "basic_regex",
        }

        # Try to use ctags if available
        if self._has_ctags():
            return self._build_ctags_symbol_index()
        else:
            # Fallback to basic regex-based symbol extraction
            return self._build_basic_symbol_index()

    def _has_ctags(self) -> bool:
        """Check if ctags is available."""
        try:
            result = subprocess.run(["ctags", "--version"],
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _build_ctags_symbol_index(self) -> Dict[str, Any]:
        """Build symbol index using ctags."""
        print("      Using ctags for symbol extraction...")

        try:
            # Generate ctags for Ruby files
            cmd = [
                "ctags", "-R", "--languages=Ruby", "--fields=+n",
                "--output-format=json", str(self.project_root)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                symbols = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            symbol = json.loads(line)
                            symbols.append(symbol)
                        except json.JSONDecodeError:
                            continue

                return {
                    "definitions": symbols,
                    "references": [],  # ctags doesn't provide references
                    "generated_with": "ctags",
                    "total_symbols": len(symbols),
                }
            else:
                print(f"      ctags failed: {result.stderr}")
                return self._build_basic_symbol_index()

        except Exception as e:
            print(f"      ctags error: {e}")
            return self._build_basic_symbol_index()

    def _build_basic_symbol_index(self) -> Dict[str, Any]:
        """Fallback basic symbol index using regex."""
        print("      Using basic regex for symbol extraction...")

        symbols = []
        ruby_files = self._find_ruby_files()

        for file_path in ruby_files:
            try:
                rel_path = file_path.relative_to(self.project_root)
                content = file_path.read_text(encoding='utf-8')

                # Extract basic symbols
                file_symbols = self._extract_basic_symbols(content, str(rel_path))
                symbols.extend(file_symbols)

            except Exception as e:
                print(f"      Error processing {file_path}: {e}")

        return {
            "definitions": symbols,
            "references": [],
            "generated_with": "basic_regex",
            "total_symbols": len(symbols),
        }

    def _extract_basic_symbols(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract basic symbols using regex patterns."""
        symbols = []
        lines = content.split('\n')

        patterns = {
            "class": re.compile(r'^\s*class\s+([A-Z][a-zA-Z0-9_]*)'),
            "module": re.compile(r'^\s*module\s+([A-Z][a-zA-Z0-9_]*)'),
            "method": re.compile(r'^\s*def\s+(self\.)?([a-zA-Z_][a-zA-Z0-9_]*[!?]?)'),
            "constant": re.compile(r'^\s*([A-Z][A-Z0-9_]*)\s*='),
            "attr": re.compile(r'^\s*attr_(reader|writer|accessor)\s+:([a-zA-Z_][a-zA-Z0-9_]*)'),
        }

        for line_num, line in enumerate(lines, 1):
            for symbol_type, pattern in patterns.items():
                match = pattern.match(line)
                if match:
                    if symbol_type == "method":
                        symbol_name = match.group(2)
                    elif symbol_type == "attr":
                        symbol_name = match.group(2)
                    else:
                        symbol_name = match.group(1)

                    symbols.append({
                        "name": symbol_name,
                        "kind": symbol_type,
                        "file": file_path,
                        "line": line_num,
                        "pattern": line.strip(),
                    })

        return symbols

    def build_convention_index(self) -> Dict[str, Any]:
        """
        Build Rails convention index (models, controllers, routes, etc.).

        Returns:
            Convention index with Rails-specific mappings
        """
        print("    Building Rails convention index...")

        convention_index = {
            "models": [],
            "controllers": [],
            "routes": [],
            "migrations": [],
            "associations": [],
            "table_mappings": {},
        }

        # Index models and their tables
        convention_index["models"] = self._index_models()
        convention_index["table_mappings"] = self._build_table_mappings(
            convention_index["models"]
        )

        # Index controllers
        convention_index["controllers"] = self._index_controllers()

        # Parse routes if available
        routes_file = self.project_root / "config" / "routes.rb"
        if routes_file.exists():
            convention_index["routes"] = self._parse_routes(routes_file)

        # Index migrations
        migration_dir = self.project_root / "db" / "migrate"
        if migration_dir.exists():
            convention_index["migrations"] = self._index_migrations(migration_dir)

        print(f"    Convention index: {len(convention_index['models'])} models, "
              f"{len(convention_index['controllers'])} controllers, "
              f"{len(convention_index['migrations'])} migrations")

        return convention_index

    def _index_models(self) -> List[Dict[str, Any]]:
        """Index Rails model files."""
        models = []
        models_dir = self.rails_paths["models"]

        if not models_dir.exists():
            return models

        for model_file in models_dir.rglob("*.rb"):
            if self._should_index_file(model_file):
                try:
                    rel_path = model_file.relative_to(self.project_root)
                    content = model_file.read_text(encoding='utf-8')

                    # Extract model information
                    model_info = self._analyze_model_file(content, str(rel_path))
                    if model_info:
                        models.append(model_info)

                except Exception as e:
                    print(f"    Error analyzing model {model_file}: {e}")

        return models

    def _analyze_model_file(self, content: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Analyze a Rails model file for conventions."""
        lines = content.split('\n')

        # Find class definition
        class_match = None
        for line in lines:
            match = re.match(r'^\s*class\s+([A-Z][a-zA-Z0-9_]*)', line)
            if match:
                class_match = match
                break

        if not class_match:
            return None

        class_name = class_match.group(1)

        # Extract table name using Rails conventions
        table_name = self._class_to_table_name(class_name)

        # Look for associations
        associations = self._extract_associations(content)

        # Look for validations
        validations = self._extract_validations(content)

        return {
            "class_name": class_name,
            "file": file_path,
            "table_name": table_name,
            "associations": associations,
            "validations": validations,
        }

    def _class_to_table_name(self, class_name: str) -> str:
        """Convert Rails model class name to table name."""
        # Simple pluralization (could use inflection library)
        snake_case = re.sub(r'([A-Z])', r'_\1', class_name).lower().lstrip('_')

        # Basic pluralization rules
        if snake_case.endswith('y'):
            return snake_case[:-1] + 'ies'
        elif snake_case.endswith(('s', 'sh', 'ch', 'x', 'z')):
            return snake_case + 'es'
        else:
            return snake_case + 's'

    def _extract_associations(self, content: str) -> List[Dict[str, str]]:
        """Extract Rails associations from model content."""
        associations = []
        lines = content.split('\n')

        association_pattern = re.compile(r'^\s*(has_many|has_one|belongs_to|has_and_belongs_to_many)\s+:([a-zA-Z_][a-zA-Z0-9_]*)')

        for line in lines:
            match = association_pattern.match(line)
            if match:
                assoc_type = match.group(1)
                assoc_name = match.group(2)
                associations.append({
                    "type": assoc_type,
                    "name": assoc_name,
                })

        return associations

    def _extract_validations(self, content: str) -> List[str]:
        """Extract Rails validations from model content."""
        validations = []
        lines = content.split('\n')

        validation_pattern = re.compile(r'^\s*validates')

        for line in lines:
            if validation_pattern.match(line):
                validations.append(line.strip())

        return validations

    def _index_controllers(self) -> List[Dict[str, Any]]:
        """Index Rails controller files."""
        controllers = []
        controllers_dir = self.rails_paths["controllers"]

        if not controllers_dir.exists():
            return controllers

        for controller_file in controllers_dir.rglob("*.rb"):
            if self._should_index_file(controller_file):
                try:
                    rel_path = controller_file.relative_to(self.project_root)
                    content = controller_file.read_text(encoding='utf-8')

                    controller_info = self._analyze_controller_file(content, str(rel_path))
                    if controller_info:
                        controllers.append(controller_info)

                except Exception as e:
                    print(f"    Error analyzing controller {controller_file}: {e}")

        return controllers

    def _analyze_controller_file(self, content: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Analyze a Rails controller file."""
        lines = content.split('\n')

        # Find class definition
        class_match = None
        for line in lines:
            match = re.match(r'^\s*class\s+([A-Z][a-zA-Z0-9_]*)', line)
            if match:
                class_match = match
                break

        if not class_match:
            return None

        class_name = class_match.group(1)

        # Extract actions (public methods)
        actions = self._extract_controller_actions(content)

        return {
            "class_name": class_name,
            "file": file_path,
            "actions": actions,
        }

    def _extract_controller_actions(self, content: str) -> List[str]:
        """Extract public method names from controller."""
        actions = []
        lines = content.split('\n')

        in_private = False
        method_pattern = re.compile(r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)')

        for line in lines:
            line = line.strip()
            if line == "private":
                in_private = True
                continue

            if not in_private:
                match = method_pattern.match(line)
                if match:
                    actions.append(match.group(1))

        return actions

    def _parse_routes(self, routes_file: Path) -> List[Dict[str, str]]:
        """Parse Rails routes file (basic implementation)."""
        routes = []

        try:
            content = routes_file.read_text(encoding='utf-8')
            lines = content.split('\n')

            resource_pattern = re.compile(r'^\s*resources?\s+:([a-zA-Z_][a-zA-Z0-9_]*)')

            for line in lines:
                match = resource_pattern.match(line)
                if match:
                    resource_name = match.group(1)
                    routes.append({
                        "type": "resource",
                        "name": resource_name,
                        "definition": line.strip(),
                    })

        except Exception as e:
            print(f"    Error parsing routes: {e}")

        return routes

    def _index_migrations(self, migration_dir: Path) -> List[Dict[str, Any]]:
        """Index Rails migration files."""
        migrations = []

        for migration_file in migration_dir.glob("*.rb"):
            try:
                rel_path = migration_file.relative_to(self.project_root)
                content = migration_file.read_text(encoding='utf-8')

                migration_info = self._analyze_migration_file(content, str(rel_path))
                if migration_info:
                    migrations.append(migration_info)

            except Exception as e:
                print(f"    Error analyzing migration {migration_file}: {e}")

        return migrations

    def _analyze_migration_file(self, content: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Analyze a Rails migration file."""
        # Extract migration class name and table operations
        class_match = re.search(r'class\s+([A-Z][a-zA-Z0-9_]*)', content)
        if not class_match:
            return None

        class_name = class_match.group(1)

        # Look for table operations
        table_operations = []
        create_table_matches = re.findall(r'create_table\s+:([a-zA-Z_][a-zA-Z0-9_]*)', content)
        for table in create_table_matches:
            table_operations.append({"type": "create", "table": table})

        return {
            "class_name": class_name,
            "file": file_path,
            "table_operations": table_operations,
        }

    def _build_table_mappings(self, models: List[Dict[str, Any]]) -> Dict[str, str]:
        """Build table name to model class mappings."""
        mappings = {}
        for model in models:
            table_name = model.get("table_name")
            class_name = model.get("class_name")
            if table_name and class_name:
                mappings[table_name] = class_name
        return mappings

    def build_semantic_index(self) -> Dict[str, Any]:
        """
        Build semantic index using code embeddings.

        Returns:
            Semantic index with embeddings (placeholder for now)
        """
        print("    Building semantic index (placeholder)...")

        # Placeholder for future semantic indexing implementation
        # Would use CodeBERT, StarCoder, or local embeddings

        return {
            "embeddings": [],
            "metadata": {
                "model": "placeholder",
                "dimensions": 0,
                "total_chunks": 0,
            },
            "status": "not_implemented"
        }