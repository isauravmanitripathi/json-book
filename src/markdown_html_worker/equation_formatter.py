#!/usr/bin/env python3
import logging
import re
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

class EquationFormatter:
    """Format equations for PDF rendering using ReportLab's built-in capabilities."""
    
    def __init__(self):
        """Initialize the equation formatter."""
        self.logger = logging.getLogger(__name__)
        self.styles = getSampleStyleSheet()
        
        # Common equations used in ML/finance - add more as needed
        self.common_equations = {
            "eq_1": "X = {x₁, x₂, ..., xₙ}",
            "eq_2": "xₜ",
            "eq_3": "t",
            "eq_4": "T",
            "eq_5": "μ",
            "eq_6": "σ²",
            "eq_7": "P(X|θ)",
            "eq_8": "∑ⁿᵢ₌₁ xᵢ",
            "eq_9": "β₀ + β₁x₁ + ... + βₙxₙ",
            "eq_10": "VaR_α(X)",
            "eq_11": "L(θ,X) = ∏ᵢ₌₁ⁿ f(xᵢ|θ)",
            "eq_12": "y = f(x) + ε",
            "eq_13": "H₀",
            "eq_14": "H₁",
            "eq_15": "∫ f(x) dx"
        }
    
    def format_equation(self, equation, eq_type='inline'):
        """
        Format an equation for PDF rendering using ReportLab's built-in rendering.
        
        Args:
            equation (str): Equation string or equation ID
            eq_type (str): 'inline' or 'block'
            
        Returns:
            reportlab.platypus.Paragraph: A paragraph with formatted equation
        """
        try:
            # Check if this is a reference to a pre-defined equation
            if equation.startswith("eq_") or equation.startswith("Equation eq_"):
                eq_id = equation.replace("Equation ", "")
                if eq_id in self.common_equations:
                    equation = self.common_equations[eq_id]
                else:
                    # Generate a simple placeholder equation if not found
                    equation = f"equation{eq_id.replace('eq_', '')}"
            
            # Clean and prepare the equation
            equation = self._clean_equation(equation)
            
            # Format as special text
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
        
        # Remove LaTeX commands that ReportLab can't handle
        equation = equation.replace('\\frac', '/')
        equation = equation.replace('\\cdot', '·')
        equation = equation.replace('\\times', '×')
        equation = equation.replace('\\pm', '±')
        equation = equation.replace('\\leq', '≤')
        equation = equation.replace('\\geq', '≥')
        equation = equation.replace('\\neq', '≠')
        equation = equation.replace('\\approx', '≈')
        equation = equation.replace('\\infty', '∞')
        equation = equation.replace('\\partial', '∂')
        equation = equation.replace('\\sum', '∑')
        equation = equation.replace('\\prod', '∏')
        equation = equation.replace('\\int', '∫')
        
        # Replace common Greek letters with their Unicode equivalents
        greek_letters = {
            '\\alpha': 'α', '\\beta': 'β', '\\gamma': 'γ', '\\delta': 'δ',
            '\\epsilon': 'ε', '\\zeta': 'ζ', '\\eta': 'η', '\\theta': 'θ',
            '\\kappa': 'κ', '\\lambda': 'λ', '\\mu': 'μ', '\\nu': 'ν',
            '\\xi': 'ξ', '\\pi': 'π', '\\rho': 'ρ', '\\sigma': 'σ',
            '\\tau': 'τ', '\\phi': 'φ', '\\chi': 'χ', '\\psi': 'ψ',
            '\\omega': 'ω'
        }
        
        for latex_sym, unicode_sym in greek_letters.items():
            equation = equation.replace(latex_sym, unicode_sym)
        
        # Convert subscripts and superscripts to cleaner format
        equation = re.sub(r'_([0-9a-zA-Z])', r'<sub>\1</sub>', equation)
        equation = re.sub(r'\^([0-9a-zA-Z])', r'<sup>\1</sup>', equation)
        
        # Replace LaTeX set notation with Unicode
        equation = equation.replace('\\in', '∈')
        equation = equation.replace('\\subset', '⊂')
        equation = equation.replace('\\supset', '⊃')
        equation = equation.replace('\\cup', '∪')
        equation = equation.replace('\\cap', '∩')
        
        return equation.strip()
    
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