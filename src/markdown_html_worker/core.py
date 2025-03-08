#!/usr/bin/env python3
import os
import json
import logging
import glob
import re
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, PageBreak, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from .markdown_parser import MarkdownParser
from .html_parser import HTMLParser
from .code_formatter import CodeFormatter
from .equation_formatter import EquationFormatter
from .utils import generate_output_filename, sort_files_naturally, ensure_dir_exists
from .components.chapter import Chapter
from .components.section import Section
from .components.code_block import CodeBlock
from .components.equation_block import EquationBlock

class MarkdownHTMLProcessor:
    """Process Markdown and HTML files to generate PDF documents."""
    
    def __init__(self, input_dir=None, output_dir=None, style_name='classic'):
        """
        Initialize the Markdown/HTML processor.
        
        Args:
            input_dir (str): Directory containing Markdown/HTML files
            output_dir (str): Directory for output PDF files
            style_name (str): Style template to use for PDFs
        """
        # Setup logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            
        self.input_dir = input_dir
        self.output_dir = output_dir or 'results/pdfs'
        self.style_name = style_name
        
        # Create output directory if it doesn't exist
        if self.output_dir:
            ensure_dir_exists(self.output_dir)
            
        # Initialize parsers
        self.markdown_parser = MarkdownParser()
        self.html_parser = HTMLParser()
        
        # Initialize formatters
        self.code_formatter = CodeFormatter()
        self.equation_formatter = EquationFormatter()
        
        # Load style configuration
        self.style_config = self._load_style_config()
        
    def _load_style_config(self):
        """
        Load style configuration from JSON file.
        
        Returns:
            dict: Style configuration
        """
        try:
            # Import style manager from PDF worker to reuse existing styles
            from src.pdf_worker.style_manager import StyleManager
            
            style_manager = StyleManager()
            style_config = style_manager.load_style(self.style_name)
            self.logger.info(f"Loaded style configuration for '{self.style_name}'")
            return style_config
        except Exception as e:
            self.logger.warning(f"Could not load style '{self.style_name}': {str(e)}")
            self.logger.warning("Using default style configuration")
            
            # Create a default style configuration
            return {
                "page": {"size": "A4", "margins": {"left": 72, "right": 72, "top": 72, "bottom": 72}},
                "chapter": {
                    "title": {"font": "Helvetica-Bold", "size": 18, "color": "#000000"},
                    "page_break": {"before": True, "after": False}
                },
                "section": {
                    "title": {"font": "Helvetica-Bold", "size": 14, "color": "#000000"}
                },
                "body_text": {
                    "font": "Helvetica", "size": 12, "color": "#000000", "alignment": "justified"
                },
                "code_block": {
                    "font": "Courier", "size": 9, "background_color": "#f5f5f5"
                }
            }
        
    def scan_directory(self, directory=None):
        """
        Scan a directory for Markdown and HTML files.
        
        Args:
            directory (str, optional): Directory to scan. If not provided, uses self.input_dir
            
        Returns:
            tuple: (list of file paths, 'markdown', 'html', or 'mixed' file type)
        """
        dir_path = directory or self.input_dir
        if not dir_path:
            raise ValueError("No directory specified for scanning")
            
        # Find all Markdown and HTML files
        md_files = glob.glob(os.path.join(dir_path, "*.md"))
        html_files = glob.glob(os.path.join(dir_path, "*.html"))
        
        # Sort files in natural order
        md_files = sort_files_naturally(md_files)
        html_files = sort_files_naturally(html_files)
        
        if md_files and not html_files:
            return md_files, 'markdown'
        elif html_files and not md_files:
            return html_files, 'html'
        elif md_files and html_files:
            return sort_files_naturally(md_files + html_files), 'mixed'
        else:
            return [], None
    
    def validate_file_types(self, file_paths):
        """
        Validate that all file types are either Markdown or HTML, not mixed.
        
        Args:
            file_paths (list): List of file paths to check
            
        Returns:
            str: 'markdown', 'html', or None if mixed or no files
        """
        if not file_paths:
            return None
            
        extensions = set(Path(file).suffix.lower() for file in file_paths)
        
        if len(extensions) == 1:
            ext = extensions.pop()
            if ext == '.md':
                return 'markdown'
            elif ext == '.html':
                return 'html'
        
        return None  # Mixed or unsupported types
        
    def process_directory(self, directory=None):
        """
        Process all Markdown or HTML files in a directory.
        
        Args:
            directory (str, optional): Directory to process. If not provided, uses self.input_dir
            
        Returns:
            list: Paths to generated PDF files
        """
        try:
            dir_path = directory or self.input_dir
            if not dir_path:
                raise ValueError("No directory specified for processing")
                
            # Scan for files
            files, file_type = self.scan_directory(dir_path)
            
            if not files:
                self.logger.warning(f"No Markdown or HTML files found in {dir_path}")
                return []
                
            if file_type == 'mixed':
                self.logger.warning("Mixed file types found. Please separate Markdown and HTML files.")
                return []
                
            # Process files
            generated_pdfs = []
            for file_path in files:
                try:
                    pdf_path = self.process_file(file_path, file_type)
                    if pdf_path:
                        generated_pdfs.append(pdf_path)
                except Exception as e:
                    self.logger.error(f"Error processing file {file_path}: {str(e)}")
                    
            self.logger.info(f"Generated {len(generated_pdfs)} PDF files")
            return generated_pdfs
            
        except Exception as e:
            self.logger.error(f"Error processing directory: {str(e)}")
            raise
            
    def process_file(self, file_path, file_type):
        """
        Process a single Markdown or HTML file.
        
        Args:
            file_path (str): Path to file to process
            file_type (str): 'markdown' or 'html'
            
        Returns:
            str: Path to generated PDF file or None if failed
        """
        try:
            self.logger.info(f"Processing {file_type} file: {file_path}")
            
            # Generate output filename
            output_path = generate_output_filename(file_path, self.output_dir)
            
            # Parse content based on file type
            if file_type == 'markdown':
                document = self.markdown_parser.parse_file(file_path)
            elif file_type == 'html':
                document = self.html_parser.parse_file(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
                
            # Generate PDF
            self._generate_pdf(document, output_path)
            
            self.logger.info(f"Generated PDF: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {str(e)}")
            return None
            
    def _generate_pdf(self, document, output_path):
        """
        Generate a PDF from parsed document content.
        
        Args:
            document (dict): Parsed document with structure and content
            output_path (str): Output PDF file path
        """
        try:
            # Get page size and margins from style configuration
            page_config = self.style_config.get('page', {})
            margins = page_config.get('margins', {'left': 72, 'right': 72, 'top': 72, 'bottom': 72})
            
            # Create document template
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=margins.get('right', 72),
                leftMargin=margins.get('left', 72),
                topMargin=margins.get('top', 72),
                bottomMargin=margins.get('bottom', 72),
                title=document.get('chapter_title', 'Document')
            )
            
            # Build the story (content flow)
            story = []
            styles = getSampleStyleSheet()
            
            # Add chapter title
            chapter = Chapter(self.style_config, document.get('chapter_title', 'Untitled'))
            chapter.add_to_story(story)
            
            # Add all sections
            for section_data in document.get('sections', []):
                # Create section component - FIXED: removed the image_handler parameter
                section = Section(
                    self.style_config,
                    section_data.get('title', ''),
                    section_data.get('content', ''),
                    section_data
                )
                
                # Add section content to story
                section.add_to_story(story, self.code_formatter, self.equation_formatter)
                
                # Add spacer after section
                story.append(Spacer(1, 12))
            
            # Build the PDF
            doc.build(story)
            
        except Exception as e:
            self.logger.error(f"Error generating PDF: {str(e)}")
            self.logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
            
            # Try to create a simplified version as fallback
            try:
                self.logger.info("Attempting to generate simplified PDF...")
                
                # Create minimal document
                doc = SimpleDocTemplate(output_path, pagesize=A4)
                story = []
                styles = getSampleStyleSheet()
                
                # Add basic title
                title = document.get('chapter_title', 'Untitled')
                story.append(Paragraph(title, styles['Title']))
                story.append(Spacer(1, 12))
                
                # Add text indicating error
                error_style = ParagraphStyle(
                    name='Error',
                    parent=styles['Normal'],
                    textColor=colors.red
                )
                story.append(Paragraph(f"Error generating full PDF: {str(e)}", error_style))
                story.append(Spacer(1, 12))
                
                # Add simplified section content
                for section_data in document.get('sections', []):
                    if section_data.get('title'):
                        story.append(Paragraph(section_data['title'], styles['Heading2']))
                        story.append(Spacer(1, 6))
                    
                    # Add plain text content - remove HTML and placeholders
                    content = section_data.get('content', '')
                    if content:
                        # Remove HTML tags
                        content = re.sub(r'<[^>]*>', '', content)
                        # Clean up equation placeholders for better display
                        content = re.sub(r'\[EQUATION:([^\]]+)\]', r'[EQUATION:\1]', content)
                        # Limit length
                        if len(content) > 500:
                            content = content[:500] + "..."
                        story.append(Paragraph(content, styles['Normal']))
                        story.append(Spacer(1, 12))
                
                # Build simplified PDF
                doc.build(story)
                self.logger.info(f"Generated simplified PDF: {output_path}")
                
            except Exception as e2:
                self.logger.error(f"Failed to create simplified PDF: {str(e2)}")
                raise e  # Raise the original error