# utils/console_utils.py
"""
Handles console output, providing rich formatting if available,
otherwise falling back to simple printing.
"""

import re
import sys
import random
from typing import Any

# --- Attempt to import Rich ---
try:
    from rich.console import Console
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeRemainingColumn,
        TimeElapsedColumn
    )
    from rich.theme import Theme
    rich_available = True
except ImportError:
    rich_available = False

# --- Define Fallbacks if Rich is not available ---

class SimpleConsole:
    """A basic console replacement that mimics rich.console.Console.print."""
    def print(self, message: Any = "", **kwargs):
        """Prints the message after attempting to remove rich formatting tags."""
        plain_message = re.sub(r'\[/?.*?\]', '', str(message))
        print(plain_message)

    def rule(self, title: str = "", **kwargs):
         """Prints a simple rule line."""
         width = 80 # Simple fixed width
         if title:
             title = f" {title} "
             print(title.center(width, "-"))
         else:
             print("-" * width)

    def status(self, message: str):
        """Provides a dummy context manager for status messages."""
        class DummyStatusContext:
            def __enter__(self):
                print(f"... {message}") # Print status start
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                 pass # No explicit end message for simple console
            def update(self, text: str):
                 print(f"... {text}") # Print status update
        return DummyStatusContext()


class SimpleProgress:
    """A basic progress bar replacement."""
    def __init__(self, console=None, disable=False, *args, **kwargs):
        self._console = console if console else SimpleConsole()
        self._disable = disable
        self._tasks = {}
        self._task_id_counter = 0
        self._total_description = "Processing"

    def add_task(self, description, total=None, **kwargs):
        if self._disable: return None
        task_id = self._task_id_counter
        # Only track one overall progress for simplicity
        if total: self._tasks['total'] = total
        if description: self._total_description = description
        self._tasks['completed'] = 0
        self._task_id_counter += 1
        self._console.print(f"Starting: {description} (Total: {total or 'N/A'})")
        return task_id # Return an ID, though it's not really used for multi-task

    def update(self, task_id, advance=None, description=None, total=None, **kwargs):
        if self._disable: return
        # Update overall progress
        if advance: self._tasks['completed'] = self._tasks.get('completed', 0) + advance
        if description: self._tasks['description'] = description # Store last description update
        if total is not None: self._tasks['total'] = total

        current_total = self._tasks.get('total')
        current_completed = self._tasks.get('completed', 0)
        current_description = self._tasks.get('description', self._total_description)

        # Print update periodically (e.g., every 5% or on completion)
        should_print = False
        if current_total and current_total > 0:
             progress_percent = (current_completed / current_total) * 100
             # Print roughly every 5% or on first/last item
             if current_completed == 1 or current_completed == current_total or \
                int(progress_percent) % 5 == 0 and random.random() < 0.2: # Add randomness
                 should_print = True
        elif advance: # Print if no total but advancing
             should_print = True

        if should_print:
             progress_str = f" {progress_percent:.1f}%" if current_total else ""
             self._console.print(f"Progress: {current_description} [{current_completed}/{current_total or '?'}] {progress_str}")


    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._disable: self._console.print("Progress finished.")


# --- Global Instances ---
_console_instance = None

def get_console():
    """Returns a shared Console instance (Rich or Simple)."""
    global _console_instance
    if _console_instance is None:
        if rich_available:
            custom_theme = Theme({
                "info": "dim cyan",
                "warning": "yellow",
                "error": "bold red",
                "success": "green",
                "debug": "dim magenta",
                "path": "cyan underline",
            })
            _console_instance = Console(theme=custom_theme)
        else:
            print("Note: 'rich' library not found. Using basic console output.", file=sys.stderr)
            _console_instance = SimpleConsole()
    return _console_instance

def get_progress_bar(**kwargs):
    """Returns a Progress bar instance (Rich or Simple)."""
    console = get_console() # Ensure console is initialized
    if rich_available:
        # Default Rich progress columns
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("({task.completed}/{task.total})"),
            TimeRemainingColumn(),
            TimeElapsedColumn(),
            console=console,
            **kwargs # Pass any extra args like 'disable'
        )
    else:
        # Return the simple fallback progress bar
        return SimpleProgress(console=console, **kwargs)