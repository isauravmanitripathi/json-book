#!/usr/bin/env python3
import os
import json
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm

class StyleGenerator:
    """Utility for creating custom style templates through an interactive interface."""
    
    def __init__(self, styles_dir='styles'):
        self.styles_dir = styles_dir
        self.console = Console()
        self.style = {}
        
        # Ensure styles directory exists
        if not os.path.exists(styles_dir):
            os.makedirs(styles_dir, exist_ok=True)
    
    def generate_style(self):
        """Generate a style template by asking the user a series of questions."""
        self.console.print(Panel("[bold blue]PDF Style Generator[/bold blue]", 
                                subtitle="Create custom style templates for your PDFs"))
        
        # Basic style information
        self.style["name"] = Prompt.ask("[bold]Enter a name for your style[/bold]")
        self.style["description"] = Prompt.ask("[bold]Enter a description[/bold]", 
                                          default="Custom style template")
        
        # Custom fonts
        include_custom_fonts = Confirm.ask("[bold]Do you want to include custom fonts?[/bold]", default=False)
        if include_custom_fonts:
            self.style["custom_fonts"] = []
            while True:
                font_name = Prompt.ask("[bold]Enter font name (as you want to reference it)[/bold]")
                
                use_custom_file = Confirm.ask("[bold]Do you want to use a custom TTF file?[/bold]", default=True)
                if use_custom_file:
                    font_path = Prompt.ask("[bold]Enter path to .ttf font file[/bold] (relative to 'fonts' directory or absolute path)")
                    
                    font_def = {
                        "name": font_name,
                        "path": font_path
                    }
                    
                    # Ask for bold, italic, bold-italic variants
                    if Confirm.ask("[bold]Do you have a bold variant for this font?[/bold]", default=False):
                        font_def["bold_path"] = Prompt.ask("[bold]Enter path to bold variant .ttf file[/bold]")
                        
                    if Confirm.ask("[bold]Do you have an italic variant for this font?[/bold]", default=False):
                        font_def["italic_path"] = Prompt.ask("[bold]Enter path to italic variant .ttf file[/bold]")
                        
                    if Confirm.ask("[bold]Do you have a bold-italic variant for this font?[/bold]", default=False):
                        font_def["bold_italic_path"] = Prompt.ask("[bold]Enter path to bold-italic variant .ttf file[/bold]")
                else:
                    # Using a standard font but with a custom name reference
                    font_def = {
                        "name": font_name
                    }
                    self.console.print(f"[dim]Note: '{font_name}' will reference a standard font.[/dim]")
                
                self.style["custom_fonts"].append(font_def)
                
                if not Confirm.ask("[bold]Add another custom font?[/bold]", default=False):
                    break
        
        # Page settings
        self.style["page"] = {}
        self.style["page"]["size"] = Prompt.ask(
            "[bold]Page size[/bold]", 
            choices=["A4", "LETTER", "LEGAL"], 
            default="A4"
        )
        
        self.console.print(Panel("[bold]Page Margins[/bold]\nSpecify the margins in points (72 points = 1 inch)"))
        self.style["page"]["margins"] = {
            "left": IntPrompt.ask("[bold]Left margin[/bold]", default=72),
            "right": IntPrompt.ask("[bold]Right margin[/bold]", default=72),
            "top": IntPrompt.ask("[bold]Top margin[/bold]", default=72),
            "bottom": IntPrompt.ask("[bold]Bottom margin[/bold]", default=72)
        }
        
        # Page numbers
        self.style["page_numbers"] = {}
        self.style["page_numbers"]["show"] = Confirm.ask("[bold]Show page numbers?[/bold]", default=True)
        
        if self.style["page_numbers"]["show"]:
            self.style["page_numbers"]["format"] = Prompt.ask(
                "[bold]Page number format[/bold] (use {current} and {total} as placeholders)",
                default="Page {current}"
            )
            self.style["page_numbers"]["position"] = Prompt.ask(
                "[bold]Page number position[/bold]",
                choices=["bottom-center", "bottom-right", "bottom-left", "top-center", "top-right", "top-left"],
                default="bottom-center"
            )
            self.style["page_numbers"]["font"] = Prompt.ask(
                "[bold]Page number font[/bold]",
                choices=["Helvetica", "Times-Roman", "Courier"],
                default="Helvetica"
            )
            self.style["page_numbers"]["size"] = IntPrompt.ask("[bold]Page number font size[/bold]", default=9)
            self.style["page_numbers"]["start_page"] = IntPrompt.ask(
                "[bold]First page to show numbers[/bold]",
                default=1
            )
        
        # Title page
        self.style["title_page"] = {}
        self.style["title_page"]["title"] = self._get_font_settings(
            "Title Page - Title", 
            default_font="Helvetica-Bold",
            default_size=28,
            default_color="#000000",
            include_alignment=True,
            include_case=True
        )
        self.style["title_page"]["title"]["spacing"] = Prompt.ask(
            "[bold]Title spacing style[/bold]",
            choices=["none", "words", "lines"],
            default="none"
        )
        
        self.style["title_page"]["author"] = self._get_font_settings(
            "Title Page - Author", 
            default_font="Helvetica",
            default_size=16,
            default_color="#000000",
            include_alignment=True
        )
        self.style["title_page"]["author"]["prefix"] = Prompt.ask(
            "[bold]Author prefix[/bold] (e.g., 'By', leave empty for none)",
            default="By"
        )
        
        self.style["title_page"]["spacing"] = {
            "top": float(Prompt.ask(
                "[bold]Proportion of page height for top spacing[/bold] (e.g., 0.4 for 40%)",
                default="0.4"
            )),
            "between": float(Prompt.ask(
                "[bold]Proportion of page height between title and author[/bold]",
                default="0.2"
            ))
        }
        
        # Table of contents
        self.style["table_of_contents"] = {}
        self.style["table_of_contents"]["title"] = {
            "text": Prompt.ask("[bold]Table of contents title[/bold]", default="CONTENTS"),
            "font": Prompt.ask(
                "[bold]TOC title font[/bold]",
                choices=["Helvetica", "Helvetica-Bold", "Times-Roman", "Times-Bold", "Courier", "Courier-Bold"],
                default="Helvetica-Bold"
            ),
            "size": IntPrompt.ask("[bold]TOC title font size[/bold]", default=16),
            "alignment": Prompt.ask(
                "[bold]TOC title alignment[/bold]",
                choices=["left", "center", "right"],
                default="center"
            )
        }
        
        # Chapter settings
        self.style["chapter"] = {}
        self.style["chapter"]["number"] = self._get_font_settings(
            "Chapter Number", 
            default_font="Helvetica-Bold",
            default_size=16,
            default_color="#000000",
            include_alignment=True,
            include_case=True
        )
        self.style["chapter"]["number"]["prefix"] = Prompt.ask(
            "[bold]Chapter number prefix[/bold] (e.g., 'Chapter')",
            default="Chapter"
        )
        
        self.style["chapter"]["title"] = self._get_font_settings(
            "Chapter Title", 
            default_font="Helvetica-Bold",
            default_size=24,
            default_color="#000000",
            include_alignment=True,
            include_case=True
        )
        
        self.style["chapter"]["divider"] = self._get_divider_settings("Chapter")
        
        self.style["chapter"]["page_break"] = {
            "before": Confirm.ask("[bold]Start each chapter on a new page?[/bold]", default=True),
            "after": Confirm.ask("[bold]Insert page break after each chapter?[/bold]", default=False)
        }
        
        # Section settings
        self.style["section"] = {}
        self.style["section"]["title"] = self._get_font_settings(
            "Section Title", 
            default_font="Helvetica-Bold",
            default_size=14,
            default_color="#000000",
            include_alignment=True
        )
        self.style["section"]["title"]["space_before"] = IntPrompt.ask(
            "[bold]Space before section title[/bold] (points)",
            default=18
        )
        self.style["section"]["title"]["space_after"] = IntPrompt.ask(
            "[bold]Space after section title[/bold] (points)",
            default=12
        )
        
        self.style["section"]["divider"] = self._get_divider_settings("Section")
        
        # Body text settings
        self.style["body_text"] = self._get_font_settings(
            "Body Text", 
            default_font="Helvetica",
            default_size=10,
            default_color="#000000",
            include_alignment=True
        )
        self.style["body_text"]["leading"] = IntPrompt.ask(
            "[bold]Line spacing (leading)[/bold] (points)",
            default=14
        )
        self.style["body_text"]["space_after"] = IntPrompt.ask(
            "[bold]Space after paragraphs[/bold] (points)",
            default=10
        )
        
        # Image settings
        include_images = Confirm.ask("[bold]Include image settings?[/bold]", default=True)
        if include_images:
            self.style["images"] = {}
            self.style["images"]["max_width"] = IntPrompt.ask(
                "[bold]Maximum image width[/bold] (points, 72 points = 1 inch)",
                default=450
            )
            self.style["images"]["space_before"] = IntPrompt.ask(
                "[bold]Space before image[/bold] (points)",
                default=10
            )
            self.style["images"]["space_after"] = IntPrompt.ask(
                "[bold]Space after image[/bold] (points)",
                default=10
            )
            self.style["images"]["full_page_threshold"] = float(Prompt.ask(
                "[bold]Threshold for full-page images[/bold] (0.0-1.0, e.g., 0.7 means images taking >70% of page height get their own page)",
                default="0.7"
            ))
            self.style["images"]["full_page_break"] = Confirm.ask(
                "[bold]Force page breaks for large images?[/bold]",
                default=False
            )
            
            self.style["images"]["caption"] = {}
            self.style["images"]["caption"]["font"] = Prompt.ask(
                "[bold]Caption font[/bold]",
                choices=["Helvetica", "Helvetica-Italic", "Times-Roman", "Times-Italic", "Courier", "Courier-Italic"],
                default="Helvetica"
            )
            self.style["images"]["caption"]["size"] = IntPrompt.ask(
                "[bold]Caption font size[/bold]",
                default=9
            )
            self.style["images"]["caption"]["leading"] = IntPrompt.ask(
                "[bold]Caption line spacing[/bold]",
                default=11
            )
            self.style["images"]["caption"]["color"] = Prompt.ask(
                "[bold]Caption color[/bold] (hex code or name)",
                default="#000000"
            )
            self.style["images"]["caption"]["space_after"] = IntPrompt.ask(
                "[bold]Space after caption[/bold] (points)",
                default=10
            )
        
        # Save the style
        filename = self._get_safe_filename(self.style["name"])
        filepath = os.path.join(self.styles_dir, f"{filename}.json")
        
        # Check if file already exists
        if os.path.exists(filepath):
            overwrite = Confirm.ask(f"[bold red]Style file {filename}.json already exists. Overwrite?[/bold red]", default=False)
            if not overwrite:
                count = 1
                while os.path.exists(filepath):
                    filepath = os.path.join(self.styles_dir, f"{filename}_{count}.json")
                    count += 1
        
        # Write the style to a file
        with open(filepath, 'w') as f:
            json.dump(self.style, f, indent=2)
        
        self.console.print(f"[bold green]Style saved to {filepath}[/bold green]")
        return filepath
    
    def _get_font_settings(self, label, default_font="Helvetica", default_size=12, 
                           default_color="#000000", include_alignment=False, include_case=False):
        """Get font settings from user input."""
        self.console.print(f"[bold]{label} Settings[/bold]")
        
        # Get available custom fonts
        custom_fonts = []
        if "custom_fonts" in self.style:
            custom_fonts = [font_def.get("name") for font_def in self.style["custom_fonts"] if "name" in font_def]
        
        # Standard fonts + any custom fonts
        available_fonts = ["Helvetica", "Helvetica-Bold", "Times-Roman", "Times-Bold", "Courier", "Courier-Bold"]
        available_fonts.extend(custom_fonts)
        
        # If custom fonts are defined, show a message about them
        if custom_fonts:
            self.console.print(f"[dim]Custom fonts available: {', '.join(custom_fonts)}[/dim]")
        
        settings = {
            "font": Prompt.ask(
                "[bold]Font[/bold]",
                choices=available_fonts,
                default=default_font
            ),
            "size": IntPrompt.ask("[bold]Font size[/bold]", default=default_size),
            "color": Prompt.ask("[bold]Color[/bold] (hex code or name)", default=default_color)
        }
        
        if include_alignment:
            settings["alignment"] = Prompt.ask(
                "[bold]Alignment[/bold]",
                choices=["left", "center", "right", "justified"],
                default="left"
            )
        
        if include_case:
            settings["case"] = Prompt.ask(
                "[bold]Text case[/bold]",
                choices=["none", "upper", "lower", "title"],
                default="none"
            )
        
        return settings
    
    def _get_divider_settings(self, label):
        """Get divider settings from user input."""
        divider_type = Prompt.ask(
            f"[bold]{label} divider type[/bold]",
            choices=["none", "solid", "dotted"],
            default="none"
        )
        
        if divider_type == "none":
            return {
                "type": "none",
                "width": 0,
                "color": "#000000",
                "spacing": {"before": 0, "after": 0}
            }
        
        return {
            "type": divider_type,
            "width": IntPrompt.ask("[bold]Divider line width[/bold]", default=1),
            "color": Prompt.ask("[bold]Divider color[/bold] (hex code or name)", default="#000000"),
            "spacing": {
                "before": IntPrompt.ask("[bold]Space before divider[/bold] (points)", default=6),
                "after": IntPrompt.ask("[bold]Space after divider[/bold] (points)", default=12)
            }
        }
    
    def _get_safe_filename(self, name):
        """Convert a name to a safe filename."""
        # Replace spaces with underscores and remove special characters
        return "".join(c if c.isalnum() or c == '_' else '_' for c in name.lower().replace(' ', '_'))

if __name__ == "__main__":
    generator = StyleGenerator()
    generator.generate_style()