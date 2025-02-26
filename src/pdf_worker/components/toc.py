# Updated src/pdf_worker/components/toc.py

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer

class TableOfContents:
    """Component for generating the table of contents."""
    
    def __init__(self, style_config, toc_object):
        """
        Initialize table of contents component.
        
        Args:
            style_config (dict): Style configuration
            toc_object: The ReportLab TableOfContents object
        """
        self.style_config = style_config
        self.toc_object = toc_object
        self.styles = getSampleStyleSheet()
        
    def add_to_story(self, story):
        """Add the table of contents to the document story."""
        toc_config = self.style_config.get('table_of_contents', {})
        title_config = toc_config.get('title', {})
        
        # Create TOC title style
        toc_title_style = ParagraphStyle(
            name='TOCTitle',
            fontSize=title_config.get('size', 18),
            leading=title_config.get('size', 18) + 4,
            alignment=1 if title_config.get('alignment') == 'center' else 0,
            spaceAfter=20,
            fontName=title_config.get('font', 'Helvetica-Bold')
        )
        
        # Add the TOC title
        toc_title_text = title_config.get('text', 'Table of Contents')
        story.append(Paragraph(toc_title_text, toc_title_style))
        
        # Add some space after the title
        story.append(Spacer(1, 10))
        
        # Ensure TOC has proper styles
        level_styles = toc_config.get('level_styles', [])
        if level_styles:
            # Configure existing TOC object (should already be configured in BookTemplate)
            pass
            
        # Add the TOC object to the story
        story.append(self.toc_object)
        
    def _parse_color(self, color_value):
        """Parse color from string or hex value."""
        if isinstance(color_value, str):
            if color_value.startswith('#'):
                return colors.HexColor(color_value)
            else:
                return getattr(colors, color_value, colors.black)
        return colors.black