#!/usr/bin/env python3
import os
import sys
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from src.json_writer.chapter_extractor import extract_section_text
from src.json_writer.write_text_gemini import generate_conversations_gemini
from src.pdf_worker.core import PDFGenerator
from src.markdown_html_worker.core import MarkdownHTMLProcessor  # Import the new processor
from style_generator import StyleGenerator

def main():
    """Main entry point for the application."""
    # Check for headless mode argument
    parser = argparse.ArgumentParser(description="Text Processing Utility")
    parser.add_argument('--headless', action='store_true', help='Run in headless mode with command line args')
    parser.add_argument('option', type=str, nargs='?', help='Option to run directly')
    parser.add_argument('input_path', type=str, nargs='?', help='Input file path')
    args, unknown = parser.parse_known_args()
    
    console = Console()
    
    # Ensure fonts directory exists
    fonts_dir = 'fonts'
    if not os.path.exists(fonts_dir):
        os.makedirs(fonts_dir, exist_ok=True)
        console.print(f"[bold yellow]Created fonts directory: {fonts_dir}[/bold yellow]")
        console.print("[dim]Place your .ttf font files in this directory to use custom fonts.[/dim]")
    
    console.print(Panel.fit(
        "[bold cyan]Text Processing Utility[/bold cyan]\n"
        "[dim]Choose an option to process your text[/dim]",
        border_style="blue"
    ))
    
    # Create options table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Option", style="dim")
    table.add_column("Action", style="cyan")
    table.add_row("1", "Extract Chapter Text from JSON")
    table.add_row("2", "Generate Articles with OpenAI")
    table.add_row("3", "Generate Articles with Gemini")
    table.add_row("4", "Generate PDF from JSON")
    table.add_row("5", "List Available PDF Styles")
    table.add_row("6", "Create New PDF Style")
    table.add_row("7", "Process Markdown/HTML Files")  # New option
    table.add_row("8", "Exit")
    console.print(table)
    
    # If headless mode is enabled, run the specified option directly
    if args.headless and args.option and args.input_path:
        choice = args.option
        input_path = args.input_path
    else:
        choice = console.input("[bold blue]Enter your choice (1-8): [/bold blue]").strip()
    
    while True:
        if choice == '1':
            # Extract chapter text option
            file_path = args.input_path if args.headless else console.input("[bold blue]Enter the path to the input JSON file: [/bold blue]").strip()
            
            if not file_path or not os.path.exists(file_path):
                console.print("[bold red]Invalid file path. Please try again.[/bold red]")
                if args.headless:
                    return
                continue

            # Ensure results/json-combined directory exists
            os.makedirs('results/json-combined', exist_ok=True)

            # Generate output file path
            base_filename = os.path.basename(file_path)
            output_filename = os.path.splitext(base_filename)[0] + '_extracted.json'
            output_path = os.path.join('results', 'json-combined', output_filename)

            try:
                # Call extraction function
                result = extract_section_text(file_path, output_path)
                
                if result:
                    console.print(f"[bold green]Text extracted successfully to {output_path}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error extracting text: {str(e)}[/bold red]")
                
            if args.headless:
                return
        
        elif choice == '2':
            # Generate with OpenAI
            file_path = args.input_path if args.headless else console.input("[bold blue]Enter the path to the input JSON file: [/bold blue]").strip()
            
            if not file_path or not os.path.exists(file_path):
                console.print("[bold red]Invalid file path. Please try again.[/bold red]")
                if args.headless:
                    return
                continue

            try:
                from src.json_writer.write_text_openai import generate_conversations
                with console.status("[bold green]Generating articles with OpenAI...", spinner="dots"):
                    result = generate_conversations(file_path)
                
                if result:
                    console.print("[bold green]Articles generated successfully![/bold green]")
                    console.print(f"[bold green]Output saved to: {result}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error generating articles: {str(e)}[/bold red]")
                
            if args.headless:
                return
        
        elif choice == '3':
            # Generate with Gemini
            file_path = args.input_path if args.headless else console.input("[bold blue]Enter the path to the input JSON file: [/bold blue]").strip()
            
            if not file_path or not os.path.exists(file_path):
                console.print("[bold red]Invalid file path. Please try again.[/bold red]")
                if args.headless:
                    return
                continue

            try:
                with console.status("[bold green]Generating articles with Gemini...", spinner="dots"):
                    result = generate_conversations_gemini(file_path)
                
                if result:
                    console.print("[bold green]Articles generated successfully![/bold green]")
                    console.print(f"[bold green]Output saved to: {result}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error generating articles: {str(e)}[/bold red]")
                
            if args.headless:
                return
        
        elif choice == '4':
            # Generate PDF
            file_path = args.input_path if args.headless else console.input("[bold blue]Enter the path to the input JSON file: [/bold blue]").strip()
            
            if not file_path or not os.path.exists(file_path):
                console.print("[bold red]Invalid file path. Please try again.[/bold red]")
                if args.headless:
                    return
                continue

            # Get book name
            book_name = Prompt.ask("[bold blue]Enter the name of the book: [/bold blue]", default="Generated Book")
            
            # Get author name
            author_name = Prompt.ask("[bold blue]Enter the name of the author: [/bold blue]", default="Author")
            
            # Get images directory path
            images_dir = Prompt.ask("[bold blue]Enter path to images directory (default: 'images'): [/bold blue]", default="images")
            if not os.path.exists(images_dir):
                console.print(f"[bold yellow]Images directory '{images_dir}' does not exist. Creating it now.[/bold yellow]")
                os.makedirs(images_dir, exist_ok=True)
            
            # Ask about multi-part PDF generation
            enable_multipart = console.input("[bold blue]Generate multi-part PDFs for large books? (y/n): [/bold blue]").strip().lower() == 'y'
            
            max_pages = 600  # Default
            if enable_multipart:
                max_pages_input = console.input("[bold blue]Maximum pages per part (default 600): [/bold blue]").strip()
                if max_pages_input and max_pages_input.isdigit():
                    max_pages = int(max_pages_input)
                console.print(f"[bold cyan]Book will be split if it exceeds {max_pages} pages[/bold cyan]")
            
            # Ask about front matter generation
            include_front_matter = console.input("[bold blue]Include front matter (copyright page, preface, etc.)? (y/n): [/bold blue]").strip().lower() == 'y'
            front_matter_options = None
            api_key = None
            
            if include_front_matter:
                console.print(Panel.fit(
                    "[bold cyan]Front Matter Options[/bold cyan]\n"
                    "[dim]Select which front matter components to include in your book[/dim]",
                    border_style="blue"
                ))
                
                front_matter_options = {}
                
                if console.input("[bold blue]Include copyright page? (y/n): [/bold blue]").strip().lower() == 'y':
                    front_matter_options['copyright'] = True
                    front_matter_options['year'] = console.input("[bold blue]Copyright year (default: current year): [/bold blue]").strip()
                    front_matter_options['publisher'] = console.input("[bold blue]Publisher name (default: Self-Published): [/bold blue]").strip()
                    front_matter_options['edition'] = console.input("[bold blue]Edition (e.g., First Edition): [/bold blue]").strip()
                    front_matter_options['isbn'] = console.input("[bold blue]ISBN (optional): [/bold blue]").strip()
                    front_matter_options['copyright_holder'] = console.input("[bold blue]Copyright holder (default: author): [/bold blue]").strip()
                    front_matter_options['additional_info'] = console.input("[bold blue]Additional copyright information: [/bold blue]").strip()
                
                if console.input("[bold blue]Include epigraph (quote or short poem)? (y/n): [/bold blue]").strip().lower() == 'y':
                    front_matter_options['epigraph'] = True
                
                if console.input("[bold blue]Include preface? (y/n): [/bold blue]").strip().lower() == 'y':
                    front_matter_options['preface'] = True
                
                if console.input("[bold blue]Include letter to the reader? (y/n): [/bold blue]").strip().lower() == 'y':
                    front_matter_options['letter_to_reader'] = True
                
                if console.input("[bold blue]Include introduction? (y/n): [/bold blue]").strip().lower() == 'y':
                    front_matter_options['introduction'] = True
                
                api_key = console.input("[bold blue]Enter Anthropic API key (or leave blank to use ANTHROPIC_API_KEY from environment): [/bold blue]").strip()
                
                console.print("[bold green]Front matter options configured![/bold green]")
            
            # Initialize the PDF Generator to get available styles
            pdf_generator = PDFGenerator(image_base_path=images_dir)
            style_names = pdf_generator.style_manager.get_style_names()
            
            if not style_names:
                console.print("[bold yellow]No style templates found. Using default style.[/bold yellow]")
                style_name = "classic"
            else:
                style_table = Table(title="Available Style Templates")
                style_table.add_column("Number", style="dim")
                style_table.add_column("Style Name", style="cyan")
                style_table.add_column("Description", style="green")
                style_table.add_column("Custom Fonts", style="yellow")
                
                for i, name in enumerate(style_names, 1):
                    try:
                        style_config = pdf_generator.style_manager.load_style(name)
                        description = style_config.get('description', 'No description available')
                        custom_fonts = style_config.get('custom_fonts', [])
                        if custom_fonts:
                            font_names = [f"{font.get('name', 'Unknown')}" for font in custom_fonts]
                            fonts_info = ", ".join(font_names)
                        else:
                            fonts_info = "None"
                    except Exception as e:
                        description = 'No description available'
                        fonts_info = 'Unknown'
                        print(f"Error loading style for description: {e}")
                    
                    style_table.add_row(str(i), name, description, fonts_info)
                
                console.print(style_table)
                
                style_choice = Prompt.ask(
                    "[bold blue]Select a style by number[/bold blue]",
                    choices=[str(i) for i in range(1, len(style_names) + 1)],
                    default="1"
                )
                
                style_name = style_names[int(style_choice) - 1]
                console.print(f"[bold green]Selected style: {style_name}[/bold green]")
            
            # Create a table of available formats
            format_table = Table(title="Available PDF Formats")
            format_table.add_column("Number", style="dim")
            format_table.add_column("Format Name", style="cyan")
            format_table.add_column("Dimensions", style="green")
            format_table.add_column("Description", style="yellow")

            formats = [
                {"id": 1, "name": "Current Size", "size": "A4", "width": 8.27, "height": 11.69, 
                "description": "Current default size (A4)"},
                {"id": 2, "name": "US Trade", "size": "CUSTOM", "width": 6, "height": 9, 
                "description": "Standard trade paperback size"},
                {"id": 3, "name": "US Letter", "size": "LETTER", "width": 8.5, "height": 11, 
                "description": "Standard US letter size"},
                {"id": 4, "name": "A4", "size": "A4", "width": 8.27, "height": 11.69, 
                "description": "Standard A4 size"},
            ]

            for fmt in formats:
                format_table.add_row(
                    str(fmt["id"]),
                    fmt["name"],
                    f"{fmt['width']}\" × {fmt['height']}\"",
                    fmt["description"]
                )

            console.print(format_table)

            # Ask user about generating multiple formats
            generate_multiple = console.input("[bold blue]Generate multiple PDF formats? (y/n): [/bold blue]").strip().lower() == 'y'

            selected_formats = []

            if generate_multiple:
                # Ask which formats to generate
                format_choices = console.input("[bold blue]Enter format numbers to generate (comma separated, or 'all'): [/bold blue]").strip()
                
                if format_choices.lower() == 'all':
                    selected_formats = formats
                else:
                    try:
                        format_ids = [int(id.strip()) for id in format_choices.split(',') if id.strip()]
                        selected_formats = [fmt for fmt in formats if fmt["id"] in format_ids]
                    except ValueError:
                        console.print("[bold red]Invalid format selection. Using current size only.[/bold red]")
                        selected_formats = [formats[0]]  # Default to current size
            else:
                # Just use current size
                selected_formats = [formats[0]]
            
            # Ensure results/pdfs directory exists
            os.makedirs('results/pdfs', exist_ok=True)
            
            try:
                with console.status("[bold green]Generating PDF...", spinner="dots"):
                    if enable_multipart:
                        if generate_multiple:
                            result = pdf_generator.generate_multiformat_pdf(
                                file_path, book_name, author_name, 
                                style_name=style_name, 
                                max_pages_per_part=max_pages,
                                front_matter_options=front_matter_options,
                                api_key=api_key,
                                formats=selected_formats
                            )
                        else:
                            result = pdf_generator.generate_pdf(
                                file_path, book_name, author_name, 
                                style_name=style_name, 
                                max_pages_per_part=max_pages,
                                front_matter_options=front_matter_options,
                                api_key=api_key
                            )
                    else:
                        if generate_multiple:
                            result = pdf_generator.generate_multiformat_pdf(
                                file_path, book_name, author_name, 
                                style_name=style_name, 
                                max_pages_per_part=1000000,
                                front_matter_options=front_matter_options,
                                api_key=api_key,
                                formats=selected_formats
                            )
                        else:
                            result = pdf_generator.generate_pdf(
                                file_path, book_name, author_name, 
                                style_name=style_name, 
                                max_pages_per_part=1000000,
                                front_matter_options=front_matter_options,
                                api_key=api_key
                            )
                
                if generate_multiple:
                    console.print(f"[bold green]PDFs generated successfully in multiple formats![/bold green]")
                    for format_name, format_result in result.items():
                        if isinstance(format_result, list):
                            console.print(f"[bold green]Format: {format_name} - {len(format_result)} parts[/bold green]")
                            for i, pdf_path in enumerate(format_result, 1):
                                console.print(f"[bold green]  Part {i} saved to: {pdf_path}[/bold green]")
                        else:
                            console.print(f"[bold green]Format: {format_name} - saved to: {format_result}[/bold green]")
                else:
                    if isinstance(result, list):
                        console.print(f"[bold green]PDF generated successfully in {len(result)} parts![/bold green]")
                        for i, pdf_path in enumerate(result, 1):
                            console.print(f"[bold green]Part {i} saved to: {pdf_path}[/bold green]")
                    else:
                        console.print("[bold green]PDF generated successfully![/bold green]")
                        console.print(f"[bold green]Output saved to: {result}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error generating PDF: {str(e)}[/bold red]")
                
            if args.headless:
                return
        
        elif choice == '5':
            # List available PDF styles
            try:
                images_dir = console.input("[bold blue]Enter path to images directory (default: 'images'): [/bold blue]").strip()
                if not images_dir:
                    images_dir = 'images'
                    
                pdf_generator = PDFGenerator(image_base_path=images_dir)
                style_names = pdf_generator.style_manager.get_style_names()
                
                if not style_names:
                    console.print("[bold yellow]No style templates found. Creating default style...[/bold yellow]")
                    pdf_generator.style_manager._create_default_style()
                    style_names = pdf_generator.style_manager.get_style_names()
                    if not style_names:
                        console.print("[bold red]Failed to create default style.[/bold red]")
                        continue
                
                style_table = Table(title="Available Style Templates")
                style_table.add_column("Style Name", style="cyan")
                style_table.add_column("Description", style="green")
                style_table.add_column("Image Support", style="magenta")
                style_table.add_column("Custom Fonts", style="yellow")
                
                for name in style_names:
                    try:
                        style_config = pdf_generator.style_manager.load_style(name)
                        description = style_config.get('description', 'No description available')
                        has_image_config = 'images' in style_config
                        image_support = "[green]✓[/green]" if has_image_config else "[yellow]Limited[/yellow]"
                        custom_fonts = style_config.get('custom_fonts', [])
                        if custom_fonts:
                            font_names = [font.get('name', 'Unknown') for font in custom_fonts]
                            fonts_info = f"[green]{', '.join(font_names)}[/green]"
                        else:
                            fonts_info = "[dim]None[/dim]"
                    except Exception as e:
                        description = 'No description available'
                        image_support = "[red]Unknown[/red]"
                        fonts_info = "[red]Unknown[/red]"
                        print(f"Error loading style for description: {e}")
                    
                    style_table.add_row(name, description, image_support, fonts_info)
                
                console.print(style_table)
                
                fonts_dir = 'fonts'
                if os.path.exists(fonts_dir) and os.listdir(fonts_dir):
                    font_files = [f for f in os.listdir(fonts_dir) if f.lower().endswith('.ttf')]
                    if font_files:
                        console.print(Panel.fit(
                            f"[bold cyan]Available Font Files in '{fonts_dir}' Directory[/bold cyan]\n"
                            f"[dim]{', '.join(font_files)}[/dim]",
                            border_style="green"
                        ))
                
                console.print(Panel.fit(
                    "[bold cyan]How to Add New Styles[/bold cyan]\n"
                    "[dim]1. Create a JSON or YAML file in the 'styles' directory\n"
                    "2. Follow the template format of existing styles\n"
                    "3. Define all required style properties\n"
                    "4. To support images, add an 'images' section to your style\n"
                    "5. The style will automatically appear in this list[/dim]",
                    border_style="blue"
                ))
                
                console.print(Panel.fit(
                    "[bold cyan]Custom Font Configuration[/bold cyan]\n"
                    "[dim]To use custom fonts in your PDFs, add a 'custom_fonts' section to your style:\n\n"
                    "\"custom_fonts\": [\n"
                    "    {\n"
                    "        \"name\": \"MyFont\",\n"
                    "        \"path\": \"MyFont-Regular.ttf\",\n"
                    "        \"bold_path\": \"MyFont-Bold.ttf\",\n"
                    "        \"italic_path\": \"MyFont-Italic.ttf\"\n"
                    "    }\n"
                    "]\n\n"
                    "Then reference the font name in any style element:\n"
                    "\"body_text\": { \"font\": \"MyFont\", ... }[/dim]",
                    border_style="yellow"
                ))
                
                console.print(Panel.fit(
                    "[bold cyan]Image Configuration[/bold cyan]\n"
                    "[dim]To support images in your PDFs, ensure your style includes an 'images' section:\n\n"
                    "\"images\": {\n"
                    "    \"max_width\": 450,\n"
                    "    \"space_before\": 12,\n"
                    "    \"space_after\": 12,\n"
                    "    \"full_page_threshold\": 0.8,\n"
                    "    \"full_page_break\": true,\n"
                    "    \"caption\": {\n"
                    "        \"font\": \"Helvetica-Italic\",\n"
                    "        \"size\": 10,\n"
                    "        \"leading\": 12,\n"
                    "        \"color\": \"#333333\"\n"
                    "    }\n"
                    "}[/dim]",
                    border_style="green"
                ))
            except Exception as e:
                console.print(f"[bold red]Error listing styles: {str(e)}[/bold red]")
                
            if args.headless:
                return
        
        elif choice == '6':
            # Create new PDF style
            try:
                console.print(Panel(
                    "[bold cyan]Create New PDF Style[/bold cyan]\n"
                    "[dim]This will guide you through creating a new style template for PDF generation.\n"
                    "You'll be prompted for various settings related to page layout, fonts, colors, etc.\n"
                    "The resulting style will be saved as a JSON file in the 'styles' directory.[/dim]",
                    border_style="blue"
                ))
                
                fonts_dir = 'fonts'
                if os.path.exists(fonts_dir) and os.listdir(fonts_dir):
                    font_files = [f for f in os.listdir(fonts_dir) if f.lower().endswith('.ttf')]
                    if font_files:
                        console.print(Panel.fit(
                            f"[bold cyan]Available Font Files in '{fonts_dir}' Directory[/bold cyan]\n"
                            f"[dim]{', '.join(font_files)}[/dim]",
                            border_style="green"
                        ))
                
                generator = StyleGenerator()
                style_path = generator.generate_style()
                
                console.print(Panel(
                    f"[bold green]Style Created Successfully![/bold green]\n"
                    f"[dim]Your new style has been saved to: {style_path}\n"
                    f"You can now select this style when generating PDFs.[/dim]",
                    border_style="green"
                ))
            except Exception as e:
                console.print(f"[bold red]Error creating style: {str(e)}[/bold red]")
                
            if args.headless:
                return
        
        elif choice == '7':
            # Process Markdown/HTML Files - New option
            try:
                console.print(Panel(
                    "[bold cyan]Process Markdown/HTML Files[/bold cyan]\n"
                    "[dim]This will convert Markdown or HTML files into PDF documents.\n"
                    "You'll need to provide a directory containing either Markdown (.md) or HTML (.html) files.\n"
                    "The files will be processed and converted to PDFs with chapter and section structure.[/dim]",
                    border_style="blue"
                ))
                
                # Get input directory
                input_dir = console.input("[bold blue]Enter path to directory with Markdown/HTML files: [/bold blue]").strip()
                
                if not input_dir or not os.path.exists(input_dir) or not os.path.isdir(input_dir):
                    console.print("[bold red]Invalid directory path. Please try again.[/bold red]")
                    continue
                
                # Get output directory
                output_dir = console.input("[bold blue]Enter path for output PDFs (default: 'results/pdfs'): [/bold blue]").strip()
                if not output_dir:
                    output_dir = 'results/pdfs'
                    
                # Ensure output directory exists
                os.makedirs(output_dir, exist_ok=True)
                
                # Get style name
                pdf_generator = PDFGenerator()
                style_names = pdf_generator.style_manager.get_style_names()
                
                if not style_names:
                    console.print("[bold yellow]No style templates found. Using default style.[/bold yellow]")
                    style_name = "classic"
                else:
                    style_table = Table(title="Available Style Templates")
                    style_table.add_column("Number", style="dim")
                    style_table.add_column("Style Name", style="cyan")
                    
                    for i, name in enumerate(style_names, 1):
                        style_table.add_row(str(i), name)
                    
                    console.print(style_table)
                    
                    style_choice = Prompt.ask(
                        "[bold blue]Select a style by number[/bold blue]",
                        choices=[str(i) for i in range(1, len(style_names) + 1)],
                        default="1"
                    )
                    
                    style_name = style_names[int(style_choice) - 1]
                    console.print(f"[bold green]Selected style: {style_name}[/bold green]")
                
                # Initialize Markdown/HTML processor
                processor = MarkdownHTMLProcessor(
                    input_dir=input_dir,
                    output_dir=output_dir,
                    style_name=style_name
                )
                
                # Scan directory to check file types
                files, file_type = processor.scan_directory()
                
                if not files:
                    console.print("[bold red]No Markdown or HTML files found in the specified directory.[/bold red]")
                    continue
                
                if file_type == 'mixed':
                    console.print("[bold red]Mixed file types found. Directory must contain only Markdown OR only HTML files.[/bold red]")
                    continue
                
                # Process files
                with console.status(f"[bold green]Processing {file_type.upper()} files...", spinner="dots"):
                    pdf_files = processor.process_directory()
                
                if pdf_files:
                    console.print(f"[bold green]{len(pdf_files)} PDFs generated successfully![/bold green]")
                    for pdf_path in pdf_files:
                        console.print(f"[bold green]PDF saved to: {pdf_path}[/bold green]")
                else:
                    console.print("[bold red]No PDFs were generated. See logs for details.[/bold red]")
                
            except Exception as e:
                console.print(f"[bold red]Error processing Markdown/HTML files: {str(e)}[/bold red]")
                
            if args.headless:
                return
        
        elif choice == '8':
            # Exit the program
            console.print("[bold red]Exiting the application.[/bold red]")
            return
        
        else:
            console.print("[bold red]Invalid choice. Please select 1-8.[/bold red]")
        
        # If in headless mode, exit after one operation
        if args.headless:
            return
            
        console.print("\n" + "-" * 80 + "\n")
        choice = console.input("[bold blue]Enter your choice (1-8): [/bold blue]").strip()

if __name__ == "__main__":
    main()