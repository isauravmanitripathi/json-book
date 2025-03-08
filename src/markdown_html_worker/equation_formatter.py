#!/usr/bin/env python3
import logging
import re
import os
import gc
import tempfile
import shutil
from pathlib import Path
from reportlab.platypus import Image, Paragraph
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

# Import matplotlib for equation rendering
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    from matplotlib import mathtext
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    
# Try importing sympy as an alternative
try:
    import sympy
    from sympy import preview
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False

class EquationFormatter:
    """
    Format equations for PDF rendering using image-based rendering.
    Falls back to ReportLab's built-in text rendering capabilities when image rendering fails.
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
        
        # Configuration for matplotlib rendering
        if MATPLOTLIB_AVAILABLE:
            self.mathtext_parser = mathtext.MathTextParser('path')
            # Configure matplotlib for better math rendering
            plt.rcParams.update({
                'mathtext.fontset': 'cm',  # Computer Modern font (TeX-like)
                'mathtext.rm': 'serif',
                'mathtext.bf': 'serif:bold',
                'mathtext.it': 'serif:italic',
                'mathtext.sf': 'sans\\-serif',
            })
    
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
        Format an equation for PDF rendering, attempting to use image rendering first.
        
        Args:
            equation (str): Equation string or equation ID
            eq_type (str): 'inline' or 'block'
            
        Returns:
            reportlab.platypus.Flowable: A flowable for the PDF (Image or Paragraph)
        """
        try:
            self.equation_counter += 1
            
            # Extract LaTeX content from markdown format if present
            latex_pattern = r'\$(.*?)\$'
            dollar_match = re.search(latex_pattern, equation)
            if dollar_match:
                # Extract the LaTeX content from within the $ delimiters
                latex_content = dollar_match.group(1).strip()
                if latex_content:
                    equation = latex_content
            
            # Check if this is a reference to an equation marker
            elif equation.startswith("[EQUATION:") or equation.startswith("Equation "):
                # This is just a placeholder, generate generic equation text
                if "[EQUATION:eq_" in equation:
                    eq_num_match = re.search(r'eq_(\d+)', equation)
                    if eq_num_match:
                        eq_num = eq_num_match.group(1)
                        equation = f"E_{{{eq_num}}}"
            
            # Clean and prepare the equation for rendering
            equation = self._clean_equation(equation)
            
            # Try to render the equation as an image
            image_path = self._render_equation_to_image(equation, eq_type, idx=self.equation_counter)
            
            if image_path:
                # Create an image flowable
                img = Image(image_path)
                
                # Scale the image appropriately
                if eq_type == 'inline':
                    scale_factor = 0.7  # Smaller for inline equations
                else:
                    scale_factor = 0.9  # Larger for block equations
                
                img.drawWidth *= scale_factor
                img.drawHeight *= scale_factor
                
                # Center block equations
                if eq_type == 'block':
                    img.hAlign = 'CENTER'
                
                return img
            else:
                # Fall back to text rendering if image creation fails
                return self._format_as_styled_text(equation, eq_type)
                
        except Exception as e:
            self.logger.error(f"Error formatting equation: {str(e)}")
            # Fallback to very simple text
            return self._format_as_basic_text(equation, eq_type)
    
    def _clean_equation(self, equation):
        """
        Clean and normalize equation text for rendering.
        
        Args:
            equation (str): Raw equation text
            
        Returns:
            str: Cleaned equation text
        """
        # Remove HTML tags if present
        equation = re.sub(r'<[^>]*>', '', equation)
        
        # Convert to LaTeX format for matplotlib and sympy
        equation = self._convert_unicode_to_latex(equation)
        
        return equation.strip()
    
    def _convert_unicode_to_latex(self, equation):
        """
        Convert Unicode math symbols to LaTeX for better rendering.
        
        Args:
            equation (str): Equation text with potential Unicode math symbols
            
        Returns:
            str: Equation with LaTeX commands
        """
        # Convert common Unicode math symbols to LaTeX
        replacements = {
            # Greek letters
            'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta',
            'ε': r'\epsilon', 'ζ': r'\zeta', 'η': r'\eta', 'θ': r'\theta',
            'κ': r'\kappa', 'λ': r'\lambda', 'μ': r'\mu', 'ν': r'\nu',
            'ξ': r'\xi', 'π': r'\pi', 'ρ': r'\rho', 'σ': r'\sigma',
            'τ': r'\tau', 'φ': r'\phi', 'χ': r'\chi', 'ψ': r'\psi',
            'ω': r'\omega',
            
            # Operators and symbols
            '∑': r'\sum', '∏': r'\prod', '∫': r'\int', '∂': r'\partial',
            '∞': r'\infty', '≈': r'\approx', '≠': r'\neq', '≤': r'\leq',
            '≥': r'\geq', '∈': r'\in', '⊂': r'\subset', '⊃': r'\supset',
            '∪': r'\cup', '∩': r'\cap', '×': r'\times', '÷': r'\div',
            '±': r'\pm', '…': r'\ldots',
            
            # Replace subscripts and superscripts
            '₀': '_0', '₁': '_1', '₂': '_2', '₃': '_3', '₄': '_4',
            '₅': '_5', '₆': '_6', '₇': '_7', '₈': '_8', '₉': '_9',
            '⁰': '^0', '¹': '^1', '²': '^2', '³': '^3', '⁴': '^4',
            '⁵': '^5', '⁶': '^6', '⁷': '^7', '⁸': '^8', '⁹': '^9',
        }
        
        # Apply replacements
        for unicode_char, latex_cmd in replacements.items():
            equation = equation.replace(unicode_char, latex_cmd)
        
        # Handle VaR notation - common in financial texts
        equation = re.sub(r'VaR_([^({\s]+)', r'\\text{VaR}_{\1}', equation)
        equation = re.sub(r'VaR_{([^}]+)}', r'\\text{VaR}_{\1}', equation)
        
        # Handle Sharpe ratio notation
        equation = re.sub(r'Sharpe', r'\\text{Sharpe}', equation)
        equation = re.sub(r'S_{ortino}', r'\\text{Sortino}', equation)
        
        # Convert subscript notation like x_i to x_{i}
        equation = re.sub(r'_([a-zA-Z0-9])(\s|$|[^\{])', r'_{\1}\2', equation)
        
        # Convert superscript notation like x^i to x^{i}
        equation = re.sub(r'\^([a-zA-Z0-9])(\s|$|[^\{])', r'^{\1}\2', equation)
        
        return equation
    
    def _render_equation_to_image(self, equation, eq_type, idx=1):
        """
        Render an equation to an image file.
        
        Args:
            equation (str): LaTeX equation string
            eq_type (str): 'inline' or 'block'
            idx (int): Index/counter for the equation
            
        Returns:
            str: Path to image file or None if rendering failed
        """
        if not MATPLOTLIB_AVAILABLE and not SYMPY_AVAILABLE:
            self.logger.warning("Neither matplotlib nor sympy is available for equation rendering")
            return None
            
        # Create filename
        filename = f"equation_{idx}_{eq_type}.png"
        temp_path = os.path.join(self.temp_dir, filename)
        
        # For verification purposes, save to equations_dir if specified
        if self.equations_dir:
            perm_path = os.path.join(self.equations_dir, filename)
        else:
            perm_path = None
        
        # Add LaTeX delimiters based on equation type
        if eq_type == 'block':
            latex_eq = f"${equation}$"
        else:
            latex_eq = f"${equation}$"
        
        # Try rendering with matplotlib first
        if MATPLOTLIB_AVAILABLE:
            try:
                # Set DPI based on equation type for better quality
                dpi = 150 if eq_type == 'block' else 120
                
                # Create figure with transparent background
                fig = plt.figure(figsize=(10, 0.5), dpi=dpi)
                fig.patch.set_alpha(0.0)
                
                # Place equation text
                if eq_type == 'block':
                    plt.text(0.5, 0.5, f"${equation}$", 
                             fontsize=14, ha='center', va='center',
                             transform=fig.transFigure)
                else:
                    plt.text(0.5, 0.5, f"${equation}$", 
                             fontsize=12, ha='center', va='center',
                             transform=fig.transFigure)
                
                # Remove axes
                plt.axis('off')
                
                # Save the equation image
                plt.savefig(temp_path, format='png', bbox_inches='tight', 
                            pad_inches=0.1, transparent=True, dpi=dpi)
                plt.close(fig)
                
                # Also save permanent copy if requested
                if perm_path:
                    shutil.copy2(temp_path, perm_path)
                    
                return temp_path
                
            except Exception as e:
                self.logger.error(f"Matplotlib equation rendering failed: {str(e)}")
                # Try sympy as fallback
        
        # Try rendering with sympy if matplotlib failed
        if SYMPY_AVAILABLE:
            try:
                # Adjust size based on equation type
                if eq_type == 'block':
                    preview(latex_eq, viewer='file', filename=temp_path, euler=False, dvioptions=['-D', '150'])
                else:
                    preview(latex_eq, viewer='file', filename=temp_path, euler=False, dvioptions=['-D', '120'])
                
                # Also save permanent copy if requested
                if perm_path:
                    shutil.copy2(temp_path, perm_path)
                    
                return temp_path
                
            except Exception as e:
                self.logger.error(f"Sympy equation rendering failed: {str(e)}")
        
        return None
    
    def _format_as_styled_text(self, equation, eq_type):
        """
        Format equation as styled text with proper formatting (fallback method).
        
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