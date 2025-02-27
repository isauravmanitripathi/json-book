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
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
    def generate_pdf(self, input_json_path, book_name, author_name, style_name='classic', 
                    output_dir='results/pdfs', max_pages_per_part=600):
        """
        Generate a PDF from JSON content using the specified style template.
        
        If the book exceeds max_pages_per_part, it will be split into multiple parts.
        Each part will have its own chapter numbering, TOC, etc.
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
        page_width = A4[0] - margins.get('left', 72) - margins.get('right', 72)
        page_height = A4[1] - margins.get('top', 72) - margins.get('bottom', 72)
        
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
                BaseDocTemplate.build(doc, simple_story)
                self.logger.info("Successfully built simplified PDF")
            except Exception as e2:
                self.logger.error(f"Failed to build even simplified PDF: {str(e2)}")
                raise
        
        return output_path