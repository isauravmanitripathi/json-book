
# Markdown to PDF Converter

This project provides a command-line utility to convert a folder containing Markdown (`.md`) files into one or more styled PDF documents. It processes the Markdown files in order of modification date, applies styling based on a JSON configuration file, and generates PDFs suitable for creating books or reports.

## Features

* **Markdown Processing:** Parses standard Markdown syntax, including fenced code blocks, tables, headings, paragraphs, and images.
* **Custom Styling:** Uses JSON files (located in the `styles/` directory) to define page layout (size, margins), fonts, colors, spacing for various elements (headings, paragraphs, code blocks, etc.).
* **Font Handling:** Supports standard PDF fonts and allows embedding custom TrueType Fonts (`.ttf`) defined in the style configuration. Requires fonts to be placed in the `fonts/` directory.
* **Table of Contents (TOC):** Automatically generates a TOC based on Chapter (Filename) and Section (H2) headings.
* **Page Numbering:** Adds customizable page numbers to the generated PDF.
* **Multiple Output Formats:** Can generate PDFs in various standard page sizes (A4, Letter, US_Trade, etc.) simultaneously based on command-line arguments. Style elements like margins and font sizes can be proportionally scaled for different output formats.
* **File Ordering:** Processes Markdown files within the input folder based on their last modification time (oldest first), suitable for chapter ordering.

## Project Structure

```
md_to_pdf_converter/
├── styles/                 # Contains JSON style configuration files
│   └── default.json        # Default style configuration
├── fonts/                  # Place custom .ttf font files here
├── output/                 # Default directory for generated PDFs
│   └── ...                 # Generated PDF files appear here
├── src/                    # Source code for the converter
│   ├── __init__.py         # Makes 'src' a Python package
│   ├── config.py           # Defines constants and page size mappings
│   ├── style_loader.py     # Loads styles and registers fonts
│   ├── markdown_parser.py  # Parses Markdown files
│   ├── pdf_components.py   # Creates ReportLab flowables from parsed content
│   ├── reportlab_helpers.py# Custom ReportLab Template and Canvas classes
│   └── pdf_generator.py    # Main class orchestrating the PDF generation
├── main.py                 # Main command-line entry point
├── requirements.txt        # (Recommended) List of dependencies
└── txt-gen.py              # Utility script to combine code (for sharing/debugging)
```

## File Breakdown

### `main.py`

* **Purpose:** The main script executed to run the converter.
* **Functionality:**
    * Parses command-line arguments using `argparse` (`input_folder`, `--style`, `--output`, `--formats`).
    * Performs basic input validation (checks if input folder exists).
    * Initializes the `StyleLoader`.
    * Validates the selected style and output formats against configuration.
    * Ensures the output directory exists.
    * Initializes and runs the `PDFGenerator`.
    * Prints success or error messages.

### `src/__init__.py`

* **Purpose:** Makes the `src` directory a Python package, allowing relative imports within the source code (e.g., `from .config import ...`).

### `src/config.py`

* **Purpose:** Defines project-wide constants and configurations.
* **Key Variables:**
    * `DEFAULT_STYLE`: Default style name ("default").
    * `DEFAULT_OUTPUT_DIR`: Default output directory ("./output").
    * `PAGE_SIZES`: Dictionary mapping format names (e.g., 'A4', 'LETTER', 'US_TRADE') to ReportLab page size tuples (width, height in points).
    * `SUPPORTED_FORMATS`: List derived from `PAGE_SIZES` keys for validation.

### `src/style_loader.py`

* **Purpose:** Handles loading style configurations and registering necessary fonts.
* **`StyleLoader` Class:**
    * `__init__(styles_dir, fonts_dir)`: Initializes with paths to styles and fonts directories.
    * `list_styles()`: Finds available `.json` style files in the `styles_dir`.
    * `load_style(style_name)`: Reads the specified JSON style file, validates basic structure, and calls `_register_fonts`. Returns the style configuration dictionary.
    * `_register_fonts(fonts_config)`: Iterates through the `fonts` section of the style config. Registers custom TTF fonts (and their bold/italic variants if defined) using `reportlab.pdfbase.pdfmetrics.registerFont` and `reportlab.pdfbase.ttfonts.TTFont`. It also attempts to set up font family mappings using `reportlab.lib.fonts.addMapping` for proper bold/italic switching within ReportLab paragraphs. Skips standard PDF fonts.
    * `_register_single_font(registration_name, font_path_obj)`: Helper to register a single TTF file, checking if it exists and handling potential `TTFError` exceptions.

### `src/markdown_parser.py`

* **Purpose:** Parses Markdown files into a structured representation.
* **`MarkdownParser` Class:**
    * `__init__()`: Initializes the `markdown` library with extensions (`fenced_code`, `tables`, `nl2br`, `sane_lists`).
    * `parse_file(md_file_path)`: Reads a Markdown file, converts it to HTML using the `markdown` library, and then parses the HTML using `BeautifulSoup`. Calls `_extract_blocks_from_soup` to get structured data.
    * `_extract_blocks_from_soup(soup)`: Iterates through the parsed HTML (`BeautifulSoup` object). Identifies elements like headings (`h2`-`h6`), paragraphs (`p`), code blocks (`pre`/`code`), tables (`table`), images (`img`), and horizontal rules (`hr`). Converts these into a list of dictionaries, each representing a content block with its type and relevant data (e.g., `{'type': 'heading', 'level': 2, 'text': '...'}`). Handles basic inline tags (`<b>`, `<i>`, `<br>`) within paragraphs and table cells.

### `src/pdf_components.py`

* **Purpose:** Contains functions that convert the structured blocks (from `MarkdownParser`) into ReportLab `Flowable` objects.
* **Helper Functions:**
    * `_parse_color()`: Converts color strings (hex, names) to ReportLab color objects.
    * `_get_alignment()`: Converts alignment strings ('left', 'center', etc.) to ReportLab constants (`TA_LEFT`, `TA_CENTER`).
    * `_get_font_name()`: Resolves logical font names (defined in the style's `fonts` section) to the actual font names registered with ReportLab (e.g., resolves 'body' to 'Times-Roman'). **Crucial for linking style definitions to registered fonts.**
    * `_apply_inline_formatting()`: Converts basic HTML-like tags (`<b>`, `<i>`, `<br/>`) in text content into ReportLab's paragraph XML tags.
* **Component Creation Functions:** (e.g., `create_toc_placeholder`, `create_chapter_heading`, `create_section_heading`, `create_other_heading`, `create_paragraph`, `create_code_block`, `create_table`, `create_image`, `create_horizontal_rule`)
    * Each function takes a block dictionary (or specific data like title/text) and the relevant style configuration section.
    * They use the helper functions to determine fonts, colors, sizes, alignment, etc., based on the style config.
    * They instantiate and return ReportLab `Flowable` objects (`Paragraph`, `Spacer`, `Image`, `Table`, `Preformatted`, `Drawing`) configured according to the style.
    * Headings intended for the TOC (`create_chapter_heading`, `create_section_heading`) are given specific `ParagraphStyle` names (`ChapterHeadingStyle`, `SectionHeadingStyle`) which are recognized by the `BookTemplate`.

### `src/reportlab_helpers.py`

* **Purpose:** Defines custom ReportLab classes for enhanced functionality.
* **`PageNumCanvas` Class:**
    * Inherits from `reportlab.pdfgen.canvas.Canvas`.
    * Overrides `showPage` to save canvas state before starting a new page.
    * Overrides `save` to iterate through saved page states *before* the final save, calling `draw_page_number` for each page if enabled in the style.
    * `draw_page_number()`: Draws the page number string onto the canvas at the position and with the style specified in the `page_numbers` section of the style config.
* **`BookTemplate` Class:**
    * Inherits from `reportlab.platypus.BaseDocTemplate`.
    * `__init__()`: Sets up page size and margins based on the loaded `style_config`. Creates the main content `Frame`. Initializes the ReportLab `TableOfContents` object. Sets the `canvasmaker` attribute to use `PageNumCanvas`. Calls `_configure_toc_styles`.
    * `_configure_toc_styles()`: Creates `ParagraphStyle` objects for different TOC levels based on the `table_of_contents.level_styles` section in the style config and assigns them to the `self.toc.levelStyles` list.
    * `afterFlowable(flowable)`: Called by ReportLab after drawing each flowable. Checks if the flowable's style name matches those used for chapter or section headings (`ChapterHeadingStyle`, `SectionHeadingStyle`). If it matches, it notifies the `self.toc` object to add an entry using `self.notify('TOCEntry', (level, text, pageNum))`.

### `src/pdf_generator.py`

* **Purpose:** Orchestrates the entire conversion process from Markdown files to PDF.
* **`PDFGenerator` Class:**
    * `__init__()`: Initializes paths, style name, formats, `StyleLoader`, and `MarkdownParser`.
    * `generate()`: The main public method. Calls `_validate_and_sort_files`, loads the base style, loops through requested formats, calls `_adjust_style_for_format` for each, and then calls `_generate_pdf_for_format` to create the PDF for that format. Returns a dictionary mapping format names to output file paths.
    * `_validate_and_sort_files()`: Checks the input folder, ensures only `.md` files are present, and sorts them by modification time.
    * `_adjust_style_for_format()`: Creates a copy of the base style and adjusts page size, margins, and potentially scales font sizes/spacing based on the target format dimensions relative to the original style's page size.
    * `_generate_pdf_for_format()`:
        * Instantiates the `BookTemplate` (or `SimpleDocTemplate` during debugging) with the adjusted style config.
        * Initializes an empty `story` list.
        * Adds the TOC placeholder.
        * Iterates through the sorted Markdown file paths.
        * For each file:
            * Determines chapter title from filename.
            * Calls `self.markdown_parser.parse_file()` to get structured blocks.
            * Adds the chapter heading flowable.
            * Loops through the parsed content blocks.
            * Calls the appropriate function from `pdf_components` based on the block type to create flowables.
            * Appends/extends the `story` list with the created flowables.
        * Calls `doc.multiBuild(story)` (or `doc.build(story)` for `SimpleDocTemplate`) to render the PDF.

### `txt-gen.py`

* **Purpose:** A utility script to gather all Python code from the project (excluding specified files/directories) into a single `combined_python_code.txt` file. Useful for sharing the codebase or feeding it into analysis tools.

## Styling

PDF appearance is controlled by JSON files in the `styles/` directory (e.g., `default.json`). Key sections include:

* `page`: Defines `size` (e.g., "A4", "LETTER", "CUSTOM") and `margins` (left, right, top, bottom in points). Custom size requires `width` and `height` keys under `page`.
* `fonts`: Maps logical font names (e.g., "body", "heading", "code") used in other style sections to actual ReportLab font names (e.g., "Times-Roman", "Helvetica-Bold") or custom font definitions (see `StyleLoader`).
* `page_numbers`: Controls visibility (`show`), format (`format` string), `position`, `font_name`, `font_size`, `color`, and starting page (`start_page`).
* `table_of_contents`: Defines the TOC `title` style and `level_styles` (list of styles for different heading levels in the TOC).
* `chapter_heading`, `section_heading`, `heading_h3` (etc.): Define font, size, color, alignment, spacing for different heading levels.
* `paragraph`: Defines default body text style (font, size, color, leading, alignment, spacing, indentation).
* `code_block`: Defines styling for fenced code blocks (font, size, background, border, padding).
* `table`: Defines styling for table `header` and `cell` (font, size, colors, alignment, padding) and `grid` lines.
* `image`: Defines spacing around images and `caption` styling.

**Custom Fonts:** To use custom fonts:

1.  Place `.ttf` font files (including bold/italic variants if available) into the `fonts/` directory.
2.  Define the font in your style JSON under the `fonts` section. For example:
    ```json
    "fonts": {
        "body": "Times-Roman", // Standard font
        "my_custom_sans": {   // Custom font family
            "normal": "MySans-Regular.ttf",
            "bold": "MySans-Bold.ttf",
            "italic": "MySans-Italic.ttf",
            "bold_italic": "MySans-BoldItalic.ttf"
        }
    }
    ```
3.  Reference the logical name (e.g., `"my_custom_sans"`) in other style sections like `paragraph` or `chapter_heading`.

## Prerequisites

* Python 3.6+
* Required Python libraries:
    * `reportlab`: For PDF generation.
    * `markdown`: For parsing Markdown files.
    * `beautifulsoup4`: For parsing the HTML output of the `markdown` library.
    * `Pillow`: (Optional but recommended) For more robust image handling (verification, dimension reading) by ReportLab.

## Setup

1.  **Get the Code:** Clone the repository or download the source files.
2.  **Navigate to Directory:** Open your terminal or command prompt and navigate to the project's root directory (`md_to_pdf_converter/`).
3.  **Create Virtual Environment:** It's highly recommended to use a virtual environment:
    ```bash
    python3 -m venv .venv
    ```
4.  **Activate Virtual Environment:**
    * macOS/Linux: `source .venv/bin/activate`
    * Windows: `.venv\Scripts\activate`
5.  **Install Dependencies:**
    ```bash
    pip install reportlab markdown beautifulsoup4 Pillow
    ```
    *(If a `requirements.txt` file is provided, use `pip install -r requirements.txt` instead).*
6.  **Add Fonts (Optional):** If you plan to use custom fonts defined in your style file, place the corresponding `.ttf` files inside the `fonts/` directory. Create the directory if it doesn't exist.
7.  **Check Styles:** Ensure the `styles/` directory exists and contains at least `default.json` (or your desired custom style file).

## How to Run

Execute the `main.py` script from your activated virtual environment in the project's root directory.

**Basic Usage:**

```bash
python3 main.py <path_to_markdown_folder>
```

* Replace `<path_to_markdown_folder>` with the actual path to the folder containing *only* your `.md` files.

**Examples:**

* Generate PDF from `my_book_chapters/` using the default style and outputting to `output/`:
    ```bash
    python3 main.py my_book_chapters/
    ```
    *(Output: `output/my_book_chapters_default_A4.pdf`)*

* Generate PDF using a custom style named `technical`:
    ```bash
    python3 main.py my_book_chapters/ --style technical
    ```
    *(Requires `styles/technical.json` to exist. Output: `output/my_book_chapters_technical_A4.pdf`)*

* Generate PDF and save it to a specific directory `build/`:
    ```bash
    python3 main.py my_book_chapters/ --output build/
    ```
    *(Output: `build/my_book_chapters_default_A4.pdf`)*

* Generate PDFs in US Trade and A4 formats using the 'modern' style:
    ```bash
    python3 main.py my_book_chapters/ --style modern --formats US_TRADE,A4
    ```
    *(Output: `output/my_book_chapters_modern_US_TRADE.pdf` and `output/my_book_chapters_modern_A4.pdf`)*

**Command-Line Arguments:**

* `input_folder` (Required): Path to the folder containing `.md` files.
* `--style` or `-s`: Name of the style file (without `.json`) from the `styles` directory. Default: `default`.
* `--output` or `-o`: Directory to save the generated PDF(s). Default: `./output`.
* `--formats` or `-f`: Comma-separated list of output formats (e.g., `A4,US_TRADE,LETTER`). See `src/config.py` for supported keys. Default: `A4`.
