#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from datetime import datetime

# Add parent directory to sys.path to allow imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from src.markdown_worker.markdown_processor import MarkdownProcessor
from src.markdown_worker.markdown_style_manager import MarkdownStyleManager
from src.markdown_worker.markdown_to_json_converter import MarkdownToJsonConverter


def process_markdown(args=None):
    """
    Process markdown files according to provided arguments.
    
    Args:
        args: Command line arguments (if None, will parse from sys.argv)
    
    Returns:
        Path to the generated JSON file
    """
    console = Console()
    
    # Parse arguments if not provided
    if args is None:
        parser = argparse.ArgumentParser(description="Markdown to JSON converter")
        parser.add_argument('--markdown_dir', '-m', type=str, help="Directory containing markdown files")
        parser.add_argument('--output', '-o', type=str, help="Output JSON file path")
        parser.add_argument('--style', '-s', type=str, default="standard", help="Markdown style to use")
        parser.add_argument('--images_dir', '-i', type=str, default="images", help="Directory for images")
        parser.add_argument('--no_process_images', action='store_true', help="Don't process/copy images")
        args = parser.parse_args()
    
    # Interactive mode if markdown_dir not provided
    markdown_dir = args.markdown_dir
    if not markdown_dir:
        markdown_dir = Prompt.ask("[bold blue]Enter path to directory containing markdown files[/bold blue]")
    
    # Verify markdown directory exists
    if not os.path.exists(markdown_dir) or not os.path.isdir(markdown_dir):
        console.print(f"[bold red]Error: Markdown directory '{markdown_dir}' not found or not a directory[/bold red]")
        return None
    
    # Count markdown files
    md_files = list(Path(markdown_dir).glob("*.md"))
    if not md_files:
        console.print(f"[bold red]Error: No markdown files (*.md) found in '{markdown_dir}'[/bold red]")
        return None
        
    console.print(f"[bold green]Found {len(md_files)} markdown files in '{markdown_dir}'[/bold green]")
    
    # Determine output path
    output_path = args.output
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = "results/json-combined"
        os.makedirs(output_dir, exist_ok=True)
        markdown_basename = os.path.basename(markdown_dir.rstrip('/'))
        output_path = os.path.join(output_dir, f"{markdown_basename}_{timestamp}.json")
        console.print(f"[bold blue]Output will be saved to: {output_path}[/bold blue]")
    
    # Display available styles and let user choose if not specified
    style_name = args.style
    style_manager = MarkdownStyleManager()
    available_styles = style_manager.get_style_names()
    
    if not style_name or style_name not in available_styles:
        console.print(Panel("[bold cyan]Available Markdown Styles[/bold cyan]"))
        
        style_table = Table(show_header=True, header_style="bold magenta")
        style_table.add_column("Number", style="dim")
        style_table.add_column("Style Name", style="cyan")
        style_table.add_column("Description", style="green")
        
        for i, name in enumerate(available_styles, 1):
            try:
                style = style_manager.load_style(name)
                description = style.get('description', 'No description available')
            except Exception:
                description = 'No description available'
            
            style_table.add_row(str(i), name, description)
        
        console.print(style_table)
        
        if style_name not in available_styles:
            style_choice = Prompt.ask(
                "[bold blue]Select a style by number[/bold blue]",
                choices=[str(i) for i in range(1, len(available_styles) + 1)],
                default="1"
            )
            style_name = available_styles[int(style_choice) - 1]
        
        console.print(f"[bold green]Using style: {style_name}[/bold green]")
    
    # Get images directory
    images_dir = args.images_dir
    process_images = not args.no_process_images
    
    # Process the markdown files
    with console.status("[bold green]Converting markdown to JSON...", spinner="dots"):
        try:
            converter = MarkdownToJsonConverter(
                markdown_dir=markdown_dir,
                style_name=style_name,
                images_dir=images_dir
            )
            output_file = converter.convert(
                output_json_path=output_path,
                process_images=process_images
            )
            
            console.print(f"[bold green]Successfully converted markdown to JSON: {output_file}[/bold green]")
            
            # Ask if user wants to generate PDF from the JSON
            generate_pdf = Confirm.ask("[bold blue]Would you like to generate a PDF from this JSON?[/bold blue]")
            
            if generate_pdf:
                # Import here to avoid circular imports
                from main import main as root_main
                
                # Add the necessary arguments to trigger PDF generation
                # These will be handled by the main entry point
                sys.argv = [
                    sys.argv[0],  # Original command
                    "4",  # Option for "Generate PDF from JSON"
                    output_file,  # Input JSON path
                    "--headless", # Headless mode flag
                ]
                
                console.print("[bold green]Launching PDF generation...[/bold green]")
                return root_main()
            
            return output_file
            
        except Exception as e:
            console.print(f"[bold red]Error converting markdown to JSON: {str(e)}[/bold red]")
            return None


def main():
    """Main entry point for markdown processing."""
    console = Console()
    
    console.print(Panel.fit(
        "[bold cyan]Markdown Processing Utility[/bold cyan]\n"
        "[dim]Convert markdown files to JSON for PDF generation[/dim]",
        border_style="blue"
    ))
    
    # Create options table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Option", style="dim")
    table.add_column("Action", style="cyan")
    table.add_row("1", "Convert Markdown to JSON")
    table.add_row("2", "List Available Markdown Styles")
    table.add_row("3", "Create New Markdown Style")
    table.add_row("4", "Return to Main Menu")
    
    console.print(table)
    
    while True:
        choice = console.input("[bold blue]Enter your choice (1-4): [/bold blue]").strip()
        
        if choice == '1':
            # Convert Markdown to JSON
            process_markdown()
            
        elif choice == '2':
            # List available styles
            style_manager = MarkdownStyleManager()
            available_styles = style_manager.get_style_names()
            
            console.print(Panel("[bold cyan]Available Markdown Styles[/bold cyan]"))
            
            style_table = Table(show_header=True, header_style="bold magenta")
            style_table.add_column("Style Name", style="cyan")
            style_table.add_column("Description", style="green")
            style_table.add_column("Features", style="yellow")
            
            for name in available_styles:
                try:
                    style = style_manager.load_style(name)
                    description = style.get('description', 'No description available')
                    
                    # Extract key features
                    features = []
                    if style.get('heading_styles', {}).get('h1', {}).get('numbered', False):
                        features.append("Numbered headings")
                    
                    code_block_style = style.get('code_blocks', {}).get('style', 'backtick')
                    code_line_numbers = style.get('code_blocks', {}).get('line_numbers', False)
                    features.append(f"{code_block_style} code blocks" + 
                                   (" with line numbers" if code_line_numbers else ""))
                    
                    if style.get('toc', {}).get('include', True):
                        features.append("Table of contents")
                        
                    features_str = ", ".join(features)
                    
                except Exception as e:
                    description = 'Error loading style'
                    features_str = "N/A"
                
                style_table.add_row(name, description, features_str)
                
            console.print(style_table)
            
            # Display tips on style usage
            console.print(Panel.fit(
                "[bold cyan]Markdown Style Usage Tips[/bold cyan]\n"
                "[dim]- Styles control how markdown content is processed and formatted\n"
                "- Different styles are optimized for different types of content\n"
                "- Technical style is best for programming books and documentation\n"
                "- Academic style is designed for scholarly papers with citations\n"
                "- Standard style provides a balanced approach for general content[/dim]",
                border_style="blue"
            ))
            
        elif choice == '3':
            console.print("[bold yellow]Feature not implemented yet. Please use existing styles.[/bold yellow]")
            
        elif choice == '4':
            # Return to main menu
            console.print("[bold green]Returning to main menu...[/bold green]")
            return
            
        else:
            console.print("[bold red]Invalid choice. Please select 1-4.[/bold red]")
        
        console.print("\n" + "-" * 80 + "\n")


if __name__ == "__main__":
    main()