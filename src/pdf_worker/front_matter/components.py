from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, PageBreak
from reportlab.lib.pagesizes import A4
import markdown
import re

from ..flowables import VerticalSpace

class FrontMatterComponent:
    """Base class for front matter components."""
    
    def __init__(self, style_config):
        """
        Initialize the front matter component.
        
        Args:
            style_config (dict): Style configuration
        """
        self.style_config = style_config
        self.styles = getSampleStyleSheet()
        
    def add_to_story(self, story):
        """
        Add the component to the document story.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement add_to_story method")
        
    def _parse_color(self, color_value):
        """Parse color from string or hex value."""
        if isinstance(color_value, str):
            if color_value.startswith('#'):
                return colors.HexColor(color_value)
            else:
                return getattr(colors, color_value, colors.black)
        return colors.black
        
    def _convert_markdown_to_rl_markup(self, md_text):
        """Convert markdown text to ReportLab markup with improved handling."""
        try:
            html = markdown.markdown(md_text)
            
            # Replace problematic HTML tags with ReportLab markup
            
            # Headers
            html = re.sub(r'<h1>(.*?)</h1>', r'<font size="20"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
            html = re.sub(r'<h2>(.*?)</h2>', r'<font size="18"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
            html = re.sub(r'<h3>(.*?)</h3>', r'<font size="16"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
            html = re.sub(r'<h4>(.*?)</h4>', r'<font size="14"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
            html = re.sub(r'<h5>(.*?)</h5>', r'<font size="12"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
            html = re.sub(r'<h6>(.*?)</h6>', r'<font size="11"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
            
            # Text formatting
            html = re.sub(r'<strong>(.*?)</strong>', r'<b>\1</b>', html)
            html = re.sub(r'<em>(.*?)</em>', r'<i>\1</i>', html)
            html = re.sub(r'<code>(.*?)</code>', r'<font face="Courier">\1</font>', html)
            
            # Lists
            html = re.sub(r'<ul>(.*?)</ul>', r'<br/>\1<br/>', html, flags=re.DOTALL)
            html = re.sub(r'<ol>(.*?)</ol>', r'<br/>\1<br/>', html, flags=re.DOTALL)
            html = re.sub(r'<li>(.*?)</li>', r'• \1<br/>', html, flags=re.DOTALL)
            
            # Links
            html = re.sub(r'<a href="(.*?)">(.*?)</a>', r'<u><font color="blue">\2</font></u> (\1)', html)
            
            # Blockquotes - important for epigraphs
            html = re.sub(r'<blockquote>(.*?)</blockquote>', r'<i>\1</i>', html, flags=re.DOTALL)
            
            # Paragraphs - ensure good spacing
            html = re.sub(r'<p>(.*?)</p>', r'\1<br/><br/>', html, flags=re.DOTALL)
            
            # Horizontal rules
            html = re.sub(r'<hr />', r'_______________________________________________<br/><br/>', html)
            
            # Fix consecutive breaks
            html = re.sub(r'<br/><br/><br/>', r'<br/><br/>', html)
            
            return html
        except Exception as e:
            print(f"Markdown conversion error: {str(e)}")
            # Return clean text as fallback
            return self._clean_text_for_reportlab(md_text)
            
    def _clean_text_for_reportlab(self, text):
        """Clean text to make it safe for ReportLab processing."""
        # Replace special XML/HTML characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        
        # Remove control characters
        text = ''.join(c for c in text if ord(c) >= 32 or c in '\n\r\t')
        
        return text
        
    def _create_heading_style(self, name, font_size=16, font_name=None, alignment=1, color=None, space_after=12):
        """Create a heading style."""
        if not font_name:
            font_name = self.style_config.get('section', {}).get('title', {}).get('font', 'Helvetica-Bold')
            
        if not color:
            color = self.style_config.get('section', {}).get('title', {}).get('color', '#000000')
            
        return ParagraphStyle(
            name=name,
            parent=self.styles['Heading1'],
            fontSize=font_size,
            leading=font_size + 4,
            alignment=alignment,
            spaceAfter=space_after,
            textColor=self._parse_color(color),
            fontName=font_name
        )
        
    def _create_body_style(self, name, font_size=12, font_name=None, alignment=4, color=None, space_after=12):
        """Create a body text style."""
        if not font_name:
            font_name = self.style_config.get('body_text', {}).get('font', 'Helvetica')
            
        if not color:
            color = self.style_config.get('body_text', {}).get('color', '#000000')
            
        return ParagraphStyle(
            name=name,
            parent=self.styles['Normal'],
            fontSize=font_size,
            leading=font_size + 2,
            alignment=alignment,
            spaceAfter=space_after,
            textColor=self._parse_color(color),
            fontName=font_name
        )


class CenteredTextComponent(FrontMatterComponent):
    """Component for centered text content like epigraphs with responsive sizing."""
    
    def __init__(self, style_config, content, title=None):
        """
        Initialize the centered text component.
        
        Args:
            style_config (dict): Style configuration
            content (str): Markdown content to display
            title (str, optional): Optional title to display
        """
        super().__init__(style_config)
        self.content = content
        self.title = title
        
    def add_to_story(self, story):
        """Add the component to the document story with responsive sizing."""
        # Add page break
        story.append(PageBreak())
        
        # Get page dimensions from style config to calculate proportional spacing
        page_config = self.style_config.get('page', {})
        
        # Calculate responsive page size
        if page_config.get('size') == 'CUSTOM' and 'height' in page_config:
            # Custom page size
            page_height = page_config['height']
        else:
            # Default to A4 height
            page_height = A4[1]
            
        # Calculate margins to get usable height
        margins = page_config.get('margins', {'top': 72, 'bottom': 72})
        usable_height = page_height - margins.get('top', 72) - margins.get('bottom', 72)
        
        # Add proportional top spacing (25% of usable height)
        vertical_space = usable_height * 0.25
        story.append(VerticalSpace(vertical_space))
        
        # Calculate font scaling based on page size
        font_scaling_factor = min(1.0, usable_height / 700)  # 700 is a reference value for A4
        
        # Add title if provided
        if self.title:
            title_font_size = int(18 * font_scaling_factor)
            title_style = self._create_heading_style(
                name="CenteredTitle",
                font_size=max(14, title_font_size),
                alignment=1,  # Center
                space_after=24 * font_scaling_factor
            )
            story.append(Paragraph(self.title, title_style))
        
        # Convert markdown to ReportLab markup
        content_markup = self._convert_markdown_to_rl_markup(self.content)
        
        # Create centered style for content with responsive sizing
        content_font_size = int(12 * font_scaling_factor)
        content_style = self._create_body_style(
            name="CenteredContent",
            font_size=max(10, content_font_size),
            alignment=1,  # Center
            space_after=12 * font_scaling_factor,
            font_name=self.style_config.get('body_text', {}).get('font', 'Helvetica-Italic')
        )
        
        # Add content
        paragraphs = content_markup.split('<br/><br/>')
        for p in paragraphs:
            if p.strip():
                story.append(Paragraph(p, content_style))
                story.append(Spacer(1, 6 * font_scaling_factor))
                
        # Add page break
        story.append(PageBreak())


class StandardTextComponent(FrontMatterComponent):
    """Component for standard text content like preface, introduction, etc. with responsive sizing."""
    
    def __init__(self, style_config, title, content):
        """
        Initialize the standard text component.
        
        Args:
            style_config (dict): Style configuration
            title (str): Component title
            content (str): Markdown content to display
        """
        super().__init__(style_config)
        self.title = title
        self.content = content
        
    def add_to_story(self, story):
        """Add the component to the document story with responsive sizing."""
        # Add page break
        story.append(PageBreak())
        
        # Get page dimensions from style config to calculate proportional spacing
        page_config = self.style_config.get('page', {})
        
        # Calculate responsive page size
        if page_config.get('size') == 'CUSTOM' and 'height' in page_config:
            # Custom page size
            page_height = page_config['height']
        else:
            # Default to A4 height
            page_height = A4[1]
            
        # Calculate margins to get usable height
        margins = page_config.get('margins', {'top': 72, 'bottom': 72})
        usable_height = page_height - margins.get('top', 72) - margins.get('bottom', 72)
        
        # Calculate font scaling based on page size
        font_scaling_factor = min(1.0, usable_height / 700)  # 700 is a reference value for A4
        
        # Add proportional top spacing
        top_space = 60 * font_scaling_factor
        story.append(Spacer(1, top_space))
        
        # Add title with responsive sizing
        title_font_size = int(18 * font_scaling_factor)
        title_style = self._create_heading_style(
            name="FrontMatterTitle",
            font_size=max(14, title_font_size),
            alignment=1,  # Center
            space_after=24 * font_scaling_factor
        )
        story.append(Paragraph(self.title, title_style))
        
        # Convert markdown to ReportLab markup
        content_markup = self._convert_markdown_to_rl_markup(self.content)
        
        # Create style for content with responsive sizing
        content_font_size = int(11 * font_scaling_factor)
        content_style = self._create_body_style(
            name="FrontMatterContent",
            font_size=max(9, content_font_size),
            alignment=4,  # Justified
            space_after=12 * font_scaling_factor
        )
        
        # Add content
        paragraphs = content_markup.split('<br/><br/>')
        for p in paragraphs:
            if p.strip():
                story.append(Paragraph(p, content_style))
                
        # Add page break
        story.append(PageBreak())


class CopyrightComponent(FrontMatterComponent):
    """Component for copyright page with improved responsive layout."""
    
    def __init__(self, style_config, content):
        """
        Initialize the copyright component.
        
        Args:
            style_config (dict): Style configuration
            content (str): Markdown content with copyright info
        """
        super().__init__(style_config)
        self.content = content
        
    def add_to_story(self, story):
        """Add the component to the document story with responsive positioning."""
        # Add page break
        story.append(PageBreak())
        
        # Get page dimensions from style config to calculate proportional spacing
        page_config = self.style_config.get('page', {})
        
        # Calculate responsive vertical spacing based on page height
        if page_config.get('size') == 'CUSTOM' and 'height' in page_config:
            # Custom page size
            page_height = page_config['height']
        else:
            # Default to A4 height
            page_height = A4[1]
            
        # Calculate margins to get usable height
        margins = page_config.get('margins', {'top': 72, 'bottom': 72})
        usable_height = page_height - margins.get('top', 72) - margins.get('bottom', 72)
        
        # Add proportional vertical space (30% of usable height)
        vertical_space = usable_height * 0.3
        story.append(VerticalSpace(vertical_space))
        
        # Convert markdown to ReportLab markup
        content_markup = self._convert_markdown_to_rl_markup(self.content)
        
        # Create responsive style for copyright content - scale font based on page size
        font_scaling_factor = min(1.0, usable_height / 700)  # 700 is a reference value for A4
        base_font_size = 9
        scaled_font_size = max(8, int(base_font_size * font_scaling_factor))
        
        copyright_style = self._create_body_style(
            name="CopyrightText",
            font_size=scaled_font_size,
            alignment=0,  # Left aligned
            space_after=6
        )
        
        # Add content
        paragraphs = content_markup.split('<br/><br/>')
        for p in paragraphs:
            if p.strip():
                story.append(Paragraph(p, copyright_style))
                
        # Add page break
        story.append(PageBreak())