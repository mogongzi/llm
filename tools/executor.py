"""
Tool execution engine for Claude function calls.

This module handles the execution of tools that Claude requests during conversations,
including weather lookups, calculations, and time queries.
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, UTC
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from urllib.request import urlopen


class ToolExecutor:
    """Executes tool calls requested by Claude."""

    def __init__(self, weather_api_key: Optional[str] = None):
        """
        Initialize the tool executor.

        Args:
            weather_api_key: OpenWeatherMap API key for weather lookups
        """
        self.weather_api_key = weather_api_key or os.getenv("OPENWEATHER_API_KEY")

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool call and return the result.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool call

        Returns:
            Dict containing the tool result with 'content' and optionally 'error'
        """
        try:
            if tool_name == "get_weather":
                return self._get_weather(parameters)
            elif tool_name == "calculate":
                return self._calculate(parameters)
            elif tool_name == "get_current_time":
                return self._get_current_time(parameters)
            else:
                return {
                    "error": f"Unknown tool: {tool_name}",
                    "content": f"Tool '{tool_name}' is not available."
                }
        except Exception as e:
            return {
                "error": str(e),
                "content": f"Error executing {tool_name}: {str(e)}"
            }

    def _get_weather(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get weather information for a location."""
        location = params.get("location", "").strip()
        units = params.get("units", "celsius").lower()

        if not location:
            return {"error": "Location is required", "content": "Please provide a location."}

        if not self.weather_api_key:
            return {
                "error": "Weather API key not configured",
                "content": "Weather service is not available. Set OPENWEATHER_API_KEY environment variable."
            }

        try:
            # Convert units for OpenWeatherMap API
            api_units = "metric" if units == "celsius" else "imperial"

            # Build API URL
            base_url = "http://api.openweathermap.org/data/2.5/weather"
            params_dict = {
                "q": location,
                "appid": self.weather_api_key,
                "units": api_units
            }
            url = f"{base_url}?{urlencode(params_dict)}"

            # Make API request
            with urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())

            # Extract relevant information
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            humidity = data["main"]["humidity"]
            description = data["weather"][0]["description"].title()

            unit_symbol = "°C" if units == "celsius" else "°F"

            weather_info = {
                "location": data["name"],
                "temperature": f"{temp:.1f}{unit_symbol}",
                "feels_like": f"{feels_like:.1f}{unit_symbol}",
                "description": description,
                "humidity": f"{humidity}%"
            }

            content = f"Weather in {weather_info['location']}:\n"
            content += f"Temperature: {weather_info['temperature']} (feels like {weather_info['feels_like']})\n"
            content += f"Conditions: {weather_info['description']}\n"
            content += f"Humidity: {weather_info['humidity']}"

            return {"content": content, "data": weather_info}

        except Exception as e:
            return {
                "error": f"Weather lookup failed: {str(e)}",
                "content": f"Could not get weather for {location}. Please check the location name."
            }

    def _calculate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform mathematical calculations."""
        expression = params.get("expression", "").strip()

        if not expression:
            return {"error": "Expression is required", "content": "Please provide a mathematical expression."}

        try:
            # Security: Only allow safe mathematical operations
            # Remove any potentially dangerous characters/functions
            safe_chars = re.compile(r'^[0-9+\-*/().,\s\w]+$')
            if not safe_chars.match(expression):
                return {
                    "error": "Invalid characters in expression",
                    "content": "Expression contains invalid characters. Only numbers, operators (+,-,*,/), parentheses, and basic math functions are allowed."
                }

            # Replace common math function names with their Python equivalents
            safe_expression = expression.lower()
            safe_expression = safe_expression.replace("sqrt", "math.sqrt")
            safe_expression = safe_expression.replace("sin", "math.sin")
            safe_expression = safe_expression.replace("cos", "math.cos")
            safe_expression = safe_expression.replace("tan", "math.tan")
            safe_expression = safe_expression.replace("log", "math.log")
            safe_expression = safe_expression.replace("exp", "math.exp")
            safe_expression = safe_expression.replace("pi", "math.pi")
            safe_expression = safe_expression.replace("e", "math.e")

            # Create a safe evaluation context
            safe_dict = {
                "__builtins__": {},
                "math": math,
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "pow": pow
            }

            result = eval(safe_expression, safe_dict)

            return {
                "content": f"{expression} = {result}",
                "result": result
            }

        except Exception as e:
            return {
                "error": f"Calculation failed: {str(e)}",
                "content": f"Could not evaluate '{expression}'. Please check the expression syntax."
            }

    def _get_current_time(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get current date and time."""
        timezone = params.get("timezone", "UTC")
        format_type = params.get("format", "human")

        try:
            # For simplicity, just use local time or UTC
            # A full implementation would use pytz for timezone handling
            if timezone.upper() == "UTC":
                now = datetime.now(UTC)
                tz_info = "UTC"
            else:
                now = datetime.now()
                tz_info = "local time"

            if format_type == "iso":
                time_str = now.isoformat()
            elif format_type == "unix":
                time_str = str(int(now.timestamp()))
            else:  # human format
                time_str = now.strftime("%Y-%m-%d %H:%M:%S")

            return {
                "content": f"Current time ({tz_info}): {time_str}",
                "timestamp": time_str,
                "timezone": tz_info
            }

        except Exception as e:
            return {
                "error": f"Time lookup failed: {str(e)}",
                "content": f"Could not get current time for timezone: {timezone}"
            }