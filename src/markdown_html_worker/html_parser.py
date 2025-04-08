#!/usr/bin/env python3
import re
import os
import logging
from pathlib import Path
from bs4 import BeautifulSoup
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter


from .components.code_block import CodeBlock
from .components.equation_block import EquationBlock

class HTMLParser:
    """Parse HTML files to extract structured content for PDF generation."""
    
    def __init__(self):
        """Initialize the HTML parser."""
        self.logger = logging.getLogger(__name__)
        
    def parse_file(self, file_path):
        """
        Parse an HTML file to extract structure and content.
        
        Args:
            file_path (str): Path to HTML file
            
        Returns:
            dict: Structured document content with sections, code blocks, etc.
        """
        try:
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Get the file name as the chapter title
            chapter_title = Path(file_path).stem
                
            # Parse content
            parsed_document = self._parse_content(content, chapter_title)
            
            return parsed_document
            
        except Exception as e:
            self.logger.error(f"Error parsing HTML file {file_path}: {str(e)}")
            raise
            
    def _parse_content(self, content, chapter_title):
        """
        Parse HTML content and extract structure.
        
        Args:
            content (str): HTML content
            chapter_title (str): Title of the chapter
            
        Returns:
            dict: Structured document content
        """
        # Initialize document structure
        document = {
            'chapter_title': chapter_title,
            'sections': []
        }
        
        # Parse HTML
        soup = BeautifulSoup(content, 'html.parser')
        
        # Look for section headers (h2 tags)
        section_headers = soup.find_all('h2')
        
        if section_headers:
            # Process each section
            for i, header in enumerate(section_headers):
                section_title = header.get_text()
                
                # Get all content until next h2 or end
                section_content = []
                current = header.next_sibling
                
                while current and (not hasattr(current, 'name') or current.name != 'h2'):
                    if hasattr(current, 'prettify'):
                        section_content.append(current.prettify())
                    elif hasattr(current, 'strip') and current.strip():
                        section_content.append(str(current))
                    current = current.next_sibling
                    
                section_html = ''.join(section_content)
                section = self._process_section(section_title, section_html)
                document['sections'].append(section)
        else:
            # If no section headers, create one section with the chapter title
            section = self._process_section(chapter_title, soup.prettify())
            document['sections'].append(section)
            
        return document
    
    def _process_section(self, title, content):
        """
        Process section content to extract code blocks, equations, etc.
        
        Args:
            title (str): Section title
            content (str): Section HTML content
            
        Returns:
            dict: Processed section content
        """
        section = {
            'title': title,
            'content': '',
            'code_blocks': [],
            'equations': []
        }
        
        # Parse content with BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract code blocks
        code_elements = soup.find_all('pre')
        for i, code_element in enumerate(code_elements):
            block_id = f"code_{i+1}"
            
            # Try to detect language
            code_class = code_element.get('class', [])
            language = 'text'
            for cls in code_class:
                if cls.startswith('language-'):
                    language = cls.replace('language-', '')
                    break
            
            code = code_element.get_text()
            section['code_blocks'].append({
                'id': block_id,
                'language': language,
                'code': code
            })
            
            # Replace code block with placeholder in BeautifulSoup
            placeholder = soup.new_tag('div')
            placeholder['id'] = block_id
            placeholder.string = f"[CODE_BLOCK:{block_id}]"
            code_element.replace_with(placeholder)
        
        # Extract equations
        equation_elements = soup.select('span.equation-placeholder')
        
        if equation_elements:
            self.logger.info(f"Found {len(equation_elements)} equation placeholders")
            
            eq_count = 0
            for eq_element in equation_elements:
                eq_id = eq_element.get('data-id', f"eq_{eq_count+1}")
                eq_count += 1
                
                # Try to find the equation text in the next paragraph or surrounding text
                eq_text = ""
                next_p = eq_element.find_next('p')
                if next_p:
                    eq_text = next_p.get_text().strip()
                    # If next paragraph seems short, likely it's the equation
                    if 5 < len(eq_text) < 500:
                        # Clean up the equation text
                        eq_text = eq_text.replace("\\\\", "\\")  # Fix double backslashes
                        
                        # Remove equation placeholder from the original text
                        next_p.extract()
                
                # If no equation text found, try to find inline equations by looking at parent paragraph
                if not eq_text and eq_element.parent:
                    parent_text = eq_element.parent.get_text()
                    # If the parent has some text around the placeholder, this might be an inline equation
                    if len(parent_text) > len(eq_element.get_text()):
                        # Get the whole paragraph as equation context
                        eq_text = parent_text
                
                # Still no equation text, use a generic placeholder
                if not eq_text:
                    eq_text = f"Equation {eq_count}"
                
                # Determine equation type (inline or block)
                eq_type = 'inline'
                if eq_element.parent and eq_element.parent.name == 'p' and len(eq_element.parent.contents) == 1:
                    eq_type = 'block'  # If the equation is the only content in a paragraph
                
                section['equations'].append({
                    'id': eq_id,
                    'equation': eq_text,
                    'type': eq_type
                })
                
                # Replace equation with placeholder
                placeholder = soup.new_tag('span')
                placeholder['id'] = eq_id
                placeholder.string = f"[EQUATION:{eq_id}]"
                eq_element.replace_with(placeholder)
        
        # Remove any script, style tags that don't belong in the PDF
        for element in soup.find_all(['script', 'style']):
            element.decompose()
            
        # Convert soup to HTML string and clean it up
        content_html = str(soup)
        
        # Process the HTML content into a format ReportLab can handle
        section['content'] = self._prepare_content_for_reportlab(content_html)
        
        return section
    
    def _prepare_content_for_reportlab(self, html_content):
        """
        Prepare HTML content for ReportLab by converting to a simpler format.
        
        Args:
            html_content (str): HTML content
            
        Returns:
            str: Processed content ready for ReportLab
        """
        # Strip HTML/body tags and doctype
        html_content = re.sub(r'<!DOCTYPE.*?>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<html.*?>|</html>|<body.*?>|</body>', '', html_content)
        
        # Replace paragraph tags with line breaks
        html_content = re.sub(r'<p.*?>(.*?)</p>', r'\1<br/><br/>', html_content, flags=re.DOTALL)
        
        # Handle headings
        for i in range(1, 7):
            html_content = re.sub(f'<h{i}.*?>(.*?)</h{i}>', r'<b>\1</b><br/><br/>', html_content, flags=re.DOTALL)
        
        # Handle formatting tags
        html_content = re.sub(r'<strong.*?>(.*?)</strong>', r'<b>\1</b>', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<em.*?>(.*?)</em>', r'<i>\1</i>', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<b.*?>(.*?)</b>', r'<b>\1</b>', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<i.*?>(.*?)</i>', r'<i>\1</i>', html_content, flags=re.DOTALL)
        
        # Handle lists
        html_content = re.sub(r'<li.*?>(.*?)</li>', r'• \1<br/>', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<ul.*?>|</ul>|<ol.*?>|</ol>', '', html_content)
        
        # Replace non-breaking spaces with regular spaces
        html_content = html_content.replace('&nbsp;', ' ')
        
        # Make sure placeholders for code blocks and equations remain intact
        html_content = re.sub(r'\[CODE_BLOCK:([^\]]+)\]', r'[CODE_BLOCK:\1]', html_content)
        html_content = re.sub(r'\[EQUATION:([^\]]+)\]', r'[EQUATION:\1]', html_content)
        
        # Remove other HTML tags but preserve their content
        html_content = re.sub(r'<(?!b>|/b>|i>|/i>|br/>|span|/span>)[^>]*>', ' ', html_content)
        
        # Clean up excessive whitespace
        html_content = re.sub(r'\s+', ' ', html_content)
        html_content = re.sub(r'<br/>\s*<br/>', '<br/><br/>', html_content)
        
        return html_content