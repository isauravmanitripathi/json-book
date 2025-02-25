from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, PageBreak

from ..flowables import VerticalSpace

class TitlePage:
    """Component for generating the title page of a book."""
    
    def __init__(self, style_config, book_name, author_name):
        """
        Initialize title page component.
        
        Args:
            style_config (dict): Style configuration
            book_name (str): Name of the book
            author_name (str): Name of the author
        """
        self.style_config = style_config
        self.book_name = book_name
        self.author_name = author_name
        self.styles = getSampleStyleSheet()
        
    def add_to_story(self, story):
        """Add the title page to the document story."""
        title_config = self.style_config.get('title_page', {})
        spacing = title_config.get('spacing', {'top': 0.4, 'between': 0.3})
        
        # Add top spacing
        story.append(VerticalSpace(A4[1] * spacing.get('top', 0.4)))
        
        # Format title based on style
        title_style = title_config.get('title', {})
        case_format = title_style.get('case', 'upper')
        spacing_format = title_style.get('spacing', 'words')
        
        # Apply case formatting
        if case_format == 'upper':
            formatted_title = self.book_name.upper()
        elif case_format == 'lower':
            formatted_title = self.book_name.lower()
        elif case_format == 'title':
            formatted_title = self.book_name.title()
        else:
            formatted_title = self.book_name
        
        # Apply spacing formatting
        if spacing_format == 'words':
            words = formatted_title.split()
            spaced_title = '<br/>'.join(words)
        elif spacing_format == 'lines':
            spaced_title = formatted_title.replace(' ', '<br/>')
        else:
            spaced_title = formatted_title
            
        # Create title style
        book_title_style = ParagraphStyle(
            name='BookTitle',
            parent=self.styles['Heading1'],
            fontSize=title_style.get('size', 32),
            spaceAfter=0,
            spaceBefore=0,
            textColor=self._parse_color(title_style.get('color', '#2E4053')),
            alignment=1 if title_style.get('alignment') == 'center' else 0,
            fontName=title_style.get('font', 'Helvetica-Bold'),
            leading=title_style.get('size', 32) + 8
        )
        
        story.append(Paragraph(spaced_title, book_title_style))
        
        # Add spacing between title and author
        story.append(VerticalSpace(A4[1] * spacing.get('between', 0.3)))
        
        # Add author with optional prefix
        author_style = title_config.get('author', {})
        author_prefix = author_style.get('prefix', '')
        
        # Create author style
        author_style_obj = ParagraphStyle(
            name='AuthorName',
            parent=self.styles['Normal'],
            fontSize=author_style.get('size', 16),
            spaceAfter=30,
            spaceBefore=0,
            textColor=self._parse_color(author_style.get('color', '#2E4053')),
            alignment=1 if author_style.get('alignment') == 'center' else 0,
            fontName=author_style.get('font', 'Helvetica')
        )
        
        if author_prefix:
            author_text = f"{author_prefix}<br/>{self.author_name}"
        else:
            author_text = self.author_name
            
        story.append(Paragraph(author_text, author_style_obj))
        story.append(PageBreak())
        
    def _parse_color(self, color_value):
        """Parse color from string or hex value."""
        if isinstance(color_value, str):
            if color_value.startswith('#'):
                return colors.HexColor(color_value)
            else:
                return getattr(colors, color_value, colors.black)
        return colors.black