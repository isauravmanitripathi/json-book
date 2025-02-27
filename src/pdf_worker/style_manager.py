import os
import json
import yaml

class StyleManager:
    """Manages PDF style templates."""
    def __init__(self, styles_dir='styles'):
        self.styles_dir = styles_dir
        self.available_styles = self._find_available_styles()
        
    def _find_available_styles(self):
        """Find all available style templates in the styles directory."""
        styles = {}
        
        # Create styles directory if it doesn't exist
        if not os.path.exists(self.styles_dir):
            os.makedirs(self.styles_dir, exist_ok=True)
        
        # Create a default style if the directory is empty
        if not os.listdir(self.styles_dir):
            self._create_default_style()
        
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
                        print(f"Successfully loaded style: {style_name}")
                except Exception as e:
                    print(f"Warning: Could not load style file {filename}: {str(e)}")
        
        # If no valid styles found, create default and add it
        if not styles:
            print("No valid styles found. Creating default style.")
            self._create_default_style()
            
            # Add the default style
            default_path = os.path.join(self.styles_dir, 'classic.json')
            if os.path.exists(default_path):
                styles['classic'] = default_path
        
        return styles
    
    def _create_default_style(self):
        """Create a default style template."""
        default_style = {
            "name": "Classic",
            "description": "A clean, professional book layout with classic typography",
            "page": {
                "size": "A4",
                "margins": {"left": 72, "right": 72, "top": 72, "bottom": 72}
            },
            "fonts": [],
            "page_numbers": {
                "show": True,
                "format": "{current} of {total}",
                "position": "bottom-right",
                "font": "Helvetica",
                "size": 9,
                "start_page": 2
            },
            "title_page": {
                "title": {
                    "font": "Helvetica-Bold",
                    "size": 32,
                    "color": "#2E4053",
                    "spacing": "words",
                    "alignment": "center",
                    "case": "upper"
                },
                "author": {
                    "font": "Helvetica",
                    "size": 16,
                    "color": "#2E4053",
                    "prefix": "By",
                    "alignment": "center"
                },
                "spacing": {
                    "top": 0.4,
                    "between": 0.3
                }
            },
            "table_of_contents": {
                "title": {
                    "text": "Table of Contents",
                    "font": "Helvetica-Bold",
                    "size": 18,
                    "alignment": "center"
                },
                "level_styles": [
                    {
                        "font_name": "Helvetica",
                        "font_size": 12,
                        "indent": 20,
                        "leading": 14,
                        "text_color": "#000000"
                    },
                    {
                        "font_name": "Helvetica",
                        "font_size": 10,
                        "indent": 40,
                        "leading": 12,
                        "text_color": "#333333"
                    }
                ]
            },
            "chapter": {
                "number": {
                    "prefix": "CHAPTER",
                    "font": "Helvetica-Bold",
                    "size": 14,
                    "color": "#000000",
                    "alignment": "center",
                    "case": "upper"
                },
                "title": {
                    "font": "Helvetica-Bold",
                    "size": 16,
                    "color": "#000000",
                    "alignment": "center",
                    "case": "upper"
                },
                "divider": {
                    "type": "dotted",
                    "width": 1,
                    "color": "#000000",
                    "spacing": {"before": 6, "after": 12}
                },
                "page_break": {
                    "before": true,
                    "after": true
                }
            },
            "section": {
                "title": {
                    "font": "Helvetica-Bold",
                    "size": 16,
                    "color": "#566573",
                    "alignment": "center",
                    "space_before": 30,
                    "space_after": 20
                },
                "divider": {
                    "type": "dotted",
                    "width": 1,
                    "color": "#000000",
                    "spacing": {"before": 6, "after": 12}
                }
            },
            "body_text": {
                "font": "Helvetica",
                "size": 12,
                "leading": 14,
                "alignment": "justified",
                "space_after": 12
            },
            "images": {
                "max_width": 450,
                "space_before": 12,
                "space_after": 12,
                "full_page_threshold": 0.8,
                "full_page_break": true,
                "caption": {
                    "font": "Helvetica-Italic",
                    "size": 10,
                    "leading": 12,
                    "color": "#333333",
                    "space_after": 12
                }
            }
        }
        
        # Make sure the directory exists
        os.makedirs(self.styles_dir, exist_ok=True)
        
        # Save the default style
        default_path = os.path.join(self.styles_dir, 'classic.json')
        with open(default_path, 'w') as f:
            json.dump(default_style, f, indent=2)
        
        print(f"Created default style template at {default_path}")
        
        # Also create a modern style with different image settings
        modern_style = default_style.copy()
        modern_style["name"] = "Modern"
        modern_style["description"] = "A clean, contemporary design with minimalist aesthetics"
        modern_style["images"] = {
            "max_width": 500,
            "space_before": 18,
            "space_after": 18,
            "full_page_threshold": 0.7,
            "full_page_break": true,
            "caption": {
                "font": "Helvetica-Italic",
                "size": 9,
                "leading": 11,
                "color": "#666666",
                "space_after": 14
            }
        }
        
        # Save the modern style
        modern_path = os.path.join(self.styles_dir, 'modern.json')
        with open(modern_path, 'w') as f:
            json.dump(modern_style, f, indent=2)
        
        print(f"Created modern style template at {modern_path}")
    
    def get_style_names(self):
        """Get a list of available style names."""
        return list(self.available_styles.keys())
    
    def load_style(self, style_name):
        """Load a style template from file."""
        if style_name not in self.available_styles:
            print(f"Style '{style_name}' not found. Falling back to default style.")
            # Attempt to create and use default
            self._create_default_style()
            style_name = 'classic'
            
        file_path = self.available_styles.get(style_name)
        if not file_path:
            raise ValueError(f"No valid style found for '{style_name}'")
        
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'r') as f:
                    return json.load(f)
            elif file_path.endswith(('.yaml', '.yml')):
                with open(file_path, 'r') as f:
                    return yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported file format: {file_path}")
        except Exception as e:
            print(f"Error loading style {style_name}: {str(e)}")
            # As a fallback, create an in-memory default style
            print("Using in-memory default style as fallback")
            return {
                "name": "Fallback",
                "description": "Default fallback style",
                "page": {"size": "A4", "margins": {"left": 72, "right": 72, "top": 72, "bottom": 72}},
                "fonts": [],
                "page_numbers": {"show": True, "format": "{current}", "position": "bottom-right", "font": "Helvetica", "size": 9},
                "title_page": {
                    "title": {"font": "Helvetica-Bold", "size": 24, "color": "#000000", "spacing": "none", "alignment": "center", "case": "none"},
                    "author": {"font": "Helvetica", "size": 12, "color": "#000000", "prefix": "By", "alignment": "center"},
                    "spacing": {"top": 0.4, "between": 0.2}
                },
                "table_of_contents": {
                    "title": {"text": "Contents", "font": "Helvetica-Bold", "size": 14, "alignment": "center"},
                    "level_styles": []
                },
                "chapter": {
                    "number": {"prefix": "Chapter", "font": "Helvetica-Bold", "size": 14, "color": "#000000", "alignment": "center"},
                    "title": {"font": "Helvetica-Bold", "size": 16, "color": "#000000", "alignment": "center"},
                    "divider": {"type": "none", "width": 0, "color": "#000000", "spacing": {"before": 0, "after": 0}},
                    "page_break": {"before": True, "after": False}
                },
                "section": {
                    "title": {"font": "Helvetica-Bold", "size": 14, "color": "#000000", "alignment": "left", "space_before": 12, "space_after": 6},
                    "divider": {"type": "none", "width": 0, "color": "#000000", "spacing": {"before": 0, "after": 0}}
                },
                "body_text": {"font": "Helvetica", "size": 12, "leading": 14, "alignment": "justified", "space_after": 12},
                "images": {
                    "max_width": 450,
                    "space_before": 12,
                    "space_after": 12,
                    "full_page_threshold": 0.8,
                    "caption": {
                        "font": "Helvetica-Italic",
                        "size": 10,
                        "leading": 12,
                        "color": "#333333",
                        "space_after": 12
                    }
                }
            }