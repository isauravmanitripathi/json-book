#!/usr/bin/env python3
import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.json_writer.chapter_extractor import extract_section_text
from src.json_writer.write_text_openai import generate_conversations

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
    table.add_row("2", "Generate Conversations from JSON")
    table.add_row("3", "Dummy Option")
    table.add_row("4", "Exit")
    console.print(table)

    while True:
        choice = console.input("[bold blue]Enter your choice (1-4): [/bold blue]").strip()

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

            # Call extraction function
            result = extract_section_text(file_path, output_path)
            
            if result:
                console.print(f"[bold green]Text extracted successfully to {output_path}[/bold green]")
        
        elif choice == '2':
            # Generate conversations option
            file_path = console.input("[bold blue]Enter the path to the input JSON file: [/bold blue]").strip()
            
            if not file_path or not os.path.exists(file_path):
                console.print("[bold red]Invalid file path. Please try again.[/bold red]")
                continue

            try:
                # Call conversation generator
                with console.status("[bold green]Generating conversations...", spinner="dots"):
                    result = generate_conversations(file_path)
                
                if result:
                    console.print("[bold green]Conversations generated successfully![/bold green]")
                    console.print(f"[bold green]Output saved to: {result}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error generating conversations: {str(e)}[/bold red]")
        
        elif choice == '3':
            # Dummy Option
            console.print("[bold yellow]Dummy Option selected. No action implemented.[/bold yellow]")
        
        elif choice == '4':
            # Exit the program
            console.print("[bold red]Exiting the application.[/bold red]")
            break
        
        else:
            console.print("[bold red]Invalid choice. Please select 1-4.[/bold red]")

if __name__ == "__main__":
    main()