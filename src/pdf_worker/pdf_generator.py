import os
import json
import re
import markdown
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph, Spacer, PageBreak, Frame, PageTemplate, Flowable, Table, TableStyle
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus.doctemplate import BaseDocTemplate

def convert_markdown_to_rl_markup(md_text):
    """
    Convert markdown text to ReportLab-friendly markup with improved spacing,
    indentation for bullets, etc.
    """
    html = markdown.markdown(md_text)

    # Extra spacing around bullet lists
    html = re.sub(r'<ul>(.*?)</ul>', r'<br/><br/>\1<br/><br/>', html, flags=re.DOTALL)

    # Headings (h1-h6)
    html = re.sub(r'<h1>(.*?)</h1>', r'<font size="18"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h2>(.*?)</h2>', r'<font size="16"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h3>(.*?)</h3>', r'<font size="14"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h4>(.*?)</h4>', r'<font size="12"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h5>(.*?)</h5>', r'<font size="10"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h6>(.*?)</h6>', r'<font size="9"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)

    # Paragraphs
    html = re.sub(r'<p>(.*?)</p>', r'\1<br/><br/>', html, flags=re.DOTALL)

    # List items
    html = re.sub(r'<li>(.*?)</li>', r'&nbsp;&nbsp;&nbsp;&nbsp;• \1<br/>', html, flags=re.DOTALL)

    # Remove leftover <ul>/<ol> tags
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
    """
    Custom Canvas that draws page numbers. We'll skip numbering on the title page
    and place the page count at bottom-right.
    """
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
            if self._pageNumber > 1:  # Skip page number on the first page (title page)
                self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        text = f"{self._pageNumber} of {page_count}"
        self.drawRightString(self._pagesize[0] - 30, 30, text)

class MyDocTemplate(BaseDocTemplate):
    """
    Custom DocTemplate that supports building a Table of Contents at the beginning.
    We store references to headings in afterFlowable and notify the TOC.
    """
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self.allowSplitting = 1

        # Create a table of contents object
        self.toc = TableOfContents()
        self.toc.levelStyles = [
            ParagraphStyle(name='TOCHeading1', fontSize=12, leftIndent=20, leading=14),
            ParagraphStyle(name='TOCHeading2', fontSize=10, leftIndent=40, leading=12),
        ]
        # You can add more styles for deeper heading levels if needed.

    def afterFlowable(self, flowable):
        """
        Called by the framework after every Flowable is processed. If the flowable
        is a Paragraph with one of our known styles (chapter or section), we notify
        the TOC so that it records the text and the page number.
        """
        if isinstance(flowable, Paragraph):
            # Check the style name to decide if it's a "chapter" or "section" in the TOC
            style_name = flowable.style.name
            text = flowable.getPlainText()

            # Suppose we consider "FancyChapterTitle" as level-0 heading, "CustomSectionTitle" as level-1
            if style_name == 'FancyChapterTitle':
                # level-0 entry
                self.notify('TOCEntry', (0, text, self.page))
            elif style_name == 'CustomSectionTitle':
                # level-1 entry
                self.notify('TOCEntry', (1, text, self.page))

class PDFGenerator:
    def __init__(self):
        # Register custom font if needed
        font_path = os.path.join('fonts', 'Alegreya-Italic.ttf')
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Jersey', font_path))

        # Initialize styles
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        """Create custom paragraph styles for chapters, sections, etc."""
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

        # We will treat 'FancyChapterTitle' as a level-0 heading for the TOC
        if 'FancyChapterNumber' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='FancyChapterNumber',
                parent=self.styles['Heading1'],
                fontSize=60,
                textColor=colors.white,
                alignment=1,
                leading=70
            ))

        if 'FancyChapterTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='FancyChapterTitle',
                parent=self.styles['Heading1'],
                fontSize=36,
                textColor=colors.white,
                alignment=1,
                leading=44
            ))

        # We'll treat 'CustomSectionTitle' as a level-1 heading for the TOC
        if 'CustomSectionTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomSectionTitle',
                parent=self.styles['Heading2'],
                fontSize=16,
                spaceAfter=20,
                spaceBefore=30,
                textColor=colors.HexColor('#566573'),
                alignment=1
            ))

        if 'CustomBodyText' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomBodyText',
                parent=self.styles['Normal'],
                fontSize=12,
                leading=14,
                spaceAfter=12,
                alignment=4
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
        """
        Add a redesigned, centered chapter page with a decorative table.
        We'll put the 'FancyChapterTitle' style for the main text,
        so it becomes a level-0 heading in the TOC.
        """
        story.append(PageBreak())
        story.append(Spacer(1, A4[1] * 0.3))
        available_width = A4[0] - 2 * 72

        # Chapter number text
        chapter_number_text = f"Chapter {chapter_id}" if chapter_id else ""
        chapter_number_para = Paragraph(chapter_number_text, self.styles['FancyChapterNumber'])
        chapter_title_para = Paragraph(chapter_name, self.styles['FancyChapterTitle'])

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
        Generate PDF from the input JSON file, with a Table of Contents placed
        after the title page but before the chapters. The 'FancyChapterTitle' style
        is recorded in the TOC as level-0 headings, and 'CustomSectionTitle' style
        is recorded as level-1 headings.
        """
        os.makedirs(output_dir, exist_ok=True)
        safe_filename = "".join(x for x in book_name if x.isalnum() or x in (' ', '-', '_')).rstrip()
        output_pdf_path = os.path.join(output_dir, f"{safe_filename}.pdf")

        # Create our custom DocTemplate that supports a Table of Contents
        doc = MyDocTemplate(
            output_pdf_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Define a single frame for all pages
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        template = PageTemplate(id='main', frames=frame)
        doc.addPageTemplates([template])

        # Read sections from JSON
        with open(input_json_path, 'r') as file:
            sections = json.load(file)

        # Sort sections
        sections.sort(key=lambda x: (int(x['chapter_id']), x['section_number']))

        story = []

        # 1) Title Page
        self._add_centered_title_page(story, book_name, author_name)

        # 2) Table of Contents placeholder
        # We'll add a heading "Table of Contents", then the actual TOC flowable
        story.append(Paragraph("Table of Contents", ParagraphStyle(
            name='TOCTitle',
            fontSize=18,
            leading=22,
            alignment=1,  # center
            spaceAfter=20
        )))
        # Add the doc's built-in TOC flowable
        story.append(doc.toc)
        story.append(PageBreak())

        # 3) Chapters and sections
        current_chapter = None
        for section in sections:
            chapter_id = section['chapter_id']
            chapter_name = section['chapter_name'].strip()

            if chapter_id != current_chapter:
                # New chapter page
                self._add_centered_chapter_page(story, chapter_id, chapter_name)
                current_chapter = chapter_id

            # Instead of using section_name as a separate heading, let's show it with 'CustomSectionTitle'
            # if you want to treat them as sub-headings in the TOC
            section_name = section['section_name'].strip()
            if section_name:
                story.append(Paragraph(section_name, self.styles['CustomSectionTitle']))

            # Convert markdown text
            text = section['text'].strip()
            rl_text = convert_markdown_to_rl_markup(text)
            story.append(Paragraph(rl_text, self.styles['CustomBodyText']))
            story.append(Spacer(1, 20))

        # 4) Build the PDF in multi-pass so that the Table of Contents gets correct page numbers
        doc.multiBuild(story, canvasmaker=PageNumCanvas)

        return output_pdf_path
