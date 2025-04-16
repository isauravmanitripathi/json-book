# src/reportlab_helpers.py

import logging
from reportlab.platypus import Frame, PageTemplate, BaseDocTemplate
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

# Assuming config.py defines PAGE_SIZES dictionary
try:
    from .config import PAGE_SIZES
except ImportError:
    # Fallback if run standalone or config not found (shouldn't happen in normal use)
    from reportlab.lib.pagesizes import A4
    PAGE_SIZES = {'A4': A4}
    print("Warning: Could not import PAGE_SIZES from config.py. Using A4 default.", file=sys.stderr)


logger = logging.getLogger(__name__)
BASE_STYLES = getSampleStyleSheet() # For fallback styles


# --- Custom Canvas for Page Numbers ---

class PageNumCanvas(canvas.Canvas):
    """
    Custom canvas class to automatically draw page numbers based on style settings.
    It collects page states and draws numbers during the final save phase.
    """
    def __init__(self, *args, **kwargs):
        # Pop custom kwarg before passing to parent
        self.page_number_settings = kwargs.pop('page_number_settings', {})
        self.fonts_config_ref = kwargs.pop('fonts_config_ref', {}) # Pass font mapping
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        logger.debug("PageNumCanvas initialized.")

    def showPage(self):
        """Overrides showPage to save the state of the canvas."""
        # Capture the state that might be modified page-to-page or needed for drawing
        # Note: Capturing __dict__ can be memory intensive if canvas object grows large.
        # Be selective if performance issues arise.
        state_to_save = {
            '_pageNumber': self._pageNumber,
            '_pagesize': self._pagesize,
            # Add other relevant state attributes if needed
        }
        self._saved_page_states.append(state_to_save)
        self._startPage() # Start the new page clean
        logger.debug(f"Canvas state saved for page {len(self._saved_page_states)}")


    def save(self):
        """Overrides save to draw page numbers on all saved pages before final save."""
        num_pages = len(self._saved_page_states)
        logger.info(f"Canvas save() called. Processing {num_pages} pages for numbering.")

        # Check if page numbering is enabled
        show_page_numbers = self.page_number_settings.get('show', True)
        if not show_page_numbers:
             logger.info("Page numbering disabled in style settings.")
             # Need to render pages properly before final save even without numbers
             for state in self._saved_page_states:
                 # Minimal state restoration needed just to call showPage correctly
                 self._pageNumber = state['_pageNumber']
                 self._pagesize = state['_pagesize']
                 super().showPage() # Call parent showPage to finalize page
             super().save() # Call parent save
             return

        # Draw page numbers if enabled
        start_page = self.page_number_settings.get('start_page', 1) # Page where numbering starts

        for i, state in enumerate(self._saved_page_states):
            # Restore necessary state attributes for drawing on this specific page
            self._pageNumber = state['_pageNumber']
            self._pagesize = state['_pagesize']
            current_page_num = i + 1 # Page index starts at 0, actual page num is +1

            if current_page_num >= start_page:
                try:
                    # Pass total pages and current page number
                    self.draw_page_number(num_pages, current_page_num)
                    logger.debug(f"Drew page number on page {current_page_num}")
                except Exception as e:
                     logger.error(f"Error drawing page number on page {current_page_num}: {e}")

            super().showPage() # Call parent showPage to finalize each page with numbers drawn

        logger.info("Finalizing PDF save.")
        super().save() # Call parent save to write the PDF file

    def draw_page_number(self, total_pages, current_page_num):
        """Draws the page number string on the current page."""
        # Use helper from pdf_components if available, otherwise local fallback
        try:
            from .pdf_components import _parse_color, _get_font_name
        except ImportError:
            # Basic fallback color parsing if component helper unavailable
            def _parse_color(color_value, default_color=colors.black):
                 if isinstance(color_value, str) and color_value.startswith('#'):
                      try: return colors.HexColor(color_value)
                      except: return default_color
                 return default_color
            def _get_font_name(lname, fconf, default): return lname or default

        settings = self.page_number_settings # Use stored settings

        # Get style attributes with defaults
        format_string = settings.get('format', 'Page {current}')
        logical_font_name = settings.get('font_name', 'Helvetica') # Logical name from style
        font_size = settings.get('font_size', 9)
        color_str = settings.get('color', '#555555')
        position = settings.get('position', 'bottom-center')

        # Format the page number text using total pages and current page number
        page_num_text = format_string.format(current=current_page_num, total=total_pages)

        # --- Set canvas state ---
        self.saveState() # Save current canvas state
        try:
            # Get the actual registered font name
            actual_font_name = _get_font_name(logical_font_name, self.fonts_config_ref, 'Helvetica')
            self.setFont(actual_font_name, font_size)
            self.setFillColor(_parse_color(color_str, default_color=colors.darkgrey))
            logger.debug(f"PageNum: Font='{actual_font_name}', Size={font_size}, Color='{color_str}'")
        except Exception as e:
            logger.error(f"Error setting font/color for page number: {e}. Using defaults.")
            self.setFillColor(colors.darkgrey)
            self.setFont('Helvetica', 9)


        # --- Calculate position ---
        page_width, page_height = self._pagesize
        # Use fixed margins for page numbers, could be made configurable in style
        margin_x = 0.5 * inch
        margin_y = 0.5 * inch

        # Position mapping
        if 'bottom' in position:
            y = margin_y
        elif 'top' in position:
            y = page_height - margin_y - font_size * 0.8 # Adjust y for top alignment
        else: # Default to bottom
            y = margin_y

        if 'center' in position:
            self.drawCentredString(page_width / 2.0, y, page_num_text)
        elif 'right' in position:
            self.drawRightString(page_width - margin_x, y, page_num_text)
        elif 'left' in position:
            self.drawString(margin_x, y, page_num_text)
        else: # Default to bottom-center if position is unknown
            logger.warning(f"Unknown page number position '{position}'. Defaulting to bottom-center.")
            self.drawCentredString(page_width / 2.0, margin_y, page_num_text)

        self.restoreState() # Restore canvas state


# --- Custom Document Template ---

class BookTemplate(BaseDocTemplate):
    """
    Custom document template for book layouts with Table of Contents support.
    Initializes page size, margins, frames, and TOC based on style config.
    Uses a custom canvas for page numbering.
    """
    def __init__(self, filename, **kwargs):
        # Extract style config, expecting it to be passed
        self.style_config = kwargs.pop('style_config', {})
        if not self.style_config:
            logger.warning("BookTemplate initialized without style_config. Using defaults.")

        page_config = self.style_config.get('page', {})
        margins = page_config.get('margins', {'left': 72, 'right': 72, 'top': 72, 'bottom': 72})
        fonts_config = self.style_config.get('fonts', {}) # Needed for TOC and PageNumCanvas

        # --- Determine Page Size ---
        page_size_name = page_config.get('size', 'A4').upper()
        if page_size_name == 'CUSTOM':
            if 'width' not in page_config or 'height' not in page_config:
                logger.error("Page size 'CUSTOM' specified in style but width/height missing. Falling back to A4.")
                self.pagesize = PAGE_SIZES['A4']
            else:
                self.pagesize = (page_config['width'], page_config['height'])
        elif page_size_name in PAGE_SIZES:
            self.pagesize = PAGE_SIZES[page_size_name]
        else:
            logger.warning(f"Unknown page size '{page_size_name}' in style. Falling back to A4.")
            self.pagesize = PAGE_SIZES['A4']

        # Initialize BaseDocTemplate with determined size and margins
        # We'll set canvasmaker later
        super().__init__(
            filename,
            pagesize=self.pagesize,
            leftMargin=margins.get('left', 72),
            rightMargin=margins.get('right', 72),
            topMargin=margins.get('top', 72),
            bottomMargin=margins.get('bottom', 72),
            **kwargs
        )

        # --- Setup Frames and Page Templates ---
        # Single frame spanning the margins for main content
        main_frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width, # BaseDocTemplate calculates width based on pagesize and margins
            self.height, # BaseDocTemplate calculates height
            id='main_frame',
            leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0
        )
        # Create a basic PageTemplate using the frame
        # The onPage function is a placeholder, could be used for static headers/footers
        main_page_template = PageTemplate(id='main', frames=[main_frame])
        self.addPageTemplates([main_page_template])

        # --- Initialize Table of Contents ---
        self.toc = TableOfContents()
        # Configure TOC styles based on style_config
        self._configure_toc_styles()

        # --- Set Custom Canvas Maker ---
        page_num_settings = self.style_config.get('page_numbers', {})
        # Pass settings needed by PageNumCanvas AND the font mapping
        self._custom_canvasmaker = lambda *args, **kw: PageNumCanvas(
             *args, page_number_settings=page_num_settings, fonts_config_ref=fonts_config, **kw
        )
        # Override the default canvasmaker used by build/multiBuild
        self.canvasmaker = self._custom_canvasmaker

        logger.info(f"BookTemplate initialized for '{filename}' with page size {self.pagesize}")


    def _configure_toc_styles(self):
        """Configures the TableOfContents object's levelStyles based on style_config."""
        # Use helper functions from pdf_components if possible, otherwise local fallbacks
        try:
            from .pdf_components import _parse_color, _get_font_name
        except ImportError:
             logger.warning("Could not import helpers from pdf_components for TOC styling. Using basic fallbacks.")
             def _parse_color(c, default): return default
             def _get_font_name(lname, fconf, default): return default or 'Helvetica'


        toc_style_config = self.style_config.get('table_of_contents', {})
        level_styles_config = toc_style_config.get('level_styles', [])
        fonts_config = self.style_config.get('fonts', {})
        default_toc_font = _get_font_name('body', fonts_config, 'Helvetica')

        # Clear existing styles and apply from config
        self.toc.levelStyles = []
        if level_styles_config and isinstance(level_styles_config, list):
            for i, level_conf in enumerate(level_styles_config):
                 if not isinstance(level_conf, dict):
                      logger.warning(f"Invalid format for TOC level style at index {i}. Skipping.")
                      continue

                 level_logical_font = level_conf.get('font_name', 'body') # Use logical name
                 level_font_name = _get_font_name(level_logical_font, fonts_config, default_toc_font)
                 level_font_size = level_conf.get('font_size', 12 - i*1)
                 level_leading = level_conf.get('leading', level_font_size * 1.25) # Ensure enough leading
                 level_indent = level_conf.get('indent', 20 + i * 20)
                 level_color = _parse_color(level_conf.get('color', '#000000'))
                 level_space_after = level_conf.get('space_after', 4)

                 style = ParagraphStyle(
                     name=f'TOCLevel{i}', # Unique name for the style
                     parent=BASE_STYLES['Normal'], # Base on Normal
                     fontName=level_font_name,
                     fontSize=level_font_size,
                     leading=level_leading,
                     leftIndent=level_indent,
                     textColor=level_color,
                     spaceAfter=level_space_after,
                     # Add other attributes like bold/italic if needed based on level_conf
                 )
                 self.toc.levelStyles.append(style)
        else:
            # Provide very basic default TOC styles if none are in the config
            if not level_styles_config:
                 logger.warning("No 'level_styles' found in 'table_of_contents' style config. Using basic defaults.")
            else:
                 logger.warning("'level_styles' in 'table_of_contents' is not a list. Using basic defaults.")

            self.toc.levelStyles.extend([
                ParagraphStyle(name='TOCLevel0', fontName=default_toc_font, fontSize=12, leftIndent=20, spaceAfter=5, leading=15),
                ParagraphStyle(name='TOCLevel1', fontName=default_toc_font, fontSize=11, leftIndent=40, spaceAfter=4, leading=14)
            ])

        # Configure dots (can be made configurable in style JSON)
        self.toc.dotsMinLevel = 0 # Show dots for all levels by default
        self.toc.dot = '.'      # Use '.' for dots

        logger.debug(f"Configured {len(self.toc.levelStyles)} TOC level styles.")


    def afterFlowable(self, flowable):
        """
        Registers TOC entries. Checks for specific style names applied
        by pdf_components functions.
        """
        # Check if the flowable has a style name we use for TOC entries
        if hasattr(flowable, 'style') and hasattr(flowable, 'getPlainText'):
            style_name = getattr(flowable.style, 'name', None)
            text = flowable.getPlainText() # Get the clean text content

            level = -1
            # --- Map Style Names to TOC Levels ---
            if style_name == 'ChapterHeadingStyle':
                level = 0 # Chapter title
            elif style_name == 'SectionHeadingStyle':
                level = 1 # Section title (H2)
            # Add elif for 'SubSectionHeadingStyle' (H3) -> level = 2 etc.

            if level >= 0:
                 # Notify the TableOfContents object to add an entry
                 # Arguments are: (level, text, pageNum, optionalKey)
                 # We don't use optionalKey here.
                 try:
                    self.notify('TOCEntry', (level, text, self.page))
                    logger.debug(f"TOC Entry (L{level}): '{text}' on page {self.page}")
                 except Exception as e:
                      logger.error(f"Failed to notify TOCEntry for '{text}': {e}")

    # Override build methods to ensure custom canvasmaker is used
    # BaseDocTemplate's multiBuild should inherently use self.canvasmaker

    def build(self, flowables, filename=None, canvasmaker=None):
        """Override build to ensure the custom canvas maker is used."""
        # If a canvasmaker is explicitly passed to build, it overrides the instance one.
        # We ensure our custom one is used unless explicitly overridden here.
        _canvasmaker = canvasmaker or self._custom_canvasmaker
        logger.info(f"Starting build process using canvasmaker: {_canvasmaker.__name__ if hasattr(_canvasmaker, '__name__') else type(_canvasmaker)}")
        super().build(flowables, filename=filename, canvasmaker=_canvasmaker)

    # multiBuild is often called internally by build, but if called directly:
    # def multiBuild(self, flowables, filename=None, canvasmaker=None):
    #     """Override multiBuild if necessary (usually not needed if self.canvasmaker is set)."""
    #     _canvasmaker = canvasmaker or self._custom_canvasmaker
    #     super().multiBuild(flowables, filename=filename, canvasmaker=_canvasmaker)