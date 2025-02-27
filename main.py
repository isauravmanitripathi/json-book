#!/usr/bin/env python3
import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from src.json_writer.chapter_extractor import extract_section_text
from src.json_writer.write_text_gemini import generate_conversations_gemini
from src.pdf_worker.core import PDFGenerator

def main():
    """Main entry point for the application."""
    console = Console()
    
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
    table.add_row("6", "Exit")
    console.print(table)

    while True:
        choice = console.input("[bold blue]Enter your choice (1-6): [/bold blue]").strip()

        if choice == '1':
            # Extract chapter text option
            file_path = console.input("[bold blue]Enter the path to the input JSON file: [/bold blue]").strip()
            
            if not file_path or not os.path.exists(file_path):
                console.print("[bold red]Invalid file path. Please try again.[/bold red]")
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
        
        elif choice == '2':
            # Generate with OpenAI
            file_path = console.input("[bold blue]Enter the path to the input JSON file: [/bold blue]").strip()
            
            if not file_path or not os.path.exists(file_path):
                console.print("[bold red]Invalid file path. Please try again.[/bold red]")
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
        
        elif choice == '3':
            # Generate with Gemini
            file_path = console.input("[bold blue]Enter the path to the input JSON file: [/bold blue]").strip()
            
            if not file_path or not os.path.exists(file_path):
                console.print("[bold red]Invalid file path. Please try again.[/bold red]")
                continue

            try:
                with console.status("[bold green]Generating articles with Gemini...", spinner="dots"):
                    result = generate_conversations_gemini(file_path)
                
                if result:
                    console.print("[bold green]Articles generated successfully![/bold green]")
                    console.print(f"[bold green]Output saved to: {result}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error generating articles: {str(e)}[/bold red]")

        elif choice == '4':
            # Generate PDF
            file_path = console.input("[bold blue]Enter the path to the input JSON file: [/bold blue]").strip()
            
            if not file_path or not os.path.exists(file_path):
                console.print("[bold red]Invalid file path. Please try again.[/bold red]")
                continue

            # Get book name
            book_name = console.input("[bold blue]Enter the name of the book: [/bold blue]").strip()
            
            if not book_name:
                console.print("[bold red]Book name cannot be empty. Please try again.[/bold red]")
                continue
                
            # Get author name
            author_name = console.input("[bold blue]Enter the name of the author: [/bold blue]").strip()
            
            if not author_name:
                console.print("[bold red]Author name cannot be empty. Please try again.[/bold red]")
                continue
            
            # Get images directory path
            images_dir = console.input("[bold blue]Enter path to images directory (default: 'images'): [/bold blue]").strip()
            if not images_dir:
                images_dir = 'images'
                
            # Create images directory if it doesn't exist
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
            
            # Initialize the PDF Generator to get available styles
            pdf_generator = PDFGenerator(image_base_path=images_dir)
            style_names = pdf_generator.style_manager.get_style_names()
            
            if not style_names:
                console.print("[bold yellow]No style templates found. Using default style.[/bold yellow]")
                style_name = "classic"
            else:
                # Create a table to show available styles
                style_table = Table(title="Available Style Templates")
                style_table.add_column("Number", style="dim")
                style_table.add_column("Style Name", style="cyan")
                style_table.add_column("Description", style="green")
                
                for i, name in enumerate(style_names, 1):
                    # Try to get description from style
                    try:
                        style_config = pdf_generator.style_manager.load_style(name)
                        description = style_config.get('description', 'No description available')
                    except Exception as e:
                        description = 'No description available'
                        print(f"Error loading style for description: {e}")
                    
                    style_table.add_row(str(i), name, description)
                
                console.print(style_table)
                
                # Prompt for style selection
                style_choice = Prompt.ask(
                    "[bold blue]Select a style by number[/bold blue]",
                    choices=[str(i) for i in range(1, len(style_names) + 1)],
                    default="1"
                )
                
                style_name = style_names[int(style_choice) - 1]
                console.print(f"[bold green]Selected style: {style_name}[/bold green]")

            # Ensure results/pdfs directory exists
            os.makedirs('results/pdfs', exist_ok=True)

            try:
                with console.status("[bold green]Generating PDF...", spinner="dots"):
                    if enable_multipart:
                        result = pdf_generator.generate_pdf(
                            file_path, book_name, author_name, 
                            style_name=style_name, 
                            max_pages_per_part=max_pages
                        )
                    else:
                        # Disable multi-part by setting a very high page limit
                        result = pdf_generator.generate_pdf(
                            file_path, book_name, author_name, 
                            style_name=style_name, 
                            max_pages_per_part=1000000
                        )
                
                if result:
                    if isinstance(result, list):
                        console.print(f"[bold green]PDF generated successfully in {len(result)} parts![/bold green]")
                        for i, pdf_path in enumerate(result, 1):
                            console.print(f"[bold green]Part {i} saved to: {pdf_path}[/bold green]")
                    else:
                        console.print("[bold green]PDF generated successfully![/bold green]")
                        console.print(f"[bold green]Output saved to: {result}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error generating PDF: {str(e)}[/bold red]")
        
        elif choice == '5':
            # List available PDF styles
            try:
                # Allow specifying custom images directory for viewing image settings
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
                
                # Create a table to show available styles
                style_table = Table(title="Available Style Templates")
                style_table.add_column("Style Name", style="cyan")
                style_table.add_column("Description", style="green")
                style_table.add_column("Image Support", style="magenta")
                
                for name in style_names:
                    # Try to get description from style
                    try:
                        style_config = pdf_generator.style_manager.load_style(name)
                        description = style_config.get('description', 'No description available')
                        
                        # Check for image support
                        has_image_config = 'images' in style_config
                        image_support = "[green]✓[/green]" if has_image_config else "[yellow]Limited[/yellow]"
                        
                    except Exception as e:
                        description = 'No description available'
                        image_support = "[red]Unknown[/red]"
                        print(f"Error loading style for description: {e}")
                    
                    style_table.add_row(name, description, image_support)
                
                console.print(style_table)
                
                # Provide instructions for adding new styles
                console.print(Panel.fit(
                    "[bold cyan]How to Add New Styles[/bold cyan]\n"
                    "[dim]1. Create a JSON or YAML file in the 'styles' directory\n"
                    "2. Follow the template format of existing styles\n"
                    "3. Define all required style properties\n"
                    "4. To support images, add an 'images' section to your style\n"
                    "5. The style will automatically appear in this list[/dim]",
                    border_style="blue"
                ))
                
                # Show image configuration hint
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
        
        elif choice == '6':
            # Exit the program
            console.print("[bold red]Exiting the application.[/bold red]")
            break
        
        else:
            console.print("[bold red]Invalid choice. Please select 1-6.[/bold red]")

if __name__ == "__main__":
    main()