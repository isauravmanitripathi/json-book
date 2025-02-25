import re
import markdown
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer

from ..flowables import DottedLineFlowable, SolidLineFlowable

class Section:
    """Component for generating a document section."""
    
    def __init__(self, style_config, section_name, section_text):
        """
        Initialize section component.
        
        Args:
            style_config (dict): Style configuration
            section_name (str): Section name
            section_text (str): Section content text
        """
        self.style_config = style_config
        self.section_name = section_name
        self.section_text = section_text
        self.styles = getSampleStyleSheet()
        
    def add_to_story(self, story):
        """Add the section to the document story."""
        section_config = self.style_config.get('section', {})
        
        if self.section_name:
            # Create section title style
            section_title_style = ParagraphStyle(
                name='CustomSectionTitle',
                parent=self.styles['Heading2'],
                fontSize=section_config.get('title', {}).get('size', 16),
                spaceAfter=section_config.get('title', {}).get('space_after', 20),
                spaceBefore=section_config.get('title', {}).get('space_before', 30),
                textColor=self._parse_color(section_config.get('title', {}).get('color', '#566573')),
                alignment=1 if section_config.get('title', {}).get('alignment') == 'center' else 0,
                fontName=section_config.get('title', {}).get('font', 'Helvetica-Bold')
            )
            
            story.append(Paragraph(self.section_name, section_title_style))
            
            # Add divider if configured
            divider_config = section_config.get('divider', {})
            if divider_config.get('type') != 'none':
                # Add spacing before divider
                story.append(Spacer(1, divider_config.get('spacing', {}).get('before', 6)))
                
                # Add the divider line
                dotted_line_width = 450  # Approximate A4 width minus margins
                
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
        
        # Convert markdown to ReportLab markup
        rl_text = self._convert_markdown_to_rl_markup(self.section_text)
        
        # Create body text style
        body_config = self.style_config.get('body_text', {})
        alignment_map = {
            'left': 0,
            'center': 1,
            'right': 2,
            'justified': 4
        }
        alignment = alignment_map.get(body_config.get('alignment', 'justified'), 4)
        
        body_style = ParagraphStyle(
            name='CustomBodyText',
            parent=self.styles['Normal'],
            fontSize=body_config.get('size', 12),
            leading=body_config.get('leading', 14),
            spaceAfter=body_config.get('space_after', 12),
            alignment=alignment,
            fontName=body_config.get('font', 'Helvetica')
        )
        
        # Add the text with the body text style
        story.append(Paragraph(rl_text, body_style))
        story.append(Spacer(1, body_config.get('space_after', 12)))
        
    def _parse_color(self, color_value):
        """Parse color from string or hex value."""
        if isinstance(color_value, str):
            if color_value.startswith('#'):
                return colors.HexColor(color_value)
            else:
                return getattr(colors, color_value, colors.black)
        return colors.black
        
    def _convert_markdown_to_rl_markup(self, md_text):
        """Convert markdown text to ReportLab markup."""
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