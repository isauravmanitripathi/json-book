#!/usr/bin/env python3
import logging
import os
import tempfile
from reportlab.platypus import Image, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

class EquationBlock:
    """Component for generating an equation block in the PDF document."""
    
    def __init__(self, style_config, equation, eq_type='inline'):
        """
        Initialize equation block component.
        
        Args:
            style_config (dict): Style configuration
            equation (str): LaTeX equation string
            eq_type (str): 'inline' or 'block'
        """
        self.logger = logging.getLogger(__name__)
        self.style_config = style_config
        self.equation = equation
        self.eq_type = eq_type
        self.styles = getSampleStyleSheet()
        
    def add_to_story(self, story, equation_formatter=None):
        """
        Add the equation to the document story.
        
        Args:
            story (list): ReportLab story (content flow)
            equation_formatter (EquationFormatter, optional): For formatting equations
            
        Returns:
            None
        """
        try:
            if equation_formatter:
                # Format equation using the provided formatter
                formatted_eq = equation_formatter.format_equation(self.equation, self.eq_type)
                story.append(formatted_eq)
            else:
                # Fallback to simple text representation
                eq_style = ParagraphStyle(
                    name='Equation',
                    parent=self.styles['Normal'],
                    alignment=TA_CENTER if self.eq_type == 'block' else 0,
                    leftIndent=20 if self.eq_type == 'block' else 0,
                    rightIndent=20 if self.eq_type == 'block' else 0,
                    spaceBefore=6 if self.eq_type == 'block' else 0,
                    spaceAfter=6 if self.eq_type == 'block' else 0,
                    fontName='Times-Italic'
                )
                
                if self.eq_type == 'block':
                    eq_text = f"<i>{self.equation}</i>"
                else:
                    eq_text = f"<i>{self.equation}</i>"
                    
                story.append(Paragraph(eq_text, eq_style))
                
        except Exception as e:
            self.logger.error(f"Error adding equation to story: {str(e)}")
            # Add a simple version as fallback
            story.append(Paragraph(f"<i>Equation: {self.equation}</i>", self.styles['Normal']))