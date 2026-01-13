#!/usr/bin/env python3
"""
Common utility functions shared across agent scripts.

This module contains reusable functions for file operations, data loading,
scholar validation, and terminal output formatting.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'


def get_project_root() -> Path:
    """Get the project root directory (parent of agent_scripts)."""
    return Path(__file__).parent.parent.resolve()


def load_json_file(file_path: Path) -> dict:
    """Load and parse a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(file_path: Path, data: dict) -> None:
    """Save data to a JSON file with proper formatting."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def archive_file(file_path: Path) -> Path:
    """
    Archive an existing file by adding timestamp to filename.

    Args:
        file_path: Path to the file to archive

    Returns:
        Path to the archived file
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    stem = file_path.stem
    archive_name = f"{stem}_archived_{timestamp}.json"
    archive_path = file_path.parent / archive_name
    shutil.copy2(file_path, archive_path)
    return archive_path


def get_validated_scholars(data: dict, strict: bool = True) -> list[dict]:
    """
    Extract scholars with validated AMiner IDs from the data.

    Supports two validation formats:
    1. Old format: {status: "success", is_same_person: true}
    2. New format: {status: "success", confidence: "high"/"medium"/"low"}

    Args:
        data: The data dictionary containing talents
        strict: If True, requires high/medium confidence or is_same_person == True.
                If False, accepts any successful validation except low confidence.

    Returns:
        List of scholars with validated AMiner IDs
    """
    scholars = []
    for talent in data.get("talents", []):
        validation = talent.get("aminer_validation", {})
        aminer_id = talent.get("aminer_id", "")

        # Skip if no aminer_id or failed
        if not aminer_id or aminer_id == "failed":
            continue

        # Skip if validation failed
        if validation.get("status") != "success":
            continue

        # Check validation format and apply criteria
        confidence = validation.get("confidence")
        is_same_person = validation.get("is_same_person")

        # New format (with confidence field)
        if confidence is not None:
            if strict:
                # Strict mode: accept high or medium confidence
                if confidence in ("high", "medium"):
                    scholars.append(talent)
            else:
                # Relaxed mode: accept any confidence except low
                if confidence != "low":
                    scholars.append(talent)
        # Old format (with is_same_person field)
        elif is_same_person is not None:
            if is_same_person is True:
                scholars.append(talent)
        # Status is success but no confidence or is_same_person
        # In strict mode, skip. In relaxed mode, accept.
        elif not strict:
            scholars.append(talent)

    return scholars


def merge_dicts(base: dict, update: dict, overwrite: bool = False) -> dict:
    """
    Merge two dictionaries, preserving existing values in base unless overwrite is True.

    Args:
        base: Base dictionary
        update: Dictionary with new values
        overwrite: If True, update values overwrite base values. If False, base values are preserved.

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in update.items():
        if key not in result:
            # Key doesn't exist in base, add it
            result[key] = value
        elif overwrite:
            # Overwrite mode: update value
            result[key] = value
        elif isinstance(result[key], dict) and isinstance(value, dict):
            # Both are dicts, recursively merge
            result[key] = merge_dicts(result[key], value, overwrite)
        elif isinstance(result[key], list) and isinstance(value, list):
            # Both are lists, extend (avoiding duplicates for simple types)
            if all(isinstance(x, (str, int, float, bool)) for x in result[key] + value):
                # Simple types: use set to avoid duplicates
                result[key] = list(dict.fromkeys(result[key] + value))
            else:
                # Complex types: just extend
                result[key] = result[key] + value
        # else: keep base value (not overwrite)

    return result


def print_progress(
    current: int,
    total: int,
    name: str,
    status: str,
    message: str = "",
    color: str = Colors.CYAN
):
    """
    Print progress information in a consistent format.

    Args:
        current: Current item number (1-indexed)
        total: Total number of items
        name: Name of the item being processed
        status: Status text (e.g., "Processing", "Success", "Error")
        message: Optional additional message
        color: ANSI color code for status
    """
    progress = f"[{current}/{total}]"
    status_colored = f"{color}{status}{Colors.ENDC}"

    if message:
        print(f"{progress} {status_colored} {name} - {message}")
    else:
        print(f"{progress} {status_colored} {name}")


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
