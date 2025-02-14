# src/pdf_worker/pdf_generator.py

import os
import json
import re
import markdown
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph, Spacer, PageBreak, BaseDocTemplate, PageTemplate, Frame,
    Flowable, Table, TableStyle
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

def extract_first_markdown_heading(md_text):
    """
    Look through the markdown text line by line for the first heading.
    A heading is a line starting with # (up to 6). Return:
      (heading_level, heading_content, new_text_without_that_heading)
    If no heading is found, return (None, None, original_text).
    """
    lines = md_text.splitlines()
    for i, line in enumerate(lines):
        match = re.match(r'^(#{1,6})\s+(.*)', line.strip())
        if match:
            # Found a heading
            heading_level = len(match.group(1))  # Number of # characters
            heading_content = match.group(2).strip()
            # Remove this line from the original text
            del lines[i]
            # Return the heading info and the rest of the text
            return heading_level, heading_content, "\n".join(lines)
    # No heading found, return None
    return None, None, md_text

def convert_markdown_to_rl_markup(md_text):
    """
    Convert markdown text to ReportLab-friendly markup with improved spacing for bullet points,
    indentation, and headings. We insert <br/> tags to force newlines where appropriate.
    """

    # Convert markdown to HTML
    html = markdown.markdown(md_text)

    # Add line breaks around <ul> ... </ul> to give some extra vertical spacing before/after bullet lists
    html = re.sub(r'<ul>(.*?)</ul>', r'<br/><br/>\1<br/><br/>', html, flags=re.DOTALL)

    # Headings: we handle h1 through h6, assigning decreasing font sizes and adding blank lines
    html = re.sub(r'<h1>(.*?)</h1>', r'<font size="18"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h2>(.*?)</h2>', r'<font size="16"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h3>(.*?)</h3>', r'<font size="14"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h4>(.*?)</h4>', r'<font size="12"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h5>(.*?)</h5>', r'<font size="10"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h6>(.*?)</h6>', r'<font size="9"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)

    # Paragraphs: replace <p>...</p> with text plus two line breaks
    html = re.sub(r'<p>(.*?)</p>', r'\1<br/><br/>', html, flags=re.DOTALL)

    # List items: indent bullet points and add a line break after each
    html = re.sub(r'<li>(.*?)</li>', r'&nbsp;&nbsp;&nbsp;&nbsp;• \1<br/>', html, flags=re.DOTALL)

    # Remove any leftover <ul> or <ol> tags (we've already handled them)
    html = html.replace('<ul>', '').replace('</ul>', '')
    html = html.replace('<ol>', '').replace('</ol>', '')

    return html

class VerticalSpace(Flowable):
    """Custom Flowable for adding vertical space."""
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
            # Skip numbering on title page
            if self._pageNumber > 1:
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
        """Create custom paragraph styles for different elements."""
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
            
        if 'AuthorName' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='AuthorName',
                parent=self.styles['Normal'],
                fontSize=16,
                spaceAfter=30,
                spaceBefore=0,
                textColor=colors.HexColor('#2E4053'),
                alignment=1,
                fontName='Helvetica'
            ))

        if 'ChapterNumber' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='ChapterNumber',
                parent=self.styles['Heading1'],
                fontSize=42,
                spaceAfter=0,
                spaceBefore=0,
                textColor=colors.HexColor('#2E4053'),
                alignment=1,
                fontName='Helvetica-Bold',
                leading=50
            ))

        if 'CustomChapterTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomChapterTitle',
                parent=self.styles['Heading1'],
                fontSize=28,
                spaceAfter=0,
                spaceBefore=0,
                textColor=colors.HexColor('#2E4053'),
                alignment=1,
                fontName='Helvetica',
                leading=36
            ))

        # We'll use this style for the extracted heading from the text
        if 'CustomSectionTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomSectionTitle',
                parent=self.styles['Heading2'],
                fontSize=16,
                spaceAfter=20,
                spaceBefore=30,
                textColor=colors.HexColor('#566573'),
                alignment=1  # center
            ))

        if 'CustomBodyText' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomBodyText',
                parent=self.styles['Normal'],
                fontSize=12,
                leading=14,
                spaceAfter=12,
                alignment=4  # justified
            ))

    def _add_centered_title_page(self, story, book_name, author_name):
        """Add a vertically centered title page with spaced words."""
        story.append(VerticalSpace(A4[1] * 0.4))
        words = book_name.upper().split()
        spaced_title = '<br/>'.join(words)
        story.append(Paragraph(spaced_title, self.styles['BookTitle']))
        story.append(VerticalSpace(A4[1] * 0.3))
        story.append(Paragraph(f"By<br/>{author_name}", self.styles['AuthorName']))
        story.append(PageBreak())

    def _add_centered_chapter_page(self, story, chapter_id, chapter_name):
        """Add a redesigned, centered chapter page with a decorative table."""
        story.append(PageBreak())
        story.append(Spacer(1, A4[1] * 0.3))
        available_width = A4[0] - 2 * 72

        # Chapter number text (optional if chapter_id is provided)
        chapter_number_text = f"Chapter {chapter_id}" if chapter_id else ""
        chapter_number_para = Paragraph(chapter_number_text, ParagraphStyle(
            name='FancyChapterNumber',
            fontSize=60,
            leading=70,
            textColor=colors.white,
            alignment=1,
            fontName='Helvetica-Bold'
        ))

        chapter_title_para = Paragraph(chapter_name, ParagraphStyle(
            name='FancyChapterTitle',
            fontSize=36,
            leading=44,
            textColor=colors.white,
            alignment=1,
            fontName='Helvetica'
        ))

        data = [[chapter_number_para], [chapter_title_para]]
        chapter_table = Table(data, colWidths=[available_width])
        chapter_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2C3E50')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
            ('TOPPADDING', (0, 0), (-1, -1), 20),
        ]))
        story.append(chapter_table)
        story.append(Spacer(1, A4[1] * 0.3))
        story.append(PageBreak())

    def generate_pdf(self, input_json_path, book_name, author_name, output_dir='results/pdfs'):
        """
        Generate PDF from the input JSON file. We ignore the 'section_name' field
        and instead parse the very first markdown heading in the 'text' field
        to use as the section heading.
        """

        # Prepare output path
        safe_filename = "".join(x for x in book_name if x.isalnum() or x in (' ', '-', '_')).rstrip()
        output_pdf_path = os.path.join(output_dir, f"{safe_filename}.pdf")

        # Set up the document
        doc = BaseDocTemplate(
            output_pdf_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        template = PageTemplate(id='main', frames=frame, onPage=lambda canvas, doc: None)
        doc.addPageTemplates([template])

        # Read JSON data
        with open(input_json_path, 'r') as file:
            sections = json.load(file)

        story = []
        self._add_centered_title_page(story, book_name, author_name)

        current_chapter = None
        sections.sort(key=lambda x: (int(x['chapter_id']), x['section_number']))

        for section in sections:
            chapter_id = section['chapter_id']
            chapter_name = section['chapter_name'].strip()

            # Add a new chapter page if needed
            if chapter_id != current_chapter:
                self._add_centered_chapter_page(story, chapter_id, chapter_name)
                current_chapter = chapter_id

            # We ignore the JSON "section_name". Instead, parse the first heading from text.
            text = section['text'].strip()
            heading_level, heading_content, remaining_text = extract_first_markdown_heading(text)

            # If we found a heading in the text, display it as a centered section title
            if heading_content:
                story.append(Paragraph(heading_content, self.styles['CustomSectionTitle']))

            # Convert the rest of the text to a more ReportLab-friendly format
            rl_text = convert_markdown_to_rl_markup(remaining_text)
            story.append(Paragraph(rl_text, self.styles['CustomBodyText']))
            story.append(Spacer(1, 20))

        # Build the final PDF
        doc.build(story, canvasmaker=PageNumCanvas)
        return output_pdf_path
