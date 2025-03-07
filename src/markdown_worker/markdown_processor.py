#!/usr/bin/env python3
import os
import re
import json
import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple

@dataclass
class MarkdownSection:
    """Represents a section within a chapter."""
    section_name: str
    section_number: str
    text: str
    images: List[Dict[str, str]] = field(default_factory=list)

@dataclass
class MarkdownChapter:
    """Represents a chapter with multiple sections."""
    chapter_id: str
    chapter_name: str
    last_modified: datetime.datetime
    sections: List[MarkdownSection] = field(default_factory=list)
    
    def to_dict(self) -> List[Dict[str, Any]]:
        """Convert to dictionary format compatible with existing JSON structure."""
        result = []
        for i, section in enumerate(self.sections, 1):
            section_dict = {
                "chapter_id": self.chapter_id,
                "chapter_name": self.chapter_name,
                "section_name": section.section_name,
                "section_number": section.section_number,
                "text": section.text
            }
            
            # Add images if any
            if section.images:
                section_dict["images"] = section.images
                
            result.append(section_dict)
        return result

class MarkdownProcessor:
    """Processes Markdown files to extract content in a structured format."""
    
    def __init__(self, markdown_dir: str):
        """
        Initialize the Markdown processor.
        
        Args:
            markdown_dir (str): Directory containing markdown files
        """
        self.markdown_dir = Path(markdown_dir)
        if not self.markdown_dir.exists() or not self.markdown_dir.is_dir():
            raise ValueError(f"Invalid markdown directory: {markdown_dir}")
    
    def process_directory(self) -> List[Dict[str, Any]]:
        """
        Process all markdown files in the directory and convert to structured format.
        
        Returns:
            List[Dict[str, Any]]: List of sections in JSON-compatible format
        """
        # Get all markdown files
        markdown_files = sorted(
            [f for f in self.markdown_dir.glob("*.md") if f.is_file()],
            key=lambda f: f.stat().st_mtime,  # Sort by modification time (oldest first)
            reverse=False
        )
        
        if not markdown_files:
            raise ValueError(f"No markdown files found in {self.markdown_dir}")
        
        # Process each file into a chapter
        chapters = []
        for i, file_path in enumerate(markdown_files, 1):
            chapter = self._process_file(file_path, f"{i}")
            chapters.append(chapter)
        
        # Convert chapters to JSON-compatible format
        result = []
        for chapter in chapters:
            result.extend(chapter.to_dict())
        
        return result
    
    def _process_file(self, file_path: Path, chapter_id: str) -> MarkdownChapter:
        """
        Process a single markdown file into a chapter with sections.
        
        Args:
            file_path (Path): Path to the markdown file
            chapter_id (str): Chapter ID/number
            
        Returns:
            MarkdownChapter: Structured chapter data
        """
        # Get file metadata
        modified_time = datetime.datetime.fromtimestamp(file_path.stat().st_mtime)
        
        # Get chapter name from filename (convert from kebab/snake case to Title Case)
        filename = file_path.stem
        chapter_name = self._format_title(filename)
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Process the content to extract sections
        sections = self._extract_sections(content)
        
        return MarkdownChapter(
            chapter_id=chapter_id,
            chapter_name=chapter_name,
            last_modified=modified_time,
            sections=sections
        )
    
    def _extract_sections(self, content: str) -> List[MarkdownSection]:
        """
        Extract sections from markdown content.
        
        Args:
            content (str): Markdown content
            
        Returns:
            List[MarkdownSection]: List of extracted sections
        """
        # Split content by level 2 headings (##)
        pattern = r'(?:^|\n)##\s+(.*?)(?=\n##\s+|\Z)'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        sections = []
        section_count = 0
        
        # Handle case where there are no ## headings
        if not re.search(pattern, content):
            # Check if there's a # heading to use as section title
            title_match = re.search(r'^#\s+(.*?)$', content, re.MULTILINE)
            section_title = title_match.group(1) if title_match else "Main Section"
            
            # Remove the # heading from content if it exists
            if title_match:
                content = re.sub(r'^#\s+.*?$\n?', '', content, 1, re.MULTILINE)
            
            # Process the entire content as one section
            section_count += 1
            processed_text = self._process_section_content(content)
            images = self._extract_images(content)
            
            sections.append(MarkdownSection(
                section_name=section_title,
                section_number=f"{section_count}",
                text=processed_text,
                images=images
            ))
            
            return sections
        
        # Process each section with ## heading
        for match in matches:
            section_count += 1
            section_text = match.group(0)
            
            # Extract section title (the ## heading)
            section_title_match = re.match(r'(?:^|\n)##\s+(.*?)(?:\n|$)', section_text)
            section_title = section_title_match.group(1) if section_title_match else f"Section {section_count}"
            
            # Remove the heading from the content
            section_content = re.sub(r'(?:^|\n)##\s+.*?(?:\n|$)', '\n', section_text, 1)
            
            # Process section content (code blocks, images, etc.)
            processed_text = self._process_section_content(section_content)
            images = self._extract_images(section_content)
            
            sections.append(MarkdownSection(
                section_name=section_title,
                section_number=f"{section_count}",
                text=processed_text,
                images=images
            ))
        
        return sections
    
    def _process_section_content(self, content: str) -> str:
        """
        Process section content to handle code blocks and other elements.
        
        Args:
            content (str): Section content
            
        Returns:
            str: Processed content
        """
        # Handle code blocks - ensure they're formatted correctly
        def code_block_replacement(match):
            code = match.group(2).strip()
            lang = match.group(1) or ""
            return f"\n```{lang}\n{code}\n```\n"
        
        # Replace code blocks with properly formatted versions
        content = re.sub(r'```(.*?)\n(.*?)```', code_block_replacement, content, flags=re.DOTALL)
        
        return content.strip()
    
    def _extract_images(self, content: str) -> List[Dict[str, str]]:
        """
        Extract image references from markdown content.
        
        Args:
            content (str): Markdown content
            
        Returns:
            List[Dict[str, str]]: List of image data (path and caption)
        """
        # Find all image references in the markdown
        # Format: ![caption](path/to/image.jpg)
        image_pattern = r'!\[(.*?)\]\((.*?)\)'
        matches = re.finditer(image_pattern, content)
        
        images = []
        for match in matches:
            caption = match.group(1) or ""
            image_path = match.group(2)
            
            # Make sure path is relative (remove any leading /)
            image_path = image_path.lstrip('/')
            
            images.append({
                "image_path": image_path,
                "caption": caption
            })
        
        return images
    
    def _format_title(self, filename: str) -> str:
        """
        Format a filename into a properly capitalized title.
        
        Args:
            filename (str): Filename (potentially in kebab-case or snake_case)
            
        Returns:
            str: Formatted title
        """
        # Replace hyphens and underscores with spaces
        title = re.sub(r'[-_]', ' ', filename)
        
        # Capitalize the first letter of each word
        title = title.title()
        
        return title
    
    def save_to_json(self, output_path: str) -> str:
        """
        Process markdown files and save the resulting structure to a JSON file.
        
        Args:
            output_path (str): Path to save the JSON output
            
        Returns:
            str: Path to the saved JSON file
        """
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Process the markdown files
        structured_data = self.process_directory()
        
        # Save to JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, indent=2, default=str)
        
        return output_path


if __name__ == "__main__":
    # Example usage
    processor = MarkdownProcessor("path/to/markdown/files")
    output_file = processor.save_to_json("output.json")
    print(f"Saved structured content to {output_file}")