"""
Rails Agent Configuration System.

Provides configuration management for the Rails code analysis agent,
including tool settings, indexing options, and performance tuning.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Union


@dataclass
class ToolConfig:
    """Configuration for external tools."""
    enabled: bool = True
    timeout: int = 30
    path: Optional[str] = None
    args: List[str] = None

    def __post_init__(self):
        if self.args is None:
            self.args = []


@dataclass
class IndexingConfig:
    """Configuration for code indexing."""
    enabled: bool = True
    auto_rebuild: bool = False
    rebuild_threshold_hours: int = 24
    max_file_size: int = 1024 * 1024  # 1MB
    include_patterns: List[str] = None
    exclude_patterns: List[str] = None
    chunk_size: int = 1000
    overlap: int = 200

    def __post_init__(self):
        if self.include_patterns is None:
            self.include_patterns = ["*.rb", "*.erb", "*.yml", "*.yaml"]
        if self.exclude_patterns is None:
            self.exclude_patterns = [
                "*/tmp/*", "*/log/*", "*/vendor/*", "*/.git/*",
                "*/node_modules/*", "*/coverage/*", "*/.bundle/*"
            ]


@dataclass
class SearchConfig:
    """Configuration for code search."""
    max_results: int = 50
    similarity_threshold: float = 0.7
    multi_tier_search: bool = True
    enable_fuzzy_matching: bool = True
    ranking_weights: Dict[str, float] = None

    def __post_init__(self):
        if self.ranking_weights is None:
            self.ranking_weights = {
                "exact_match": 1.0,
                "model_definition": 0.9,
                "symbol_definition": 0.8,
                "related_controller": 0.7,
                "association": 0.6
            }


@dataclass
class EmbeddingConfig:
    """Configuration for code embeddings."""
    enabled: bool = True
    model_type: str = "auto"  # auto, codebert, simple
    cache_embeddings: bool = True
    batch_size: int = 32
    max_sequence_length: int = 512

    def __post_init__(self):
        if self.model_type not in ["auto", "codebert", "simple"]:
            self.model_type = "auto"


@dataclass
class RailsAgentConfig:
    """Main Rails agent configuration."""
    # General settings
    project_root: str = "."
    enabled: bool = False
    debug_mode: bool = False

    # Cache settings
    cache_dir: str = "cache"
    persistent_cache: bool = True

    # Tool configurations
    tree_sitter: ToolConfig = None
    solargraph: ToolConfig = None
    ruby_lsp: ToolConfig = None
    ast_grep: ToolConfig = None
    ctags: ToolConfig = None
    ripgrep: ToolConfig = None

    # Feature configurations
    indexing: IndexingConfig = None
    search: SearchConfig = None
    embeddings: EmbeddingConfig = None

    # Performance settings
    max_concurrent_operations: int = 4
    operation_timeout: int = 60

    def __post_init__(self):
        # Initialize sub-configs if not provided
        if self.tree_sitter is None:
            self.tree_sitter = ToolConfig()
        if self.solargraph is None:
            self.solargraph = ToolConfig()
        if self.ruby_lsp is None:
            self.ruby_lsp = ToolConfig()
        if self.ast_grep is None:
            self.ast_grep = ToolConfig()
        if self.ctags is None:
            self.ctags = ToolConfig()
        if self.ripgrep is None:
            self.ripgrep = ToolConfig(args=["--type", "ruby"])

        if self.indexing is None:
            self.indexing = IndexingConfig()
        if self.search is None:
            self.search = SearchConfig()
        if self.embeddings is None:
            self.embeddings = EmbeddingConfig()

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RailsAgentConfig':
        """Create configuration from dictionary."""
        # Convert nested dictionaries to dataclass instances
        if 'tree_sitter' in data and isinstance(data['tree_sitter'], dict):
            data['tree_sitter'] = ToolConfig(**data['tree_sitter'])
        if 'solargraph' in data and isinstance(data['solargraph'], dict):
            data['solargraph'] = ToolConfig(**data['solargraph'])
        if 'ruby_lsp' in data and isinstance(data['ruby_lsp'], dict):
            data['ruby_lsp'] = ToolConfig(**data['ruby_lsp'])
        if 'ast_grep' in data and isinstance(data['ast_grep'], dict):
            data['ast_grep'] = ToolConfig(**data['ast_grep'])
        if 'ctags' in data and isinstance(data['ctags'], dict):
            data['ctags'] = ToolConfig(**data['ctags'])
        if 'ripgrep' in data and isinstance(data['ripgrep'], dict):
            data['ripgrep'] = ToolConfig(**data['ripgrep'])

        if 'indexing' in data and isinstance(data['indexing'], dict):
            data['indexing'] = IndexingConfig(**data['indexing'])
        if 'search' in data and isinstance(data['search'], dict):
            data['search'] = SearchConfig(**data['search'])
        if 'embeddings' in data and isinstance(data['embeddings'], dict):
            data['embeddings'] = EmbeddingConfig(**data['embeddings'])

        return cls(**data)


class RailsAgentConfigManager:
    """
    Manages Rails agent configuration loading, saving, and validation.
    """

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_file: Path to configuration file (default: config/rails_agent.json)
        """
        if config_file is None:
            config_file = "config/rails_agent.json"

        self.config_file = Path(config_file)
        self._config: Optional[RailsAgentConfig] = None

    def load_config(self) -> RailsAgentConfig:
        """
        Load configuration from file or create default.

        Returns:
            Rails agent configuration
        """
        if self._config is not None:
            return self._config

        # Try to load from file
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._config = RailsAgentConfig.from_dict(data)
                return self._config
            except Exception as e:
                print(f"Error loading config from {self.config_file}: {e}")

        # Create default configuration
        self._config = self._create_default_config()
        return self._config

    def save_config(self, config: Optional[RailsAgentConfig] = None) -> None:
        """
        Save configuration to file.

        Args:
            config: Configuration to save (uses current if None)
        """
        if config is None:
            config = self._config

        if config is None:
            raise ValueError("No configuration to save")

        # Ensure config directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config to {self.config_file}: {e}")

    def _create_default_config(self) -> RailsAgentConfig:
        """Create default Rails agent configuration."""
        # Detect project root (look for Rails indicators)
        project_root = self._detect_project_root()

        return RailsAgentConfig(
            project_root=str(project_root),
            enabled=False,  # Start disabled by default
            debug_mode=False
        )

    def _detect_project_root(self) -> Path:
        """Detect Rails project root by looking for key files."""
        current = Path.cwd()

        # Look for Rails indicators
        rails_indicators = [
            "Gemfile",
            "config/application.rb",
            "app",
            "db"
        ]

        for parent in [current] + list(current.parents):
            if all((parent / indicator).exists() for indicator in rails_indicators[:2]):
                return parent

        # Fallback to current directory
        return current

    def update_config(self, **kwargs) -> None:
        """
        Update configuration settings.

        Args:
            **kwargs: Configuration settings to update
        """
        config = self.load_config()

        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
            else:
                print(f"Warning: Unknown configuration key: {key}")

        self._config = config

    def get_tool_config(self, tool_name: str) -> Optional[ToolConfig]:
        """
        Get configuration for specific tool.

        Args:
            tool_name: Name of tool (tree_sitter, solargraph, etc.)

        Returns:
            Tool configuration or None if not found
        """
        config = self.load_config()
        return getattr(config, tool_name, None)

    def is_tool_enabled(self, tool_name: str) -> bool:
        """
        Check if tool is enabled.

        Args:
            tool_name: Name of tool

        Returns:
            True if tool is enabled
        """
        tool_config = self.get_tool_config(tool_name)
        return tool_config is not None and tool_config.enabled

    def get_cache_directory(self) -> Path:
        """Get cache directory path."""
        config = self.load_config()
        cache_dir = Path(config.cache_dir)

        if not cache_dir.is_absolute():
            cache_dir = Path(config.project_root) / cache_dir

        return cache_dir

    def validate_config(self) -> List[str]:
        """
        Validate configuration and return list of issues.

        Returns:
            List of validation error messages
        """
        config = self.load_config()
        issues = []

        # Validate project root
        project_root = Path(config.project_root)
        if not project_root.exists():
            issues.append(f"Project root does not exist: {project_root}")

        # Validate cache directory
        try:
            cache_dir = self.get_cache_directory()
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(f"Cannot create cache directory: {e}")

        # Validate indexing patterns
        if not config.indexing.include_patterns:
            issues.append("No include patterns specified for indexing")

        # Validate search settings
        if config.search.max_results <= 0:
            issues.append("Max results must be positive")

        if not (0 <= config.search.similarity_threshold <= 1):
            issues.append("Similarity threshold must be between 0 and 1")

        return issues

    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self._config = self._create_default_config()

    def export_config(self, output_file: str) -> None:
        """
        Export configuration to file.

        Args:
            output_file: Path to output file
        """
        config = self.load_config()

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)

    def import_config(self, input_file: str) -> None:
        """
        Import configuration from file.

        Args:
            input_file: Path to input file
        """
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self._config = RailsAgentConfig.from_dict(data)

    def get_environment_overrides(self) -> Dict[str, Any]:
        """
        Get configuration overrides from environment variables.

        Returns:
            Dictionary of environment-based config overrides
        """
        overrides = {}

        # Check for environment variables
        env_mappings = {
            'RAILS_AGENT_ENABLED': ('enabled', lambda x: x.lower() == 'true'),
            'RAILS_AGENT_DEBUG': ('debug_mode', lambda x: x.lower() == 'true'),
            'RAILS_AGENT_PROJECT_ROOT': ('project_root', str),
            'RAILS_AGENT_CACHE_DIR': ('cache_dir', str),
            'RAILS_AGENT_MAX_RESULTS': ('search.max_results', int),
            'RAILS_AGENT_SIMILARITY_THRESHOLD': ('search.similarity_threshold', float),
        }

        for env_var, (config_key, converter) in env_mappings.items():
            env_value = os.environ.get(env_var)
            if env_value is not None:
                try:
                    overrides[config_key] = converter(env_value)
                except (ValueError, TypeError) as e:
                    print(f"Invalid environment variable {env_var}: {e}")

        return overrides

    def apply_environment_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        overrides = self.get_environment_overrides()
        config = self.load_config()

        for key, value in overrides.items():
            if '.' in key:
                # Handle nested keys (e.g., 'search.max_results')
                parts = key.split('.')
                obj = config
                for part in parts[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, parts[-1], value)
            else:
                setattr(config, key, value)

        self._config = config


# Global configuration manager instance
_config_manager = None


def get_config_manager() -> RailsAgentConfigManager:
    """Get or create global configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = RailsAgentConfigManager()
    return _config_manager


def get_config() -> RailsAgentConfig:
    """Get current Rails agent configuration."""
    return get_config_manager().load_config()


# Configuration presets for different use cases
PRESETS = {
    "minimal": {
        "enabled": True,
        "embeddings": {"enabled": False},
        "tree_sitter": {"enabled": False},
        "solargraph": {"enabled": False},
        "ruby_lsp": {"enabled": False},
    },
    "standard": {
        "enabled": True,
        "embeddings": {"enabled": True, "model_type": "simple"},
        "search": {"max_results": 25},
    },
    "full": {
        "enabled": True,
        "embeddings": {"enabled": True, "model_type": "codebert"},
        "search": {"max_results": 50, "multi_tier_search": True},
        "indexing": {"auto_rebuild": True},
    },
    "performance": {
        "enabled": True,
        "max_concurrent_operations": 8,
        "operation_timeout": 30,
        "indexing": {"max_file_size": 512 * 1024},  # 512KB
        "search": {"max_results": 20},
    }
}


def apply_preset(preset_name: str) -> None:
    """
    Apply a configuration preset.

    Args:
        preset_name: Name of preset to apply
    """
    if preset_name not in PRESETS:
        raise ValueError(f"Unknown preset: {preset_name}")

    config_manager = get_config_manager()
    config = config_manager.load_config()

    preset_data = PRESETS[preset_name]

    # Apply preset recursively
    def apply_nested(target, source):
        for key, value in source.items():
            if isinstance(value, dict) and hasattr(target, key):
                apply_nested(getattr(target, key), value)
            else:
                setattr(target, key, value)

    apply_nested(config, preset_data)
    config_manager.save_config(config)