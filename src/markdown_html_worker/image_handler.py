from reportlab.lib import colors
from reportlab.platypus import Image, Paragraph, Spacer, KeepTogether
from reportlab.lib.styles import ParagraphStyle
import os
from PIL import Image as PILImage
import logging
import re

class ImageHandler:
    """Handles image processing for PDF generation in the Markdown/HTML processor."""
    
    def __init__(self, style_config, image_base_path='images'):
        """
        Initialize the image handler.
        
        Args:
            style_config (dict): Style configuration
            image_base_path (str): Base path to look for images
        """
        self.style_config = style_config
        self.image_base_path = image_base_path
        self.image_counter = 0
        self.logger = logging.getLogger(__name__)
        
        # Get image style settings or use defaults
        self.image_style = self.style_config.get('images', {})
        
        # Create caption style
        body_config = self.style_config.get('body_text', {})
        caption_font = self.image_style.get('caption', {}).get('font', 'Helvetica-Italic')
        
        self.caption_style = ParagraphStyle(
            name='ImageCaption',
            fontName=caption_font,
            fontSize=self.image_style.get('caption', {}).get('size', body_config.get('size', 10) - 2),
            leading=self.image_style.get('caption', {}).get('leading', body_config.get('leading', 12)),
            textColor=self._parse_color(self.image_style.get('caption', {}).get('color', '#333333')),
            alignment=1,  # Center alignment
            spaceAfter=self.image_style.get('caption', {}).get('space_after', 12)
        )
        
    def _parse_color(self, color_value):
        """Parse color from string or hex value."""
        if isinstance(color_value, str):
            if color_value.startswith('#'):
                return colors.HexColor(color_value)
            else:
                return getattr(colors, color_value, colors.black)
        return colors.black
    
    def process_image(self, img_path, caption=None):
        """
        Process an image and return its flowable representation.
        
        Args:
            img_path (str): Path to the image file
            caption (str, optional): Caption for the image
            
        Returns:
            list: List of flowables (image and caption)
        """
        try:
            # Increment image counter
            self.image_counter += 1
            
            # Resolve image path
            if not os.path.isabs(img_path):
                img_path = os.path.join(self.image_base_path, img_path)
            
            if not os.path.exists(img_path):
                self.logger.warning(f"Image not found: {img_path}")
                # Return a placeholder
                return self._create_placeholder(caption)
            
            # Create ReportLab image
            reportlab_image = Image(img_path)
            
            # Scale image to fit within available width
            max_width = self.image_style.get('max_width', 450)
            scale_factor = min(1.0, max_width / reportlab_image.drawWidth)
            
            # Apply scaling
            reportlab_image.drawWidth *= scale_factor
            reportlab_image.drawHeight *= scale_factor
            
            # Center image
            reportlab_image.hAlign = 'CENTER'
            
            # Prepare caption
            if caption:
                caption_text = f"<b>Figure {self.image_counter}:</b> {caption}"
            else:
                caption_text = f"<b>Figure {self.image_counter}</b>"
            
            caption_paragraph = Paragraph(caption_text, self.caption_style)
            
            # Space before and after image
            space_before = self.image_style.get('space_before', 12)
            space_after = self.image_style.get('space_after', 12)
            
            # Group image and caption together
            return [
                Spacer(1, space_before),
                reportlab_image,
                Spacer(1, 4),  # Small space between image and caption
                caption_paragraph,
                Spacer(1, space_after)
            ]
            
        except Exception as e:
            self.logger.error(f"Error processing image: {str(e)}")
            return self._create_placeholder(caption)
    
    def _create_placeholder(self, caption=None):
        """Create a placeholder for missing or invalid images."""
        # Create a text placeholder
        placeholder_style = ParagraphStyle(
            name='ImagePlaceholder',
            parent=self.caption_style,
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.gray
        )
        
        # Caption text
        if caption:
            caption_text = f"<b>Figure {self.image_counter} (Image not found):</b> {caption}"
        else:
            caption_text = f"<b>Figure {self.image_counter} (Image not found)</b>"
        
        return [
            Spacer(1, 12),
            Paragraph("[Image Placeholder]", placeholder_style),
            Spacer(1, 4),
            Paragraph(caption_text, self.caption_style),
            Spacer(1, 12)
        ]