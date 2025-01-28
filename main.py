#!/usr/bin/env python3
import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.json_writer.chapter_extractor import extract_section_text
from src.json_writer.write_text_gemini import generate_conversations_gemini
from src.pdf_worker import PDFGenerator

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
    table.add_row("5", "Exit")
    console.print(table)

    while True:
        choice = console.input("[bold blue]Enter your choice (1-5): [/bold blue]").strip()

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

            # Ensure results/pdfs directory exists
            os.makedirs('results/pdfs', exist_ok=True)

            try:
                with console.status("[bold green]Generating PDF...", spinner="dots"):
                    pdf_generator = PDFGenerator()
                    result = pdf_generator.generate_pdf(file_path, book_name, author_name)
                
                if result:
                    console.print("[bold green]PDF generated successfully![/bold green]")
                    console.print(f"[bold green]Output saved to: {result}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error generating PDF: {str(e)}[/bold red]")
        
        elif choice == '5':
            # Exit the program
            console.print("[bold red]Exiting the application.[/bold red]")
            break
        
        else:
            console.print("[bold red]Invalid choice. Please select 1-5.[/bold red]")

if __name__ == "__main__":
    main()