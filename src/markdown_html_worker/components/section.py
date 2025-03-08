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
                
                # Process content with code blocks and equations
                remaining_content = content

                # Process markdown content for inline LaTeX
                remaining_content = self._process_inline_latex(remaining_content, story, equation_formatter, body_style)
                
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
                
                # Also check for equation patterns directly in the content
                if equation_formatter:
                    # Process any remaining content after handling all placeholders
                    remaining_content = self._process_inline_latex(remaining_content, story, equation_formatter, body_style)
                else:
                    # No equation formatter, just add the text with paragraph breaks
                    # Convert markdown to ReportLab markup
                    rl_text = self._convert_markdown_to_rl_markup(self.section_text)
                    
                    # Break the text into smaller paragraphs
                    paragraphs = self._break_into_paragraphs(rl_text)
                    
                    # Add paragraphs to story
                    for p in paragraphs:
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
                
    def _process_inline_latex(self, content, story, equation_formatter, body_style):
        """Process content for inline LaTeX equations."""
        if not equation_formatter:
            return content
            
        # Look for LaTeX patterns $...$
        result_content = content
        inline_pattern = r'\$(.*?)\$'
        
        matches = list(re.finditer(inline_pattern, content))
        if not matches:
            return content
            
        # Process content in segments, handling each LaTeX block
        last_end = 0
        for match in matches:
            start, end = match.span()
            
            # Add text before the equation
            if start > last_end:
                before_text = content[last_end:start]
                if before_text.strip():
                    for p in self._break_into_paragraphs(before_text):
                        if p.strip():
                            try:
                                story.append(Paragraph(p, body_style))
                            except:
                                clean_p = self._clean_text_for_reportlab(p)
                                story.append(Paragraph(clean_p, body_style))
            
            # Process the equation
            equation = match.group(1)
            eq_type = 'inline'  # Assume inline for $ delimiters
            
            # Add equation with small spacing
            story.append(Spacer(1, 2))
            eq_element = equation_formatter.format_equation(equation, eq_type)
            story.append(eq_element)
            story.append(Spacer(1, 2))
            
            last_end = end
        
        # Add any remaining content
        if last_end < len(content):
            remaining = content[last_end:]
            if remaining.strip():
                for p in self._break_into_paragraphs(remaining):
                    if p.strip():
                        try:
                            story.append(Paragraph(p, body_style))
                        except:
                            clean_p = self._clean_text_for_reportlab(p)
                            story.append(Paragraph(clean_p, body_style))
        
        # Return empty content since we've processed it all
        return ""
    
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
            
            # Handle math notation - preserve LaTeX equations
            html = re.sub(r'\$(.*?)\$', r'$\1$', html, flags=re.DOTALL)
            
            # Handle emphasis correctly
            html = re.sub(r'<em>(.*?)</em>', r'<i>\1</i>', html, flags=re.DOTALL)
            html = re.sub(r'<strong>(.*?)</strong>', r'<b>\1</b>', html, flags=re.DOTALL)
            
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
        # Skip if the text contains LaTeX equations to preserve them
        if '$' in text:
            # Skip equation patterns to ensure they don't get broken across paragraphs
            pattern = r'\$(.*?)\$'
            matches = list(re.finditer(pattern, text))
            if matches:
                # Process text as one paragraph if it contains equations
                # This ensures equations stay intact
                return [text]
        
        # Split by double line breaks
        if '<br/><br/>' in text:
            return text.split('<br/><br/>')
        
        # If no <br/><br/>, use regex to split on consecutive whitespace or actual double newlines
        return re.split(r'\n\s*\n|\r\n\s*\r\n', text)
            
    def _clean_text_for_reportlab(self, text):
        """Clean text to make it safe for ReportLab processing."""
        # Preserve LaTeX equations
        if '$' in text:
            # Temporarily replace equation content with placeholders
            pattern = r'\$(.*?)\$'
            eq_placeholders = {}
            
            for i, match in enumerate(re.finditer(pattern, text, re.DOTALL)):
                placeholder = f"__EQ_PLACEHOLDER_{i}__"
                eq_placeholders[placeholder] = match.group(0)
                text = text.replace(match.group(0), placeholder, 1)
        
        # Replace special XML/HTML characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        
        # Remove control characters
        text = ''.join(c for c in text if ord(c) >= 32 or c in '\n\r\t')
        
        # Replace problematic Unicode characters but preserve common ones
        printable_chars = set(range(32, 127))  # ASCII printable
        # Add common Unicode ranges that are usually safe
        printable_chars.update(range(0x00A0, 0x00FF))  # Latin-1 Supplement
        printable_chars.update(range(0x0100, 0x017F))  # Latin Extended-A
        printable_chars.update(range(0x2000, 0x206F))  # General Punctuation
        
        text = ''.join(c if (ord(c) in printable_chars or c in '\n\r\t') else ' ' for c in text)
        
        # Make sure equation placeholders are preserved
        text = re.sub(r'\[EQUATION:([^\]]+)\]', r'[EQUATION:\1]', text)
        
        # Restore LaTeX equations if any
        if '$' in text or '__EQ_PLACEHOLDER_' in text:
            for placeholder, equation in eq_placeholders.items():
                text = text.replace(placeholder, equation)
        
        return text