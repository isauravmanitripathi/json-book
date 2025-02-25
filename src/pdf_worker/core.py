import os
import json
import traceback
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak

from .style_manager import StyleManager
from .components.title_page import TitlePage
from .components.toc import TableOfContents
from .components.chapter import Chapter
from .components.section import Section
from .templates.book_template import BookTemplate

class PDFGenerator:
    """Generates PDF books from JSON content using style templates."""
    def __init__(self):
        self.style_manager = StyleManager()
        self.styles = getSampleStyleSheet()
        
    def generate_pdf(self, input_json_path, book_name, author_name, style_name='classic', output_dir='results/pdfs'):
        """Generate a PDF from JSON content using the specified style template."""
        try:
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Create a safe filename based on the book name
            safe_filename = "".join(x for x in book_name if x.isalnum() or x in (' ', '-', '_')).rstrip()
            output_pdf_path = os.path.join(output_dir, f"{safe_filename}.pdf")
            
            # Load the style template
            style_config = self.style_manager.load_style(style_name)
            print(f"Loaded style: {style_name}")
            
            # Create document template
            doc = BookTemplate(
                output_pdf_path,
                style_config=style_config
            )
            
            # Load content from JSON
            with open(input_json_path, 'r') as file:
                sections = json.load(file)
            
            print(f"Loaded JSON with {len(sections)} sections")
            
            # Sort sections by chapter and section number
            try:
                # Try to sort numerically first
                sections.sort(key=lambda x: (int(x.get('chapter_id', 0)), float(x.get('section_number', 0))))
                print("Sorted sections numerically")
            except (ValueError, TypeError) as e:
                # Fallback sorting if numeric conversion fails
                print(f"Numeric sorting failed: {e}, using string sorting as fallback")
                sections.sort(key=lambda x: (str(x.get('chapter_id', '')), str(x.get('section_number', ''))))
            
            # Build the story
            story = []
            
            # Add title page
            title_page = TitlePage(style_config, book_name, author_name)
            title_page.add_to_story(story)
            print("Added title page")
            
            # Add table of contents
            toc = TableOfContents(style_config, doc.toc)
            toc.add_to_story(story)
            print("Added table of contents")
            story.append(PageBreak())
            
            # Process sections and chapters
            current_chapter = None
            for section_data in sections:
                chapter_id = section_data.get('chapter_id', '')
                chapter_name = section_data.get('chapter_name', '').strip()
                
                # Add chapter page if this is a new chapter
                if chapter_id != current_chapter:
                    print(f"Processing chapter {chapter_id}: {chapter_name}")
                    chapter = Chapter(style_config, chapter_id, chapter_name)
                    chapter.add_to_story(story)
                    current_chapter = chapter_id
                
                # Add this section
                section_name = section_data.get('section_name', '').strip()
                section_text = section_data.get('text', '').strip()
                print(f"  - Section: {section_name}")
                
                section = Section(style_config, section_name, section_text)
                section.add_to_story(story)
            
            # Build the PDF
            print("Building PDF...")
            doc.build(story)
            
            print(f"PDF generated successfully: {output_pdf_path}")
            return output_pdf_path
            
        except Exception as e:
            print(f"Error generating PDF: {str(e)}")
            traceback.print_exc()
            raise