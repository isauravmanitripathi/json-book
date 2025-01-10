# src/pdf_worker/pdf_generator.py

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, NextPageTemplate
from reportlab.platypus.flowables import Flowable, KeepTogether
from reportlab.pdfgen import canvas
import os
import json

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
                fontSize=24,
                spaceAfter=10,
                spaceBefore=0,
                textColor=colors.HexColor('#2E4053'),
                alignment=1
            ))

        # Chapter Title style
        if 'CustomChapterTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomChapterTitle',
                parent=self.styles['Heading1'],
                fontSize=28,
                spaceAfter=0,
                spaceBefore=10,
                textColor=colors.HexColor('#2E4053'),
                alignment=1
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
        """Add a vertically centered chapter page"""
        # Add vertical space to center the chapter title
        story.append(VerticalSpace(A4[1] * 0.4))  # Move down 40% of page height
        
        if chapter_id:
            story.append(Paragraph(f"Chapter {chapter_id}", self.styles['ChapterNumber']))
            story.append(Paragraph(f"{chapter_name}", self.styles['CustomChapterTitle']))
        else:
            story.append(Paragraph(chapter_name, self.styles['CustomChapterTitle']))
        
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
            data = json.load(file)

        # Process articles
        story = []
        
        # Add title page with author name
        self._add_centered_title_page(story, book_name, author_name)

        current_chapter = None
        
        # Sort articles
        articles = data['articles']
        articles.sort(key=lambda x: (
            x['chapter_id'] if x['chapter_id'] else x['section_number'],
            x['section_number']
        ))

        for article in articles:
            chapter_name = article['chapter_name'].strip()
            section_name = article['section_name'].strip()
            section_number = article['section_number'].strip()
            text = article['text'].strip()

            # Check if we're starting a new chapter
            chapter_identifier = article['chapter_id'] if article['chapter_id'] else chapter_name
            if chapter_identifier != current_chapter:
                # Add chapter page
                self._add_centered_chapter_page(story, article['chapter_id'], chapter_name)
                current_chapter = chapter_identifier

            # Add section title
            full_section_title = f"{section_number}. {section_name}"
            story.append(Paragraph(full_section_title, self.styles['CustomSectionTitle']))

            # Add section text
            story.append(Paragraph(text, self.styles['CustomBodyText']))
            story.append(Spacer(1, 20))

        # Build PDF with page numbers
        doc.build(story, canvasmaker=PageNumCanvas)
        return output_pdf_path