#!/usr/bin/env python3

import argparse
import os
import sys
from datetime import datetime

# --- Import project modules using absolute paths from 'src' ---
# This assumes 'main.py' is in the root 'md_to_pdf_converter' directory
# and source code is in 'md_to_pdf_converter/src/'
try:
    # Explicitly import from the 'src' package
    from src.pdf_generator import PDFGenerator
    from src.style_loader import StyleLoader
    from src.config import DEFAULT_STYLE, DEFAULT_OUTPUT_DIR, PAGE_SIZES # Assuming PAGE_SIZES is defined in config.py
except ImportError as e:
    print(f"Error importing project modules: {e}", file=sys.stderr)
    print("Please ensure this script is run from the project root directory ('md_to_pdf_converter')", file=sys.stderr)
    print(f"Check that the 'src' directory exists relative to this script and contains __init__.py and other modules.", file=sys.stderr)
    sys.exit(1)
except ModuleNotFoundError as e:
    # More specific error for Python 3.6+
    print(f"Error: Could not find required module: {e}", file=sys.stderr)
    print("Ensure all source files (pdf_generator.py, style_loader.py, config.py) exist in the 'src' directory.")
    sys.exit(1)

def main():
    """Main entry point for the Markdown to PDF converter."""

    # Define supported formats based on config for help message
    try:
        supported_formats_str = ', '.join(PAGE_SIZES.keys())
    except NameError: # Fallback if config import failed partially
        supported_formats_str = "A4, LETTER, LEGAL, US_TRADE (Check config.py)"


    parser = argparse.ArgumentParser(
        description="Convert a folder of Markdown files into a styled PDF book, ordered by modification date.",
        formatter_class=argparse.RawTextHelpFormatter # Preserves formatting in help text
    )

    parser.add_argument(
        "input_folder",
        help="Path to the folder containing ONLY Markdown (.md) files."
    )
    parser.add_argument(
        "--style", "-s",
        default=DEFAULT_STYLE,
        help=f"Name of the style file (without .json) from the 'styles' directory.\nDefault: {DEFAULT_STYLE}"
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save the generated PDF(s).\nDefault: {DEFAULT_OUTPUT_DIR}"
    )
    parser.add_argument(
        "--formats", "-f",
        default="A4", # Default to generating only A4
        help="Comma-separated list of output formats (e.g., A4,US_Trade,LETTER).\n"
             f"Supported formats: {supported_formats_str}\n"
             "Default: A4"
    )
    # Future arguments could include: --verbose, --log-file, --title, --author

    args = parser.parse_args()

    # --- Basic Input Validation ---
    if not os.path.isdir(args.input_folder):
        print(f"Error: Input folder not found or is not a directory: {args.input_folder}", file=sys.stderr)
        sys.exit(1)

    # --- Initialize Style Loader and Validate Style ---
    try:
        project_root = os.path.dirname(os.path.abspath(__file__))
        styles_dir = os.path.join(project_root, 'styles')
        fonts_dir = os.path.join(project_root, 'fonts')

        if not os.path.isdir(styles_dir):
             print(f"Warning: 'styles' directory not found at {styles_dir}. Will attempt to use default style '{DEFAULT_STYLE}'.", file=sys.stderr)
             # StyleLoader will raise error later if default is also missing

        style_loader = StyleLoader(styles_dir=styles_dir, fonts_dir=fonts_dir)
        available_styles = style_loader.list_styles()

        # Check if default style exists if no styles found, otherwise error
        if not available_styles and args.style == DEFAULT_STYLE:
             print(f"Warning: No styles found in '{styles_dir}'. Attempting to proceed with default style logic within StyleLoader.", file=sys.stderr)
        elif not available_styles:
             print(f"Error: No style files found in {styles_dir}. Cannot proceed.", file=sys.stderr)
             sys.exit(1)
        elif args.style not in available_styles:
             # Check case-insensitively? For now, exact match.
             print(f"Error: Style '{args.style}' not found in {styles_dir}.", file=sys.stderr)
             print(f"Available styles: {', '.join(available_styles)}", file=sys.stderr)
             sys.exit(1)

    except Exception as e:
         print(f"Error initializing styles: {e}", file=sys.stderr)
         import traceback; traceback.print_exc() # Show traceback for init errors
         sys.exit(1)

    # --- Parse and Validate Formats ---
    try:
        # Convert format names to uppercase for consistent checking against PAGE_SIZES keys
        output_formats = [fmt.strip().upper() for fmt in args.formats.split(',') if fmt.strip()]
        if not output_formats:
            raise ValueError("No valid formats specified in --formats argument.")

        # Validate formats against config keys (PAGE_SIZES)
        valid_config_formats = PAGE_SIZES.keys()
        for fmt in output_formats:
            # Allow "CUSTOM" format conceptually, but its validity depends on the chosen style file
            if fmt not in valid_config_formats and fmt != "CUSTOM":
                 raise ValueError(f"Unsupported format: '{fmt}'. Supported from config: {supported_formats_str}")
    except Exception as e:
        print(f"Error parsing --formats argument: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Ensure output directory exists ---
    try:
        os.makedirs(args.output, exist_ok=True)
    except OSError as e:
        print(f"Error creating output directory '{args.output}': {e}", file=sys.stderr)
        sys.exit(1)

    # --- Run PDF Generation ---
    print(f"Starting PDF generation...")
    print(f"  Input Folder: {os.path.abspath(args.input_folder)}")
    print(f"  Style: {args.style}")
    print(f"  Output Directory: {os.path.abspath(args.output)}")
    print(f"  Formats: {', '.join(output_formats)}")

    start_time = datetime.now()

    try:
        # Pass the already initialized style_loader to the generator
        generator = PDFGenerator(
            input_folder=args.input_folder,
            output_dir=args.output,
            style_name=args.style,
            formats=output_formats, # Pass the list of validated, uppercase format names
            style_loader=style_loader
        )
        # The generate method handles loading style, validation, sorting, parsing, building
        generated_files_map = generator.generate() # Expecting dict: {'FORMAT': [path1, path2...]}

        if not generated_files_map:
            print("\nPDF generation finished, but no files map was returned. Check logs or input.", file=sys.stderr)
        else:
            print("\nPDF Generation Successful!")
            for fmt, path_or_list in generated_files_map.items():
                 if isinstance(path_or_list, list): # Handle multi-part output for a format
                      print(f"  - Format '{fmt}':")
                      for path in path_or_list:
                           print(f"    - {os.path.relpath(path)}") # Show relative path for cleaner output
                 else: # Should technically always be a list now, but handle just in case
                      print(f"  - Format '{fmt}': {os.path.relpath(path_or_list)}")

    except Exception as e:
        print(f"\n--- PDF Generation Failed ---", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        # Uncomment the following line for a full traceback during development
        import traceback; traceback.print_exc()
        sys.exit(1)

    end_time = datetime.now()
    duration = end_time - start_time
    print(f"\nTotal time: {duration}")

if __name__ == "__main__":
    main()