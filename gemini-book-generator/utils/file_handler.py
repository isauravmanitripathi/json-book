# utils/file_handler.py
"""
Utility functions for reliably loading and saving JSON files.
"""

import json
from pathlib import Path
import traceback
from typing import Optional, Dict, Any

# Import the console instance from console_utils
try:
    from .console_utils import get_console
except ImportError: # Fallback for direct execution or unusual structure
    from console_utils import get_console

console = get_console()


def load_json_file(file_path: Path) -> Optional[Dict]:
    """
    Load and parse JSON file, returning None on error.

    Args:
        file_path: Path object pointing to the JSON file.

    Returns:
        Loaded dictionary or None if an error occurs.
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path) # Ensure it's a Path object

    try:
        with file_path.open('r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        # Logged as warning, might be expected (e.g., first run log file)
        # console.print(f"[yellow]Warning: File not found at {file_path}[/yellow]")
        return None
    except json.JSONDecodeError as e:
        console.print(f"[error]Error loading JSON: Invalid JSON format.[/error]")
        console.print(f"File: [path]{file_path}[/path]")
        console.print(f"Error details: {e}")
        # Attempt to show context of the error
        try:
            with file_path.open('r', encoding='utf-8') as file_check:
                content = file_check.read()
                lines = content.splitlines()
                if 0 < e.lineno <= len(lines):
                    console.print(f"Problem near line {e.lineno}, column {e.colno}:")
                    # Print a few lines around the error line for context
                    start = max(0, e.lineno - 2)
                    end = min(len(lines), e.lineno + 1)
                    for i in range(start, end):
                         line_num_str = f"{i+1}: ".rjust(len(str(end)) + 2)
                         prefix = f"{line_num_str}"
                         indicator = ">>" if i == e.lineno - 1 else "  "
                         console.print(f"{prefix}{indicator}{lines[i]}")
                    # Pointer line (adjusting for line number prefix and indicator)
                    pointer_spaces = len(prefix) + len(indicator) + (e.colno - 1)
                    console.print(" " * pointer_spaces + "^")
        except Exception as read_err:
             console.print(f"[warning]Could not read file to show error location: {read_err}[/warning]")
        return None
    except Exception as e:
        console.print(f"[error]Unexpected error loading JSON file: {e}[/error]")
        console.print(f"File: [path]{file_path}[/path]")
        console.print(traceback.format_exc())
        return None


def save_json_file(data: Dict[str, Any], file_path: Path) -> bool:
    """
    Save data to a JSON file, returning True on success, False on error.

    Args:
        data: The dictionary to save.
        file_path: Path object for the destination JSON file.

    Returns:
        True if save was successful, False otherwise.
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path) # Ensure it's a Path object

    try:
        # Ensure the parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # Save atomically by writing to temp file then renaming (optional but safer)
        # For simplicity here, direct write:
        with file_path.open('w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        console.print(f"[error]Error saving JSON file: {e}[/error]")
        console.print(f"Path: [path]{file_path}[/path]")
        # console.print(traceback.format_exc()) # Uncomment for debugging if needed
        return False