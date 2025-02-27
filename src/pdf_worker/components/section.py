import re
import markdown
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer

from ..flowables import DottedLineFlowable, SolidLineFlowable
from ..image_handler import ImageHandler

class Section:
    """Component for generating a document section."""
    
    def __init__(self, style_config, section_name, section_text, section_data=None, image_handler=None):
        """
        Initialize section component.
        
        Args:
            style_config (dict): Style configuration
            section_name (str): Section name
            section_text (str): Section content text
            section_data (dict, optional): Full section data including images
            image_handler (ImageHandler, optional): Image handler instance
        """
        self.style_config = style_config
        self.section_name = section_name if section_name else ""
        self.section_text = section_text if section_text else ""
        self.section_data = section_data or {}
        self.image_handler = image_handler
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
            
            # Handle potential encoding or special character issues in section name
            try:
                story.append(Paragraph(self.section_name, section_title_style))
            except Exception as e:
                print(f"Error adding section title: {str(e)}")
                # Try a simplified version
                safe_title = ''.join(c for c in self.section_name if ord(c) < 128)  # Remove non-ASCII chars
                story.append(Paragraph(safe_title, section_title_style))
            
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
        
        # Skip if no text content
        if not self.section_text:
            # Check if there are images without text
            if self.image_handler and self.section_data.get('images'):
                # Create body text style for image captions
                body_config = self.style_config.get('body_text', {})
                body_style = self._create_body_style(body_config)
                
                # Process images
                image_flowables = self.image_handler.process_section_images(self.section_data, body_style)
                
                # Add images to story
                for flowable in image_flowables:
                    story.append(flowable)
            return
            
        try:
            # Convert markdown to ReportLab markup
            rl_text = self._convert_markdown_to_rl_markup(self.section_text)
            
            # Create body text style
            body_config = self.style_config.get('body_text', {})
            body_style = self._create_body_style(body_config)
            
            # Check if there are images to process
            if self.image_handler and self.section_data.get('images'):
                # Process images
                image_flowables = self.image_handler.process_section_images(self.section_data, body_style)
                
                # Distribute images within text
                combined_flowables = self.image_handler.distribute_images(rl_text, image_flowables, body_style)
                
                # Add all flowables to story
                for flowable in combined_flowables:
                    story.append(flowable)
            else:
                # No images, just add text normally
                # Break the text into smaller paragraphs to avoid issues with very long content
                max_paragraph_length = 10000  # Maximum safe paragraph length
                
                # Split text by paragraphs (double newlines)
                paragraphs = rl_text.split('<br/><br/>')
                
                for p in paragraphs:
                    if not p.strip():
                        continue  # Skip empty paragraphs
                        
                    # If paragraph is too long, split it further
                    if len(p) > max_paragraph_length:
                        # Split by single newlines or sentences
                        chunks = p.split('<br/>') if '<br/>' in p else re.split(r'(?<=[.!?]) +', p)
                        current_chunk = ""
                        
                        for chunk in chunks:
                            if len(current_chunk) + len(chunk) < max_paragraph_length:
                                if current_chunk:
                                    current_chunk += ' ' + chunk
                                else:
                                    current_chunk = chunk
                            else:
                                if current_chunk:
                                    try:
                                        story.append(Paragraph(current_chunk, body_style))
                                    except:
                                        # If fails, try a simpler version
                                        story.append(Paragraph(
                                            self._clean_text_for_reportlab(current_chunk), 
                                            body_style
                                        ))
                                current_chunk = chunk
                        
                        # Add the last chunk if any
                        if current_chunk:
                            try:
                                story.append(Paragraph(current_chunk, body_style))
                            except:
                                story.append(Paragraph(
                                    self._clean_text_for_reportlab(current_chunk), 
                                    body_style
                                ))
                    else:
                        # Add paragraph directly if it's not too long
                        try:
                            story.append(Paragraph(p, body_style))
                        except:
                            story.append(Paragraph(
                                self._clean_text_for_reportlab(p), 
                                body_style
                            ))
                        
                story.append(Spacer(1, body_config.get('space_after', 12)))
            
        except Exception as e:
            print(f"Error adding section text: {str(e)}")
            # Add a simple paragraph as fallback
            try:
                simple_style = ParagraphStyle(
                    name='SimpleText',
                    parent=self.styles['Normal'],
                    fontSize=12,
                    leading=14
                )
                
                # Add a simplified, cleaned version of the text
                clean_text = self._clean_text_for_reportlab(self.section_text)
                if len(clean_text) > 5000:
                    clean_text = clean_text[:5000] + "... (text truncated for PDF safety)"
                    
                story.append(Paragraph(clean_text, simple_style))
            except:
                print("Could not add even simplified text")
        
    def _create_body_style(self, body_config):
        """Create and return body text style based on configuration."""
        alignment_map = {
            'left': 0,
            'center': 1,
            'right': 2,
            'justified': 4
        }
        alignment = alignment_map.get(body_config.get('alignment', 'justified'), 4)
        
        return ParagraphStyle(
            name='CustomBodyText',
            parent=self.styles['Normal'],
            fontSize=body_config.get('size', 12),
            leading=body_config.get('leading', 14),
            spaceAfter=body_config.get('space_after', 12),
            alignment=alignment,
            fontName=body_config.get('font', 'Helvetica')
        )
        
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
        try:
            html = markdown.markdown(md_text)
            
            # Replace problematic HTML tags with simpler ReportLab markup
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
            
            # Remove any remaining HTML tags that might cause issues
            html = re.sub(r'<[^>]*>', '', html)
            
            return html
        except Exception as e:
            print(f"Markdown conversion error: {str(e)}")
            # Return a cleaned version of the original text as fallback
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
        
        # Replace problematic Unicode characters
        text = ''.join(c if ord(c) < 128 else ' ' for c in text)
        
        return text