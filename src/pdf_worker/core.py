import os
import json
import traceback
import logging
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import PageBreak, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus.doctemplate import BaseDocTemplate

from .style_manager import StyleManager
from .components.title_page import TitlePage
from .components.toc import TableOfContents
from .components.chapter import Chapter
from .components.section import Section
from .templates.book_template import BookTemplate, PageNumCanvas
from .image_handler import ImageHandler
from .front_matter_manager import FrontMatterManager

class PDFGenerator:
    """Generates PDF books from JSON content using style templates."""
    def __init__(self, image_base_path='images'):
        """
        Initialize the PDF Generator
        
        Args:
            image_base_path (str): Base path for image files
        """
        self.style_manager = StyleManager()
        self.styles = getSampleStyleSheet()
        self.image_base_path = image_base_path
        self.front_matter_manager = None
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
    def generate_pdf(self, input_json_path, book_name, author_name, style_name='classic', 
                    output_dir='results/pdfs', max_pages_per_part=600, front_matter_options=None,
                    api_key=None):
        """
        Generate a PDF from JSON content using the specified style template.
        
        If the book exceeds max_pages_per_part, it will be split into multiple parts.
        Each part will have its own chapter numbering, TOC, etc.
        
        Args:
            input_json_path (str): Path to input JSON file
            book_name (str): Name of the book
            author_name (str): Name of the author
            style_name (str, optional): Style template to use.
            output_dir (str, optional): Directory to save output PDF(s).
            max_pages_per_part (int, optional): Maximum pages per part for multi-part PDFs.
            front_matter_options (dict, optional): Front matter components to include.
                - copyright (bool): Include copyright page
                - epigraph (bool): Include epigraph
                - preface (bool): Include preface
                - letter_to_reader (bool): Include letter to reader
                - introduction (bool): Include introduction
                - other copyright info fields: year, publisher, edition, etc.
            api_key (str, optional): Anthropic API key for front matter generation.
            
        Returns:
            str or list: Path(s) to generated PDF file(s)
        """
        try:
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Create a safe filename based on the book name
            safe_filename = "".join(x for x in book_name if x.isalnum() or x in (' ', '-', '_')).rstrip()
            
            # Load the style template
            style_config = self.style_manager.load_style(style_name)
            self.logger.info(f"Loaded style: {style_name}")
            
            # Initialize the image handler
            image_handler = ImageHandler(style_config, self.image_base_path)
            self.logger.info(f"Initialized image handler with base path: {self.image_base_path}")
            
            # Initialize front matter manager if front matter options provided
            if front_matter_options:
                self.front_matter_manager = FrontMatterManager(style_config, api_key=api_key)
            
            # Store front matter options and input path for later use
            self.front_matter_options = front_matter_options
            self.input_json_path = input_json_path
            
            # Load content from JSON
            with open(input_json_path, 'r') as file:
                sections = json.load(file)
            
            self.logger.info(f"Loaded JSON with {len(sections)} sections")
            
            # Sort sections properly by chapter_id and section_number
            self._sort_sections(sections)
            self.logger.info("Sections sorted by chapter_id and section_number")
            
            # Group sections by chapter, maintaining the original order
            chapters = {}
            chapter_order = []  # To preserve original order of chapters
            
            for section_data in sections:
                chapter_id = section_data.get('chapter_id', '')
                
                if chapter_id not in chapters:
                    chapters[chapter_id] = []
                    chapter_order.append(chapter_id)
                    
                chapters[chapter_id].append(section_data)
            
            # Now divide chapters into parts based on estimated page count, preserving order
            parts = self._divide_into_parts(chapters, chapter_order, style_config, max_pages_per_part)
            self.logger.info(f"Book will be divided into {len(parts)} parts")
            
            # Generate each part as a separate PDF
            generated_pdfs = []
            for part_num, part_chapters in enumerate(parts, 1):
                part_filename = f"{safe_filename}_Part{part_num}.pdf" if len(parts) > 1 else f"{safe_filename}.pdf"
                output_pdf_path = os.path.join(output_dir, part_filename)
                
                part_title = f"{book_name} - Part {part_num}" if len(parts) > 1 else book_name
                
                # Generate this part's PDF
                self._generate_single_pdf(output_pdf_path, part_title, author_name, style_config, 
                                        part_chapters, image_handler, part_num, len(parts))
                generated_pdfs.append(output_pdf_path)
                self.logger.info(f"Generated part {part_num} at {output_pdf_path}")
            
            if len(generated_pdfs) == 1:
                return generated_pdfs[0]  # Return single path for single PDFs
            return generated_pdfs
            
        except Exception as e:
            self.logger.error(f"Error generating PDF: {str(e)}")
            traceback.print_exc()
            raise
    
    def generate_multiformat_pdf(self, input_json_path, book_name, author_name, style_name='classic', 
                     output_dir='results/pdfs', max_pages_per_part=600, front_matter_options=None,
                     api_key=None, formats=None):
        """
        Generate PDFs in multiple formats/dimensions from JSON content.
        
        Args:
            input_json_path (str): Path to input JSON file
            book_name (str): Name of the book
            author_name (str): Name of the author
            style_name (str, optional): Style template to use.
            output_dir (str, optional): Directory to save output PDF(s).
            max_pages_per_part (int, optional): Maximum pages per part for multi-part PDFs.
            front_matter_options (dict, optional): Front matter components to include.
            api_key (str, optional): Anthropic API key for front matter generation.
            formats (list, optional): List of format dictionaries with the following keys:
                - name (str): Format name (e.g., "US Letter", "A4", etc.)
                - size (str): Page size name (e.g., "LETTER", "A4")
                - width (float): Page width in inches
                - height (float): Page height in inches
            
        Returns:
            dict: Dictionary mapping format names to paths of generated PDF files
        """
        # Define default formats if none provided
        if formats is None:
            formats = [
                {"name": "US Trade", "size": "CUSTOM", "width": 6, "height": 9},
                {"name": "US Letter", "size": "LETTER", "width": 8.5, "height": 11},
                {"name": "A4", "size": "A4", "width": 8.27, "height": 11.69},
            ]
        
        # Dictionary to store paths to generated PDFs
        generated_pdfs = {}
        
        # Remember original style config
        original_style = self.style_manager.load_style(style_name)
        
        # Generate PDF in each format
        for format_config in formats:
            self.logger.info(f"Generating PDF in {format_config['name']} format ({format_config['width']}\" x {format_config['height']}\")")
            
            # Adjust the style config for this format
            adjusted_style = self._adjust_style_for_format(original_style, format_config)
            
            # Create a safe filename with format info
            format_suffix = format_config['name'].replace(' ', '_')
            safe_book_name = "".join(x for x in book_name if x.isalnum() or x in (' ', '-', '_')).rstrip()
            format_filename = f"{safe_book_name}_{format_suffix}"
            
            # Generate PDF with adjusted style
            result = self._generate_pdf_with_style(
                input_json_path, book_name, author_name, 
                adjusted_style, format_config,
                output_dir, format_filename, 
                max_pages_per_part, front_matter_options, api_key
            )
            
            # Store the result
            generated_pdfs[format_config['name']] = result
            self.logger.info(f"Completed generation of {format_config['name']} format")
        
        return generated_pdfs

    def _adjust_style_for_format(self, style_config, format_config):
        """
        Adjust style configuration for a specific format.
        
        Args:
            style_config (dict): Original style configuration
            format_config (dict): Format specification
            
        Returns:
            dict: Adjusted style configuration
        """
        # Create a deep copy of the style config to avoid modifying the original
        import copy
        adjusted_style = copy.deepcopy(style_config)
        
        # Set the page size
        adjusted_style['page'] = adjusted_style.get('page', {})
        
        if format_config['size'] == 'CUSTOM':
            # For custom sizes, we need to set the dimensions in points (72 points = 1 inch)
            adjusted_style['page']['width'] = format_config['width'] * 72
            adjusted_style['page']['height'] = format_config['height'] * 72
            adjusted_style['page']['size'] = 'CUSTOM'
        else:
            # For standard sizes, we can use the predefined constants
            adjusted_style['page']['size'] = format_config['size']
        
        # Adjust margins proportionally to maintain similar whitespace ratios
        original_margins = adjusted_style['page'].get('margins', {'left': 72, 'right': 72, 'top': 72, 'bottom': 72})
        
        # Calculate scale factors based on dimension changes
        # Assuming original style is based on A4 or US Letter
        original_width = 8.5 * 72  # Default to US Letter width in points
        original_height = 11 * 72  # Default to US Letter height in points
        
        if style_config['page'].get('size') == 'A4':
            original_width = 8.27 * 72
            original_height = 11.69 * 72
        elif style_config['page'].get('width') and style_config['page'].get('height'):
            original_width = style_config['page']['width']
            original_height = style_config['page']['height']
        
        # Calculate new dimensions in points
        new_width = format_config['width'] * 72
        new_height = format_config['height'] * 72
        
        # Calculate scaling factors
        width_scale = new_width / original_width
        height_scale = new_height / original_height
        
        # Scale margins proportionally
        adjusted_style['page']['margins'] = {
            'left': int(original_margins['left'] * width_scale),
            'right': int(original_margins['right'] * width_scale),
            'top': int(original_margins['top'] * height_scale),
            'bottom': int(original_margins['bottom'] * height_scale)
        }
        
        # Scale font sizes proportionally for smaller formats
        if new_width < original_width or new_height < original_height:
            scale_factor = min(width_scale, height_scale)
            self._scale_font_sizes(adjusted_style, scale_factor)
        
        return adjusted_style

    def _scale_font_sizes(self, style_config, scale_factor):
        """
        Scale font sizes in the style configuration based on a scale factor.
        Only scales down if scale_factor < 1.0.
        
        Args:
            style_config (dict): Style configuration to adjust
            scale_factor (float): Scaling factor
        """
        # Only scale down, not up
        if scale_factor >= 0.9:
            return
            
        # Apply minimum scale factor
        scale_factor = max(scale_factor, 0.8)
        
        # Scale font sizes in various sections
        for section in ['title_page', 'table_of_contents', 'chapter', 'section', 'body_text']:
            if section in style_config:
                self._scale_section_fonts(style_config[section], scale_factor)
        
        # Handle page numbers
        if 'page_numbers' in style_config and 'size' in style_config['page_numbers']:
            style_config['page_numbers']['size'] = int(style_config['page_numbers']['size'] * scale_factor)

    def _scale_section_fonts(self, section_config, scale_factor):
        """
        Scale font sizes within a section configuration.
        
        Args:
            section_config (dict): Section configuration
            scale_factor (float): Scaling factor
        """
        # Handle nested configurations
        for key, value in section_config.items():
            if isinstance(value, dict):
                if 'size' in value:
                    # Scale font size
                    value['size'] = int(value['size'] * scale_factor)
                
                # Recursively scale nested dictionaries
                self._scale_section_fonts(value, scale_factor)
            elif key == 'size' and isinstance(value, (int, float)):
                # Direct size attribute
                section_config[key] = int(value * scale_factor)

    def _generate_pdf_with_style(self, input_json_path, book_name, author_name, 
                           style_config, format_config, output_dir, filename_base, 
                           max_pages_per_part, front_matter_options, api_key):
        """
        Generate a PDF with a specific style configuration.
        
        Args:
            input_json_path (str): Path to input JSON file
            book_name (str): Name of the book
            author_name (str): Name of the author
            style_config (dict): Style configuration
            format_config (dict): Format specification
            output_dir (str): Directory to save output PDF(s)
            filename_base (str): Base filename for the PDF
            max_pages_per_part (int): Maximum pages per part for multi-part PDFs
            front_matter_options (dict): Front matter components to include
            api_key (str): Anthropic API key for front matter generation
            
        Returns:
            str or list: Path(s) to generated PDF file(s)
        """
        try:
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Initialize the image handler
            image_handler = ImageHandler(style_config, self.image_base_path)
            self.logger.info(f"Initialized image handler with base path: {self.image_base_path}")
            
            # Initialize front matter manager if front matter options provided
            if front_matter_options:
                self.front_matter_manager = FrontMatterManager(style_config, api_key=api_key)
            
            # Store front matter options and input path for later use
            self.front_matter_options = front_matter_options
            self.input_json_path = input_json_path
            
            # Load content from JSON
            with open(input_json_path, 'r') as file:
                sections = json.load(file)
            
            self.logger.info(f"Loaded JSON with {len(sections)} sections")
            
            # Sort sections properly by chapter_id and section_number
            self._sort_sections(sections)
            self.logger.info("Sections sorted by chapter_id and section_number")
            
            # Group sections by chapter, maintaining the original order
            chapters = {}
            chapter_order = []  # To preserve original order of chapters
            
            for section_data in sections:
                chapter_id = section_data.get('chapter_id', '')
                
                if chapter_id not in chapters:
                    chapters[chapter_id] = []
                    chapter_order.append(chapter_id)
                    
                chapters[chapter_id].append(section_data)
            
            # Divide chapters into parts based on estimated page count, preserving order
            parts = self._divide_into_parts(chapters, chapter_order, style_config, max_pages_per_part)
            self.logger.info(f"Book will be divided into {len(parts)} parts")
            
            # Generate each part as a separate PDF
            generated_pdfs = []
            for part_num, part_chapters in enumerate(parts, 1):
                # Format part info in filename
                # Format part info in filename (keep format in filename but not in title)
                if len(parts) > 1:
                    part_filename = f"{filename_base}_Part{part_num}.pdf"
                    part_title = f"{book_name} - Part {part_num}"
                else:
                    part_filename = f"{filename_base}.pdf"
                    part_title = book_name
                    
                output_pdf_path = os.path.join(output_dir, part_filename)
                
                # Generate this part's PDF
                self._generate_single_pdf(output_pdf_path, part_title, author_name, style_config, 
                                        part_chapters, image_handler, part_num, len(parts))
                generated_pdfs.append(output_pdf_path)
                self.logger.info(f"Generated part {part_num} at {output_pdf_path}")
            
            if len(generated_pdfs) == 1:
                return generated_pdfs[0]  # Return single path for single PDFs
            return generated_pdfs
            
        except Exception as e:
            self.logger.error(f"Error generating PDF: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
            
    def _sort_sections(self, sections):
        """
        Sort sections properly by chapter_id and section_number.
        Handles different formats of chapter_id and section_number.
        """
        def get_sort_key(section):
            chapter_id = section.get('chapter_id', '0')
            section_number = section.get('section_number', '0')
            
            # Try to convert chapter_id to int for numeric sorting
            try:
                chapter_key = int(chapter_id)
            except (ValueError, TypeError):
                chapter_key = chapter_id
                
            # Handle section numbers like "1.1.1" by splitting into parts
            if isinstance(section_number, str) and '.' in section_number:
                section_parts = []
                for part in section_number.split('.'):
                    try:
                        section_parts.append(int(part))
                    except (ValueError, TypeError):
                        section_parts.append(part)
                return (chapter_key, section_parts)
            else:
                # Try numeric conversion, fallback to string comparison
                try:
                    return (chapter_key, float(section_number))
                except (ValueError, TypeError):
                    return (chapter_key, section_number)
        
        sections.sort(key=get_sort_key)
    
    def _estimate_chapter_pages(self, chapter_data, style_config):
        """
        Estimate how many pages a chapter will take based on text content.
        This is a rough estimation based on character count and page dimensions.
        """
        # Get page dimensions from style
        page_config = style_config.get('page', {})
        margins = page_config.get('margins', {'left': 72, 'right': 72, 'top': 72, 'bottom': 72})
        
        # Get page size - could be custom or standard
        if page_config.get('size') == 'CUSTOM' and 'width' in page_config and 'height' in page_config:
            page_width = page_config['width']
            page_height = page_config['height']
        else:
            # Use A4 as default
            page_width = A4[0]
            page_height = A4[1]
        
        # Apply margins
        page_width = page_width - margins.get('left', 72) - margins.get('right', 72)
        page_height = page_height - margins.get('top', 72) - margins.get('bottom', 72)
        
        # Get font size and leading from body text style
        body_config = style_config.get('body_text', {})
        font_size = body_config.get('size', 12)
        leading = body_config.get('leading', 14)
        
        # Calculate available space per page in characters
        chars_per_line = int(page_width / (font_size * 0.6))  # Rough estimate for average char width
        lines_per_page = int(page_height / leading)
        chars_per_page = chars_per_line * lines_per_page
        
        # Calculate total characters in chapter
        total_chars = 0
        image_count = 0
        for section in chapter_data:
            # Add section title + text
            section_name = section.get('section_name', '')
            section_text = section.get('text', '')
            total_chars += len(section_name) + len(section_text)
            
            # Count images
            images = section.get('images', [])
            image_count += len(images)
        
        # Add fixed overhead for chapter title, TOC entry, etc. (approximately 1 page)
        estimated_pages = (total_chars / chars_per_page) + 1.0
        
        # Add space for images (rough estimate)
        estimated_pages += image_count * 0.5  # Assume each image takes about half a page on average
        
        # Add page breaks as needed
        chapter_config = style_config.get('chapter', {})
        if chapter_config.get('page_break', {}).get('before', True):
            estimated_pages += 1
        if chapter_config.get('page_break', {}).get('after', True):
            estimated_pages += 1
            
        return max(1, round(estimated_pages))  # Ensure at least 1 page
    
    def _divide_into_parts(self, chapters, chapter_order, style_config, max_pages_per_part):
        """
        Divide chapters into parts, ensuring each part doesn't exceed max_pages_per_part.
        Always keeps all sections of a chapter together in the same part.
        Maintains the original order of chapters.
        """
        parts = []
        current_part = []
        current_part_pages = 0
        
        # Process chapters in their original order
        for chapter_id in chapter_order:
            chapter_data = chapters[chapter_id]
            
            # Estimate pages for this chapter
            chapter_pages = self._estimate_chapter_pages(chapter_data, style_config)
            
            # If adding this chapter would exceed the max pages and we already have content,
            # finish the current part and start a new one
            if current_part_pages + chapter_pages > max_pages_per_part and current_part:
                parts.append(current_part)
                current_part = []
                current_part_pages = 0
            
            # Handle extremely large chapters that exceed the max_pages_per_part on their own
            if chapter_pages > max_pages_per_part and not current_part:
                self.logger.warning(f"Chapter {chapter_id} exceeds max_pages_per_part on its own ({chapter_pages} estimated pages)")
            
            # Add this chapter to the current part
            current_part.append((chapter_id, chapter_data))
            current_part_pages += chapter_pages
            
        # Add the last part if it has content
        if current_part:
            parts.append(current_part)
            
        return parts
    
    def _generate_single_pdf(self, output_path, book_title, author_name, style_config, chapters_data, 
                            image_handler, part_num=None, total_parts=None):
        """Generate a single PDF part."""
        # Create document template
        doc = BookTemplate(
            output_path,
            style_config=style_config
        )
        
        # Build the story
        story = []
        
        # Add title page with part info if applicable
        title_page = TitlePage(style_config, book_title, author_name)
        title_page.add_to_story(story)
        self.logger.info(f"Added title page for {book_title}")
        
        # Add front matter if requested
        if self.front_matter_manager:
            book_info = {
                'title': book_title,
                'author': author_name,
                'front_matter': self.front_matter_options
            }
            # Add other copyright info if provided
            if self.front_matter_options and self.front_matter_options.get('copyright', False):
                for key in ['year', 'publisher', 'edition', 'isbn', 'copyright_holder', 'additional_info']:
                    if key in self.front_matter_options:
                        book_info[key] = self.front_matter_options[key]
                        
            # Generate and add front matter components
            self.front_matter_manager.add_front_matter(story, book_info, self.input_json_path)
            self.logger.info("Added front matter components")
        
        # Add table of contents placeholder - this will be populated during multiBuild
        toc = TableOfContents(style_config, doc.toc)
        toc.add_to_story(story)
        self.logger.info("Added table of contents")
        story.append(PageBreak())
        
        # Reset image counter for each part
        image_handler.image_counter = 0
        
        # Process chapters and sections in order
        for chapter_idx, (original_chapter_id, sections) in enumerate(chapters_data, 1):
            # Use sequential chapter numbers within each part
            chapter_id = str(chapter_idx)
            
            # Get chapter name from first section
            chapter_name = sections[0].get('chapter_name', '').strip()
            
            self.logger.info(f"Processing chapter {chapter_id} (original ID: {original_chapter_id}): {chapter_name}")
            chapter = Chapter(style_config, chapter_id, chapter_name)
            chapter.add_to_story(story)
            
            # Add all sections for this chapter
            for section_data in sections:
                section_name = section_data.get('section_name', '').strip()
                section_text = section_data.get('text', '').strip()
                
                # Skip sections with empty content
                if not section_text and not section_name and not section_data.get('images'):
                    self.logger.info(f"  - Skipping empty section")
                    continue
                    
                self.logger.info(f"  - Section: {section_name}")
                
                # Create section object with full section data for image processing
                section = Section(
                    style_config, 
                    section_name, 
                    section_text, 
                    section_data=section_data,
                    image_handler=image_handler
                )
                
                # Add to story and explicitly check for errors
                try:
                    section.add_to_story(story)
                except Exception as e:
                    self.logger.error(f"  - Error adding section '{section_name}': {str(e)}")
                    # Try adding a simplified version of the section
                    try:
                        # Create a simpler section with just the name as a fallback
                        story.append(Paragraph(f"Section: {section_name}", 
                                              ParagraphStyle(name='SimpleSection', 
                                                            fontName='Helvetica-Bold', 
                                                            fontSize=12)))
                        if section_text:
                            story.append(Paragraph(section_text, 
                                                  ParagraphStyle(name='SimpleText', 
                                                                fontName='Helvetica', 
                                                                fontSize=10)))
                        self.logger.info(f"  - Added simplified version of section '{section_name}'")
                    except Exception as e2:
                        self.logger.error(f"  - Could not add section '{section_name}' even in simplified form: {str(e2)}")
        
        # Build the PDF - use BaseDocTemplate.multiBuild directly to avoid recursion
        self.logger.info(f"Building PDF for part {part_num if part_num else 1}...")
        
        # Create canvasmaker function
        page_number_settings = style_config.get('page_numbers', {})
        canvasmaker = lambda *args, **kw: PageNumCanvas(*args, page_number_settings=page_number_settings, **kw)
        
        # Call multiBuild directly from BaseDocTemplate to avoid the recursion issue
        try:
            BaseDocTemplate.multiBuild(doc, story, canvasmaker=canvasmaker)
        except Exception as e:
            self.logger.error(f"Error during PDF build: {str(e)}")
            # Try to build with a simpler story
            try:
                self.logger.info("Attempting to build PDF with simplified content...")
                simple_story = [Paragraph(f"{book_title}", ParagraphStyle(name='Title', fontName='Helvetica-Bold', fontSize=24))]
                simple_story.append(Paragraph(f"By {author_name}", ParagraphStyle(name='Author', fontName='Helvetica', fontSize=14)))
                simple_story.append(PageBreak())
                
                # Add a simplified TOC
                simple_story.append(Paragraph("Table of Contents", ParagraphStyle(name='TOCTitle', fontName='Helvetica-Bold', fontSize=18)))
                
                # Add simplified chapters
                for chapter_idx, (original_chapter_id, sections) in enumerate(chapters_data, 1):
                    simple_story.append(PageBreak())
                    chapter_name = sections[0].get('chapter_name', '').strip()
                    simple_story.append(Paragraph(f"Chapter {chapter_idx}: {chapter_name}", 
                                                 ParagraphStyle(name='ChapterTitle', fontName='Helvetica-Bold', fontSize=16)))
                    
                    # Add simplified sections
                    for section_data in sections:
                        section_name = section_data.get('section_name', '').strip()
                        if section_name:
                            simple_story.append(Paragraph(section_name, 
                                                        ParagraphStyle(name='SectionTitle', fontName='Helvetica-Bold', fontSize=14)))
                
                # Build with simpler content
                # Build with simpler content
                BaseDocTemplate.build(doc, simple_story)
                self.logger.info("Successfully built simplified PDF")
            except Exception as e2:
                self.logger.error(f"Failed to build even simplified PDF: {str(e2)}")
                raise
        
        return output_path