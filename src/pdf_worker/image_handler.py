from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, Spacer, KeepTogether, CondPageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
import os
from PIL import Image as PILImage
import logging
import re

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
        
        # Create caption style - use a safe font that's definitely available
        body_config = self.style_config.get('body_text', {})
        caption_font = self.image_style.get('caption', {}).get('font', 'Helvetica')
        
        # Ensure we use a standard font that will be available
        if "italic" in caption_font.lower() and not caption_font.endswith("-Italic"):
            # If italic is requested but not in standard format, use a standard italic font
            caption_font = "Helvetica-Italic"
        elif caption_font not in ['Helvetica', 'Helvetica-Bold', 'Helvetica-Italic', 
                                  'Times-Roman', 'Times-Bold', 'Times-Italic', 
                                  'Courier', 'Courier-Bold', 'Courier-Italic']:
            # Default to a safe font if an unsupported font is requested
            caption_font = "Helvetica"
            
        self.caption_style = ParagraphStyle(
            name='ImageCaption',
            fontName=caption_font,
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
                
                # Reduce spacing before and after image to minimize empty space
                # Use smaller spaces for inline images, larger for full-page ones
                space_before = self.image_style.get('space_before', 12)
                space_after = self.image_style.get('space_after', 12)
                
                if not is_full_page:
                    # Reduce spacing for inline images to avoid excessive whitespace
                    space_before = max(6, space_before // 2)
                    space_after = max(6, space_after // 2)
                
                # Group image and caption together
                image_group = [
                    Spacer(1, space_before),
                    reportlab_image,
                    Spacer(1, 4),  # Reduced space between image and caption
                    caption_paragraph,
                    Spacer(1, space_after)
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
        Distribute images within text paragraphs and break long paragraphs.
        
        Args:
            text (str): The section text
            image_flowables (list): List of image flowables
            body_text_style (ParagraphStyle): Style for the body text
            
        Returns:
            list: Combined list of text and image flowables
        """
        if not image_flowables:
            # Even if there are no images, we should still break up long paragraphs
            return self._break_long_paragraphs(text, body_text_style)
        
        # First, break the text into better paragraphs
        paragraphs = self._split_into_paragraphs(text)
        
        # Make sure we don't have paragraphs that are too long
        all_paragraphs = []
        for p in paragraphs:
            all_paragraphs.extend(self._break_long_paragraph(p))
            
        # Create paragraph flowables
        para_flowables = [Paragraph(p, body_text_style) for p in all_paragraphs if p.strip()]
        
        # For single image, place it at an optimal position (not necessarily at the end)
        if len(image_flowables) == 1:
            if len(para_flowables) <= 2:
                # If there are only 1-2 paragraphs, put the image at the end
                combined = para_flowables + image_flowables
            else:
                # Otherwise, place it after approximately 1/3 of the paragraphs
                insert_pos = max(1, len(para_flowables) // 3)
                combined = para_flowables[:insert_pos] + image_flowables + para_flowables[insert_pos:]
            return combined
        
        # For multiple images, distribute them between paragraphs
        combined = []
        
        # Calculate spacing between images
        if len(para_flowables) >= len(image_flowables):
            # We have enough paragraphs to space out images
            paragraph_chunks = self._divide_paragraphs(para_flowables, len(image_flowables))
            
            # Interleave paragraph chunks and images
            for i, chunk in enumerate(paragraph_chunks):
                combined.extend(chunk)
                if i < len(image_flowables):
                    combined.append(image_flowables[i])
                    
            # Add any remaining paragraph chunks
            if len(paragraph_chunks) > len(image_flowables):
                combined.extend(paragraph_chunks[-1])
        else:
            # More images than paragraphs, alternate paragraph-image
            for i in range(max(len(para_flowables), len(image_flowables))):
                if i < len(para_flowables):
                    combined.append(para_flowables[i])
                if i < len(image_flowables):
                    combined.append(image_flowables[i])
        
        return combined
    
    def _split_into_paragraphs(self, text):
        """Split text into better paragraph chunks based on content analysis."""
        # First, split by any double newlines that already exist
        initial_paragraphs = text.split('\n\n')
        
        if len(initial_paragraphs) > 1:
            return initial_paragraphs
            
        # If there's only one paragraph, try to split it more intelligently
        # Split on single newlines as a start
        paragraphs = text.split('\n')
        
        if len(paragraphs) > 1:
            return paragraphs
            
        # If we still have just one paragraph, try to break by sentences at reasonable intervals
        return self._break_long_paragraph(text)
    
    def _break_long_paragraph(self, text, max_length=800):
        """Break a long paragraph into smaller manageable pieces."""
        if len(text) <= max_length:
            return [text]
            
        # Split by sentences (look for period, question mark, or exclamation mark followed by a space)
        sentence_endings = [m.start() for m in re.finditer(r'[.!?]\s+', text)]
        
        if not sentence_endings:
            # If we can't find sentence boundaries, just break by length
            chunks = []
            for i in range(0, len(text), max_length):
                chunks.append(text[i:i+max_length])
            return chunks
        
        # Group sentences into chunks of appropriate length
        chunks = []
        start_idx = 0
        current_length = 0
        
        for end_idx in sentence_endings:
            sentence_length = (end_idx + 2) - start_idx  # +2 to include the period and space
            
            if current_length + sentence_length > max_length:
                # This sentence would make the chunk too long, so start a new chunk
                chunks.append(text[start_idx:end_idx+2].strip())
                start_idx = end_idx + 2
                current_length = 0
            else:
                current_length += sentence_length
        
        # Add any remaining text
        if start_idx < len(text):
            chunks.append(text[start_idx:].strip())
            
        return chunks
    
    def _break_long_paragraphs(self, text, body_text_style):
        """Break long text into paragraphs and convert to flowables."""
        paragraphs = self._split_into_paragraphs(text)
        
        # Break any paragraphs that are still too long
        all_paragraphs = []
        for p in paragraphs:
            all_paragraphs.extend(self._break_long_paragraph(p))
            
        # Convert to paragraph flowables
        return [Paragraph(p, body_text_style) for p in all_paragraphs if p.strip()]
    
    def _divide_paragraphs(self, paragraphs, num_divisions):
        """Divide paragraphs into approximately equal chunks."""
        if num_divisions <= 1:
            return [paragraphs]
            
        chunk_size = max(1, len(paragraphs) // num_divisions)
        chunks = []
        
        for i in range(0, len(paragraphs), chunk_size):
            chunks.append(paragraphs[i:i+chunk_size])
            
        # If we didn't get enough chunks, combine some of the smaller ones
        if len(chunks) > num_divisions:
            while len(chunks) > num_divisions:
                # Find the smallest chunk
                smallest_idx = min(range(len(chunks)), key=lambda i: len(chunks[i]))
                
                # If it's the last chunk, combine it with the second-to-last
                if smallest_idx == len(chunks) - 1:
                    chunks[smallest_idx-1].extend(chunks[smallest_idx])
                    chunks.pop()
                else:
                    # Otherwise combine it with the next chunk
                    chunks[smallest_idx].extend(chunks[smallest_idx+1])
                    chunks.pop(smallest_idx+1)
        
        return chunks