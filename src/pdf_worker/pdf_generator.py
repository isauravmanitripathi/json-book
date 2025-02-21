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
    html = markdown.markdown(md_text)
    html = re.sub(r'<ul>(.*?)</ul>', r'<br/><br/>\1<br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h1>(.*?)</h1>', r'<font size="18"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h2>(.*?)</h2>', r'<font size="16"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h3>(.*?)</h3>', r'<font size="14"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h4>(.*?)</h4>', r'<font size="12"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h5>(.*?)</h5>', r'<font size="10"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h6>(.*?)</h6>', r'<font size="9"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<p>(.*?)</p>', r'\1<br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<li>(.*?)</li>', r'&nbsp;&nbsp;&nbsp;&nbsp;• \1<br/>', html, flags=re.DOTALL)
    html = html.replace('<ul>', '').replace('</ul>', '')
    html = html.replace('<ol>', '').replace('</ol>', '')
    return html

class VerticalSpace(Flowable):
    def __init__(self, space):
        self.space = space
    def wrap(self, *args):
        return (0, self.space)
    def draw(self):
        pass

class DottedLineFlowable(Flowable):
    """
    Draws a dotted (dashed) horizontal line across the given width.
    """
    def __init__(self, width, line_width=1, dash=(1,2), color=colors.black):
        super().__init__()
        self.width = width
        self.line_width = line_width
        self.dash = dash
        self.color = color
    def wrap(self, available_width, available_height):
        return (self.width, self.line_width)
    def draw(self):
        self.canv.saveState()
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.line_width)
        self.canv.setDash(self.dash)
        self.canv.line(0, 0, self.width, 0)
        self.canv.restoreState()

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
            if self._pageNumber > 1:
                self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        text = f"{self._pageNumber} of {page_count}"
        self.drawRightString(self._pagesize[0] - 30, 30, text)

class MyDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self.allowSplitting = 1
        self.toc = TableOfContents()
        self.toc.levelStyles = [
            ParagraphStyle(name='TOCHeading1', fontSize=12, leftIndent=20, leading=14),
            ParagraphStyle(name='TOCHeading2', fontSize=10, leftIndent=40, leading=12),
        ]
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            style_name = flowable.style.name
            text = flowable.getPlainText()
            if style_name == 'FancyChapterTitle':
                self.notify('TOCEntry', (0, text, self.page))
            elif style_name == 'CustomSectionTitle':
                self.notify('TOCEntry', (1, text, self.page))

class PDFGenerator:
    def __init__(self):
        font_path = os.path.join('fonts', 'Alegreya-Italic.ttf')
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Jersey', font_path))
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
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
        story.append(VerticalSpace(A4[1] * 0.4))
        words = book_name.upper().split()
        spaced_title = '<br/>'.join(words)
        story.append(Paragraph(spaced_title, self.styles['BookTitle']))
        story.append(VerticalSpace(A4[1] * 0.3))
        story.append(Paragraph(f"By<br/>{author_name}", self.styles['AuthorName']))
        story.append(PageBreak())

    def _add_centered_chapter_page(self, story, chapter_id, chapter_name):
        story.append(PageBreak())
        story.append(Spacer(1, A4[1] * 0.25))
        # Define a style for the chapter number and title
        chap_num_style = ParagraphStyle(
            name='ChapterNumberStyle',
            parent=self.styles['Heading1'],
            fontSize=14,
            leading=16,
            alignment=1,
            textColor=colors.black
        )
        chap_title_style = ParagraphStyle(
            name='ChapterTitleStyle',
            parent=self.styles['Heading1'],
            fontSize=16,
            leading=18,
            alignment=1,
            textColor=colors.black
        )
        chapter_number_text = f"CHAPTER {chapter_id}"
        story.append(Paragraph(chapter_number_text, chap_num_style))
        story.append(Spacer(1, 6))
        # Add a dotted line drawn across the available width
        dotted_line_width = A4[0] - 2 * 72
        story.append(DottedLineFlowable(dotted_line_width))
        story.append(Spacer(1, 12))
        chapter_name_upper = chapter_name.upper()
        story.append(Paragraph(chapter_name_upper, chap_title_style))
        story.append(Spacer(1, 6))
        story.append(DottedLineFlowable(dotted_line_width))
        story.append(PageBreak())

    def generate_pdf(self, input_json_path, book_name, author_name, output_dir='results/pdfs'):
        os.makedirs(output_dir, exist_ok=True)
        safe_filename = "".join(x for x in book_name if x.isalnum() or x in (' ', '-', '_')).rstrip()
        output_pdf_path = os.path.join(output_dir, f"{safe_filename}.pdf")
        doc = MyDocTemplate(
            output_pdf_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        template = PageTemplate(id='main', frames=frame)
        doc.addPageTemplates([template])
        with open(input_json_path, 'r') as file:
            sections = json.load(file)
        sections.sort(key=lambda x: (int(x['chapter_id']), x['section_number']))
        story = []
        self._add_centered_title_page(story, book_name, author_name)
        story.append(Paragraph("Table of Contents", ParagraphStyle(
            name='TOCTitle',
            fontSize=18,
            leading=22,
            alignment=1,
            spaceAfter=20
        )))
        story.append(doc.toc)
        story.append(PageBreak())
        current_chapter = None
        for section in sections:
            chapter_id = section['chapter_id']
            chapter_name = section['chapter_name'].strip()
            if chapter_id != current_chapter:
                self._add_centered_chapter_page(story, chapter_id, chapter_name)
                current_chapter = chapter_id
            section_name = section['section_name'].strip()
            if section_name:
                story.append(Paragraph(section_name, self.styles['CustomSectionTitle']))
                story.append(Spacer(1, 6))
                dotted_line_width = A4[0] - 2 * 72
                story.append(DottedLineFlowable(dotted_line_width))
                story.append(Spacer(1, 12))
            text = section['text'].strip()
            rl_text = convert_markdown_to_rl_markup(text)
            story.append(Paragraph(rl_text, self.styles['CustomBodyText']))
            story.append(Spacer(1, 20))
        doc.multiBuild(story, canvasmaker=PageNumCanvas)
        return output_pdf_path
