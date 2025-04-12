# utils/log_handler.py
"""
Handles the creation, loading, updating, and saving of the unified log file
for tracking processing status, progress, and errors.
"""

from datetime import datetime
import json
from pathlib import Path
import traceback
from typing import Optional, Dict, Any, Tuple, Set, List

# Import utilities and config
try:
    from .console_utils import get_console
    from . import file_handler
    # Assuming config.py is in the parent directory or accessible via PYTHONPATH
    try:
         import config
    except ImportError:
        from .. import config # Try relative import
except ImportError: # Fallback for direct execution or unusual structure
    from console_utils import get_console
    import file_handler
    # Define minimal fallbacks if config cannot be imported
    config = type('obj', (object,), {
         'STATUS_PENDING_OUTLINE': 'pending_outline',
         'STATUS_ERROR': 'error'
     })() # Dummy config object


console = get_console()


def _create_new_log_structure(input_file_path: str) -> Dict[str, Any]:
    """Creates the basic structure for a new log file."""
    console.print("Creating new log structure.")
    return {
        "input_file_path": input_file_path,
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "total_duration_seconds": None,
        "model_used_general": None, # Will be set by main
        "outline_model_used": None,
        "content_model_used": None,
        "overall_status": config.STATUS_PENDING_OUTLINE,
        "outline_file_path": None,
        "content_file_path_planned": None, # Path template before timestamp
        "content_file_path": None,      # Final path after successful run
        "processed_items": [], # List of strings like "stage:key"
        "errors": [],          # List of error detail dicts
        "api_calls": []        # List of API call attempt dicts (optional detailed logging)
    }

def load_log(log_file_path: Path, force_restart: bool, input_file_path: str) -> Tuple[Dict[str, Any], Set[str]]:
    """
    Loads an existing log file or creates a new one.

    Args:
        log_file_path: Path to the log file.
        force_restart: If True, ignores existing log and creates a new one.
        input_file_path: Path to the original input file (used if creating new log).

    Returns:
        A tuple containing:
            - log_data (Dict): The loaded or newly created log data.
            - processed_items_set (Set): A set of keys for items already processed.
    """
    if not isinstance(log_file_path, Path):
        log_file_path = Path(log_file_path) # Ensure Path object

    log_data = None
    processed_items_set = set()

    if not force_restart and log_file_path.exists():
        console.print(f"Found existing log file: [path]{log_file_path}[/path]")
        log_data = file_handler.load_json_file(log_file_path)
        if log_data:
            # Basic validation
            if isinstance(log_data.get("processed_items"), list) and \
               isinstance(log_data.get("errors"), list) and \
               log_data.get("overall_status"):
                console.print(f"Log file loaded. Status: [yellow]{log_data['overall_status']}[/yellow]. {len(log_data['processed_items'])} items previously processed.")
                processed_items_set = set(log_data["processed_items"])
                # Ensure essential keys exist even if loading older log version
                log_data.setdefault("api_calls", [])
                log_data.setdefault("content_file_path_planned", None)
                log_data.setdefault("content_file_path", None)
            else:
                console.print("[warning]Existing log file has unexpected structure. Creating new log.[/warning]")
                log_data = None # Invalidate loaded data
        else:
            console.print("[warning]Existing log file found but failed to load. Creating new log.[/warning]")

    if log_data is None:
        # Create new if no valid log exists or force_restart is True
        if force_restart:
            console.print("[yellow]Ignoring existing log file due to --force-restart flag.[/yellow]")
        log_data = _create_new_log_structure(input_file_path)

    return log_data, processed_items_set


def save_log(log_data: Dict[str, Any], log_file_path: Path) -> bool:
    """
    Saves the current log data state to the specified file.

    Args:
        log_data: The log data dictionary.
        log_file_path: Path to the log file.

    Returns:
        True if save was successful, False otherwise.
    """
    try:
        # Ensure lists are sorted for consistent output (optional but good practice)
        if "processed_items" in log_data:
            log_data["processed_items"] = sorted(list(set(log_data["processed_items"])))
        # Optionally sort errors by timestamp?
        # log_data.get("errors", []).sort(key=lambda x: x.get("timestamp", ""))

        if file_handler.save_json_file(log_data, log_file_path):
            # console.print(f"Log saved to {log_file_path}", style="dim") # Too verbose?
            return True
        else:
            console.print(f"[error]Failed to save log file to [path]{log_file_path}[/path][/error]")
            return False
    except Exception as e:
        console.print(f"[error]Unexpected error saving log: {e}[/error]")
        return False


def log_item_success(log_data: Dict[str, Any], stage: str, item_key: str):
    """Adds an item key to the list of processed items."""
    unique_key = f"{stage}:{item_key}"
    if unique_key not in log_data.get("processed_items", []):
         # Use setdefault to ensure list exists
         log_data.setdefault("processed_items", []).append(unique_key)


def log_error(log_data: Dict[str, Any], stage: str, item_key: str, error_details: Dict[str, Any]):
    """Logs an error encountered during processing."""
    error_entry = {
        "timestamp": datetime.now().isoformat(),
        "stage": stage,
        "item_key": item_key,
        **error_details # Include fields like 'error', 'traceback', 'status' etc.
    }
    # Use setdefault to ensure list exists
    log_data.setdefault("errors", []).append(error_entry)


def update_status(log_data: Dict[str, Any], new_status: str):
    """Updates the overall status of the processing run."""
    log_data["overall_status"] = new_status
    console.print(f"Status updated to: [yellow]{new_status}[/yellow]")


def log_api_call(log_data: Dict[str, Any], stage: str, item_key: str, call_details: Dict[str, Any]):
    """Logs details about an API call attempt (optional)."""
    api_call_entry = {
        "timestamp": datetime.now().isoformat(),
        "stage": stage,
        "item_key": item_key,
        **call_details # Include model, attempt, status, prompt_len, response_len, error etc.
    }
    # Use setdefault to ensure list exists
    log_data.setdefault("api_calls", []).append(api_call_entry)