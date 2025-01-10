# src/pdf_worker/pdf_generator.py

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import json

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
        # Chapter style
        if 'CustomChapterTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomChapterTitle',
                parent=self.styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                spaceBefore=50,
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

    def generate_pdf(self, input_json_path, output_pdf_path):
        """Generate PDF from the input JSON file"""
        # Create PDF document
        doc = SimpleDocTemplate(
            output_pdf_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Read JSON data
        with open(input_json_path, 'r') as file:
            data = json.load(file)

        # Process articles
        story = []
        current_chapter = None
        
        # Sort articles by chapter_id (if exists) and section_number
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
                
                # Add chapter title
                chapter_title = f"Chapter {article['chapter_id']}: {chapter_name}" if article['chapter_id'] else chapter_name
                story.append(Paragraph(chapter_title, self.styles['CustomChapterTitle']))
                current_chapter = chapter_identifier

            # Add section title
            full_section_title = f"{section_number}. {section_name}"
            story.append(Paragraph(full_section_title, self.styles['CustomSectionTitle']))

            # Add section text
            story.append(Paragraph(text, self.styles['CustomBodyText']))
            story.append(Spacer(1, 20))

        # Build PDF
        doc.build(story)
        return output_pdf_path