#!/usr/bin/env python3
import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

class MarkdownStyleManager:
    """Manages markdown style templates for content processing."""
    
    def __init__(self, styles_dir: str = 'markdown_styles'):
        """
        Initialize the Markdown Style Manager.
        
        Args:
            styles_dir (str): Directory containing markdown style templates
        """
        self.styles_dir = styles_dir
        self.available_styles = self._find_available_styles()
        
    def _find_available_styles(self) -> Dict[str, str]:
        """
        Find all available style templates in the styles directory.
        
        Returns:
            Dict[str, str]: Dictionary mapping style names to file paths
        """
        styles = {}
        
        # Create styles directory if it doesn't exist
        if not os.path.exists(self.styles_dir):
            os.makedirs(self.styles_dir, exist_ok=True)
        
        # Create a default style if the directory is empty
        if not os.listdir(self.styles_dir):
            self._create_default_styles()
        
        # Try to load each style file
        for filename in os.listdir(self.styles_dir):
            if filename.endswith(('.json', '.yaml', '.yml')):
                style_name = os.path.splitext(filename)[0]
                file_path = os.path.join(self.styles_dir, filename)
                
                # Verify the file is valid before adding it
                try:
                    if os.path.getsize(file_path) == 0:
                        print(f"Warning: Style file {filename} is empty, skipping")
                        continue
                        
                    with open(file_path, 'r') as f:
                        content = f.read().strip()
                        if not content:
                            print(f"Warning: Style file {filename} is empty, skipping")
                            continue
                            
                        if filename.endswith('.json'):
                            json.loads(content)  # Test if valid JSON
                        elif filename.endswith(('.yaml', '.yml')):
                            yaml.safe_load(content)  # Test if valid YAML
                        
                        styles[style_name] = file_path
                        print(f"Successfully loaded markdown style: {style_name}")
                except Exception as e:
                    print(f"Warning: Could not load markdown style file {filename}: {str(e)}")
        
        # If no valid styles found, create default and add it
        if not styles:
            print("No valid markdown styles found. Creating default styles.")
            self._create_default_styles()
            
            # Add the default style
            default_path = os.path.join(self.styles_dir, 'standard.json')
            if os.path.exists(default_path):
                styles['standard'] = default_path
        
        return styles
    
    def _create_default_styles(self) -> None:
        """Create default markdown style templates."""
        # Standard style - clean, professional markdown processing
        standard_style = {
            "name": "Standard",
            "description": "A clean, professional markdown processing style",
            "heading_styles": {
                "h1": {
                    "prefix": "# ",
                    "suffix": "",
                    "capitalize": "title",
                    "spacing": {"before": 2, "after": 1},
                    "numbered": False,
                    "number_format": "{chapter}.",
                    "include_in_toc": True,
                    "toc_level": 1
                },
                "h2": {
                    "prefix": "## ",
                    "suffix": "",
                    "capitalize": "title",
                    "spacing": {"before": 1, "after": 1},
                    "numbered": False,
                    "number_format": "{chapter}.{section}.",
                    "include_in_toc": True,
                    "toc_level": 2
                },
                "h3": {
                    "prefix": "### ",
                    "suffix": "",
                    "capitalize": "title",
                    "spacing": {"before": 1, "after": 1},
                    "numbered": False,
                    "number_format": "{chapter}.{section}.{subsection}.",
                    "include_in_toc": True,
                    "toc_level": 3
                }
            },
            "code_blocks": {
                "style": "backtick",  # backtick or indented
                "line_numbers": False,
                "highlight_syntax": True,
                "default_language": "",
                "spacing": {"before": 1, "after": 1}
            },
            "links": {
                "style": "inline",  # inline or reference
                "include_title": True,
                "auto_convert_urls": True
            },
            "images": {
                "alt_text_required": True,
                "center_align": True,
                "caption_style": "below",  # below or figure
                "figure_prefix": "Figure {number}: "
            },
            "lists": {
                "bullet_style": "-",  # -, *, or +
                "spacing": {"before": 1, "after": 1},
                "indent_spaces": 2
            },
            "tables": {
                "include_header_separator": True,
                "align_columns": True,
                "caption_style": "above"  # above or below
            },
            "quotes": {
                "style": "blockquote",  # blockquote
                "spacing": {"before": 1, "after": 1}
            },
            "horizontal_rules": {
                "style": "dashes",  # dashes, asterisks, or underscores
                "spacing": {"before": 1, "after": 1}
            },
            "emphasis": {
                "bold_style": "asterisks",  # asterisks or underscores
                "italic_style": "underscores"  # asterisks or underscores
            },
            "toc": {
                "title": "Table of Contents",
                "include": True,
                "max_depth": 3,
                "numbered": False,
                "include_title": True
            },
            "metadata": {
                "include": True,
                "format": "yaml",  # yaml or none
                "fields": ["title", "author", "date", "description"]
            },
            "footnotes": {
                "style": "reference",  # reference or inline
                "location": "end_of_document"  # end_of_document or end_of_section
            }
        }
        
        # Make sure the directory exists
        os.makedirs(self.styles_dir, exist_ok=True)
        
        # Save the standard style
        standard_path = os.path.join(self.styles_dir, 'standard.json')
        with open(standard_path, 'w') as f:
            json.dump(standard_style, f, indent=2)
        
        print(f"Created standard markdown style template at {standard_path}")
        
        # Technical style - for technical documentation with code focus
        technical_style = {
            "name": "Technical",
            "description": "Optimized for technical documentation with code samples",
            "heading_styles": {
                "h1": {
                    "prefix": "# ",
                    "suffix": "",
                    "capitalize": "title",
                    "spacing": {"before": 2, "after": 1},
                    "numbered": True,
                    "number_format": "{chapter}. ",
                    "include_in_toc": True,
                    "toc_level": 1
                },
                "h2": {
                    "prefix": "## ",
                    "suffix": "",
                    "capitalize": "title",
                    "spacing": {"before": 1, "after": 1},
                    "numbered": True,
                    "number_format": "{chapter}.{section} ",
                    "include_in_toc": True,
                    "toc_level": 2
                },
                "h3": {
                    "prefix": "### ",
                    "suffix": "",
                    "capitalize": "title",
                    "spacing": {"before": 1, "after": 1},
                    "numbered": True,
                    "number_format": "{chapter}.{section}.{subsection} ",
                    "include_in_toc": True,
                    "toc_level": 3
                }
            },
            "code_blocks": {
                "style": "backtick",
                "line_numbers": True,
                "highlight_syntax": True,
                "default_language": "python",
                "spacing": {"before": 1, "after": 1}
            },
            "links": {
                "style": "reference",
                "include_title": True,
                "auto_convert_urls": True
            },
            "images": {
                "alt_text_required": True,
                "center_align": True,
                "caption_style": "figure",
                "figure_prefix": "Figure {chapter}.{number}: "
            },
            "lists": {
                "bullet_style": "-",
                "spacing": {"before": 1, "after": 1},
                "indent_spaces": 4
            },
            "tables": {
                "include_header_separator": True,
                "align_columns": True,
                "caption_style": "above"
            },
            "quotes": {
                "style": "blockquote",
                "spacing": {"before": 1, "after": 1}
            },
            "horizontal_rules": {
                "style": "dashes",
                "spacing": {"before": 1, "after": 1}
            },
            "emphasis": {
                "bold_style": "asterisks",
                "italic_style": "asterisks"
            },
            "toc": {
                "title": "Contents",
                "include": True,
                "max_depth": 3,
                "numbered": True,
                "include_title": True
            },
            "metadata": {
                "include": True,
                "format": "yaml",
                "fields": ["title", "author", "date", "version", "description"]
            },
            "footnotes": {
                "style": "reference",
                "location": "end_of_section"
            }
        }
        
        # Save the technical style
        technical_path = os.path.join(self.styles_dir, 'technical.json')
        with open(technical_path, 'w') as f:
            json.dump(technical_style, f, indent=2)
        
        print(f"Created technical markdown style template at {technical_path}")
        
        # Academic style for scholarly documents
        academic_style = {
            "name": "Academic",
            "description": "For scholarly and academic documents with citations",
            "heading_styles": {
                "h1": {
                    "prefix": "# ",
                    "suffix": "",
                    "capitalize": "title",
                    "spacing": {"before": 2, "after": 1},
                    "numbered": True,
                    "number_format": "{chapter}. ",
                    "include_in_toc": True,
                    "toc_level": 1
                },
                "h2": {
                    "prefix": "## ",
                    "suffix": "",
                    "capitalize": "title",
                    "spacing": {"before": 1, "after": 1},
                    "numbered": True,
                    "number_format": "{chapter}.{section} ",
                    "include_in_toc": True,
                    "toc_level": 2
                },
                "h3": {
                    "prefix": "### ",
                    "suffix": "",
                    "capitalize": "title",
                    "spacing": {"before": 1, "after": 1},
                    "numbered": True,
                    "number_format": "{chapter}.{section}.{subsection} ",
                    "include_in_toc": True,
                    "toc_level": 3
                }
            },
            "code_blocks": {
                "style": "backtick",
                "line_numbers": False,
                "highlight_syntax": True,
                "default_language": "",
                "spacing": {"before": 1, "after": 1}
            },
            "links": {
                "style": "reference",
                "include_title": True,
                "auto_convert_urls": False
            },
            "images": {
                "alt_text_required": True,
                "center_align": True,
                "caption_style": "figure",
                "figure_prefix": "Figure {chapter}.{number}: "
            },
            "lists": {
                "bullet_style": "*",
                "spacing": {"before": 1, "after": 1},
                "indent_spaces": 4
            },
            "tables": {
                "include_header_separator": True,
                "align_columns": True,
                "caption_style": "above"
            },
            "quotes": {
                "style": "blockquote",
                "spacing": {"before": 1, "after": 1}
            },
            "horizontal_rules": {
                "style": "asterisks",
                "spacing": {"before": 1, "after": 1}
            },
            "emphasis": {
                "bold_style": "asterisks",
                "italic_style": "underscores"
            },
            "toc": {
                "title": "Table of Contents",
                "include": True,
                "max_depth": 3,
                "numbered": True,
                "include_title": True
            },
            "metadata": {
                "include": True,
                "format": "yaml",
                "fields": ["title", "author", "date", "abstract", "keywords"]
            },
            "footnotes": {
                "style": "reference",
                "location": "end_of_document"
            },
            "citations": {
                "style": "reference",
                "format": "chicago",
                "include_bibliography": True,
                "bibliography_title": "References"
            },
            "abstract": {
                "include": True,
                "title": "Abstract",
                "include_in_toc": True
            }
        }
        
        # Save the academic style
        academic_path = os.path.join(self.styles_dir, 'academic.json')
        with open(academic_path, 'w') as f:
            json.dump(academic_style, f, indent=2)
        
        print(f"Created academic markdown style template at {academic_path}")
    
    def get_style_names(self) -> List[str]:
        """
        Get a list of available style names.
        
        Returns:
            List[str]: List of style names
        """
        return list(self.available_styles.keys())
    
    def load_style(self, style_name: str) -> Dict[str, Any]:
        """
        Load a style template from file.
        
        Args:
            style_name (str): Name of the style to load
            
        Returns:
            Dict[str, Any]: Style configuration
            
        Raises:
            ValueError: If style not found or invalid
        """
        if style_name not in self.available_styles:
            print(f"Style '{style_name}' not found. Falling back to default style.")
            # Attempt to create and use default
            self._create_default_styles()
            style_name = 'standard'
            
        file_path = self.available_styles.get(style_name)
        if not file_path:
            raise ValueError(f"No valid style found for '{style_name}'")
        
        try:
            # Load style from file
            style_config = self._load_style_file(file_path)
            return style_config
                
        except Exception as e:
            print(f"Error loading style {style_name}: {str(e)}")
            # As a fallback, create an in-memory default style
            print("Using in-memory default style as fallback")
            return {
                "name": "Fallback",
                "description": "Default fallback style for markdown processing",
                "heading_styles": {
                    "h1": {"prefix": "# ", "capitalize": "title"},
                    "h2": {"prefix": "## ", "capitalize": "title"},
                    "h3": {"prefix": "### ", "capitalize": "title"}
                },
                "code_blocks": {"style": "backtick", "highlight_syntax": True},
                "lists": {"bullet_style": "-", "indent_spaces": 2},
                "toc": {"title": "Table of Contents", "include": True, "max_depth": 3},
                "metadata": {"include": False}
            }

    def _load_style_file(self, file_path: str) -> Dict[str, Any]:
        """
        Load style data from a file.
        
        Args:
            file_path (str): Path to the style file
            
        Returns:
            Dict[str, Any]: Style configuration
            
        Raises:
            ValueError: If file format is unsupported
        """
        if file_path.endswith('.json'):
            with open(file_path, 'r') as f:
                return json.load(f)
        elif file_path.endswith(('.yaml', '.yml')):
            with open(file_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")


if __name__ == "__main__":
    # Example usage
    style_manager = MarkdownStyleManager()
    style_names = style_manager.get_style_names()
    print(f"Available styles: {style_names}")
    
    # Load a style
    if style_names:
        style = style_manager.load_style(style_names[0])
        print(f"Loaded style: {style['name']}")
        print(f"Description: {style['description']}")