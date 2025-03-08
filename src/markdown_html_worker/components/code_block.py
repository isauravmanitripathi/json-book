#!/usr/bin/env python3
import logging
from reportlab.platypus import Preformatted, Paragraph
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT

class CodeBlock:
    """Component for generating a code block in the PDF document."""
    
    def __init__(self, style_config, code, language=None):
        """
        Initialize code block component.
        
        Args:
            style_config (dict): Style configuration
            code (str): The code to format
            language (str, optional): Programming language for syntax highlighting
        """
        self.logger = logging.getLogger(__name__)
        self.style_config = style_config
        self.code = code
        self.language = language
        self.styles = getSampleStyleSheet()
        
    def add_to_story(self, story):
        """
        Add the code block to the document story.
        
        Args:
            story (list): ReportLab story (content flow)
            
        Returns:
            None
        """
        try:
            # Get code style configuration
            code_config = self.style_config.get('code_block', {})
            
            # Create code style
            code_style = ParagraphStyle(
                name='CodeBlock',
                parent=self.styles['Code'],
                fontName='Courier',
                fontSize=code_config.get('size', 9),
                leading=code_config.get('leading', 12),
                leftIndent=code_config.get('left_indent', 20),
                rightIndent=code_config.get('right_indent', 20),
                spaceBefore=code_config.get('space_before', 10),
                spaceAfter=code_config.get('space_after', 10),
                backColor=self._parse_color(code_config.get('background_color', '#f5f5f5')),
                borderPadding=code_config.get('border_padding', 5),
                borderWidth=code_config.get('border_width', 1),
                borderColor=self._parse_color(code_config.get('border_color', '#cccccc')),
                alignment=TA_LEFT
            )
            
            # Clean up the code
            cleaned_code = self._clean_code(self.code)
            
            # Add language label if provided
            if self.language and self.language != 'text':
                language_style = ParagraphStyle(
                    name='LanguageLabel',
                    parent=self.styles['Normal'],
                    fontSize=8,
                    textColor=colors.gray,
                    alignment=TA_LEFT,
                    spaceBefore=2,
                    spaceAfter=2
                )
                story.append(Paragraph(f"<i>{self.language}</i>", language_style))
            
            # Create preformatted text for the code
            formatted_code = Preformatted(cleaned_code, code_style)
            story.append(formatted_code)
            
        except Exception as e:
            self.logger.error(f"Error adding code block to story: {str(e)}")
            # Add a simple version as fallback
            story.append(Paragraph(f"<pre>{self.code}</pre>", self.styles['Normal']))
    
    def _clean_code(self, code):
        """
        Clean code for safe rendering in PDF.
        
        Args:
            code (str): Raw code
            
        Returns:
            str: Cleaned code
        """
        # Escape special characters
        code = code.replace('&', '&amp;')
        code = code.replace('<', '&lt;')
        code = code.replace('>', '&gt;')
        
        return code
    
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
                return getattr(colors, color_value, colors.lightgrey)
        return colors.lightgrey