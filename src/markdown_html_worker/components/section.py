#!/usr/bin/env python3
import re
import markdown
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, KeepTogether

from ..flowables import DottedLineFlowable, SolidLineFlowable
from .equation_block import EquationBlock

class Section:
    """Component for generating a document section."""
    
    def __init__(self, style_config, section_name, section_text, section_data=None):
        """
        Initialize section component.
        
        Args:
            style_config (dict): Style configuration
            section_name (str): Section name
            section_text (str): Section content text
            section_data (dict, optional): Full section data including code blocks and equations
        """
        self.style_config = style_config
        self.section_name = section_name if section_name else ""
        self.section_text = section_text if section_text else ""
        self.section_data = section_data or {}
        self.styles = getSampleStyleSheet()
        
    def add_to_story(self, story, code_formatter=None, equation_formatter=None):
        """
        Add the section to the document story.
        
        Args:
            story (list): ReportLab story (content flow)
            code_formatter (CodeFormatter, optional): For formatting code blocks
            equation_formatter (EquationFormatter, optional): For formatting equations
            
        Returns:
            None
        """
        try:
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
            
            # Skip if no text content and no extra data
            if not self.section_text and not self.section_data:
                return
                
            # Create body text style
            body_config = self.style_config.get('body_text', {})
            body_style = self._create_body_style(body_config)
            
            # Check if we have section data with code blocks or equations
            if self.section_data:
                code_blocks = self.section_data.get('code_blocks', [])
                equations = self.section_data.get('equations', [])
                content = self.section_data.get('content', self.section_text)
                
                # Start processing with entire content
                remaining_content = content
                
                # First, process code blocks
                if code_formatter and code_blocks:
                    for code_block in code_blocks:
                        block_id = code_block.get('id')
                        placeholder = f"[CODE_BLOCK:{block_id}]"
                        
                        if placeholder in remaining_content:
                            # Split content at placeholder
                            parts = remaining_content.split(placeholder, 1)
                            
                            # Add text before placeholder
                            if parts[0].strip():
                                for p in self._break_into_paragraphs(parts[0]):
                                    if p.strip():
                                        try:
                                            story.append(Paragraph(p, body_style))
                                        except:
                                            clean_p = self._clean_text_for_reportlab(p)
                                            story.append(Paragraph(clean_p, body_style))
                            
                            # Add code block
                            story.append(Spacer(1, 6))
                            code = code_block.get('code', '')
                            language = code_block.get('language', 'text')
                            story.append(code_formatter.format_code_block(code, language))
                            story.append(Spacer(1, 6))
                            
                            # Continue with remaining content
                            remaining_content = parts[1] if len(parts) > 1 else ""
                
                # Then, process equations
                if equation_formatter and equations:
                    for equation in equations:
                        eq_id = equation.get('id')
                        placeholder = f"[EQUATION:{eq_id}]"
                        
                        if placeholder in remaining_content:
                            # Split content at placeholder
                            parts = remaining_content.split(placeholder, 1)
                            
                            # Add text before placeholder
                            if parts[0].strip():
                                for p in self._break_into_paragraphs(parts[0]):
                                    if p.strip():
                                        try:
                                            story.append(Paragraph(p, body_style))
                                        except:
                                            clean_p = self._clean_text_for_reportlab(p)
                                            story.append(Paragraph(clean_p, body_style))
                            
                            # Add equation
                            story.append(Spacer(1, 6))
                            eq = equation.get('equation', '')
                            eq_type = equation.get('type', 'inline')
                            
                            # Add equation wrapped in KeepTogether to avoid breaking across pages
                            eq_element = equation_formatter.format_equation(eq, eq_type)
                            story.append(eq_element)
                            story.append(Spacer(1, 6))
                            
                            # Continue with remaining content
                            remaining_content = parts[1] if len(parts) > 1 else ""
                
                # Check for any standalone equations in the remaining content
                # These are lines that start and end with $
                if equation_formatter and remaining_content:
                    remaining_content = self._process_standalone_equations(remaining_content, story, equation_formatter, body_style)
                
                # Add any remaining content after processing all placeholders
                if remaining_content.strip():
                    for p in self._break_into_paragraphs(remaining_content):
                        if p.strip():
                            try:
                                story.append(Paragraph(p, body_style))
                            except:
                                clean_p = self._clean_text_for_reportlab(p)
                                story.append(Paragraph(clean_p, body_style))
            else:
                # No section data, just add the text with paragraph breaks
                # Convert markdown to ReportLab markup
                rl_text = self._convert_markdown_to_rl_markup(self.section_text)
                
                # Process standalone equations in the text
                if equation_formatter:
                    rl_text = self._process_standalone_equations(rl_text, story, equation_formatter, body_style)
                    
                # Add any remaining text as paragraphs
                if rl_text.strip():
                    for p in self._break_into_paragraphs(rl_text):
                        if p.strip():
                            try:
                                story.append(Paragraph(p, body_style))
                            except Exception as e:
                                # If fails, try a simpler version by removing potentially problematic chars
                                clean_p = self._clean_text_for_reportlab(p)
                                story.append(Paragraph(clean_p, body_style))
                
                # Add space after all paragraphs
                story.append(Spacer(1, body_config.get('space_after', 12)))
                
        except Exception as e:
            print(f"Error adding section content: {str(e)}")
            # Add a simple error message as fallback
            try:
                error_style = ParagraphStyle(
                    name='ErrorStyle',
                    parent=self.styles['Normal'],
                    textColor=colors.red
                )
                story.append(Paragraph(f"Error processing section: {str(e)}", error_style))
            except:
                print("Could not add even simplified error message")
                
    def _process_standalone_equations(self, content, story, equation_formatter, body_style):
        """
        Process standalone equations (lines that start and end with $).
        
        Args:
            content (str): Content text
            story (list): Report story to add to
            equation_formatter (EquationFormatter): Equation formatter
            body_style (ParagraphStyle): Body text style
            
        Returns:
            str: Remaining content after processing equations
        """
        # Process the text line by line
        lines = content.split('\n')
        processed_content = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Check for standalone equation line (starts and ends with $)
            if line.startswith('$') and line.endswith('$'):
                # First, add any accumulated content as paragraphs
                if processed_content:
                    accumulated_text = '\n'.join(processed_content)
                    for p in self._break_into_paragraphs(accumulated_text):
                        if p.strip():
                            try:
                                story.append(Paragraph(p, body_style))
                            except:
                                clean_p = self._clean_text_for_reportlab(p)
                                story.append(Paragraph(clean_p, body_style))
                    processed_content = []
                
                # Add spacer before equation
                story.append(Spacer(1, 6))
                
                # Format and add the equation
                eq_type = 'block'
                eq_element = equation_formatter.format_equation(line, eq_type)
                story.append(eq_element)
                
                # Add spacer after equation
                story.append(Spacer(1, 6))
            else:
                # Regular text - accumulate
                processed_content.append(lines[i])
            
            i += 1
        
        # Return any remaining accumulated content
        return '\n'.join(processed_content)
    
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
            
            # Handle emphasis correctly
            html = re.sub(r'<em>(.*?)</em>', r'<i>\1</i>', html, flags=re.DOTALL)
            html = re.sub(r'<strong>(.*?)</strong>', r'<b>\1</b>', html, flags=re.DOTALL)
            
            # Preserve dollar signs for equations ($ and $$)
            html = html.replace('$', '$')
            
            # Preserve [EQUATION:...] placeholders
            html = re.sub(r'\[EQUATION:([^\]]+)\]', r'[EQUATION:\1]', html)
            
            # Remove any remaining HTML tags that might cause issues
            html = re.sub(r'<(?!i>|/i>|b>|/b>|br/>|font|/font>)[^>]*>', '', html)
            
            return html
        except Exception as e:
            print(f"Markdown conversion error: {str(e)}")
            # Return a cleaned version of the original text as fallback
            return self._clean_text_for_reportlab(md_text)
    
    def _break_into_paragraphs(self, text):
        """Break text into paragraphs for better rendering."""
        # Split by double line breaks
        if '<br/><br/>' in text:
            return text.split('<br/><br/>')
        
        # If no <br/><br/>, use regex to split on consecutive whitespace or actual double newlines
        return re.split(r'\n\s*\n|\r\n\s*\r\n', text)
            
    def _clean_text_for_reportlab(self, text):
        """Clean text to make it safe for ReportLab processing."""
        # Replace special XML/HTML characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        
        # Remove control characters
        text = ''.join(c for c in text if ord(c) >= 32 or c in '\n\r\t')
        
        # Preserve dollar signs for equations
        # Don't modify $ characters as they're important for equations
        
        # Make sure equation placeholders are preserved
        text = re.sub(r'\[EQUATION:([^\]]+)\]', r'[EQUATION:\1]', text)
        
        return text