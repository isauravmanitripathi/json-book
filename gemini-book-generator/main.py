# main.py
"""
Main orchestration script for generating book outlines and content using Gemini API.

Handles command-line arguments, initializes logging, manages state,
and calls stage-specific processing modules.
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import time
from collections import deque
import traceback

# --- Import Configuration and Modules ---
try:
    import config
    from api import gemini_client
    # Placeholders for modules we haven't created yet
    from stages import outline_generator
    from stages import content_generator
    from utils import file_handler
    from utils import log_handler
    from utils import console_utils
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Ensure the script is run from the project root directory and")
    print("that all modules (config.py, api/gemini_client.py, stages/*, utils/*) exist.")
    sys.exit(1)

# --- Main Function ---
def main():
    start_time_main = datetime.now()
    print(f"\n--- Script Execution Started: {start_time_main.strftime('%Y-%m-%d %H:%M:%S')} ---")

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description='Generate book outlines and content using Google Gemini API.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--input_file',
        type=str,
        required=True,
        help='Path to the input JSON file containing the initial book structure.'
    )
    parser.add_argument(
        '--output_dir',
        type=str,
        default='results',
        help='Base directory to save output files (logs, intermediate, final content).'
    )
    parser.add_argument(
        '--model',
        type=str,
        default=None, # Default set below based on config
        help='Default Gemini model for generation (can be overridden by OUTLINE_GEMINI_MODEL for Stage 1).'
    )
    parser.add_argument(
        '--outline_model',
        type=str,
        default=config.OUTLINE_GEMINI_MODEL,
        help='Specific Gemini model for outline generation (Stage 1).'
    )
    parser.add_argument(
        '--content_model',
        type=str,
        default=config.DEFAULT_GEMINI_MODEL, # Keep separate content model config
        help='Specific Gemini model for content generation (Stage 2).'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run a quick API connection test before processing.'
    )
    parser.add_argument(
        '--force-restart',
        action='store_true',
        help='Ignore existing log file and start processing from scratch.'
    )
    args = parser.parse_args()

    # Set default model if not provided via args
    if args.model is None:
        args.model = config.DEFAULT_GEMINI_MODEL # General default if others aren't specified

    # Use the general model arg as default for specific models if they are still at config default
    if args.outline_model == config.OUTLINE_GEMINI_MODEL:
        args.outline_model = args.model
    if args.content_model == config.DEFAULT_GEMINI_MODEL:
         args.content_model = args.model


    # --- Initialization ---
    console = console_utils.get_console()
    console.print(f"Input file: [cyan]{args.input_file}[/cyan]")
    console.print(f"Output directory: [cyan]{args.output_dir}[/cyan]")
    console.print(f"Outline Model: [cyan]{args.outline_model}[/cyan]")
    console.print(f"Content Model: [cyan]{args.content_model}[/cyan]")
    console.print(f"Force Restart: [yellow]{args.force_restart}[/yellow]")

    # Load API Key
    load_dotenv()
    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        console.print("[bold red]Fatal Error: GOOGLE_API_KEY not found in environment variables or .env file.[/bold red]")
        sys.exit(1)
    else:
        console.print(f"Found API key (starts: {api_key[:5]}..., ends: ...{api_key[-4:]})")

    # API Test
    if args.test:
        console.print("\n--- Running API Test ---")
        # Test both models if they differ
        models_to_test = set([args.outline_model, args.content_model])
        all_tests_passed = True
        for model_name in models_to_test:
             if not gemini_client.test_gemini_api(api_key, model_name=model_name):
                 all_tests_passed = False
                 console.print(f"[bold red]API test failed for model {model_name}.[/bold red]")
        if not all_tests_passed:
             console.print("[bold red]One or more API tests failed. Exiting. Please check your API key, billing status, model names, and internet connection.[/bold red]")
             sys.exit(1)
        else:
            console.print("[green]--- API Test(s) Complete ---[/green]")


    # --- Path Setup ---
    input_path = Path(args.input_file)
    if not input_path.is_file():
        console.print(f"[bold red]Fatal Error: Input file not found at '{args.input_file}'[/bold red]")
        sys.exit(1)

    input_file_stem = input_path.stem
    output_base_dir = Path(args.output_dir)
    output_run_dir = output_base_dir / input_file_stem # Subdir for this specific run

    try:
        output_run_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"Ensured output directory exists: [cyan]{output_run_dir.resolve()}[/cyan]")
    except Exception as e:
        console.print(f"[bold red]Fatal Error: Could not create output directory '{output_run_dir}'. Check permissions. Error: {e}[/bold red]")
        sys.exit(1)

    # Define file paths
    log_file_path = output_run_dir / f"{input_file_stem}{config.LOG_FILENAME_SUFFIX}"
    outline_file_path = output_run_dir / f"{input_file_stem}{config.OUTLINE_FILENAME_SUFFIX}"
    # Content filename needs timestamp, will be finalized later
    content_file_path_template = output_run_dir / f"{input_file_stem}{config.CONTENT_FILENAME_SUFFIX_TEMPLATE}"


    # --- Logging and State Check ---
    log_data, processed_items_set = log_handler.load_log(log_file_path, force_restart=args.force_restart, input_file_path=str(input_path))
    current_status = log_data.get("overall_status", config.STATUS_PENDING_OUTLINE) # Default to starting outline

    # Initialize shared rate limiting deque
    api_call_timestamps = deque(maxlen=config.API_CALL_LIMIT_PER_MINUTE)

    # --- Main Processing Logic ---
    outline_data = None
    content_data = None
    final_content_path = None
    exit_code = 0

    try:
        # === Stage 1: Outline Generation ===
        if current_status == config.STATUS_PENDING_OUTLINE:
            console.print("\n[bold blue]=== Starting Stage 1: Outline Generation ===[/bold blue]")
            log_data["outline_model_used"] = args.outline_model # Log the model used for this stage
            log_handler.update_status(log_data, config.STATUS_PENDING_OUTLINE) # Explicitly set status
            log_handler.save_log(log_data, log_file_path) # Save initial state

            initial_data = file_handler.load_json_file(str(input_path))
            if initial_data is None:
                raise ValueError(f"Failed to load input file: {input_path}")

            outline_data, success = outline_generator.run_outline_stage(
                initial_data=initial_data,
                api_key=api_key,
                model_name=args.outline_model,
                temperature=config.API_TEMPERATURE_OUTLINE,
                max_tokens=config.API_MAX_OUTPUT_TOKENS_OUTLINE,
                output_dir=output_run_dir, # Pass run dir
                outline_file_path=outline_file_path,
                log_data=log_data,
                log_file_path=log_file_path,
                processed_items_set=processed_items_set,
                api_call_timestamps_deque=api_call_timestamps,
                console=console
            )

            if success:
                console.print("[bold green]Stage 1: Outline Generation Completed Successfully.[/bold green]")
                log_handler.update_status(log_data, config.STATUS_OUTLINE_COMPLETE)
                log_data["outline_file_path"] = str(outline_file_path.resolve())
                current_status = config.STATUS_OUTLINE_COMPLETE
            else:
                console.print("[bold red]Stage 1: Outline Generation Failed or Partially Completed. See log.[/bold red]")
                log_handler.update_status(log_data, config.STATUS_ERROR)
                raise RuntimeError("Outline generation failed.") # Stop processing

            log_handler.save_log(log_data, log_file_path) # Save status update


        # === Stage 2: Content Generation ===
        # Proceed only if outline stage is complete (either just finished or from previous run)
        if current_status == config.STATUS_OUTLINE_COMPLETE:
             console.print("\n[bold blue]=== Starting Stage 2: Content Generation ===[/bold blue]")
             log_data["content_model_used"] = args.content_model # Log the model used for this stage
             log_handler.update_status(log_data, config.STATUS_PENDING_CONTENT)
             log_handler.save_log(log_data, log_file_path)

             # Load outline data if not already in memory (i.e., if resuming)
             if outline_data is None:
                 if outline_file_path.exists():
                     console.print(f"Loading outline data from: {outline_file_path}")
                     outline_data = file_handler.load_json_file(str(outline_file_path))
                     if outline_data is None:
                         raise ValueError(f"Failed to load intermediate outline file: {outline_file_path}")
                 else:
                     # This should not happen if status is outline_complete, but handle defensively
                     raise FileNotFoundError(f"Cannot start Stage 2: Outline file missing at {outline_file_path} despite log status.")

             # Define final content path with timestamp
             timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
             final_content_path = Path(str(content_file_path_template).format(timestamp=timestamp_str))
             log_data["content_file_path_planned"] = str(final_content_path.resolve()) # Store planned path

             content_data, success = content_generator.run_content_stage(
                outline_data=outline_data,
                api_key=api_key,
                model_name=args.content_model,
                temperature=config.API_TEMPERATURE_CONTENT,
                max_tokens=config.API_MAX_OUTPUT_TOKENS_CONTENT,
                output_dir=output_run_dir,
                final_content_path=final_content_path, # Pass the specific final path
                log_data=log_data,
                log_file_path=log_file_path,
                processed_items_set=processed_items_set,
                api_call_timestamps_deque=api_call_timestamps,
                console=console
             )

             if success:
                console.print("[bold green]Stage 2: Content Generation Completed Successfully.[/bold green]")
                log_handler.update_status(log_data, config.STATUS_CONTENT_COMPLETE)
                log_data["content_file_path"] = str(final_content_path.resolve()) # Confirm final path
                current_status = config.STATUS_CONTENT_COMPLETE
             else:
                console.print("[bold red]Stage 2: Content Generation Failed or Partially Completed. See log.[/bold red]")
                log_handler.update_status(log_data, config.STATUS_ERROR)
                # Don't raise exception here, allow finalization/logging

             log_handler.save_log(log_data, log_file_path) # Save status update

        elif current_status == config.STATUS_CONTENT_COMPLETE:
             console.print("\n[bold green]Log indicates Content Generation is already complete. Skipping processing.[/bold green]")
             final_content_path = Path(log_data.get("content_file_path", "Unknown")) # Get path from log
             # Check if the file actually exists
             if not final_content_path.exists() and "content_file_path_planned" in log_data:
                  final_content_path = Path(log_data["content_file_path_planned"])


    except KeyboardInterrupt:
        console.print("\n[bold yellow]Process interrupted by user. Saving log before exiting...[/bold yellow]")
        exit_code = 130 # Standard exit code for Ctrl+C
    except FileNotFoundError as e:
         console.print(f"[bold red]ERROR: Required file not found: {e}[/bold red]")
         log_handler.log_error(log_data, "main", "setup", {"error": str(e), "traceback": traceback.format_exc()})
         log_handler.update_status(log_data, config.STATUS_ERROR)
         exit_code = 1
    except ValueError as e:
         console.print(f"[bold red]ERROR: Data loading or validation error: {e}[/bold red]")
         log_handler.log_error(log_data, "main", "data_handling", {"error": str(e), "traceback": traceback.format_exc()})
         log_handler.update_status(log_data, config.STATUS_ERROR)
         exit_code = 1
    except RuntimeError as e: # Catch specific runtime errors raised by stages
         console.print(f"[bold red]ERROR: Processing stage failed: {e}[/bold red]")
         # Error should already be logged by the stage, status set in log_data
         exit_code = 1
    except Exception as e:
        console.print(f"\n[bold red]An unexpected critical error occurred:[/bold red]")
        console.print(traceback.format_exc())
        # Log this critical error
        log_handler.log_error(log_data, "main", "critical", {"error": str(e), "traceback": traceback.format_exc()})
        log_handler.update_status(log_data, config.STATUS_ERROR)
        exit_code = 1
    finally:
        # --- Finalization ---
        end_time_main = datetime.now()
        log_data["end_time"] = end_time_main.isoformat()
        log_data["total_duration_seconds"] = (end_time_main - start_time_main).total_seconds()
        log_handler.save_log(log_data, log_file_path) # Save final log state

        console.print("\n[bold green]=== Processing Finished ===[/bold green]")
        console.print(f"Final Status: [bold {'green' if current_status == config.STATUS_CONTENT_COMPLETE else 'yellow' if current_status == config.STATUS_OUTLINE_COMPLETE else 'red'}]{current_status}[/bold]")
        console.print(f"Log file saved to: [link=file://{log_file_path.resolve()}]{log_file_path.resolve()}[/link]")
        if outline_file_path.exists():
             console.print(f"Intermediate outline file: [link=file://{outline_file_path.resolve()}]{outline_file_path.resolve()}[/link]")
        if final_content_path and final_content_path.exists():
             console.print(f"Final content file saved to: [link=file://{final_content_path.resolve()}]{final_content_path.resolve()}[/link]")
        elif "content_file_path" in log_data:
             console.print(f"Final content file (from log): [link=file://{log_data['content_file_path']}]{log_data['content_file_path']}[/link]")
        elif log_data.get("overall_status") == config.STATUS_CONTENT_COMPLETE:
             console.print("[yellow]Warning: Log indicates content complete, but final content file path not found or file missing.[/yellow]")

        print(f"\n--- Script Execution Finished: {end_time_main.strftime('%Y-%m-%d %H:%M:%S')} ---")
        sys.exit(exit_code)


# --- Entry Point ---
if __name__ == "__main__":
    # Ensure the script's directory is potentially added to path if needed,
    # though running as `python main.py` from root should generally work.
    # script_dir = Path(__file__).parent.resolve()
    # if str(script_dir) not in sys.path:
    #     sys.path.insert(0, str(script_dir))

    main()