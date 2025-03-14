#!/usr/bin/env python3
import re
import os
import logging
import markdown
from pathlib import Path
from mistune import Markdown
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter

class MarkdownParser:
    """Parse Markdown files to extract structured content for PDF generation."""
    
    def __init__(self):
        """Initialize the Markdown parser."""
        self.logger = logging.getLogger(__name__)
        
    def parse_file(self, file_path):
        """
        Parse a Markdown file to extract structure and content.
        
        Args:
            file_path (str): Path to Markdown file
            
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
            self.logger.error(f"Error parsing Markdown file {file_path}: {str(e)}")
            raise
            
    def _parse_content(self, content, chapter_title):
        """
        Parse markdown content and extract structure.
        
        Args:
            content (str): Markdown content
            chapter_title (str): Title of the chapter
            
        Returns:
            dict: Structured document content
        """
        # Initialize document structure
        document = {
            'chapter_title': chapter_title,
            'sections': []
        }
        
        # Split content by section headers (## headers)
        current_section_title = None
        current_section_content = []
        current_section = None
        
        lines = content.split('\n')
        for line in lines:
            # Check if line is a section header
            section_match = re.match(r'^##\s+(.+)$', line)
            
            if section_match:
                # Save previous section if exists
                if current_section_title:
                    section_content = '\n'.join(current_section_content)
                    section = self._process_section(current_section_title, section_content)
                    document['sections'].append(section)
                
                # Start new section
                current_section_title = section_match.group(1)
                current_section_content = []
            else:
                # Add line to current section
                current_section_content.append(line)
        
        # Add final section
        if current_section_title:
            section_content = '\n'.join(current_section_content)
            section = self._process_section(current_section_title, section_content)
            document['sections'].append(section)
        else:
            # If no section headers, create one section with the chapter title
            section = self._process_section(chapter_title, '\n'.join(current_section_content))
            document['sections'].append(section)
            
        return document
    
    def _process_section(self, title, content):
        """
        Process section content to extract code blocks, equations, etc.
        
        Args:
            title (str): Section title
            content (str): Section content
            
        Returns:
            dict: Processed section content
        """
        section = {
            'title': title,
            'content': [],
            'code_blocks': [],
            'equations': []
        }
        
        # Extract code blocks
        code_blocks = self._extract_code_blocks(content)
        for i, code_block in enumerate(code_blocks):
            block_id = f"code_{i+1}"
            section['code_blocks'].append({
                'id': block_id,
                'language': code_block['language'],
                'code': code_block['code']
            })
            # Replace code block in content with placeholder
            content = content.replace(code_block['original'], f"[CODE_BLOCK:{block_id}]")
        
        # Extract LaTeX equations - both inline and block
        equations = self._extract_latex_equations(content)
        for i, equation in enumerate(equations):
            eq_id = f"eq_{i+1}"
            section['equations'].append({
                'id': eq_id,
                'equation': equation['equation'],
                'type': equation['type']
            })
            # Replace equation in content with placeholder
            content = content.replace(equation['original'], f"[EQUATION:{eq_id}]")
        
        # Store processed content
        section['content'] = content
        
        return section
    
    def _extract_code_blocks(self, content):
        """
        Extract code blocks from markdown content.
        
        Args:
            content (str): Markdown content
            
        Returns:
            list: Extracted code blocks with language info
        """
        code_blocks = []
        # Regex to match markdown code blocks like ```python ... ```
        pattern = r'```([a-z]*)\n(.*?)```'
        
        for match in re.finditer(pattern, content, re.DOTALL):
            language = match.group(1) or 'text'
            code = match.group(2).strip()
            original = match.group(0)
            
            code_blocks.append({
                'language': language,
                'code': code,
                'original': original
            })
            
        return code_blocks
    
    def _extract_latex_equations(self, content):
        """
        Extract LaTeX equations from markdown content.
        
        Args:
            content (str): Markdown content
            
        Returns:
            list: Extracted equations
        """
        equations = []
        
        # Match block equations ($$...$$)
        block_pattern = r'\$\$(.*?)\$\$'
        for match in re.finditer(block_pattern, content, re.DOTALL):
            equation = match.group(1).strip()
            original = match.group(0)
            
            equations.append({
                'equation': equation,
                'type': 'block',
                'original': original
            })
        
        # Match inline equations ($...$) - but not if they're part of block equations
        # First, replace block equations with placeholders to avoid matching their delimiters
        content_with_placeholders = content
        for i, match in enumerate(re.finditer(block_pattern, content, re.DOTALL)):
            content_with_placeholders = content_with_placeholders.replace(match.group(0), f"BLOCK_EQ_PLACEHOLDER_{i}")
        
        # Now match inline equations
        inline_pattern = r'(?<!\$)\$(.*?)\$(?!\$)'
        for match in re.finditer(inline_pattern, content_with_placeholders, re.DOTALL):
            # Get the original equation text from the original content
            start_idx = match.start()
            end_idx = match.end()
            
            # Ensure we're not inside a code block
            code_block = False
            for block in self._extract_code_blocks(content):
                block_start = content.find(block['original'])
                block_end = block_start + len(block['original'])
                if block_start <= start_idx and end_idx <= block_end:
                    code_block = True
                    break
            
            if not code_block:
                equation = match.group(1).strip()
                original = f"${equation}$"
                
                equations.append({
                    'equation': equation,
                    'type': 'inline',
                    'original': original
                })
        
        # Also catch any placeholders from a previous run
        for match in re.finditer(r'\[EQUATION:([^\]]+)\]', content):
            eq_id = match.group(1)
            original = match.group(0)
            
            equations.append({
                'id': eq_id,
                'equation': f"EQUATION_PLACEHOLDER_{eq_id}",  # This will be replaced by the equation formatter
                'type': 'inline',
                'original': original
            })
                
        return equations