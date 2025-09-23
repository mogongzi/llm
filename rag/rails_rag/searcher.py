"""
Rails Code Searcher - Multi-tier search engine for Rails codebases.

Provides intelligent search across multiple layers:
1. Symbol Search: Fast lookups for classes, methods, constants
2. Structural Search: AST-based pattern matching
3. Semantic Search: Code embedding similarity
4. SQL Search: SQL query to Rails code mapping
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import json


class RailsCodeSearcher:
    """
    Multi-tier search engine for Rails codebases.

    Combines different search strategies to provide comprehensive
    code discovery capabilities with intelligent ranking.
    """

    def __init__(self, project_root: str = ".", max_results: int = 50, similarity_threshold: float = 0.7):
        """
        Initialize the Rails code searcher.

        Args:
            project_root: Root directory of Rails project
            max_results: Maximum number of results to return
            similarity_threshold: Minimum similarity score for semantic results
        """
        self.project_root = Path(project_root).resolve()
        self.max_results = max_results
        self.similarity_threshold = similarity_threshold

    def search(self, query: str, index_data: Dict[str, Any], query_type: str = "auto") -> List[Dict[str, Any]]:
        """
        Main search entry point with multi-tier strategy.

        Args:
            query: Search query
            index_data: Pre-built Rails index data
            query_type: Type of search ("sql", "semantic", "symbol", "auto")

        Returns:
            Ranked list of search results
        """
        if query_type == "auto":
            query_type = self._detect_query_type(query)

        results = []

        if query_type == "sql":
            results = self._search_sql(query, index_data)
        elif query_type == "symbol":
            results = self._search_symbol(query, index_data)
        elif query_type == "semantic":
            results = self._search_semantic(query, index_data)
        else:
            # Multi-tier search for unknown/general queries
            results = self._multi_tier_search(query, index_data)

        # Rank and limit results
        ranked_results = self._rank_results(results, query)
        return ranked_results[:self.max_results]

    def _detect_query_type(self, query: str) -> str:
        """Detect the type of search query."""
        query_lower = query.lower().strip()

        # SQL indicators
        sql_keywords = {'select', 'insert', 'update', 'delete', 'from', 'where', 'join'}
        if any(keyword in query_lower for keyword in sql_keywords):
            return "sql"

        # Symbol indicators (class/method names)
        if re.match(r'^[A-Z][a-zA-Z0-9_]*$', query.strip()):  # PascalCase
            return "symbol"
        if re.match(r'^[a-z_][a-zA-Z0-9_]*[!?]?$', query.strip()):  # snake_case/method
            return "symbol"

        # Default to semantic for natural language
        return "semantic"

    def _search_sql(self, sql_query: str, index_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for code related to SQL query."""
        results = []

        # Parse SQL to extract table names
        table_names = self._extract_table_names(sql_query)

        # Use convention index to map tables to models
        conventions = index_data.get("components", {}).get("conventions", {})
        table_mappings = conventions.get("table_mappings", {})

        for table_name in table_names:
            # Find corresponding model
            model_class = table_mappings.get(table_name)
            if model_class:
                # Search for model definition
                model_results = self._find_model_definition(model_class, index_data)
                results.extend(model_results)

                # Search for controller related to this model
                controller_results = self._find_related_controller(model_class, index_data)
                results.extend(controller_results)

            # Search for exact SQL string matches
            exact_matches = self._search_exact_string(sql_query)
            results.extend(exact_matches)

        return results

    def _extract_table_names(self, sql: str) -> List[str]:
        """Extract table names from SQL query."""
        table_names = []

        # Common patterns for table names in SQL
        patterns = [
            r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)',  # SELECT ... FROM table
            r'INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)',  # INSERT INTO table
            r'UPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)', # UPDATE table
            r'DELETE\s+FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', # DELETE FROM table
            r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)',  # JOIN table
        ]

        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            table_names.extend(matches)

        return list(set(table_names))  # Remove duplicates

    def _find_model_definition(self, model_class: str, index_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find model class definition."""
        results = []

        # Search in structural index
        structural = index_data.get("components", {}).get("structural", {})
        classes = structural.get("classes", [])

        for class_info in classes:
            if class_info.get("name") == model_class:
                results.append({
                    "type": "model_definition",
                    "file": class_info.get("file"),
                    "line": class_info.get("line"),
                    "content": class_info.get("definition", ""),
                    "score": 0.95,
                    "description": f"Model class definition: {model_class}",
                })

        return results

    def _find_related_controller(self, model_class: str, index_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find controller related to model using Rails conventions."""
        results = []

        # Convert model name to controller name
        # User -> UsersController, ShoppingCart -> ShoppingCartsController
        controller_name = self._model_to_controller_name(model_class)

        # Search in conventions index
        conventions = index_data.get("components", {}).get("conventions", {})
        controllers = conventions.get("controllers", [])

        for controller_info in controllers:
            if controller_info.get("class_name") == controller_name:
                results.append({
                    "type": "related_controller",
                    "file": controller_info.get("file"),
                    "line": 1,  # Class definition typically at top
                    "content": f"class {controller_name}",
                    "score": 0.8,
                    "description": f"Related controller: {controller_name}",
                    "actions": controller_info.get("actions", []),
                })

        return results

    def _model_to_controller_name(self, model_class: str) -> str:
        """Convert model class name to controller class name."""
        # User -> UsersController
        # ShoppingCart -> ShoppingCartsController

        # Convert to plural (basic implementation)
        plural = model_class
        if model_class.endswith('y'):
            plural = model_class[:-1] + 'ies'
        elif model_class.endswith(('s', 'sh', 'ch', 'x', 'z')):
            plural = model_class + 'es'
        else:
            plural = model_class + 's'

        return f"{plural}Controller"

    def _search_exact_string(self, search_string: str) -> List[Dict[str, Any]]:
        """Search for exact string matches using ripgrep."""
        results = []

        try:
            # Use ripgrep for fast exact string search
            cmd = [
                "rg", "--line-number", "--with-filename", "--type", "ruby",
                search_string, str(self.project_root)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if ':' in line and line.strip():
                        parts = line.split(':', 2)
                        if len(parts) >= 3:
                            file_path = parts[0]
                            line_number = int(parts[1])
                            content = parts[2].strip()

                            # Make path relative
                            try:
                                rel_path = Path(file_path).relative_to(self.project_root)
                            except ValueError:
                                rel_path = Path(file_path)

                            results.append({
                                "type": "exact_match",
                                "file": str(rel_path),
                                "line": line_number,
                                "content": content,
                                "score": 0.9,
                                "description": "Exact string match",
                            })

        except Exception as e:
            print(f"Error in exact string search: {e}")

        return results

    def _search_symbol(self, symbol_name: str, index_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for symbol definitions and references."""
        results = []

        # Search in symbol index
        symbols = index_data.get("components", {}).get("symbols", {})
        definitions = symbols.get("definitions", [])

        for symbol in definitions:
            if symbol.get("name") == symbol_name:
                results.append({
                    "type": "symbol_definition",
                    "file": symbol.get("file"),
                    "line": symbol.get("line"),
                    "content": symbol.get("pattern", ""),
                    "score": 0.95,
                    "description": f"{symbol.get('kind', 'Symbol')}: {symbol_name}",
                    "symbol_kind": symbol.get("kind"),
                })

        # Also search in structural index for classes/methods
        structural = index_data.get("components", {}).get("structural", {})

        for item_type in ["classes", "methods", "modules"]:
            items = structural.get(item_type, [])
            for item in items:
                if item.get("name") == symbol_name:
                    results.append({
                        "type": f"{item_type[:-1]}_definition",  # classes -> class_definition
                        "file": item.get("file"),
                        "line": item.get("line"),
                        "content": item.get("definition", ""),
                        "score": 0.9,
                        "description": f"{item_type[:-1].capitalize()}: {symbol_name}",
                    })

        return results

    def _search_semantic(self, query: str, index_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search using semantic similarity (placeholder for now)."""
        results = []

        # Placeholder for semantic search implementation
        # Would use code embeddings to find similar code

        semantic_index = index_data.get("components", {}).get("semantic", {})
        if semantic_index.get("status") == "not_implemented":
            # Fallback to keyword-based search
            results = self._keyword_fallback_search(query, index_data)

        return results

    def _keyword_fallback_search(self, query: str, index_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fallback keyword search when semantic search is not available."""
        results = []

        # Extract keywords from query
        keywords = self._extract_keywords(query)

        for keyword in keywords:
            # Try symbol search for each keyword
            symbol_results = self._search_symbol(keyword, index_data)
            results.extend(symbol_results)

            # Try exact string search
            exact_results = self._search_exact_string(keyword)
            results.extend(exact_results)

        return results

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from natural language query."""
        # Simple keyword extraction (could be enhanced with NLP)
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', query)

        # Filter out common words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'how', 'what', 'where', 'when', 'why', 'find',
            'search', 'look', 'get', 'show', 'code', 'function', 'method', 'class'
        }

        keywords = [word for word in words if word.lower() not in stop_words and len(word) > 2]

        return keywords

    def _multi_tier_search(self, query: str, index_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Multi-tier search combining all strategies."""
        all_results = []

        # Try each search strategy
        strategies = [
            ("symbol", self._search_symbol),
            ("semantic", self._search_semantic),
        ]

        for strategy_name, strategy_func in strategies:
            try:
                strategy_results = strategy_func(query, index_data)
                # Tag results with strategy
                for result in strategy_results:
                    result["search_strategy"] = strategy_name
                all_results.extend(strategy_results)
            except Exception as e:
                print(f"Error in {strategy_name} search: {e}")

        return all_results

    def _rank_results(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Rank search results by relevance."""
        if not results:
            return []

        # Sort by score (descending) and then by type priority
        type_priority = {
            "model_definition": 10,
            "symbol_definition": 9,
            "class_definition": 8,
            "method_definition": 7,
            "related_controller": 6,
            "exact_match": 5,
            "module_definition": 4,
        }

        def score_result(result):
            base_score = result.get("score", 0.5)
            type_bonus = type_priority.get(result.get("type", ""), 0) * 0.01
            return base_score + type_bonus

        # Sort by computed score
        ranked = sorted(results, key=score_result, reverse=True)

        # Remove duplicates (same file and line)
        seen = set()
        unique_results = []

        for result in ranked:
            key = (result.get("file"), result.get("line"))
            if key not in seen:
                seen.add(key)
                unique_results.append(result)

        return unique_results