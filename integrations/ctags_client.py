"""
Universal Ctags Client Integration.

Provides integration with Universal Ctags for symbol indexing
and cross-reference generation in Ruby/Rails codebases.
"""

from __future__ import annotations

import csv
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import io


class CtagsClient:
    """
    Universal Ctags client for symbol indexing.

    Provides symbol extraction, cross-references, and navigation
    capabilities using the Universal Ctags tool.
    """

    def __init__(self, project_root: str = "."):
        """
        Initialize ctags client.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root).resolve()
        self.available = self._check_availability()
        self.tags_file = self.project_root / ".tags"

    def _check_availability(self) -> bool:
        """Check if ctags is available."""
        try:
            result = subprocess.run(
                ["ctags", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and "Universal Ctags" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def is_available(self) -> bool:
        """Check if ctags is available for use."""
        return self.available

    def generate_tags(self, languages: Optional[List[str]] = None, recursive: bool = True) -> bool:
        """
        Generate tags file for the project.

        Args:
            languages: List of languages to index (default: ["Ruby"])
            recursive: Whether to search recursively

        Returns:
            True if tags generation succeeded
        """
        if not self.available:
            return False

        if languages is None:
            languages = ["Ruby"]

        try:
            cmd = [
                "ctags",
                "--languages=" + ",".join(languages),
                "--fields=+n+s+t+k+l",  # Enhanced fields
                "--extras=+r",  # Include references
                "--output-format=e-ctags",  # Extended format
                f"--tag-file={self.tags_file}"
            ]

            if recursive:
                cmd.append("-R")
                cmd.append(str(self.project_root))
            else:
                # Add specific files if not recursive
                ruby_files = list(self.project_root.glob("*.rb"))
                cmd.extend(str(f) for f in ruby_files)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.project_root
            )

            return result.returncode == 0

        except Exception:
            return False

    def load_tags(self) -> List[Dict[str, Any]]:
        """
        Load and parse tags from tags file.

        Returns:
            List of tag entries
        """
        if not self.tags_file.exists():
            return []

        tags = []

        try:
            with open(self.tags_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('!'):  # Skip comments
                        tag = self._parse_tag_line(line)
                        if tag:
                            tags.append(tag)

        except Exception:
            pass

        return tags

    def _parse_tag_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single ctags line into structured data."""
        try:
            # Basic ctags format: tag_name<TAB>file_name<TAB>ex_cmd;"<TAB>extension_fields
            parts = line.split('\t')
            if len(parts) < 3:
                return None

            tag_name = parts[0]
            file_name = parts[1]
            ex_cmd = parts[2]

            # Parse extension fields
            extensions = {}
            if len(parts) > 3:
                for i in range(3, len(parts)):
                    part = parts[i]
                    if ':' in part:
                        key, value = part.split(':', 1)
                        extensions[key] = value
                    elif part.endswith(';'):
                        # Pattern field
                        extensions['pattern'] = part[:-1]

            return {
                "name": tag_name,
                "file": file_name,
                "pattern": ex_cmd,
                "kind": extensions.get("kind", ""),
                "line": int(extensions.get("line", 0)) if extensions.get("line", "").isdigit() else 0,
                "scope": extensions.get("scope", ""),
                "signature": extensions.get("signature", ""),
                "language": extensions.get("language", ""),
                "extensions": extensions
            }

        except Exception:
            return None

    def find_symbol(self, symbol_name: str, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find symbol by name.

        Args:
            symbol_name: Name of symbol to find
            kind: Optional kind filter (c=class, f=function, etc.)

        Returns:
            List of matching symbols
        """
        tags = self.load_tags()
        matches = []

        for tag in tags:
            if tag["name"] == symbol_name:
                if kind is None or tag["kind"] == kind:
                    matches.append(tag)

        return matches

    def find_class(self, class_name: str) -> List[Dict[str, Any]]:
        """
        Find class definition.

        Args:
            class_name: Name of class to find

        Returns:
            List of class definitions
        """
        return self.find_symbol(class_name, kind="c")

    def find_method(self, method_name: str, class_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find method definition.

        Args:
            method_name: Name of method to find
            class_name: Optional class to search within

        Returns:
            List of method definitions
        """
        methods = self.find_symbol(method_name, kind="f")

        if class_name:
            # Filter by class scope
            filtered = []
            for method in methods:
                scope = method.get("scope", "")
                if class_name in scope:
                    filtered.append(method)
            return filtered

        return methods

    def get_class_members(self, class_name: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all members (methods, constants, etc.) of a class.

        Args:
            class_name: Name of class

        Returns:
            Dictionary with categorized class members
        """
        tags = self.load_tags()
        members = {
            "methods": [],
            "constants": [],
            "variables": [],
            "modules": []
        }

        for tag in tags:
            scope = tag.get("scope", "")
            if class_name in scope:
                kind = tag.get("kind", "")

                if kind == "f":  # Function/method
                    members["methods"].append(tag)
                elif kind == "c":  # Constant
                    members["constants"].append(tag)
                elif kind == "v":  # Variable
                    members["variables"].append(tag)
                elif kind == "m":  # Module
                    members["modules"].append(tag)

        return members

    def get_file_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Get all symbols defined in a specific file.

        Args:
            file_path: Path to file

        Returns:
            List of symbols in the file
        """
        tags = self.load_tags()
        file_symbols = []

        # Normalize file path
        try:
            normalized_path = str(Path(file_path).relative_to(self.project_root))
        except ValueError:
            normalized_path = str(file_path)

        for tag in tags:
            tag_file = tag.get("file", "")
            if tag_file == normalized_path or tag_file.endswith(normalized_path):
                file_symbols.append(tag)

        return file_symbols

    def find_references(self, symbol_name: str) -> List[Dict[str, Any]]:
        """
        Find references to a symbol (if ctags supports references).

        Args:
            symbol_name: Symbol to find references for

        Returns:
            List of reference locations
        """
        # This requires ctags with reference support
        # For now, return symbol definitions
        return self.find_symbol(symbol_name)

    def get_rails_models(self) -> List[Dict[str, Any]]:
        """
        Get all Rails model classes.

        Returns:
            List of Rails model information
        """
        tags = self.load_tags()
        models = []

        for tag in tags:
            file_path = tag.get("file", "")
            if "/models/" in file_path and tag.get("kind") == "c":
                # This is likely a Rails model
                model_info = tag.copy()
                model_info["table_name"] = self._class_to_table_name(tag["name"])
                models.append(model_info)

        return models

    def get_rails_controllers(self) -> List[Dict[str, Any]]:
        """
        Get all Rails controller classes.

        Returns:
            List of Rails controller information
        """
        tags = self.load_tags()
        controllers = []

        for tag in tags:
            file_path = tag.get("file", "")
            if "/controllers/" in file_path and tag.get("kind") == "c":
                # This is likely a Rails controller
                controllers.append(tag)

        return controllers

    def get_controller_actions(self, controller_name: str) -> List[Dict[str, Any]]:
        """
        Get actions (methods) for a specific controller.

        Args:
            controller_name: Name of controller class

        Returns:
            List of controller actions
        """
        return self.get_class_members(controller_name)["methods"]

    def _class_to_table_name(self, class_name: str) -> str:
        """Convert Rails model class name to table name."""
        # Convert CamelCase to snake_case and pluralize
        import re
        snake_case = re.sub(r'([A-Z])', r'_\1', class_name).lower().lstrip('_')

        # Simple pluralization
        if snake_case.endswith('y'):
            return snake_case[:-1] + 'ies'
        elif snake_case.endswith(('s', 'sh', 'ch', 'x', 'z')):
            return snake_case + 'es'
        else:
            return snake_case + 's'

    def analyze_rails_structure(self) -> Dict[str, Any]:
        """
        Comprehensive Rails structure analysis using ctags.

        Returns:
            Complete Rails structure information
        """
        if not self.available:
            return {"available": False}

        # Generate fresh tags
        if not self.generate_tags():
            return {"available": True, "error": "Failed to generate tags"}

        analysis = {
            "available": True,
            "models": self.get_rails_models(),
            "controllers": self.get_rails_controllers(),
            "total_symbols": len(self.load_tags()),
            "files_indexed": len(set(tag["file"] for tag in self.load_tags())),
        }

        return analysis

    def find_symbol_usages(self, symbol_name: str, file_pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find usages of a symbol using grep on the codebase.

        Args:
            symbol_name: Symbol to find usages for
            file_pattern: Optional file pattern to limit search

        Returns:
            List of usage locations
        """
        usages = []

        try:
            cmd = ["grep", "-rn", symbol_name, str(self.project_root)]

            if file_pattern:
                cmd.extend(["--include", file_pattern])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        parts = line.split(':', 2)
                        if len(parts) >= 3:
                            file_path = parts[0]
                            line_number = parts[1]
                            content = parts[2]

                            usages.append({
                                "file": file_path,
                                "line": int(line_number) if line_number.isdigit() else 0,
                                "content": content.strip(),
                                "symbol": symbol_name,
                                "type": "usage"
                            })

        except Exception:
            pass

        return usages

    def export_symbols_json(self, output_file: Optional[str] = None) -> str:
        """
        Export all symbols to JSON format.

        Args:
            output_file: Optional output file path

        Returns:
            Path to exported JSON file
        """
        import json

        tags = self.load_tags()

        if output_file is None:
            output_file = str(self.project_root / "symbols.json")

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(tags, f, indent=2, ensure_ascii=False)

        return output_file

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get symbol statistics.

        Returns:
            Statistics about indexed symbols
        """
        tags = self.load_tags()

        stats = {
            "total_symbols": len(tags),
            "files": len(set(tag["file"] for tag in tags)),
            "kinds": {},
            "languages": {}
        }

        for tag in tags:
            kind = tag.get("kind", "unknown")
            language = tag.get("language", "unknown")

            stats["kinds"][kind] = stats["kinds"].get(kind, 0) + 1
            stats["languages"][language] = stats["languages"].get(language, 0) + 1

        return stats