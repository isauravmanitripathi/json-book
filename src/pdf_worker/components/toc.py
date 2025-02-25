from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph

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
        
        story.append(Paragraph(title_config.get('text', 'Table of Contents'), toc_title_style))
        
        # Configure TOC level styles
        level_styles = toc_config.get('level_styles', [])
        if level_styles:
            self.toc_object.levelStyles = []
            for i, level_style in enumerate(level_styles):
                style = ParagraphStyle(
                    name=f'TOCHeading{i+1}',
                    fontSize=level_style.get('font_size', 12 - i),
                    leftIndent=level_style.get('indent', 20 + i*20),
                    leading=level_style.get('leading', 14 - i*2),
                    fontName=level_style.get('font_name', 'Helvetica')
                )
                
                # Apply italic if specified
                if level_style.get('italic', False):
                    if '-Italic' not in style.fontName:
                        style.fontName = style.fontName + '-Italic'
                
                # Apply text color
                if 'text_color' in level_style:
                    style.textColor = self._parse_color(level_style.get('text_color'))
                
                self.toc_object.levelStyles.append(style)
        
        story.append(self.toc_object)
        
    def _parse_color(self, color_value):
        """Parse color from string or hex value."""
        if isinstance(color_value, str):
            if color_value.startswith('#'):
                return colors.HexColor(color_value)
            else:
                return getattr(colors, color_value, colors.black)
        return colors.black