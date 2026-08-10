"""
This module provides a centralized utility to resolve project paths and load
the application configuration from config.json.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_FILE_PATH = PROJECT_ROOT / "config" / "config.json"


def load_config() -> dict:
    """Loads and returns the runtime configuration dictionary from config.json.

    Returns:
        dict: The parsed configuration parameters.

    Raises:
        FileNotFoundError: If config/config.json does not exist at the project root.
    """
    if not CONFIG_FILE_PATH.exists():
        raise FileNotFoundError(
            f"Configuration file not found at expected path: {CONFIG_FILE_PATH}"
        )

    with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


config = load_config()
