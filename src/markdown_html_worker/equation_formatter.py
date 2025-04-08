#!/usr/bin/env python3
import logging
import re
import os
import gc
import tempfile
import shutil
from pathlib import Path
import subprocess
from reportlab.platypus import Image, Paragraph
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

# Import PIL for resizing images
try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Try to import markdown
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

class EquationFormatter:
    """
    Format equations for PDF rendering using a simplified approach.
    Detects LaTeX equations in markdown content and formats them for display.
    """
    
    def __init__(self, equations_dir=None, keep_equation_images=False):
        """
        Initialize the equation formatter.
        
        Args:
            equations_dir (str, optional): Directory to store equation images for verification
            keep_equation_images (bool): Whether to keep generated equation images
        """
        self.logger = logging.getLogger(__name__)
        self.styles = getSampleStyleSheet()
        self.equation_counter = 0
        self.keep_equation_images = keep_equation_images
        
        # Set up equations directory
        if equations_dir:
            self.equations_dir = Path(equations_dir)
            os.makedirs(self.equations_dir, exist_ok=True)
        else:
            self.equations_dir = None
            
        # Create a temporary directory for equation images
        self.temp_dir = tempfile.mkdtemp(prefix='equations_')
    
    def __del__(self):
        """Clean up temporary files when the object is destroyed."""
        self.cleanup()
    
    def cleanup(self):
        """Remove temporary files and run garbage collection."""
        try:
            if not self.keep_equation_images and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                self.logger.info(f"Removed temporary equation directory: {self.temp_dir}")
        except Exception as e:
            self.logger.error(f"Error cleaning up temporary files: {str(e)}")
        
        # Run garbage collection
        gc.collect()
    
    def format_equation(self, equation, eq_type='inline'):
        """
        Format an equation for PDF rendering.
        
        Args:
            equation (str): Equation string or equation ID
            eq_type (str): 'inline' or 'block'
            
        Returns:
            reportlab.platypus.Flowable: A flowable for the PDF (Image or Paragraph)
        """
        try:
            self.equation_counter += 1
            
            # Clean dollar sign markers from equations
            if equation.startswith('$') and equation.endswith('$'):
                equation = equation[1:-1].strip()
            
            # Check if this contains any text that looks like a placeholder
            if equation.startswith("[EQUATION:") or equation.startswith("Equation "):
                if "eq_" in equation:
                    # Extract the equation number for reference
                    eq_num_match = re.search(r'eq_(\d+)', equation)
                    if eq_num_match:
                        eq_num = eq_num_match.group(1)
                        equation = f"Equation {eq_num}"
            
            # Create styled text equation representation
            return self._format_as_styled_text(equation, eq_type)
                
        except Exception as e:
            self.logger.error(f"Error formatting equation: {str(e)}")
            # Fallback to very simple text
            return self._format_as_basic_text(equation, eq_type)
    
    def _format_as_styled_text(self, equation, eq_type):
        """
        Format equation as styled text with proper formatting.
        
        Args:
            equation (str): Cleaned equation text
            eq_type (str): 'inline' or 'block'
            
        Returns:
            reportlab.platypus.Paragraph: A properly styled paragraph
        """
        # For block equations, center and add more space
        if eq_type == 'block':
            equation_style = ParagraphStyle(
                name='BlockEquation',
                parent=self.styles['Normal'],
                fontName='Times-Italic',  # Use italic for equations
                fontSize=12,
                leading=14,
                spaceBefore=8,
                spaceAfter=8,
                alignment=TA_CENTER  # Center block equations
            )
            # Add special styling for block equations
            return Paragraph(f'<font face="Times-Italic" size="12">{equation}</font>', equation_style)
        else:
            # Inline equation
            equation_style = ParagraphStyle(
                name='InlineEquation',
                parent=self.styles['Normal'],
                fontName='Times-Italic',  # Use italic for equations
                fontSize=10,
                leading=12
            )
            # Keep it simpler for inline equations
            return Paragraph(f'<font face="Times-Italic">{equation}</font>', equation_style)
    
    def _format_as_basic_text(self, equation, eq_type):
        """
        Most basic fallback for equation formatting.
        
        Args:
            equation (str): Equation text
            eq_type (str): 'inline' or 'block'
            
        Returns:
            reportlab.platypus.Paragraph: A very simple paragraph
        """
        # Create a very simple style
        style = ParagraphStyle(
            name='BasicEquation',
            parent=self.styles['Normal'],
            fontName='Times-Italic'
        )
        
        # Just render as italic text
        return Paragraph(f"<i>{equation}</i>", style)