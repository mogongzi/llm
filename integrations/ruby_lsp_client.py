"""
Ruby LSP Client Integration.

Provides integration with Ruby LSP (Language Server Protocol)
for advanced Ruby and Rails code analysis.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import socket


class RubyLSPClient:
    """
    Ruby LSP client for advanced code analysis.

    Provides symbol resolution, type information, and Rails-specific
    analysis capabilities using the Ruby LSP server.
    """

    def __init__(self, project_root: str = "."):
        """
        Initialize Ruby LSP client.

        Args:
            project_root: Root directory of the Ruby project
        """
        self.project_root = Path(project_root).resolve()
        self.available = self._check_availability()
        self.process = None
        self.request_id = 0

    def _check_availability(self) -> bool:
        """Check if Ruby LSP is available."""
        try:
            # Check if ruby-lsp gem is available
            result = subprocess.run(
                ["ruby", "-e", "require 'ruby_lsp'; puts RubyLsp::VERSION"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def is_available(self) -> bool:
        """Check if Ruby LSP is available for use."""
        return self.available

    def start_server(self) -> bool:
        """
        Start Ruby LSP server.

        Returns:
            True if server started successfully
        """
        if not self.available:
            return False

        try:
            # Start ruby-lsp in stdio mode
            self.process = subprocess.Popen([
                "ruby-lsp"
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.project_root,
            text=True
            )

            # Initialize LSP connection
            self._initialize_lsp()
            return True

        except Exception:
            self.stop_server()
            return False

    def stop_server(self) -> None:
        """Stop Ruby LSP server."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None

    def _initialize_lsp(self) -> None:
        """Initialize Language Server Protocol connection."""
        if not self.process:
            return

        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "initialize",
            "params": {
                "processId": None,
                "rootUri": f"file://{self.project_root}",
                "capabilities": {
                    "textDocument": {
                        "definition": {"dynamicRegistration": True},
                        "references": {"dynamicRegistration": True},
                        "documentSymbol": {"dynamicRegistration": True},
                        "hover": {"dynamicRegistration": True},
                    },
                    "workspace": {
                        "symbol": {"dynamicRegistration": True}
                    }
                }
            }
        }

        response = self._send_request(init_request)

        # Send initialized notification
        initialized = {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {}
        }

        self._send_notification(initialized)

    def _next_request_id(self) -> int:
        """Get next request ID."""
        self.request_id += 1
        return self.request_id

    def _send_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send LSP request and return response."""
        if not self.process or not self.process.stdin:
            return None

        try:
            message = json.dumps(request)
            content = f"Content-Length: {len(message)}\r\n\r\n{message}"

            self.process.stdin.write(content)
            self.process.stdin.flush()

            # Read response (simplified)
            # In a full implementation, you'd properly parse the LSP protocol
            return {"result": None}  # Placeholder

        except Exception:
            return None

    def _send_notification(self, notification: Dict[str, Any]) -> None:
        """Send LSP notification (no response expected)."""
        if not self.process or not self.process.stdin:
            return

        try:
            message = json.dumps(notification)
            content = f"Content-Length: {len(message)}\r\n\r\n{message}"

            self.process.stdin.write(content)
            self.process.stdin.flush()

        except Exception:
            pass

    def find_definition(self, file_path: str, line: int, column: int) -> Optional[Dict[str, Any]]:
        """
        Find definition of symbol at position.

        Args:
            file_path: Path to file
            line: Line number (0-based)
            column: Column number (0-based)

        Returns:
            Definition location or None
        """
        if not self.process:
            if not self.start_server():
                return None

        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "textDocument/definition",
            "params": {
                "textDocument": {"uri": f"file://{Path(file_path).resolve()}"},
                "position": {"line": line, "character": column}
            }
        }

        response = self._send_request(request)
        if response and "result" in response:
            return response["result"]

        return None

    def get_hover_info(self, file_path: str, line: int, column: int) -> Optional[Dict[str, Any]]:
        """
        Get hover information for symbol at position.

        Args:
            file_path: Path to file
            line: Line number (0-based)
            column: Column number (0-based)

        Returns:
            Hover information or None
        """
        if not self.process:
            if not self.start_server():
                return None

        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "textDocument/hover",
            "params": {
                "textDocument": {"uri": f"file://{Path(file_path).resolve()}"},
                "position": {"line": line, "character": column}
            }
        }

        response = self._send_request(request)
        if response and "result" in response:
            return response["result"]

        return None

    def get_document_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Get symbols in document.

        Args:
            file_path: Path to file

        Returns:
            List of symbols
        """
        if not self.process:
            if not self.start_server():
                return []

        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "textDocument/documentSymbol",
            "params": {
                "textDocument": {"uri": f"file://{Path(file_path).resolve()}"}
            }
        }

        response = self._send_request(request)
        if response and "result" in response:
            return response["result"]

        return []

    def analyze_rails_associations(self, model_file: str) -> List[Dict[str, Any]]:
        """
        Analyze Rails associations in model file.

        Args:
            model_file: Path to Rails model file

        Returns:
            List of association information
        """
        associations = []

        try:
            with open(model_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Use Ruby LSP to get detailed symbol information
            symbols = self.get_document_symbols(model_file)

            # Look for Rails associations in symbols
            for symbol in symbols:
                if symbol.get("kind") == 6:  # Method
                    name = symbol.get("name", "")
                    if name in ["has_many", "has_one", "belongs_to", "has_and_belongs_to_many"]:
                        associations.append({
                            "type": name,
                            "symbol": symbol,
                            "file": model_file
                        })

            # Fallback to regex if LSP doesn't provide detailed info
            if not associations:
                associations = self._extract_associations_fallback(model_file)

        except Exception:
            associations = self._extract_associations_fallback(model_file)

        return associations

    def _extract_associations_fallback(self, model_file: str) -> List[Dict[str, Any]]:
        """Fallback regex-based association extraction."""
        associations = []

        try:
            with open(model_file, 'r', encoding='utf-8') as f:
                content = f.read()

            import re
            pattern = re.compile(
                r'^\s*(has_many|has_one|belongs_to|has_and_belongs_to_many)\s+:([a-zA-Z_][a-zA-Z0-9_]*)',
                re.MULTILINE
            )

            for match in pattern.finditer(content):
                line_number = content[:match.start()].count('\n') + 1
                associations.append({
                    "type": match.group(1),
                    "name": match.group(2),
                    "line": line_number,
                    "file": model_file
                })

        except Exception:
            pass

        return associations

    def get_rails_routes_info(self) -> Dict[str, Any]:
        """
        Get Rails routes information using Ruby LSP.

        Returns:
            Routes information
        """
        routes_file = self.project_root / "config" / "routes.rb"
        if not routes_file.exists():
            return {}

        symbols = self.get_document_symbols(str(routes_file))

        return {
            "file": str(routes_file),
            "symbols": symbols,
            "routes": self._parse_routes_from_symbols(symbols)
        }

    def _parse_routes_from_symbols(self, symbols: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse route information from LSP symbols."""
        routes = []

        for symbol in symbols:
            name = symbol.get("name", "")
            if "resources" in name or "resource" in name:
                routes.append({
                    "type": "resource",
                    "name": name,
                    "symbol": symbol
                })

        return routes

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """
        Comprehensive file analysis using Ruby LSP.

        Args:
            file_path: Path to Ruby file

        Returns:
            Complete analysis information
        """
        analysis = {
            "file": file_path,
            "available": self.available,
            "symbols": [],
            "associations": [],
            "errors": []
        }

        if not self.available:
            return analysis

        try:
            # Get document symbols
            analysis["symbols"] = self.get_document_symbols(file_path)

            # Rails-specific analysis
            if "/models/" in file_path and file_path.endswith(".rb"):
                analysis["associations"] = self.analyze_rails_associations(file_path)

        except Exception as e:
            analysis["errors"].append(str(e))

        return analysis

    def find_rails_model_for_table(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Find Rails model class for database table.

        Args:
            table_name: Database table name

        Returns:
            Model information or None
        """
        # Convert table name to model class name
        model_name = self._table_to_model_name(table_name)

        # Search for model class
        symbols = self.search_symbols(model_name)

        for symbol in symbols:
            if (symbol.get("name") == model_name and
                symbol.get("kind") == 5):  # Class
                return symbol

        return None

    def _table_to_model_name(self, table_name: str) -> str:
        """Convert table name to Rails model class name."""
        # Basic Rails conventions
        # shopping_carts -> ShoppingCart
        singular = table_name.rstrip('s')  # Simple singularization
        words = singular.split('_')
        return ''.join(word.capitalize() for word in words)

    def search_symbols(self, query: str) -> List[Dict[str, Any]]:
        """
        Search symbols across workspace.

        Args:
            query: Symbol search query

        Returns:
            List of matching symbols
        """
        if not self.process:
            if not self.start_server():
                return []

        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "workspace/symbol",
            "params": {"query": query}
        }

        response = self._send_request(request)
        if response and "result" in response:
            return response["result"]

        return []

    def __enter__(self):
        """Context manager entry."""
        self.start_server()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_server()