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

class PageNumCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
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
                spaceAfter=30,
                spaceBefore=100,
                textColor=colors.HexColor('#2E4053'),
                alignment=1,  # Center alignment
                fontName='Helvetica-Bold'
            ))

        # Chapter Number style
        if 'ChapterNumber' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='ChapterNumber',
                parent=self.styles['Heading1'],
                fontSize=24,
                spaceAfter=10,
                spaceBefore=100,
                textColor=colors.HexColor('#2E4053'),
                alignment=1  # Center alignment
            ))

        # Chapter Title style
        if 'CustomChapterTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomChapterTitle',
                parent=self.styles['Heading1'],
                fontSize=28,
                spaceAfter=30,
                spaceBefore=10,
                textColor=colors.HexColor('#2E4053'),
                alignment=1  # Center alignment
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

    def generate_pdf(self, input_json_path, book_name, output_dir='results/pdfs'):
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
        
        # Add title page
        story.append(Paragraph(book_name.upper(), self.styles['BookTitle']))
        story.append(PageBreak())

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
                # Add page break if not the first chapter
                if current_chapter is not None:
                    story.append(PageBreak())
                
                # Add chapter number and title separately
                if article['chapter_id']:
                    story.append(Paragraph(f"Chapter {article['chapter_id']}", self.styles['ChapterNumber']))
                    story.append(Paragraph(f"{chapter_name}", self.styles['CustomChapterTitle']))
                else:
                    story.append(Paragraph(chapter_name, self.styles['CustomChapterTitle']))
                
                current_chapter = chapter_identifier
                # Add page break after chapter title
                story.append(PageBreak())

            # Add section title
            full_section_title = f"{section_number}. {section_name}"
            story.append(Paragraph(full_section_title, self.styles['CustomSectionTitle']))

            # Add section text
            story.append(Paragraph(text, self.styles['CustomBodyText']))
            story.append(Spacer(1, 20))

        # Build PDF with page numbers
        doc.build(story, canvasmaker=PageNumCanvas)
        return output_pdf_path