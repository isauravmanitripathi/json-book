from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, PageBreak

from ..flowables import DottedLineFlowable, SolidLineFlowable

class Chapter:
    """Component for generating a book chapter."""
    
    def __init__(self, style_config, chapter_id, chapter_name):
        """
        Initialize chapter component.
        
        Args:
            style_config (dict): Style configuration
            chapter_id (str): Chapter ID or number
            chapter_name (str): Chapter name
        """
        self.style_config = style_config
        self.chapter_id = chapter_id
        self.chapter_name = chapter_name
        self.styles = getSampleStyleSheet()
        
    def add_to_story(self, story):
        """Add the chapter to the document story."""
        chapter_config = self.style_config.get('chapter', {})
        
        # Add page break before chapter if configured
        if chapter_config.get('page_break', {}).get('before', True):
            story.append(PageBreak())
        
        # Add spacing at top of page
        story.append(Spacer(1, A4[1] * 0.25))
        
        # Format chapter number
        number_config = chapter_config.get('number', {})
        number_prefix = number_config.get('prefix', 'CHAPTER')
        chapter_number_text = f"{number_prefix} {self.chapter_id}"
        if number_config.get('case', '') == 'upper':
            chapter_number_text = chapter_number_text.upper()
            
        # Create chapter number style
        chapter_num_style = ParagraphStyle(
            name='ChapterNumberStyle',
            parent=self.styles['Heading1'],
            fontSize=number_config.get('size', 14),
            leading=number_config.get('size', 14) + 2,
            alignment=1 if number_config.get('alignment') == 'center' else 0,
            textColor=self._parse_color(number_config.get('color', '#000000')),
            fontName=number_config.get('font', 'Helvetica-Bold')
        )
            
        story.append(Paragraph(chapter_number_text, chapter_num_style))
        
        # Add divider if configured
        divider_config = chapter_config.get('divider', {})
        if divider_config.get('type') != 'none':
            # Add spacing before divider
            story.append(Spacer(1, divider_config.get('spacing', {}).get('before', 6)))
            
            # Add the divider line
            dotted_line_width = A4[0] - 2 * 72
            
            if divider_config.get('type') == 'dotted':
                story.append(DottedLineFlowable(
                    dotted_line_width,
                    line_width=divider_config.get('width', 1),
                    color=self._parse_color(divider_config.get('color', '#000000'))
                ))
            elif divider_config.get('type') == 'solid':
                story.append(SolidLineFlowable(
                    dotted_line_width,
                    line_width=divider_config.get('width', 1),
                    color=self._parse_color(divider_config.get('color', '#000000'))
                ))
            
            # Add spacing after divider
            story.append(Spacer(1, divider_config.get('spacing', {}).get('after', 12)))
        
        # Format chapter title
        title_config = chapter_config.get('title', {})
        if title_config.get('case', '') == 'upper':
            chapter_name = self.chapter_name.upper()
        elif title_config.get('case', '') == 'lower':
            chapter_name = self.chapter_name.lower()
        elif title_config.get('case', '') == 'title':
            chapter_name = self.chapter_name.title()
        else:
            chapter_name = self.chapter_name
            
        # Create chapter title style
        chapter_title_style = ParagraphStyle(
            name='ChapterTitleStyle',
            parent=self.styles['Heading1'],
            fontSize=title_config.get('size', 16),
            leading=title_config.get('size', 16) + 2,
            alignment=1 if title_config.get('alignment') == 'center' else 0,
            textColor=self._parse_color(title_config.get('color', '#000000')),
            fontName=title_config.get('font', 'Helvetica-Bold')
        )
            
        story.append(Paragraph(chapter_name, chapter_title_style))
        
        # Add subtitle if provided in the chapter config
        if 'subtitle' in chapter_config and chapter_config.get('subtitle', {}).get('text'):
            subtitle_config = chapter_config.get('subtitle', {})
            subtitle_text = subtitle_config.get('text')
            subtitle_style = ParagraphStyle(
                name='ChapterSubtitleStyle',
                parent=self.styles['Heading2'],
                fontSize=subtitle_config.get('size', 14),
                leading=subtitle_config.get('size', 14) + 2,
                alignment=1 if subtitle_config.get('alignment') == 'center' else 0,
                textColor=self._parse_color(subtitle_config.get('color', '#333333')),
                fontName=subtitle_config.get('font', 'Times-Italic'),
                italic=subtitle_config.get('italic', True)
            )
            story.append(Spacer(1, 12))
            story.append(Paragraph(subtitle_text, subtitle_style))
        
        # Add bottom divider if needed
        if divider_config.get('type') != 'none':
            story.append(Spacer(1, divider_config.get('spacing', {}).get('before', 6)))
            
            dotted_line_width = A4[0] - 2 * 72
            
            if divider_config.get('type') == 'dotted':
                story.append(DottedLineFlowable(
                    dotted_line_width,
                    line_width=divider_config.get('width', 1),
                    color=self._parse_color(divider_config.get('color', '#000000'))
                ))
            elif divider_config.get('type') == 'solid':
                story.append(SolidLineFlowable(
                    dotted_line_width,
                    line_width=divider_config.get('width', 1),
                    color=self._parse_color(divider_config.get('color', '#000000'))
                ))
        
        # Add page break after chapter if configured
        if chapter_config.get('page_break', {}).get('after', True):
            story.append(PageBreak())
            
    def _parse_color(self, color_value):
        """Parse color from string or hex value."""
        if isinstance(color_value, str):
            if color_value.startswith('#'):
                return colors.HexColor(color_value)
            else:
                return getattr(colors, color_value, colors.black)
        return colors.black