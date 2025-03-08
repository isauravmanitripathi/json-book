#!/usr/bin/env python3
import logging
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, PageBreak

class Chapter:
    """Component for generating a book chapter from Markdown/HTML content."""
    
    def __init__(self, style_config, chapter_title):
        """
        Initialize chapter component.
        
        Args:
            style_config (dict): Style configuration
            chapter_title (str): Chapter title
        """
        self.logger = logging.getLogger(__name__)
        self.style_config = style_config
        self.chapter_title = chapter_title
        self.styles = getSampleStyleSheet()
        
    def add_to_story(self, story):
        """
        Add the chapter to the document story.
        
        Args:
            story (list): ReportLab story (content flow)
            
        Returns:
            None
        """
        try:
            # Add page break before chapter
            story.append(PageBreak())
            
            # Get chapter style configuration
            chapter_config = self.style_config.get('chapter', {})
            
            # Create chapter title style
            title_config = chapter_config.get('title', {})
            chapter_style = ParagraphStyle(
                name='ChapterTitle',
                parent=self.styles['Heading1'],
                fontSize=title_config.get('size', 24),
                leading=title_config.get('size', 24) + 6,
                alignment=1 if title_config.get('alignment') == 'center' else 0,
                textColor=self._parse_color(title_config.get('color', '#000000')),
                fontName=title_config.get('font', 'Helvetica-Bold'),
                spaceAfter=24
            )
            
            # Format chapter title
            if title_config.get('case') == 'upper':
                chapter_title = self.chapter_title.upper()
            elif title_config.get('case') == 'lower':
                chapter_title = self.chapter_title.lower()
            elif title_config.get('case') == 'title':
                chapter_title = self.chapter_title.title()
            else:
                chapter_title = self.chapter_title
                
            # Add chapter title to story
            story.append(Paragraph(chapter_title, chapter_style))
            
            # Add chapter number if specified
            if chapter_config.get('show_number', False) and hasattr(self, 'chapter_number'):
                number_config = chapter_config.get('number', {})
                number_style = ParagraphStyle(
                    name='ChapterNumber',
                    parent=self.styles['Heading2'],
                    fontSize=number_config.get('size', 16),
                    alignment=1 if number_config.get('alignment') == 'center' else 0,
                    textColor=self._parse_color(number_config.get('color', '#000000')),
                    fontName=number_config.get('font', 'Helvetica-Bold'),
                    spaceAfter=12
                )
                
                prefix = number_config.get('prefix', 'Chapter')
                chapter_num_text = f"{prefix} {self.chapter_number}"
                
                story.append(Paragraph(chapter_num_text, number_style))
                
            # Add spacer after chapter title
            story.append(Spacer(1, 24))
            
        except Exception as e:
            self.logger.error(f"Error adding chapter to story: {str(e)}")
            # Add a simple version as fallback
            story.append(Paragraph(self.chapter_title, self.styles['Heading1']))
    
    def _parse_color(self, color_value):
        """
        Parse color from string or hex value.
        
        Args:
            color_value (str): Color as hex code or name
            
        Returns:
            reportlab.lib.colors.Color: Color object
        """
        if isinstance(color_value, str):
            if color_value.startswith('#'):
                return colors.HexColor(color_value)
            else:
                return getattr(colors, color_value, colors.black)
        return colors.black