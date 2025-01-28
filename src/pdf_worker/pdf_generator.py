# src/pdf_worker/pdf_generator.py

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas
import os
import json
from collections import defaultdict

class VerticalSpace(Flowable):
    """Custom Flowable for adding vertical space"""
    def __init__(self, space):
        self.space = space
        
    def wrap(self, *args):
        return (0, self.space)
        
    def draw(self):
        pass

class PageNumCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            if self._pageNumber > 1:  # Skip page number on title page
                self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        page_num = self._pageNumber
        text = f"{page_num} of {page_count}"
        self.drawRightString(self._pagesize[0] - 30, 30, text)

class PDFGenerator:
    def __init__(self):
        # Register custom font if needed
        font_path = os.path.join('fonts', 'Jersey15-Regular.ttf')
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Jersey', font_path))
        
        # Initialize styles
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        """Create custom paragraph styles for different elements"""
        # Book Title style
        if 'BookTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='BookTitle',
                parent=self.styles['Heading1'],
                fontSize=32,
                spaceAfter=0,
                spaceBefore=0,
                textColor=colors.HexColor('#2E4053'),
                alignment=1,
                fontName='Helvetica-Bold',
                leading=40
            ))
            
        # Author style
        if 'AuthorName' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='AuthorName',
                parent=self.styles['Normal'],
                fontSize=16,
                spaceAfter=30,
                spaceBefore=0,
                textColor=colors.HexColor('#2E4053'),
                alignment=1,  # Center alignment
                fontName='Helvetica'
            ))

        # Chapter Number style
        if 'ChapterNumber' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='ChapterNumber',
                parent=self.styles['Heading1'],
                fontSize=42,  # Larger font for chapter number
                spaceAfter=0,
                spaceBefore=0,
                textColor=colors.HexColor('#2E4053'),
                alignment=1,  # Centered
                fontName='Helvetica-Bold',
                leading=50  # Extra line height for better spacing
            ))

        # Chapter Title style
        if 'CustomChapterTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomChapterTitle',
                parent=self.styles['Heading1'],
                fontSize=28,  # Smaller than chapter number
                spaceAfter=0,
                spaceBefore=0,
                textColor=colors.HexColor('#2E4053'),
                alignment=1,  # Centered
                fontName='Helvetica',
                leading=36  # Extra line height for better spacing
            ))

        # Section style
        if 'CustomSectionTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomSectionTitle',
                parent=self.styles['Heading2'],
                fontSize=16,
                spaceAfter=20,
                spaceBefore=30,
                textColor=colors.HexColor('#566573')
            ))

        # Body text style
        if 'CustomBodyText' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomBodyText',
                parent=self.styles['Normal'],
                fontSize=12,
                leading=14,
                spaceAfter=12,
                alignment=4  # Justified alignment
            ))

    def _add_centered_title_page(self, story, book_name, author_name):
        """Add a vertically centered title page with spaced words"""
        # Add vertical space to center the title
        story.append(VerticalSpace(A4[1] * 0.4))  # Move down 40% of page height
        
        # Split the book name into words and join with line breaks
        words = book_name.upper().split()
        spaced_title = '<br/>'.join(words)
        story.append(Paragraph(spaced_title, self.styles['BookTitle']))
        
        # Add author name at the bottom of the page
        story.append(VerticalSpace(A4[1] * 0.3))  # Add space between title and author
        story.append(Paragraph(f"By<br/>{author_name}", self.styles['AuthorName']))
        
        story.append(PageBreak())

    def _add_centered_chapter_page(self, story, chapter_id, chapter_name):
        """Add a perfectly centered chapter page with clean layout"""
        # Force a page break before the chapter page
        story.append(PageBreak())
        
        # Center content vertically
        story.append(VerticalSpace(A4[1] * 0.4))  # Move down 40% of page height
        
        # Clean up chapter name - remove any \n characters and extra spaces
        chapter_name = ' '.join(chapter_name.replace('\n', ' ').split())
        
        # Create chapter styles with perfect centering
        chapter_number_style = ParagraphStyle(
            'ChapterNumber',
            parent=self.styles['ChapterNumber'],
            alignment=1,  # Center alignment
            spaceBefore=0,
            spaceAfter=30,  # Space between number and title
        )
        
        chapter_title_style = ParagraphStyle(
            'ChapterTitle',
            parent=self.styles['CustomChapterTitle'],
            alignment=1,  # Center alignment
            spaceBefore=0,
            spaceAfter=0,
        )

        # Add chapter number (if exists)
        if chapter_id:
            story.append(Paragraph(f"Chapter {chapter_id}", chapter_number_style))
            if chapter_name and chapter_name.strip():
                story.append(Paragraph(chapter_name, chapter_title_style))
        else:
            story.append(Paragraph(chapter_name, chapter_title_style))

        # Force a page break after the chapter page
        story.append(PageBreak())

    def generate_pdf(self, input_json_path, book_name, author_name, output_dir='results/pdfs'):
        """Generate PDF from the input JSON file"""
        # Create output filename from book name
        safe_filename = "".join(x for x in book_name if x.isalnum() or x in (' ', '-', '_')).rstrip()
        output_pdf_path = os.path.join(output_dir, f"{safe_filename}.pdf")
        
        # Create PDF document
        doc = BaseDocTemplate(
            output_pdf_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Create page template
        frame = Frame(
            doc.leftMargin,
            doc.bottomMargin,
            doc.width,
            doc.height,
            id='normal'
        )
        template = PageTemplate(id='main', frames=frame, onPage=lambda canvas, doc: None)
        doc.addPageTemplates([template])

        # Read JSON data
        with open(input_json_path, 'r') as file:
            sections = json.load(file)

        # Create story for the PDF
        story = []
        
        # Add title page with author name
        self._add_centered_title_page(story, book_name, author_name)

        # Group sections by chapter
        current_chapter = None
        
        # Sort sections by chapter_id and section_number
        sections.sort(key=lambda x: (int(x['chapter_id']), x['section_number']))
        
        for section in sections:
            chapter_id = section['chapter_id']
            chapter_name = section['chapter_name'].strip()
            
            # If we're starting a new chapter, add the chapter page
            if chapter_id != current_chapter:
                self._add_centered_chapter_page(story, chapter_id, chapter_name)
                current_chapter = chapter_id
            
            # Add section content
            section_name = section['section_name'].strip()
            section_number = section['section_number'].strip()
            text = section['text'].strip()

            # Add section title
            full_section_title = f"{section_number}. {section_name}"
            story.append(Paragraph(full_section_title, self.styles['CustomSectionTitle']))

            # Add section text
            story.append(Paragraph(text, self.styles['CustomBodyText']))
            story.append(Spacer(1, 20))

        # Build PDF with page numbers
        doc.build(story, canvasmaker=PageNumCanvas)
        return output_pdf_path