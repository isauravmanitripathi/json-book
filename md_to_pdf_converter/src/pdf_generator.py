# src/pdf_generator.py

import os
import logging
from pathlib import Path
from datetime import datetime
import copy # For deep copying styles
import html # Import for escaping error messages

# ReportLab Imports
from reportlab.platypus import PageBreak, Spacer, Paragraph, SimpleDocTemplate, Table, TableStyle, Image, Preformatted # Import SimpleDocTemplate and others needed
from reportlab.graphics.shapes import Line, Drawing # For horizontal rule
from reportlab.lib.units import inch # For image/hr size
from reportlab.lib.pagesizes import A4 # Default base size for scaling calculation
from reportlab.lib.styles import getSampleStyleSheet # Basic default styles
from reportlab.lib import colors # For error message color

# Project Module Imports
from .style_loader import StyleLoader
from .markdown_parser import MarkdownParser
# BookTemplate is NOT used in this test version
# from .reportlab_helpers import BookTemplate
# Import the module containing component creation functions
from . import pdf_components # Still needed for _get_font_name etc. if used, though less critical for this test
# Import constants and page size definitions
from .config import PAGE_SIZES

logger = logging.getLogger(__name__)
BASE_STYLES = getSampleStyleSheet() # Use BASE_STYLES for fallback/test styles


class PDFGenerator:
    """
    Orchestrates the conversion of a folder of Markdown files into styled PDFs.
    Handles file validation, sorting, parsing, styling, multi-format output,
    and ReportLab document generation.
    """

    def __init__(self, input_folder, output_dir, style_name, formats, style_loader):
        """
        Initialize the PDF Generator.

        Args:
            input_folder (str): Path to the folder containing Markdown files.
            output_dir (str): Path to the directory where PDFs will be saved.
            style_name (str): The name of the style to use (from styles directory).
            formats (list): A list of strings representing desired output formats (e.g., ['A4', 'US_TRADE']).
            style_loader (StyleLoader): An initialized StyleLoader instance.
        """
        self.input_folder = Path(input_folder).resolve() # Use absolute path
        self.output_dir = Path(output_dir).resolve()
        self.style_name = style_name
        self.output_formats = formats # List of format names (strings)
        self.style_loader = style_loader # Use the pre-initialized loader
        self.markdown_parser = MarkdownParser() # Initialize the parser

        if not self.input_folder.is_dir():
            raise FileNotFoundError(f"Input folder not found: {self.input_folder}")

        self.output_dir.mkdir(parents=True, exist_ok=True) # Ensure output dir exists
        logger.info(f"PDFGenerator initialized for folder: {self.input_folder}")

    def generate(self):
        """
        Main method to generate the PDF(s) for all specified formats.
        Sorts files by modification date before processing.

        Returns:
            dict: A dictionary mapping format names (str) to the list of generated
                  PDF file paths (list of str). Returns an empty dict if generation fails
                  or no files are processed.
        """
        logger.info(f"Starting PDF generation process...")
        generated_files_map = {}

        try:
            # 1. Validate folder and get sorted list of Markdown files
            sorted_md_files = self._validate_and_sort_files()
            if not sorted_md_files:
                logger.warning(f"No valid Markdown files (.md) found in '{self.input_folder}'. No PDFs will be generated.")
                return {}

            logger.info(f"Found and sorted {len(sorted_md_files)} Markdown file(s) by modification date (oldest first).")

            # 2. Load the base style configuration using the provided loader
            # Still load style to get page size, margins etc.
            base_style_config = self.style_loader.load_style(self.style_name)
            if not base_style_config:
                 raise ValueError(f"Failed to load base style '{self.style_name}'.")
            logger.info(f"Loaded base style '{self.style_name}'. Font registration attempted.")

            # 3. Loop through each requested output format
            for fmt_key in self.output_formats:
                fmt = fmt_key.upper() # Use uppercase for internal consistency if needed
                logger.info(f"--- Generating format: {fmt_key} ---")
                try:
                    # 3a. Adjust style for the current format (mainly for page size/margins)
                    adjusted_style_config = self._adjust_style_for_format(base_style_config, fmt)

                    # 3b. Determine output filename
                    book_name_base = self.input_folder.name
                    output_filename = f"{book_name_base}_{self.style_name}_{fmt_key}.pdf"
                    output_path = self.output_dir / output_filename

                    # 3c. Generate the PDF for this specific format
                    # *** NOTE: This calls the version using SimpleDocTemplate ***
                    pdf_paths = self._generate_pdf_for_format(
                        sorted_md_files,
                        adjusted_style_config, # Pass adjusted style (for page size/margins)
                        fmt_key,
                        output_path
                    )
                    generated_files_map[fmt_key] = pdf_paths
                    logger.info(f"Successfully generated format {fmt_key} at: {output_path}")

                except Exception as format_error:
                    logger.error(f"Failed to generate format '{fmt_key}': {format_error}", exc_info=True)

        except Exception as e:
            logger.error(f"An critical error occurred during PDF generation: {e}", exc_info=True)
            return {}

        logger.info("PDF generation process completed.")
        return generated_files_map

    def _validate_and_sort_files(self):
        """
        Scans the input folder, validates files are exclusively Markdown,
        and sorts them by modification time (oldest first).
        """
        # (Keep this function as it was - no changes needed here)
        md_files = []
        has_other_files = False
        if not self.input_folder.exists():
             raise FileNotFoundError(f"Input folder does not exist: {self.input_folder}")
        logger.debug(f"Scanning folder: {self.input_folder}")
        for item in self.input_folder.iterdir():
            if item.is_file() and not item.name.startswith('.'):
                if item.suffix.lower() == '.md': md_files.append(item)
                else:
                    logger.warning(f"Non-markdown file found: {item.name}. Aborting operation.")
                    has_other_files = True; break
        if has_other_files: raise ValueError(f"Input folder '{self.input_folder.name}' must contain only Markdown (.md) files.")
        if not md_files: logger.warning(f"No Markdown files (.md) found in input folder: {self.input_folder}"); return []
        try: md_files.sort(key=lambda x: x.stat().st_mtime); logger.debug("Files sorted by modification time (oldest first).")
        except OSError as e: logger.error(f"Error accessing file stats for sorting: {e}"); raise OSError(f"Could not sort files by modification time: {e}")
        return md_files

    def _adjust_style_for_format(self, base_style_config, target_format_key):
        """Adjusts the base style configuration for the target output format (mainly for page size/margins)."""
        # (Keep this function as it was - no changes needed here)
        adjusted_style = copy.deepcopy(base_style_config)
        logger.debug(f"Adjusting style '{self.style_name}' for output format: {target_format_key}")
        page_config = adjusted_style.setdefault('page', {})
        original_margins = page_config.get('margins', {'left': 72, 'right': 72, 'top': 72, 'bottom': 72})
        original_size_name = base_style_config.get('page', {}).get('size', 'A4').upper()
        if original_size_name == 'CUSTOM':
            if 'width' not in base_style_config['page'] or 'height' not in base_style_config['page']: raise ValueError("Base style is 'CUSTOM' but lacks width/height definitions required for scaling.")
            original_width, original_height = base_style_config['page']['width'], base_style_config['page']['height']
        elif original_size_name in PAGE_SIZES: original_width, original_height = PAGE_SIZES[original_size_name]
        else: logger.warning(f"Unknown base page size '{original_size_name}' in style. Assuming A4."); original_width, original_height = PAGE_SIZES['A4']
        if target_format_key == 'CUSTOM':
             if 'width' not in page_config or 'height' not in page_config: raise ValueError(f"Output format is 'CUSTOM', but style lacks width/height.")
             target_width, target_height = page_config['width'], page_config['height']; page_config['size'] = 'CUSTOM'
        elif target_format_key in PAGE_SIZES:
             target_width, target_height = PAGE_SIZES[target_format_key]; page_config['size'] = target_format_key; page_config.pop('width', None); page_config.pop('height', None)
        else: raise ValueError(f"Invalid target format: {target_format_key}")
        width_scale = target_width / original_width if original_width else 1; height_scale = target_height / original_height if original_height else 1
        min_margin = 18
        adjusted_margins = {k: max(min_margin, int(original_margins.get(k, 72) * (width_scale if k in ('left', 'right') else height_scale))) for k in ['left', 'right', 'top', 'bottom']}
        page_config['margins'] = adjusted_margins
        # Scaling fonts is less relevant when using SimpleDocTemplate and basic styles, can be skipped for this test
        # a4_area = PAGE_SIZES['A4'][0] * PAGE_SIZES['A4'][1]; target_area = target_width * target_height; area_ratio = target_area / a4_area if a4_area else 1
        # if area_ratio < 0.7: scale_factor = max(0.8, min(width_scale, height_scale, 1.0)); # ... scale fonts ...
        return adjusted_style

    def _scale_style_elements_recursively(self, style_element, factor):
        """ Recursively scales numeric values associated with size/spacing keys. """
        # (Keep this function as it was - might not be used in this test, but no harm keeping it)
        keys_to_scale = ['font_size', 'leading', 'space_before', 'space_after','indent', 'first_line_indent', 'padding', 'padding_bottom','border_width']
        min_values = {'font_size': 7, 'leading': 8, 'space_before': 2, 'space_after': 2, 'indent': 0, 'first_line_indent': 0, 'padding': 1, 'padding_bottom': 1, 'border_width': 0.1}
        if isinstance(style_element, dict):
            for key, value in style_element.items():
                if key in keys_to_scale and isinstance(value, (int, float)):
                     min_val = min_values.get(key, 0); scaled_val = int(value * factor) if isinstance(value, int) else (value * factor)
                     style_element[key] = max(min_val, round(scaled_val, 1) if isinstance(scaled_val, float) else scaled_val)
                elif isinstance(value, (dict, list)): self._scale_style_elements_recursively(value, factor)
        elif isinstance(style_element, list):
            for item in style_element: self._scale_style_elements_recursively(item, factor)

    # --- METHOD USING SimpleDocTemplate and ACTUAL CONTENT ---
    def _generate_pdf_for_format(self, sorted_md_files, style_config, format_name, output_path):
        """
        Generates a single PDF file using SimpleDocTemplate and actual Markdown content.
        """
        logger.info(f"--- Initializing SimpleDocTemplate for {output_path} ---")

        # Get page size and margins from style_config for SimpleDocTemplate
        page_config = style_config.get('page', {})
        margins = page_config.get('margins', {'left': 72, 'right': 72, 'top': 72, 'bottom': 72})
        page_size_name = page_config.get('size', 'A4').upper()
        if page_size_name == 'CUSTOM' and 'width' in page_config and 'height' in page_config:
             page_size = (page_config['width'], page_config['height'])
        elif page_size_name in PAGE_SIZES:
             page_size = PAGE_SIZES[page_size_name]
        else:
             page_size = PAGE_SIZES['A4'] # Fallback

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=page_size,
            rightMargin=margins.get('right', 72),
            leftMargin=margins.get('left', 72),
            topMargin=margins.get('top', 72),
            bottomMargin=margins.get('bottom', 72)
        )

        story = []
        error_style = BASE_STYLES['Code']
        error_style.textColor = colors.red
        # fonts_config = style_config.get('fonts', {}) # Less critical for this test

        # --- Skip TOC placeholder logic ---
        logger.debug("Skipping TOC placeholder for SimpleDocTemplate.")

        # --- Process Actual Markdown Content ---
        logger.info("--- PROCESSING ACTUAL MARKDOWN CONTENT (using SimpleDocTemplate) ---")
        image_base_dir = self.input_folder
        total_flowables_added = 0

        for i, md_file_path in enumerate(sorted_md_files):
            chapter_number = i + 1
            clean_stem = md_file_path.stem.replace('_', ' ').replace('-', ' ')
            chapter_title = ' '.join(clean_stem.split()).title()
            logger.info(f"  Processing Chapter {chapter_number}: '{chapter_title}' ({md_file_path.name})")

            try:
                # Parse the Markdown file
                parsed_content_blocks = self.markdown_parser.parse_file(md_file_path)
                logger.debug(f"    Parsed {len(parsed_content_blocks)} blocks from {md_file_path.name}")

                # Add chapter title using a basic style
                story.append(Spacer(1, 12))
                story.append(Paragraph(f"Chapter {chapter_number}: {chapter_title}", BASE_STYLES['h1']))
                story.append(Spacer(1, 12))
                story_len_before_blocks = len(story)

                # Process content blocks within the chapter
                for block_index, block in enumerate(parsed_content_blocks):
                    block_type = block.get('type')

                    try:
                        flowable_to_add = None
                        is_list_of_flowables = False # Most components here return single flowable

                        # --- Convert parsed block to BASIC ReportLab Flowable(s) ---
                        if block_type == 'heading':
                            level = block.get('level')
                            text = block.get('text', '')
                            if not text: continue
                            if level == 2:
                                flowable_to_add = Paragraph(text, BASE_STYLES['h2'])
                            elif level >= 3 and level <= 6:
                                flowable_to_add = Paragraph(text, BASE_STYLES['h3']) # Use h3 for all lower levels for simplicity

                        elif block_type == 'paragraph':
                            text = block.get('text', '')
                            if text:
                                # Apply basic inline formatting before creating Paragraph
                                formatted_text = pdf_components._apply_inline_formatting(text)
                                flowable_to_add = Paragraph(formatted_text, BASE_STYLES['Normal'])

                        elif block_type == 'code':
                            content = block.get('content', '')
                            if content:
                                # Escape content for Preformatted
                                escaped_content = html.escape(content)
                                flowable_to_add = Preformatted(escaped_content, BASE_STYLES['Code'])

                        elif block_type == 'table':
                             headers = block.get('headers', [])
                             rows = block.get('rows', [])
                             if headers or rows:
                                 # Create basic table data (apply basic formatting to cell text)
                                 data = []
                                 if headers:
                                     data.append([pdf_components._apply_inline_formatting(h) for h in headers])
                                 for row in rows:
                                     data.append([pdf_components._apply_inline_formatting(cell) for cell in row])

                                 if data:
                                    ts = TableStyle([
                                        ('GRID', (0,0), (-1,-1), 1, colors.grey),
                                        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey) # Simple header background
                                        ])
                                    flowable_to_add = Table(data, style=ts, hAlign='LEFT') # Use Table, align left

                        elif block_type == 'image':
                            path = block.get('path', '')
                            alt_text = block.get('alt', '')
                            if path:
                                try:
                                    img_path_obj = Path(path)
                                    if not img_path_obj.is_absolute():
                                        full_image_path = image_base_dir.resolve() / img_path_obj
                                    else:
                                        full_image_path = img_path_obj

                                    if full_image_path.is_file():
                                        # Create image, scale slightly if needed
                                        img_flowable = Image(str(full_image_path))
                                        img_width, img_height = img_flowable.drawWidth, img_flowable.drawHeight
                                        available_width = doc.width # Use SimpleDocTemplate's width
                                        if img_width > available_width:
                                            ratio = available_width / img_width
                                            img_flowable.drawWidth = available_width
                                            img_flowable.drawHeight = img_height * ratio
                                        img_flowable.hAlign = 'CENTER'
                                        flowable_to_add = [img_flowable] # Put in a list to use extend
                                        # Add caption if alt text exists
                                        if alt_text:
                                            caption_style = BASE_STYLES['Italic']
                                            caption_style.alignment = 1 # Center
                                            flowable_to_add.append(Spacer(1, 4))
                                            flowable_to_add.append(Paragraph(alt_text, caption_style))
                                        is_list_of_flowables = True # Use extend because we have a list now
                                    else:
                                        logger.warning(f"Image not found: {full_image_path}")
                                        flowable_to_add = Paragraph(f"[Image not found: {path}]", error_style)
                                except Exception as img_err:
                                    logger.error(f"Error loading image '{path}': {img_err}")
                                    flowable_to_add = Paragraph(f"[Error loading image: {path}]", error_style)

                        elif block_type == 'horizontal_rule':
                             hr_drawing = Drawing(doc.width, 1) # Use doc width
                             hr_drawing.add(Line(0, 0, doc.width, 0))
                             flowable_to_add = hr_drawing # Drawing is a single flowable

                        # --- Append/Extend the story + Logging ---
                        if flowable_to_add is not None:
                            if is_list_of_flowables:
                                story.extend(flowable_to_add)
                                logger.debug(f"        Block {block_index} ({block_type}): Extended story with {len(flowable_to_add)} flowables (Types: {[type(f).__name__ for f in flowable_to_add]})")
                                total_flowables_added += len(flowable_to_add)
                            else:
                                story.append(flowable_to_add)
                                logger.debug(f"        Block {block_index} ({block_type}): Appended story with flowable: {type(flowable_to_add).__name__}")
                                total_flowables_added += 1
                        elif block_type: # Log only if known type wasn't handled
                                logger.warning(f"      Skipping unsupported block type: {block_type}")

                    except Exception as block_error:
                        logger.error(f"      Error processing block {block_index} ({block_type or 'Unknown'}) in {md_file_path.name}: {block_error}", exc_info=True)
                        escaped_block_error_msg = html.escape(str(block_error))
                        story.append(Paragraph(f"<i>[Error processing block #{block_index} ({block_type}): {escaped_block_error_msg}]</i>", error_style))

                logger.debug(f"    Finished processing blocks for {md_file_path.name}. Story length: {len(story)} (added {len(story) - story_len_before_blocks} flowables)")
                story.append(PageBreak()) # Page break after each file/chapter for clarity

            except Exception as file_error:
                 logger.error(f"  Failed to process file {md_file_path.name}: {file_error}", exc_info=True)
                 escaped_error_msg = html.escape(str(file_error))
                 story.append(Paragraph(f"<b>[Critical Error processing chapter file {md_file_path.name}: {escaped_error_msg}]</b>", error_style))
                 story.append(PageBreak())

        # --- Build the PDF Document using SimpleDocTemplate ---
        logger.info(f"Total flowables added to story across all files: {total_flowables_added}")
        logger.info(f"Final story contains {len(story)} flowables before building.")
        if len(story) < 50:
             for i, f in enumerate(story[:50]):
                 # Check if flowable is Paragraph to avoid errors with other types like Drawing
                 text_preview = ""
                 if hasattr(f, 'text'):
                     text_preview = f.text[:100]
                 elif isinstance(f, Spacer):
                     text_preview = f"Space: {f.height}"
                 elif isinstance(f, Image):
                     text_preview = f"Image: {f.filename}"
                 # Add more types as needed
                 logger.debug(f"  Final Story item {i}: {type(f).__name__} - {text_preview}...")


        logger.info(f"Building PDF document using SimpleDocTemplate: {output_path}...")
        try:
            # SimpleDocTemplate uses 'build'
            doc.build(story)
            logger.info("--- Successfully built PDF with ACTUAL content using SimpleDocTemplate. ---")
        except Exception as build_error:
             logger.error(f"--- Critical error during SimpleDocTemplate build process for {output_path}: {build_error} ---", exc_info=True)
             raise

        return [str(output_path)]