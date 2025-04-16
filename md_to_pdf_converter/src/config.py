# src/config.py

# Standard ReportLab units and page sizes
from reportlab.lib.pagesizes import A4, LETTER, LEGAL
from reportlab.lib.units import inch

# --- Default Settings ---
DEFAULT_STYLE = "default"
DEFAULT_OUTPUT_DIR = "./output" # Relative to where main.py is run (project root)

# --- Page Size Definitions (in points) ---
# Used for validation and mapping format names to dimensions.
# ReportLab page sizes are defined as (width, height) tuples in points.
PAGE_SIZES = {
    'A4': A4,                           # (595.275590551181, 841.8897637795275)
    'LETTER': LETTER,                   # (612.0, 792.0)
    'LEGAL': LEGAL,                     # (612.0, 1008.0)
    'US_TRADE': (6 * inch, 9 * inch)    # (432.0, 648.0) - Common book size
    # Add other common sizes if needed, e.g.:
    # 'A5': (419.5275590551181, 595.275590551181),
    # 'B5': (498.8976377952756, 708.6614173228346)
}

# List of format keys supported by the --formats argument
# Used in main.py for validation and help text.
SUPPORTED_FORMATS = list(PAGE_SIZES.keys())

# --- Other Constants (Examples - adjust as needed) ---
# MAX_PARAGRAPH_LENGTH = 800 # Could be used by pdf_components to split long text
# DEFAULT_IMAGE_DPI = 300 # Could be used by image handler