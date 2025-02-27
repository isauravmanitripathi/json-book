from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, Spacer, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
import os
from PIL import Image as PILImage
import logging

class ImageHandler:
    """Handles image processing and integration into PDFs."""
    
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
        # In the ImageHandler.__init__ method, modify the caption_style creation:
        self.caption_style = ParagraphStyle(
            name='ImageCaption',
            fontName=self.image_style.get('caption', {}).get('font', 'Helvetica'), # Remove -Italic
            fontSize=self.image_style.get('caption', {}).get('size', body_config.get('size', 10)),
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
    
    def process_section_images(self, section_data, body_text_style):
        """
        Process images for a section and return flowables to be integrated into the story.
        
        Args:
            section_data (dict): Section data including text and images
            body_text_style (ParagraphStyle): Style for the body text
            
        Returns:
            tuple: (text_paragraphs, image_flowables)
                text_paragraphs: List of text paragraphs
                image_flowables: List of image flowables (can be inserted between paragraphs)
        """
        # Check if section has images
        images = section_data.get('images', [])
        if not images:
            return None, []
        
        # Process all images in the section
        image_flowables = []
        
        for img_data in images:
            try:
                # Get image path and caption
                img_path = img_data.get('image_path', '')
                caption = img_data.get('caption', '')
                
                # Full path to image
                full_path = os.path.join(self.image_base_path, img_path)
                if not os.path.exists(full_path):
                    self.logger.warning(f"Image not found: {full_path}")
                    continue
                
                # Increment image counter
                self.image_counter += 1
                
                # Get image dimensions using PIL
                with PILImage.open(full_path) as img:
                    img_width, img_height = img.size
                
                # Create ReportLab image
                reportlab_image = Image(full_path)
                
                # Get available width (considering margins)
                page_config = self.style_config.get('page', {})
                margins = page_config.get('margins', {'left': 72, 'right': 72})
                available_width = 595 - margins.get('left', 72) - margins.get('right', 72)  # A4 width = 595pt
                
                # Scale image to fit within available width
                max_width = self.image_style.get('max_width', available_width)
                scale_factor = min(1.0, max_width / reportlab_image.drawWidth)
                
                # Check if image should be treated as a full-page image
                is_full_page = False
                if self.image_style.get('full_page_threshold', 0.8):
                    # If image height after scaling would take up most of the page, make it full page
                    page_height = 842  # A4 height = 842pt
                    available_height = page_height - margins.get('top', 72) - margins.get('bottom', 72)
                    if (reportlab_image.drawHeight * scale_factor) > (available_height * self.image_style.get('full_page_threshold', 0.8)):
                        is_full_page = True
                        # Recalculate scale factor for full page
                        scale_factor = min(
                            available_width / reportlab_image.drawWidth,
                            (available_height * 0.85) / reportlab_image.drawHeight  # Use 85% of height to leave room for caption
                        )
                
                # Apply scaling
                reportlab_image.drawWidth *= scale_factor
                reportlab_image.drawHeight *= scale_factor
                
                # Center image
                reportlab_image.hAlign = 'CENTER'
                
                # Prepare caption text
                if caption:
                    caption_text = f"<b>Figure {self.image_counter}:</b> {caption}"
                else:
                    caption_text = f"<b>Figure {self.image_counter}</b>"
                
                caption_paragraph = Paragraph(caption_text, self.caption_style)
                
                # Group image and caption together
                image_group = [
                    Spacer(1, self.image_style.get('space_before', 12)),
                    reportlab_image,
                    Spacer(1, 6),
                    caption_paragraph,
                    Spacer(1, self.image_style.get('space_after', 12))
                ]
                
                # For full-page images, we might want to page break before and after
                if is_full_page and self.image_style.get('full_page_break', True):
                    from reportlab.platypus import PageBreak
                    image_group.insert(0, PageBreak())
                    image_group.append(PageBreak())
                
                # Keep image and caption together
                image_flowables.append(KeepTogether(image_group))
                
            except Exception as e:
                self.logger.error(f"Error processing image: {str(e)}")
                continue
        
        return image_flowables
    
    def distribute_images(self, text, image_flowables, body_text_style):
        """
        Distribute images within text paragraphs.
        
        Args:
            text (str): The section text
            image_flowables (list): List of image flowables
            body_text_style (ParagraphStyle): Style for the body text
            
        Returns:
            list: Combined list of text and image flowables
        """
        if not image_flowables:
            return [Paragraph(text, body_text_style)]
        
        # Split text into paragraphs
        paragraphs = text.split('\n\n')
        if len(paragraphs) == 1:
            # If there's only one paragraph, split by sentences to create more insertion points
            import re
            # Split by sentence-ending punctuation followed by space or newline
            sentences = re.split(r'([.!?])\s+', text)
            # Recombine sentences to keep the ending punctuation
            paragraphs = []
            for i in range(0, len(sentences), 2):
                if i+1 < len(sentences):
                    paragraphs.append(sentences[i] + sentences[i+1])
                else:
                    paragraphs.append(sentences[i])
        
        # Create paragraph flowables
        para_flowables = [Paragraph(p, body_text_style) for p in paragraphs if p.strip()]
        
        # For single image, add it at the end of text
        if len(image_flowables) == 1:
            combined = para_flowables + image_flowables
            return combined
        
        # For multiple images, distribute them between paragraphs
        combined = []
        
        # Calculate spacing between images
        if len(para_flowables) >= len(image_flowables):
            # We have enough paragraphs to space out images
            spacing = max(1, len(para_flowables) // (len(image_flowables) + 1))
            
            # Place images after selected paragraphs
            img_index = 0
            for i, para in enumerate(para_flowables):
                combined.append(para)
                
                # Add image after certain paragraphs
                if img_index < len(image_flowables) and (i + 1) % spacing == 0:
                    combined.append(image_flowables[img_index])
                    img_index += 1
            
            # Add any remaining images at the end
            combined.extend(image_flowables[img_index:])
            
        else:
            # More images than paragraphs, alternate paragraph-image
            for i in range(max(len(para_flowables), len(image_flowables))):
                if i < len(para_flowables):
                    combined.append(para_flowables[i])
                if i < len(image_flowables):
                    combined.append(image_flowables[i])
        
        return combined