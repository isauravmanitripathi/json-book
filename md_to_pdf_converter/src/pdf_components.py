# src/pdf_components.py

import logging
from reportlab.platypus import Paragraph, Spacer, Image, Table, TableStyle, Preformatted, PageBreak, KeepTogether, Flowable
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.utils import ImageReader # Efficient image handling
# Ensure Pillow is installed: pip install Pillow
try:
    from PIL import Image as PILImage # Use PIL for checking image properties
except ImportError:
    logging.warning("Pillow library not found. Image processing might be less robust. `pip install Pillow` recommended.")
    PILImage = None # Set to None if not found

from pathlib import Path # Use Path for robust path handling
import os
import re
import html # Import html for escaping error messages

# Import necessary objects from ReportLab's graphics library for horizontal rule
from reportlab.graphics.shapes import Line, Drawing
# Import pdfmetrics for font checks
from reportlab.pdfbase import pdfmetrics

# --- ADDED IMPORT ---
from .config import PAGE_SIZES
# --------------------

logger = logging.getLogger(__name__)
# Get ReportLab's default stylesheet correctly (uses capitalized keys)
BASE_STYLES = getSampleStyleSheet()

# --- Helper Functions ---

def _parse_color(color_value, default_color=colors.black):
    """Safely parse color from string (hex, name) or ReportLab color object."""
    if isinstance(color_value, str):
        color_value = color_value.strip()
        if color_value.startswith('#'):
            try:
                return colors.HexColor(color_value)
            except ValueError:
                logger.warning(f"Invalid hex color '{color_value}'. Using default.")
                return default_color
        else:
            try:
                return getattr(colors, color_value, default_color)
            except AttributeError:
                 logger.warning(f"Unknown color name '{color_value}'. Using default.")
                 return default_color
    elif isinstance(color_value, (colors.Color, colors.CMYKColor, colors.PCMYKColor)):
        return color_value
    elif color_value is None:
         return None
    logger.debug(f"Color value '{color_value}' is not a string or Color object. Using default.")
    return default_color

def _get_alignment(align_str):
    """Convert alignment string (style config) to ReportLab constant."""
    align_map = {
        'LEFT': TA_LEFT, 'CENTER': TA_CENTER, 'RIGHT': TA_RIGHT, 'JUSTIFIED': TA_JUSTIFY,
        'CENTRE': TA_CENTER, 'DECIMAL': TA_RIGHT
    }
    return align_map.get(str(align_str).upper(), TA_LEFT)

def _get_alignment_string(align_str):
     """Convert alignment string (style config) to ReportLab TableStyle command string."""
     align_map = {
         'LEFT': 'LEFT', 'CENTER': 'CENTRE', 'CENTRE': 'CENTRE', 'RIGHT': 'RIGHT',
         'JUSTIFIED': 'LEFT', 'DECIMAL': 'DECIMAL'
     }
     return align_map.get(str(align_str).upper(), 'LEFT')

# --- CORRECTED _get_font_name Function ---
def _get_font_name(logical_name, fonts_config, default_font="Helvetica"):
    """
    Gets the registered ReportLab font name based on the logical name
    defined in the style's 'fonts' section. Handles standard fonts too.
    """
    if not logical_name:
        logger.debug(f"No logical font name provided, using default '{default_font}'.")
        return default_font

    standard_fonts = [
        'Courier', 'Courier-Bold', 'Courier-Oblique', 'Courier-BoldOblique',
        'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique',
        'Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic',
        'Symbol', 'ZapfDingbats'
    ]
    if logical_name in standard_fonts:
        logger.debug(f"Using standard font '{logical_name}'.")
        return logical_name

    font_info = fonts_config.get(logical_name)
    actual_font_name = None

    if isinstance(font_info, str):
        actual_font_name = font_info # Use the VALUE from the config directly
        logger.debug(f"Logical name '{logical_name}' maps to string '{actual_font_name}'. Using this name.")
    elif isinstance(font_info, dict):
        if 'normal' in font_info:
            actual_font_name = logical_name # Use the family name mapped by StyleLoader
            logger.debug(f"Logical name '{logical_name}' maps to a dict (family definition). Using family name '{actual_font_name}'.")
        else:
            logger.warning(f"Font definition for '{logical_name}' is a dict but missing 'normal' variant. Falling back.")
            actual_font_name = None
    else:
        logger.warning(f"Logical name '{logical_name}' not found or has invalid format in fonts config. Falling back.")
        actual_font_name = None

    if actual_font_name:
        try:
            pdfmetrics.getFont(actual_font_name)
            logger.debug(f"Verified font '{actual_font_name}' is registered.")
            return actual_font_name
        except KeyError:
            logger.warning(f"Font name '{actual_font_name}' resolved for logical name '{logical_name}' but it is NOT registered in pdfmetrics! Falling back to default '{default_font}'.")
            try:
                 pdfmetrics.getFont(default_font)
                 return default_font
            except KeyError:
                 logger.error(f"Default font '{default_font}' is also not registered! Falling back to 'Helvetica'.")
                 return 'Helvetica'
    else:
        logger.debug(f"Falling back to default font '{default_font}' for logical name '{logical_name}'.")
        try:
             pdfmetrics.getFont(default_font)
             return default_font
        except KeyError:
             logger.error(f"Default font '{default_font}' is also not registered! Falling back to 'Helvetica'.")
             return 'Helvetica'
# --- End CORRECTED _get_font_name Function ---


def _apply_inline_formatting(text):
    """
    Convert basic HTML inline tags (<b>, <i>, <br/>) to ReportLab XML tags.
    Escapes other XML special characters first.
    """
    if not isinstance(text, str):
         text = str(text)
    text = html.escape(text)
    text = re.sub(r'&lt;(/?)(b|strong)&gt;', r'<\1b>', text, flags=re.IGNORECASE)
    text = re.sub(r'&lt;(/?)(i|em)&gt;', r'<\1i>', text, flags=re.IGNORECASE)
    text = re.sub(r'&lt;br\s*/?&gt;', '<br/>', text, flags=re.IGNORECASE)
    return text

# --- PDF Component Creation Functions ---

def create_toc_placeholder(toc_object, style_config):
    """Creates flowables for the Table of Contents title and placeholder."""
    toc_style_config = style_config.get('table_of_contents', {})
    title_style_dict = toc_style_config.get('title', {})
    fonts_config = style_config.get('fonts', {})
    flowables = []
    toc_title_font = _get_font_name(title_style_dict.get('font_name'), fonts_config, 'Helvetica-Bold')
    toc_title_size = title_style_dict.get('font_size', 18)
    rl_title_style = ParagraphStyle(
        name='TOCTitleStyle', parent=BASE_STYLES['Heading1'], fontName=toc_title_font,
        fontSize=toc_title_size, textColor=_parse_color(title_style_dict.get('color', '#000000')),
        alignment=_get_alignment(title_style_dict.get('alignment', 'center')),
        spaceAfter=title_style_dict.get('space_after', 20), leading=toc_title_size * 1.2
    )
    title_text = title_style_dict.get('text', 'Table of Contents')
    flowables.append(Paragraph(title_text, rl_title_style))
    flowables.append(Spacer(1, 10))
    flowables.append(toc_object)
    return flowables


def create_chapter_heading(chapter_number, chapter_title, style_dict, fonts_config):
    """Creates flowables for a chapter heading."""
    flowables = []
    style_name_for_toc = 'ChapterHeadingStyle'
    font_name = _get_font_name(style_dict.get('font_name'), fonts_config, 'Helvetica-Bold')
    font_size = style_dict.get('font_size', 20)
    heading_style = ParagraphStyle(
        name=style_name_for_toc, parent=BASE_STYLES['Heading1'], fontName=font_name,
        fontSize=font_size, textColor=_parse_color(style_dict.get('color', '#000000')),
        alignment=_get_alignment(style_dict.get('alignment', 'left')),
        spaceBefore=style_dict.get('space_before', 30), spaceAfter=style_dict.get('space_after', 15),
        leading=font_size * 1.2
    )
    full_title = f"Chapter {chapter_number}: {chapter_title}"
    flowables.append(Paragraph(_apply_inline_formatting(full_title), heading_style))
    return flowables


def create_section_heading(section_title, style_dict, fonts_config):
    """Creates a Paragraph flowable for a section heading (H2)."""
    style_name_for_toc = 'SectionHeadingStyle'
    font_name = _get_font_name(style_dict.get('font_name'), fonts_config, 'Helvetica-Bold')
    font_size = style_dict.get('font_size', 16)
    heading_style = ParagraphStyle(
        name=style_name_for_toc, parent=BASE_STYLES['Heading2'], fontName=font_name,
        fontSize=font_size, textColor=_parse_color(style_dict.get('color', '#222222')),
        alignment=_get_alignment(style_dict.get('alignment', 'left')),
        spaceBefore=style_dict.get('space_before', 18), spaceAfter=style_dict.get('space_after', 10),
        leading=font_size * 1.2
    )
    return Paragraph(_apply_inline_formatting(section_title), heading_style)


def create_other_heading(level, text, style_config, fonts_config):
    """Creates a Paragraph for H3-H6, using a slightly modified paragraph style."""
    style_name = f'OtherHeading{level}'
    base_style_dict = style_config.get('paragraph', {}).copy()
    heading_style_dict = style_config.get(f'heading_h{level}', base_style_dict)
    logical_font_name = heading_style_dict.get('font_name', 'heading')
    default_bold_font = 'Helvetica-Bold'
    font_name = _get_font_name(logical_font_name, fonts_config, default_bold_font)

    try:
        is_base_bold = any(b in font_name for b in ['Bold', 'Bd', 'bold'])
        if not is_base_bold:
            bold_variant_registered_name = None
            possible_bold_names = [f"{logical_font_name}-Bold", f"{logical_font_name}-bold", f"{font_name}-Bold", f"{font_name}-bold"]
            for name_to_try in possible_bold_names:
                 if not name_to_try: continue
                 try:
                     pdfmetrics.getFont(name_to_try)
                     bold_variant_registered_name = name_to_try
                     break
                 except KeyError: continue
            if bold_variant_registered_name:
                font_name = bold_variant_registered_name
            else:
                logger.debug(f"Bold font variant for heading level {level} ('{logical_font_name}') not found/registered. Using '{font_name}'.")
                if not any(b in font_name for b in ['Bold', 'Bd', 'bold']):
                     logger.warning(f"Resolved font '{font_name}' for H{level} ('{logical_font_name}') is not bold. Forcing fallback '{default_bold_font}'.")
                     font_name = default_bold_font
    except Exception as e:
        logger.error(f"Error checking bold font for heading {level} ('{logical_font_name}'): {e}. Using fallback '{font_name}'.")
        if not font_name: font_name = default_bold_font

    default_size = max(10, 14 - (level - 3))
    font_size = heading_style_dict.get('font_size', default_size)
    default_space_before = max(4, 12 - (level - 3))
    space_before = heading_style_dict.get('space_before', default_space_before)
    default_space_after = max(2, 6 - (level - 3))
    space_after = heading_style_dict.get('space_after', default_space_after)

    heading_style = ParagraphStyle(
        name=style_name, parent=BASE_STYLES['Normal'], fontName=font_name, fontSize=font_size,
        textColor=_parse_color(heading_style_dict.get('color', '#333333')),
        alignment=_get_alignment(heading_style_dict.get('alignment', 'left')),
        spaceBefore=space_before, spaceAfter=space_after, leading=font_size * 1.2,
        firstLineIndent=heading_style_dict.get('first_line_indent', 0)
    )
    logger.debug(f"Creating H{level} heading '{text[:30]}...' with style: Font={font_name}, Size={font_size}")
    return Paragraph(_apply_inline_formatting(text), heading_style)


def create_paragraph(text, style_dict, fonts_config):
    """Creates a Paragraph flowable, handling basic inline formatting."""
    formatted_text = _apply_inline_formatting(text)
    logical_font_name = style_dict.get('font_name', 'body')
    font_name = _get_font_name(logical_font_name, fonts_config, 'Times-Roman')
    is_italic = style_dict.get('italic', False)

    if is_italic:
        resolved_italic_font = font_name
        try:
            possible_italic_names = [f"{logical_font_name}-Italic", f"{font_name}-Italic", f"{font_name}-Oblique"]
            found_italic = False
            for name_to_try in possible_italic_names:
                 if not name_to_try: continue
                 try:
                     pdfmetrics.getFont(name_to_try)
                     resolved_italic_font = name_to_try
                     found_italic = True
                     break
                 except KeyError: continue
            if found_italic:
                 font_name = resolved_italic_font
                 logger.debug(f"Applied italic font '{font_name}' for paragraph.")
            else:
                 logger.warning(f"Italic requested for paragraph (logical font '{logical_font_name}'), but no registered Italic/Oblique variant found for '{font_name}'. Using base font.")
        except Exception as e:
            logger.error(f"Error checking italic font for paragraph ('{logical_font_name}'): {e}")

    para_style = ParagraphStyle(
        name='BodyParagraph', parent=BASE_STYLES['Normal'], fontName=font_name,
        fontSize=style_dict.get('font_size', 11), textColor=_parse_color(style_dict.get('color', '#000000')),
        alignment=_get_alignment(style_dict.get('alignment', 'justified')),
        leading=style_dict.get('leading', 14), spaceAfter=style_dict.get('space_after', 6),
        firstLineIndent=style_dict.get('first_line_indent', 18)
    )
    try:
        return Paragraph(formatted_text, para_style)
    except Exception as e:
        logger.error(f"Error creating Paragraph: {e}. Text: '{formatted_text[:100]}...'")
        fallback_style = BASE_STYLES['Normal']
        clean_text = re.sub(r'<[^>]+>', '', formatted_text)
        clean_text = clean_text.replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
        clean_text = clean_text.replace('\u2013', '-').replace('\u2014', '--')
        try:
            return Paragraph(clean_text, fallback_style)
        except Exception as e2:
            logger.error(f"Fallback Paragraph creation also failed: {e2}")
            error_para_style = ParagraphStyle(name='ErrorPara', textColor=colors.red)
            # Escape the error message itself for safety when displaying it
            escaped_error = html.escape(str(e))
            return Paragraph(f"[Error rendering paragraph: {escaped_error}]", error_para_style)


def create_code_block(code_content, language, style_dict, fonts_config):
    """Creates a Preformatted flowable for a code block."""
    logger.debug(f"Creating code block (lang: {language}): {code_content[:100]}...")
    code_font_name = _get_font_name(style_dict.get('font_name'), fonts_config, 'Courier')

    code_style = ParagraphStyle(
        name='CodeBlockStyle', parent=BASE_STYLES['Code'], fontName=code_font_name,
        fontSize=style_dict.get('font_size', 9), leading=style_dict.get('leading', 11),
        textColor=_parse_color(style_dict.get('text_color', '#000000')),
        backColor=_parse_color(style_dict.get('background_color', '#f0f0f0'), default_color=None),
        borderPadding=style_dict.get('padding', 10), borderWidth=style_dict.get('border_width', 0.5),
        borderColor=_parse_color(style_dict.get('border_color', '#cccccc'), default_color=None),
        spaceBefore=style_dict.get('space_before', 8), spaceAfter=style_dict.get('space_after', 8),
        wordWrap='CJK', alignment=TA_LEFT
    )
    escaped_code = html.escape(code_content)
    return Preformatted(escaped_code, code_style)


def create_table(headers, rows, style_dict, fonts_config):
    """Creates a ReportLab Table flowable from header and row data."""
    flowables = []
    logger.debug(f"Creating table with {len(headers)} headers and {len(rows)} rows.")

    header_style_dict = style_dict.get('header', {})
    cell_style_dict = style_dict.get('cell', {})
    grid_style_dict = style_dict.get('grid', {})
    table_h_align = style_dict.get('alignment', 'CENTER').upper()

    cell_font = _get_font_name(cell_style_dict.get('font_name'), fonts_config, 'Times-Roman')
    header_font = _get_font_name(header_style_dict.get('font_name'), fonts_config, 'Helvetica-Bold')

    cell_para_style = ParagraphStyle(
        name='TableCellContent', parent=BASE_STYLES['Normal'], fontName=cell_font,
        fontSize=cell_style_dict.get('font_size', 10), textColor=_parse_color(cell_style_dict.get('text_color', '#000000')),
        alignment=_get_alignment(cell_style_dict.get('alignment', 'LEFT')),
        leading=cell_style_dict.get('font_size', 10) * 1.2
    )
    header_para_style = ParagraphStyle(
        name='TableHeaderContent', parent=BASE_STYLES['Normal'], fontName=header_font,
        fontSize=header_style_dict.get('font_size', 10), textColor=_parse_color(header_style_dict.get('text_color', '#000000')),
        alignment=_get_alignment(header_style_dict.get('alignment', 'CENTER')),
        leading=header_style_dict.get('font_size', 10) * 1.2
    )

    styled_table_data = []
    if headers:
        styled_headers = [Paragraph(_apply_inline_formatting(h), header_para_style) for h in headers]
        styled_table_data.append(styled_headers)
    for row in rows:
        styled_row = [Paragraph(_apply_inline_formatting(cell), cell_para_style) for cell in row]
        styled_table_data.append(styled_row)

    if not styled_table_data:
        logger.warning("Attempted to create a table with no data.")
        return []

    ts_commands = []
    cell_padding = cell_style_dict.get('padding', 3)
    ts_commands.extend([
        ('LEFTPADDING', (0, 0), (-1, -1), cell_padding), ('RIGHTPADDING', (0, 0), (-1, -1), cell_padding),
        ('TOPPADDING', (0, 0), (-1, -1), cell_padding), ('BOTTOMPADDING', (0, 0), (-1, -1), cell_padding),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])

    if headers:
        header_row_index = 0
        header_bg = _parse_color(header_style_dict.get('background_color', '#e0e0e0'), default_color=None)
        header_pad_bottom = header_style_dict.get('padding_bottom', 4)
        ts_commands.append(('BOTTOMPADDING', (0, header_row_index), (-1, header_row_index), header_pad_bottom))
        if header_bg:
            ts_commands.append(('BACKGROUND', (0, header_row_index), (-1, header_row_index), header_bg))

    grid_width = grid_style_dict.get('width', 0.5)
    grid_color = _parse_color(grid_style_dict.get('color', '#aaaaaa'))
    if grid_width > 0 and grid_color:
        if grid_style_dict.get('use_inner_lines', True):
            ts_commands.append(('INNERGRID', (0, 0), (-1, -1), grid_width, grid_color))
        if grid_style_dict.get('use_outer_lines', True):
            ts_commands.append(('BOX', (0, 0), (-1, -1), grid_width, grid_color))

    try:
        table = Table(styled_table_data, style=TableStyle(ts_commands), hAlign=table_h_align)
    except Exception as e:
        logger.error(f"Error creating ReportLab Table object: {e}")
        err_style = ParagraphStyle(name='TableError', textColor=colors.red)
        return [Paragraph(f"[Error creating table: {html.escape(str(e))}]", err_style)]

    flowables.append(Spacer(1, style_dict.get('space_before', 10)))
    flowables.append(table)
    flowables.append(Spacer(1, style_dict.get('space_after', 10)))
    return flowables


def create_image(image_path_str, alt_text, style_dict, base_dir):
    """Creates flowables for an Image and its caption."""
    caption_style_dict = style_dict.get('caption', {})
    fonts_config = style_dict.get('_fonts_config_ref', {})
    flowables = []

    image_path = Path(image_path_str)
    if not image_path.is_absolute():
        full_image_path = base_dir.resolve() / image_path
    else:
        full_image_path = image_path

    if not full_image_path.is_file():
        logger.warning(f"Image file not found at resolved path: {full_image_path} (Original: '{image_path_str}', Base: '{base_dir}')")
        err_style = ParagraphStyle(name='ImageError', textColor=colors.red, fontSize=9)
        flowables.append(Paragraph(f"[Image not found: {html.escape(image_path_str)}]", err_style))
        return flowables

    logger.debug(f"Processing image: {full_image_path}")
    try:
        img_width_pt, img_height_pt = None, None
        if PILImage:
            try:
                with PILImage.open(full_image_path) as img:
                    img.verify()
                    with PILImage.open(full_image_path) as img_dim:
                        img_width_px, img_height_px = img_dim.size
                        dpi = img_dim.info.get('dpi', (72, 72))
                        dpi_x = dpi[0] if isinstance(dpi, (tuple, list)) and len(dpi) > 0 else 72
                        dpi_y = dpi[1] if isinstance(dpi, (tuple, list)) and len(dpi) > 1 else 72
                        img_width_pt = img_width_px * 72.0 / dpi_x
                        img_height_pt = img_height_px * 72.0 / dpi_y
                        logger.debug(f"Image dimensions (PIL): {img_width_px}x{img_height_px} px @ ({dpi_x},{dpi_y}) dpi -> {img_width_pt:.2f}x{img_height_pt:.2f} pt")
            except Exception as pil_error:
                logger.warning(f"PIL failed for image {full_image_path}: {pil_error}. Attempting ReportLab ImageReader only.")
                img_width_pt, img_height_pt = None, None

        if img_width_pt is None or img_height_pt is None:
            img_reader = ImageReader(full_image_path)
            img_width_pt, img_height_pt = img_reader.getSize()
            if img_width_pt is None or img_height_pt is None or img_width_pt <= 0 or img_height_pt <= 0:
                raise ValueError(f"ReportLab ImageReader failed to get valid dimensions ({img_width_pt}x{img_height_pt}).")
            logger.debug(f"Image dimensions (ReportLab): {img_width_pt:.2f}x{img_height_pt:.2f} pt")

        available_width = 6.5 * inch # Fallback approximation

        if img_width_pt > available_width:
            scale_factor = available_width / float(img_width_pt)
            img_draw_width = available_width
            img_draw_height = img_height_pt * scale_factor
        else:
            img_draw_width = img_width_pt
            img_draw_height = img_height_pt

        rl_image = Image(full_image_path, width=img_draw_width, height=img_draw_height)
        rl_image.hAlign = style_dict.get('alignment', 'CENTER').upper()

        caption_para = None
        caption_text = alt_text or ""
        if caption_text:
            caption_text = caption_text.replace('\n', ' ').strip()
            logical_font_name = caption_style_dict.get('font_name', 'body')
            caption_font = _get_font_name(logical_font_name, fonts_config, 'Helvetica')
            caption_is_italic = caption_style_dict.get('italic', True)

            if caption_is_italic:
                 resolved_italic_font = caption_font
                 try:
                     possible_italic_names = [f"{logical_font_name}-Italic", f"{caption_font}-Italic", f"{caption_font}-Oblique"]
                     found_italic = False
                     for name_to_try in possible_italic_names:
                          if not name_to_try: continue
                          try:
                              pdfmetrics.getFont(name_to_try)
                              resolved_italic_font = name_to_try
                              found_italic = True
                              break
                          except KeyError: continue
                     if found_italic: caption_font = resolved_italic_font
                     else: logger.warning(f"Italic requested for caption ('{logical_font_name}'), but no Italic/Oblique variant found for '{caption_font}'.")
                 except Exception as e: logger.error(f"Error checking italic font for caption ('{logical_font_name}'): {e}")

            caption_style = ParagraphStyle(
                name='ImageCaptionStyle', parent=BASE_STYLES['Italic'] if caption_is_italic else BASE_STYLES['Normal'],
                fontName=caption_font, fontSize=caption_style_dict.get('font_size', 9),
                textColor=_parse_color(caption_style_dict.get('color', '#555555')),
                leading=caption_style_dict.get('leading', 11),
                alignment=_get_alignment(caption_style_dict.get('alignment', 'center')),
                spaceBefore=caption_style_dict.get('space_before', 4),
            )
            caption_para = Paragraph(_apply_inline_formatting(caption_text), caption_style)

        image_group = [
            Spacer(1, style_dict.get('space_before', 10)),
            rl_image
        ]
        if caption_para: image_group.append(caption_para)
        image_group.append(Spacer(1, style_dict.get('space_after', 10)))
        flowables.append(KeepTogether(image_group))

    except Exception as e:
        logger.error(f"Failed to create image flowable for '{full_image_path}': {e}", exc_info=True)
        err_style = ParagraphStyle(name='ImageError', textColor=colors.red, fontSize=9)
        escaped_error = html.escape(str(e))
        flowables.append(Paragraph(f"[Error processing image: {html.escape(image_path_str)} - {escaped_error}]", err_style))

    return flowables

def create_horizontal_rule(style_dict):
    """ Creates a horizontal rule flowable using ReportLab Graphics. """
    # Use PAGE_SIZES imported at the top
    page_width = PAGE_SIZES.get('A4')[0] # Default A4 width
    available_width = 6.5 * inch # Fallback

    line_width = style_dict.get('width', 0.5)
    color = _parse_color(style_dict.get('color', colors.grey))
    space_before = style_dict.get('space_before', 12)
    space_after = style_dict.get('space_after', 12)

    drawing_height = line_width * 2
    drawing = Drawing(available_width, drawing_height)
    line = Line(0, drawing_height / 2, available_width, drawing_height / 2)
    line.strokeColor = color
    line.strokeWidth = line_width
    drawing.add(line)

    return [Spacer(1, space_before), drawing, Spacer(1, space_after)]