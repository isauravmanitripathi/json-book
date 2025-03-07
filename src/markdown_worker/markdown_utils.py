#!/usr/bin/env python3
"""
Markdown utilities for enhanced markdown processing.
"""
import re
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union

def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    """
    Extract code blocks from markdown text.
    
    Args:
        text (str): Markdown text
        
    Returns:
        List[Dict[str, str]]: List of code blocks with language and content
    """
    # Find all code blocks using fenced code block syntax
    # Format: ```language
    #         code
    #         ```
    code_block_pattern = r'```(.*?)\n(.*?)```'
    matches = re.finditer(code_block_pattern, text, re.DOTALL)
    
    code_blocks = []
    for match in matches:
        language = match.group(1).strip() or "text"
        code = match.group(2).strip()
        
        code_blocks.append({
            "language": language,
            "content": code
        })
    
    return code_blocks

def extract_metadata(text: str) -> Tuple[Dict[str, str], str]:
    """
    Extract YAML metadata from the front matter of a markdown file.
    
    Args:
        text (str): Markdown text
        
    Returns:
        Tuple[Dict[str, str], str]: Metadata dictionary and content without metadata
    """
    # Pattern for YAML front matter
    # Format: ---
    #         key: value
    #         ---
    metadata_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.search(metadata_pattern, text, re.DOTALL)
    
    metadata = {}
    content = text
    
    if match:
        # Extract and parse metadata
        metadata_text = match.group(1)
        lines = metadata_text.strip().split('\n')
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()
        
        # Remove metadata from content
        content = text[match.end():]
    
    return metadata, content

def process_link_references(text: str) -> str:
    """
    Convert markdown link references to inline links.
    
    Args:
        text (str): Markdown text
        
    Returns:
        str: Text with converted links
    """
    # Find all link reference definitions
    # Format: [label]: URL "title"
    ref_pattern = r'^\[([^\]]+)\]:\s*(\S+)(?:\s+["\'](.*)["\'])?\s*$'
    ref_matches = re.finditer(ref_pattern, text, re.MULTILINE)
    
    # Build a dictionary of references
    refs = {}
    for match in ref_matches:
        label = match.group(1)
        url = match.group(2)
        title = match.group(3) or ""
        
        refs[label.lower()] = {
            "url": url,
            "title": title
        }
    
    # Remove reference definitions from text
    text = re.sub(ref_pattern, '', text, flags=re.MULTILINE)
    
    # Replace reference-style links with inline links
    # Format: [text][label]
    def replace_ref_link(match):
        text = match.group(1)
        label = match.group(2) or text
        
        ref = refs.get(label.lower())
        if ref:
            title_attr = f' "{ref["title"]}"' if ref["title"] else ""
            return f'[{text}]({ref["url"]}{title_attr})'
        else:
            return match.group(0)
    
    text = re.sub(r'\[([^\]]+)\]\[([^\]]*)\]', replace_ref_link, text)
    
    return text

def add_syntax_highlighting(code_blocks: List[Dict[str, str]], style: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Add syntax highlighting information to code blocks based on style settings.
    
    Args:
        code_blocks (List[Dict[str, str]]): List of code blocks
        style (Dict[str, Any]): Style configuration
        
    Returns:
        List[Dict[str, str]]: Enhanced code blocks with syntax highlighting info
    """
    code_style = style.get("code_blocks", {})
    highlight_syntax = code_style.get("highlight_syntax", True)
    line_numbers = code_style.get("line_numbers", False)
    
    if not highlight_syntax:
        return code_blocks
    
    enhanced_blocks = []
    for block in code_blocks:
        enhanced_block = block.copy()
        
        # Add line numbers if requested
        if line_numbers:
            lines = block["content"].split("\n")
            numbered_lines = []
            for i, line in enumerate(lines, 1):
                numbered_lines.append(f"{i:3d} | {line}")
            enhanced_block["content"] = "\n".join(numbered_lines)
        
        # Add highlighting info
        enhanced_block["highlight"] = True
        
        enhanced_blocks.append(enhanced_block)
    
    return enhanced_blocks

def extract_image_info(text: str) -> List[Dict[str, str]]:
    """
    Extract image information from markdown text.
    
    Args:
        text (str): Markdown text
        
    Returns:
        List[Dict[str, str]]: List of image info (path, alt text, title)
    """
    # Find all image references
    # Format: ![alt text](path/to/image.jpg "title")
    image_pattern = r'!\[([^\]]*)\]\(([^)]+)(?:\s+"([^"]*)")?\)'
    matches = re.finditer(image_pattern, text)
    
    images = []
    for match in matches:
        alt_text = match.group(1) or ""
        path = match.group(2)
        title = match.group(3) or ""
        
        # Split path and query params if any
        path_parts = path.split('?', 1)
        path = path_parts[0]
        
        # Extract width and height from query params if present
        width = None
        height = None
        if len(path_parts) > 1:
            query = path_parts[1]
            width_match = re.search(r'width=(\d+)', query)
            height_match = re.search(r'height=(\d+)', query)
            
            if width_match:
                width = int(width_match.group(1))
            if height_match:
                height = int(height_match.group(1))
        
        image_info = {
            "path": path,
            "alt_text": alt_text,
            "title": title
        }
        
        if width:
            image_info["width"] = width
        if height:
            image_info["height"] = height
            
        images.append(image_info)
    
    return images

def generate_toc(text: str, style: Dict[str, Any]) -> str:
    """
    Generate a table of contents based on headings in the markdown text.
    
    Args:
        text (str): Markdown text
        style (Dict[str, Any]): Style configuration
        
    Returns:
        str: Table of contents markdown
    """
    toc_config = style.get("toc", {})
    if not toc_config.get("include", True):
        return ""
    
    # Extract headings
    heading_pattern = r'^(#{1,6})\s+(.+?)(?:\s+\{#([^}]+)\})?\s*$'
    matches = re.finditer(heading_pattern, text, re.MULTILINE)
    
    headings = []
    for match in matches:
        level = len(match.group(1))
        text = match.group(2)
        anchor = match.group(3) or re.sub(r'[^\w\- ]', '', text).lower().replace(' ', '-')
        
        # Check if heading should be included in TOC
        max_depth = toc_config.get("max_depth", 3)
        if level <= max_depth:
            headings.append({
                "level": level,
                "text": text,
                "anchor": anchor
            })
    
    # Generate TOC
    toc_title = toc_config.get("title", "Table of Contents")
    toc_lines = [f"# {toc_title}\n"]
    
    for heading in headings:
        indent = "  " * (heading["level"] - 1)
        number_prefix = ""
        
        # Add numbering if enabled
        if toc_config.get("numbered", False):
            # TODO: Implement hierarchical numbering if needed
            pass
        
        toc_lines.append(f"{indent}- [{heading['text']}](#{heading['anchor']})")
    
    return "\n".join(toc_lines)

def normalize_markdown(text: str, style: Dict[str, Any]) -> str:
    """
    Normalize markdown according to style guidelines.
    
    Args:
        text (str): Markdown text
        style (Dict[str, Any]): Style configuration
        
    Returns:
        str: Normalized markdown
    """
    # Extract and reapply metadata
    metadata, content = extract_metadata(text)
    
    # Process link references
    content = process_link_references(content)
    
    # Normalize heading styles
    heading_styles = style.get("heading_styles", {})
    
    # Normalize h1 headings
    if "h1" in heading_styles:
        h1_style = heading_styles["h1"]
        h1_prefix = h1_style.get("prefix", "# ")
        h1_suffix = h1_style.get("suffix", "")
        h1_capitalize = h1_style.get("capitalize", "none")
        
        def normalize_h1(match):
            text = match.group(1)
            
            # Apply capitalization
            if h1_capitalize == "upper":
                text = text.upper()
            elif h1_capitalize == "lower":
                text = text.lower()
            elif h1_capitalize == "title":
                text = text.title()
                
            return f"{h1_prefix}{text}{h1_suffix}"
        
        content = re.sub(r'^#\s+(.+?)$', normalize_h1, content, flags=re.MULTILINE)
    
    # Normalize h2 headings
    if "h2" in heading_styles:
        h2_style = heading_styles["h2"]
        h2_prefix = h2_style.get("prefix", "## ")
        h2_suffix = h2_style.get("suffix", "")
        h2_capitalize = h2_style.get("capitalize", "none")
        
        def normalize_h2(match):
            text = match.group(1)
            
            # Apply capitalization
            if h2_capitalize == "upper":
                text = text.upper()
            elif h2_capitalize == "lower":
                text = text.lower()
            elif h2_capitalize == "title":
                text = text.title()
                
            return f"{h2_prefix}{text}{h2_suffix}"
        
        content = re.sub(r'^##\s+(.+?)$', normalize_h2, content, flags=re.MULTILINE)
    
    # Normalize h3 headings
    if "h3" in heading_styles:
        h3_style = heading_styles["h3"]
        h3_prefix = h3_style.get("prefix", "### ")
        h3_suffix = h3_style.get("suffix", "")
        h3_capitalize = h3_style.get("capitalize", "none")
        
        def normalize_h3(match):
            text = match.group(1)
            
            # Apply capitalization
            if h3_capitalize == "upper":
                text = text.upper()
            elif h3_capitalize == "lower":
                text = text.lower()
            elif h3_capitalize == "title":
                text = text.title()
                
            return f"{h3_prefix}{text}{h3_suffix}"
        
        content = re.sub(r'^###\s+(.+?)$', normalize_h3, content, flags=re.MULTILINE)
    
    # Normalize list styles
    list_style = style.get("lists", {})
    bullet_style = list_style.get("bullet_style", "-")
    
    # Replace bullet styles
    content = re.sub(r'^[ \t]*[*+-](?=\s)', f"{bullet_style}", content, flags=re.MULTILINE)
    
    # Normalize code blocks
    code_style = style.get("code_blocks", {})
    default_language = code_style.get("default_language", "")
    
    def normalize_code_block(match):
        language = match.group(1).strip() or default_language
        code = match.group(2)
        return f"```{language}\n{code}```"
    
    content = re.sub(r'```(.*?)\n(.*?)```', normalize_code_block, content, flags=re.DOTALL)
    
    # Reapply metadata if needed
    if metadata and style.get("metadata", {}).get("include", True):
        metadata_format = style.get("metadata", {}).get("format", "yaml")
        
        if metadata_format == "yaml":
            metadata_lines = ["---"]
            for key, value in metadata.items():
                metadata_lines.append(f"{key}: {value}")
            metadata_lines.append("---\n")
            
            content = "\n".join(metadata_lines) + content
    
    return content

if __name__ == "__main__":
    # Example usage
    markdown_text = """---
title: Test Document
author: John Doe
---

# Heading 1

## Section 1.1

```python
def hello_world():
    print("Hello, world!")
```

![Image Description](path/to/image.jpg "Image Title")

[Link reference][ref]

[ref]: https://example.com "Example"
"""
    
    # Extract code blocks
    code_blocks = extract_code_blocks(markdown_text)
    print(f"Found {len(code_blocks)} code blocks")
    
    # Extract metadata
    metadata, content = extract_metadata(markdown_text)
    print(f"Metadata: {metadata}")
    
    # Extract images
    images = extract_image_info(markdown_text)
    print(f"Found {len(images)} images")