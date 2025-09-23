"""
Solargraph Language Server Protocol Client.

Provides integration with Solargraph for Ruby symbol resolution,
definitions, references, and intelligent code analysis.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import socket
import threading


class SolargraphClient:
    """
    Solargraph LSP client for Ruby symbol analysis.

    Provides symbol resolution, go-to-definition, find-references,
    and other language server capabilities.
    """

    def __init__(self, project_root: str = "."):
        """
        Initialize Solargraph client.

        Args:
            project_root: Root directory of the Ruby project
        """
        self.project_root = Path(project_root).resolve()
        self.available = self._check_availability()
        self.process = None
        self.socket = None
        self.request_id = 0

    def _check_availability(self) -> bool:
        """Check if Solargraph is available."""
        try:
            result = subprocess.run(
                ["solargraph", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def is_available(self) -> bool:
        """Check if Solargraph is available for use."""
        return self.available

    def start_server(self) -> bool:
        """
        Start Solargraph language server.

        Returns:
            True if server started successfully
        """
        if not self.available:
            return False

        try:
            # Start Solargraph in socket mode
            port = self._find_free_port()
            self.process = subprocess.Popen([
                "solargraph", "socket", "--port", str(port)
            ], cwd=self.project_root)

            # Give it time to start
            time.sleep(2)

            # Connect to the socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect(("localhost", port))

            # Initialize LSP connection
            self._initialize_lsp()

            return True

        except Exception:
            self.stop_server()
            return False

    def stop_server(self) -> None:
        """Stop Solargraph language server."""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

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

    def _find_free_port(self) -> int:
        """Find a free port for Solargraph server."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def _initialize_lsp(self) -> None:
        """Initialize Language Server Protocol connection."""
        if not self.socket:
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
                    }
                }
            }
        }

        self._send_request(init_request)

        # Send initialized notification
        initialized = {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {}
        }

        self._send_request(initialized)

    def _next_request_id(self) -> int:
        """Get next request ID."""
        self.request_id += 1
        return self.request_id

    def _send_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send LSP request and return response."""
        if not self.socket:
            return None

        try:
            message = json.dumps(request)
            content = f"Content-Length: {len(message)}\r\n\r\n{message}"

            self.socket.send(content.encode('utf-8'))

            # Read response (simplified)
            response_data = self.socket.recv(4096).decode('utf-8')

            # Parse LSP response format
            if "\r\n\r\n" in response_data:
                _, json_data = response_data.split("\r\n\r\n", 1)
                return json.loads(json_data)

        except Exception:
            pass

        return None

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
        if not self.socket:
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

    def find_references(self, file_path: str, line: int, column: int) -> List[Dict[str, Any]]:
        """
        Find references to symbol at position.

        Args:
            file_path: Path to file
            line: Line number (0-based)
            column: Column number (0-based)

        Returns:
            List of reference locations
        """
        if not self.socket:
            if not self.start_server():
                return []

        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "textDocument/references",
            "params": {
                "textDocument": {"uri": f"file://{Path(file_path).resolve()}"},
                "position": {"line": line, "character": column},
                "context": {"includeDeclaration": True}
            }
        }

        response = self._send_request(request)
        if response and "result" in response:
            return response["result"]

        return []

    def get_document_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Get symbols (classes, methods, etc.) in document.

        Args:
            file_path: Path to file

        Returns:
            List of symbols in document
        """
        if not self.socket:
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

    def search_symbols(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for symbols across workspace.

        Args:
            query: Symbol search query

        Returns:
            List of matching symbols
        """
        if not self.socket:
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

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """
        Comprehensive analysis of Ruby file using Solargraph.

        Args:
            file_path: Path to Ruby file

        Returns:
            Analysis including symbols, references, etc.
        """
        analysis = {
            "file": file_path,
            "symbols": self.get_document_symbols(file_path),
            "available": self.available
        }

        return analysis

    def find_class_definition(self, class_name: str) -> Optional[Dict[str, Any]]:
        """
        Find definition of a specific class.

        Args:
            class_name: Name of class to find

        Returns:
            Class definition location or None
        """
        symbols = self.search_symbols(class_name)

        for symbol in symbols:
            if (symbol.get("name") == class_name and
                symbol.get("kind") == 5):  # LSP SymbolKind.Class = 5
                return symbol

        return None

    def find_method_definition(self, method_name: str, class_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find definition(s) of a specific method.

        Args:
            method_name: Name of method to find
            class_name: Optional class name to narrow search

        Returns:
            List of method definition locations
        """
        symbols = self.search_symbols(method_name)
        methods = []

        for symbol in symbols:
            if (symbol.get("name") == method_name and
                symbol.get("kind") == 6):  # LSP SymbolKind.Method = 6

                # Filter by class if specified
                if class_name:
                    container = symbol.get("containerName", "")
                    if class_name not in container:
                        continue

                methods.append(symbol)

        return methods

    def get_class_methods(self, class_name: str) -> List[Dict[str, Any]]:
        """
        Get all methods for a specific class.

        Args:
            class_name: Name of class

        Returns:
            List of methods in the class
        """
        # Find class first
        class_def = self.find_class_definition(class_name)
        if not class_def:
            return []

        # Get file location
        location = class_def.get("location", {})
        file_uri = location.get("uri", "")

        if not file_uri.startswith("file://"):
            return []

        file_path = file_uri[7:]  # Remove "file://" prefix

        # Get document symbols
        symbols = self.get_document_symbols(file_path)
        methods = []

        def extract_methods(symbols_list, parent_name=""):
            for symbol in symbols_list:
                if symbol.get("kind") == 6:  # Method
                    symbol["class_name"] = parent_name
                    methods.append(symbol)

                # Recursively check children
                children = symbol.get("children", [])
                if children:
                    current_name = symbol.get("name", "")
                    extract_methods(children, current_name)

        extract_methods(symbols)

        # Filter methods for specific class
        class_methods = [m for m in methods if m.get("class_name") == class_name]
        return class_methods

    def __enter__(self):
        """Context manager entry."""
        self.start_server()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_server()