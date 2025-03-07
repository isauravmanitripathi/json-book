#!/usr/bin/env python3
import os
import re
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple

from .markdown_processor import MarkdownProcessor
from .markdown_style_manager import MarkdownStyleManager

class MarkdownToJsonConverter:
    """
    Converts markdown files to the JSON structure expected by the PDF generator.
    Handles styling, code blocks, and image extraction according to style guidelines.
    """
    
    def __init__(self, markdown_dir: str, style_name: str = "standard", images_dir: str = "images"):
        """
        Initialize the markdown to JSON converter.
        
        Args:
            markdown_dir (str): Directory containing markdown files
            style_name (str): Name of the style to use
            images_dir (str): Directory for storing extracted images
        """
        self.markdown_dir = Path(markdown_dir)
        self.images_dir = Path(images_dir)
        
        # Initialize style manager and load style
        self.style_manager = MarkdownStyleManager()
        self.style = self.style_manager.load_style(style_name)
        
        # Initialize markdown processor
        self.processor = MarkdownProcessor(markdown_dir)
        
        # Ensure image directory exists
        if not self.images_dir.exists():
            os.makedirs(self.images_dir, exist_ok=True)
    
    def convert(self, output_json_path: str, process_images: bool = True) -> str:
        """
        Convert markdown files to JSON structure.
        
        Args:
            output_json_path (str): Path to save the output JSON
            process_images (bool): Whether to process and copy images
            
        Returns:
            str: Path to the generated JSON file
        """
        # Process markdown files to get structured content
        structured_data = self.processor.process_directory()
        
        # Apply styling according to style guidelines
        styled_data = self._apply_styling(structured_data)
        
        # Process and handle images if requested
        if process_images:
            styled_data = self._process_images(styled_data)
        
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_json_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Write the JSON output
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(styled_data, f, indent=2, ensure_ascii=False)
        
        return output_json_path
    
    def _apply_styling(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply styling to the structured data according to style guidelines.
        
        Args:
            data (List[Dict[str, Any]]): Structured data from markdown processor
            
        Returns:
            List[Dict[str, Any]]: Styled data
        """
        styled_data = []
        
        for item in data:
            styled_item = item.copy()
            
            # Apply heading styling
            styled_item = self._style_headings(styled_item)
            
            # Process code blocks according to style
            if "text" in styled_item:
                styled_item["text"] = self._style_code_blocks(styled_item["text"])
            
            styled_data.append(styled_item)
            
        return styled_data
    
    def _style_headings(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply heading styling according to style guidelines.
        
        Args:
            item (Dict[str, Any]): Section item
            
        Returns:
            Dict[str, Any]: Item with styled headings
        """
        heading_styles = self.style.get("heading_styles", {})
        
        # Chapter title styling (h1)
        h1_style = heading_styles.get("h1", {})
        if "chapter_name" in item and h1_style:
            chapter_name = item["chapter_name"]
            
            # Apply capitalization
            capitalization = h1_style.get("capitalize", "none")
            if capitalization == "upper":
                chapter_name = chapter_name.upper()
            elif capitalization == "lower":
                chapter_name = chapter_name.lower()
            elif capitalization == "title":
                chapter_name = chapter_name.title()
                
            # Apply numbering if enabled
            if h1_style.get("numbered", False):
                number_format = h1_style.get("number_format", "{chapter}.")
                chapter_number = number_format.format(chapter=item.get("chapter_id", ""))
                chapter_name = f"{chapter_number} {chapter_name}"
                
            item["chapter_name"] = chapter_name
            
        # Section title styling (h2)
        h2_style = heading_styles.get("h2", {})
        if "section_name" in item and h2_style:
            section_name = item["section_name"]
            
            # Apply capitalization
            capitalization = h2_style.get("capitalize", "none")
            if capitalization == "upper":
                section_name = section_name.upper()
            elif capitalization == "lower":
                section_name = section_name.lower()
            elif capitalization == "title":
                section_name = section_name.title()
                
            # Apply numbering if enabled
            if h2_style.get("numbered", False):
                number_format = h2_style.get("number_format", "{chapter}.{section}.")
                section_number = number_format.format(
                    chapter=item.get("chapter_id", ""),
                    section=item.get("section_number", "")
                )
                section_name = f"{section_number} {section_name}"
                
            item["section_name"] = section_name
            
        return item
    
    def _style_code_blocks(self, text: str) -> str:
        """
        Style code blocks according to style guidelines.
        
        Args:
            text (str): Text content
            
        Returns:
            str: Text with styled code blocks
        """
        code_style = self.style.get("code_blocks", {})
        style_type = code_style.get("style", "backtick")
        highlight_syntax = code_style.get("highlight_syntax", True)
        default_language = code_style.get("default_language", "")
        
        # For backtick style (```), ensure proper formatting
        if style_type == "backtick":
            # Function to replace code blocks with properly formatted ones
            def code_block_replacer(match):
                code = match.group(2).strip()
                lang = match.group(1) or default_language
                
                # Add line numbers if requested
                if code_style.get("line_numbers", False):
                    # Add line numbers to each line
                    lines = code.split("\n")
                    numbered_lines = []
                    for i, line in enumerate(lines, 1):
                        numbered_lines.append(f"{i:3d} | {line}")
                    code = "\n".join(numbered_lines)
                
                return f"\n```{lang}\n{code}\n```\n"
            
            # Apply the code block styling
            text = re.sub(r'```(.*?)\n(.*?)```', code_block_replacer, text, flags=re.DOTALL)
            
        # For indented style (4 spaces), convert to backtick style for compatibility
        elif style_type == "indented":
            # Find indented code blocks and convert to backtick style
            def indented_to_backtick(match):
                code = match.group(1).strip()
                return f"\n```{default_language}\n{code}\n```\n"
                
            # Pattern for indented code blocks (4+ spaces or tab at beginning of line)
            pattern = r'(?:^|\n)(?:[ ]{4,}|\t)(.*?)(?=\n[^ \t]|\Z)'
            text = re.sub(pattern, indented_to_backtick, text, flags=re.DOTALL)
            
        return text
    
    def _process_images(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process and handle images in the structured data.
        
        Args:
            data (List[Dict[str, Any]]): Structured data
            
        Returns:
            List[Dict[str, Any]]: Data with processed images
        """
        result = []
        
        # Image counter for generating sequential figure numbers
        image_counter = 1
        
        for item in data:
            # Skip items without images
            if "images" not in item or not item["images"]:
                result.append(item)
                continue
                
            processed_item = item.copy()
            processed_images = []
            
            for img in item["images"]:
                image_path = img.get("image_path", "")
                caption = img.get("caption", "")
                
                # Skip if no image path
                if not image_path:
                    continue
                    
                # Process the image path
                src_path = None
                
                # Check if it's a URL (no need to copy, just reference)
                if image_path.startswith(('http://', 'https://')):
                    processed_path = image_path
                else:
                    # Check if image exists relative to markdown dir
                    src_path = self.markdown_dir / image_path
                    if not src_path.exists():
                        # Try direct path
                        src_path = Path(image_path)
                        
                    # If file exists, copy it to images dir with appropriate name
                    if src_path.exists():
                        chapter_id = item.get("chapter_id", "").zfill(2)
                        img_filename = f"{chapter_id}_image_{image_counter}{src_path.suffix}"
                        
                        # Ensure chapter subfolder exists
                        chapter_images_dir = self.images_dir / chapter_id
                        os.makedirs(chapter_images_dir, exist_ok=True)
                        
                        # Copy the image
                        dest_path = chapter_images_dir / img_filename
                        shutil.copy2(src_path, dest_path)
                        
                        # Set the processed path relative to images_dir
                        processed_path = f"{chapter_id}/{img_filename}"
                    else:
                        # Image not found, skip
                        print(f"Warning: Image not found: {image_path}")
                        continue
                
                # Style the caption
                img_style = self.style.get("images", {})
                if caption and img_style.get("caption_style") == "figure":
                    caption_prefix = img_style.get("figure_prefix", "Figure {number}: ")
                    caption = caption_prefix.format(
                        chapter=item.get("chapter_id", ""),
                        number=image_counter
                    ) + caption
                
                # Add the processed image
                processed_images.append({
                    "image_path": processed_path,
                    "caption": caption
                })
                
                # Increment image counter
                image_counter += 1
            
            # Update the item with processed images
            processed_item["images"] = processed_images
            result.append(processed_item)
            
        return result


if __name__ == "__main__":
    # Example usage
    converter = MarkdownToJsonConverter(
        markdown_dir="path/to/markdown/files",
        style_name="standard",
        images_dir="images"
    )
    output_file = converter.convert("output.json")
    print(f"Converted markdown to JSON: {output_file}")