#!/usr/bin/env python3
import logging
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from reportlab.platypus import Paragraph, Preformatted
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT

class CodeFormatter:
    """Format code blocks for PDF rendering with syntax highlighting."""
    
    def __init__(self):
        """Initialize the code formatter."""
        self.logger = logging.getLogger(__name__)
        self.styles = getSampleStyleSheet()
        
    def format_code_block(self, code, language=None):
        """
        Format a code block for PDF rendering.
        
        Args:
            code (str): The code to format
            language (str, optional): Programming language for syntax highlighting
            
        Returns:
            reportlab.platypus.Flowable: A reportlab flowable object for the PDF
        """
        try:
            # Create a code style
            code_style = ParagraphStyle(
                name='CodeBlock',
                parent=self.styles['Code'],
                fontName='Courier',
                fontSize=9,
                leading=12,
                leftIndent=20,
                rightIndent=20,
                spaceBefore=10,
                spaceAfter=10,
                backColor=colors.lightgrey,
                borderPadding=5,
                borderWidth=1,
                borderColor=colors.grey,
                alignment=TA_LEFT
            )
            
            # Create preformatted text for the code
            formatted_code = Preformatted(code, code_style)
            
            return formatted_code
            
        except Exception as e:
            self.logger.error(f"Error formatting code block: {str(e)}")
            # Fallback to simple formatting
            return Paragraph(f"<pre>{code}</pre>", self.styles['Normal'])
    
    def highlight_code(self, code, language):
        """
        Apply syntax highlighting to code.
        
        Args:
            code (str): The code to highlight
            language (str): Programming language for syntax highlighting
            
        Returns:
            str: HTML formatted code with syntax highlighting
        """
        try:
            if language and language != 'text':
                lexer = get_lexer_by_name(language, stripall=True)
            else:
                lexer = guess_lexer(code)
                
            formatter = HtmlFormatter(style='colorful')
            result = highlight(code, lexer, formatter)
            
            # Remove surrounding <div> and <pre> tags as we'll apply our own styles
            result = result.replace('<div class="highlight">', '').replace('</div>', '')
            result = result.replace('<pre>', '').replace('</pre>', '')
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error highlighting code: {str(e)}")
            return code  # Return original code as fallback