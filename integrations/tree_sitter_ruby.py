"""
Tree-sitter Ruby Parser Integration.

Provides AST-based parsing and analysis of Ruby code using tree-sitter.
Enables precise structural code analysis for Rails applications.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import json


class TreeSitterRuby:
    """
    Tree-sitter Ruby parser wrapper.

    Provides AST parsing and analysis capabilities for Ruby code
    using the tree-sitter parsing library.
    """

    def __init__(self, project_root: str = "."):
        """
        Initialize tree-sitter Ruby parser.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root).resolve()
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if tree-sitter is available."""
        try:
            result = subprocess.run(
                ["tree-sitter", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def is_available(self) -> bool:
        """Check if tree-sitter is available for use."""
        return self.available

    def parse_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Parse a Ruby file and return AST information.

        Args:
            file_path: Path to Ruby file to parse

        Returns:
            Parsed AST information or None if parsing fails
        """
        if not self.available:
            return None

        try:
            # Use tree-sitter to parse Ruby file
            result = subprocess.run([
                "tree-sitter", "parse", file_path, "--quiet"
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return self._parse_tree_sitter_output(result.stdout, file_path)
            else:
                return None

        except Exception:
            return None

    def _parse_tree_sitter_output(self, output: str, file_path: str) -> Dict[str, Any]:
        """Parse tree-sitter output into structured data."""
        # This is a simplified parser for tree-sitter output
        # In a full implementation, you'd use the tree-sitter Python bindings

        parsed = {
            "file": file_path,
            "classes": [],
            "methods": [],
            "modules": [],
            "constants": [],
            "syntax_errors": []
        }

        lines = output.split('\n')
        for line in lines:
            line = line.strip()

            # Look for class definitions
            if 'class:' in line or 'class_name:' in line:
                # Extract class information from tree-sitter output
                # This would be more sophisticated with actual tree-sitter bindings
                pass

            # Look for method definitions
            if 'method:' in line or 'def:' in line:
                # Extract method information
                pass

        return parsed

    def extract_classes(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract class definitions from Ruby file.

        Args:
            file_path: Path to Ruby file

        Returns:
            List of class information dictionaries
        """
        ast_data = self.parse_file(file_path)
        if ast_data:
            return ast_data.get("classes", [])

        # Fallback to regex-based extraction
        return self._extract_classes_fallback(file_path)

    def extract_methods(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract method definitions from Ruby file.

        Args:
            file_path: Path to Ruby file

        Returns:
            List of method information dictionaries
        """
        ast_data = self.parse_file(file_path)
        if ast_data:
            return ast_data.get("methods", [])

        # Fallback to regex-based extraction
        return self._extract_methods_fallback(file_path)

    def extract_modules(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract module definitions from Ruby file.

        Args:
            file_path: Path to Ruby file

        Returns:
            List of module information dictionaries
        """
        ast_data = self.parse_file(file_path)
        if ast_data:
            return ast_data.get("modules", [])

        # Fallback to regex-based extraction
        return self._extract_modules_fallback(file_path)

    def find_method_calls(self, file_path: str, method_name: str) -> List[Dict[str, Any]]:
        """
        Find all calls to a specific method in Ruby file.

        Args:
            file_path: Path to Ruby file
            method_name: Name of method to find calls for

        Returns:
            List of method call locations
        """
        # Placeholder for tree-sitter based method call analysis
        # Would require actual tree-sitter Ruby bindings
        return self._find_method_calls_fallback(file_path, method_name)

    def extract_associations(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract Rails associations from model file.

        Args:
            file_path: Path to Rails model file

        Returns:
            List of association information
        """
        associations = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Look for Rails associations
            import re
            association_pattern = re.compile(
                r'^\s*(has_many|has_one|belongs_to|has_and_belongs_to_many)\s+:([a-zA-Z_][a-zA-Z0-9_]*)',
                re.MULTILINE
            )

            for match in association_pattern.finditer(content):
                line_number = content[:match.start()].count('\n') + 1
                associations.append({
                    "type": match.group(1),
                    "name": match.group(2),
                    "line": line_number,
                    "file": file_path
                })

        except Exception:
            pass

        return associations

    def _extract_classes_fallback(self, file_path: str) -> List[Dict[str, Any]]:
        """Fallback regex-based class extraction."""
        classes = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            import re
            class_pattern = re.compile(r'^\s*class\s+([A-Z][a-zA-Z0-9_]*)', re.MULTILINE)

            for match in class_pattern.finditer(content):
                line_number = content[:match.start()].count('\n') + 1
                classes.append({
                    "name": match.group(1),
                    "line": line_number,
                    "file": file_path,
                    "type": "class"
                })

        except Exception:
            pass

        return classes

    def _extract_methods_fallback(self, file_path: str) -> List[Dict[str, Any]]:
        """Fallback regex-based method extraction."""
        methods = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            import re
            method_pattern = re.compile(r'^\s*def\s+(self\.)?([a-zA-Z_][a-zA-Z0-9_]*[!?]?)', re.MULTILINE)

            for match in method_pattern.finditer(content):
                line_number = content[:match.start()].count('\n') + 1
                is_class_method = match.group(1) is not None
                method_name = match.group(2)

                methods.append({
                    "name": method_name,
                    "line": line_number,
                    "file": file_path,
                    "type": "class_method" if is_class_method else "instance_method"
                })

        except Exception:
            pass

        return methods

    def _extract_modules_fallback(self, file_path: str) -> List[Dict[str, Any]]:
        """Fallback regex-based module extraction."""
        modules = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            import re
            module_pattern = re.compile(r'^\s*module\s+([A-Z][a-zA-Z0-9_]*)', re.MULTILINE)

            for match in module_pattern.finditer(content):
                line_number = content[:match.start()].count('\n') + 1
                modules.append({
                    "name": match.group(1),
                    "line": line_number,
                    "file": file_path,
                    "type": "module"
                })

        except Exception:
            pass

        return modules

    def _find_method_calls_fallback(self, file_path: str, method_name: str) -> List[Dict[str, Any]]:
        """Fallback regex-based method call finding."""
        calls = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            import re
            # Look for method calls (simple pattern)
            call_pattern = re.compile(rf'\b{re.escape(method_name)}\b', re.MULTILINE)

            for match in call_pattern.finditer(content):
                line_number = content[:match.start()].count('\n') + 1
                line_content = content.split('\n')[line_number - 1].strip()

                calls.append({
                    "method": method_name,
                    "line": line_number,
                    "file": file_path,
                    "context": line_content
                })

        except Exception:
            pass

        return calls

    def analyze_rails_file(self, file_path: str) -> Dict[str, Any]:
        """
        Comprehensive analysis of Rails file.

        Args:
            file_path: Path to Rails file

        Returns:
            Complete analysis including classes, methods, associations, etc.
        """
        analysis = {
            "file": file_path,
            "classes": self.extract_classes(file_path),
            "methods": self.extract_methods(file_path),
            "modules": self.extract_modules(file_path),
        }

        # Add Rails-specific analysis for model files
        if "/models/" in file_path and file_path.endswith(".rb"):
            analysis["associations"] = self.extract_associations(file_path)

        return analysis

    def batch_analyze(self, file_paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Analyze multiple Ruby files in batch.

        Args:
            file_paths: List of file paths to analyze

        Returns:
            Dictionary mapping file paths to analysis results
        """
        results = {}

        for file_path in file_paths:
            try:
                results[file_path] = self.analyze_rails_file(file_path)
            except Exception as e:
                results[file_path] = {"error": str(e)}

        return results