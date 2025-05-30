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
        
        # Extract equations - looking for the pattern of standalone lines with $ delimiters
        equations = self._extract_equations(content)
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
    
    def _extract_equations(self, content):
        """
        Extract equations from markdown content, focusing on the pattern 
        of standalone equations with empty lines before and after.
        
        Args:
            content (str): Markdown content
            
        Returns:
            list: Extracted equations
        """
        equations = []
        
        # Process the content line by line to find equations on their own lines
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Check for standalone equation pattern: empty line, equation line with $ delimiters, empty line
            if line.startswith('$') and line.endswith('$'):
                # Check if this is a standalone equation (empty lines before and after)
                is_standalone = False
                if (i == 0 or not lines[i-1].strip()) and (i == len(lines)-1 or not lines[i+1].strip()):
                    is_standalone = True
                
                # Extract the equation
                equation = line
                equation_type = 'block' if is_standalone else 'inline'
                
                equations.append({
                    'equation': equation,
                    'type': equation_type,
                    'original': line
                })
            
            # Check for additional equations patterns like [EQUATION:eq_id]
            elif '[EQUATION:' in line:
                for match in re.finditer(r'\[EQUATION:([^\]]+)\]', line):
                    eq_id = match.group(1)
                    original = match.group(0)
                    
                    equations.append({
                        'id': eq_id,
                        'equation': f"EQUATION_{eq_id}",
                        'type': 'inline',
                        'original': original
                    })
            
            i += 1
        
        return equations