import json
import os
from rich.console import Console
from rich.panel import Panel

def extract_section_text(input_file_path):
    """
    Extract pure text from dialogues, combining all dialogue text for each section.
    
    Args:
    input_file_path (str): Path to the input JSON file
    
    Returns:
    list: Extracted text in the specified format
    """
    # Initialize console for rich output
    console = Console()

    # Validate input file
    if not os.path.exists(input_file_path):
        console.print(f"[bold red]Error: File not found at {input_file_path}[/bold red]")
        return None

    # Read the input JSON file
    try:
        with open(input_file_path, 'r', encoding='utf-8') as file:
            input_data = json.load(file)
    except json.JSONDecodeError:
        console.print("[bold red]Error: Invalid JSON file[/bold red]")
        return None
    except Exception as e:
        console.print(f"[bold red]Error reading file: {e}[/bold red]")
        return None

    # Create output structure
    output_data = []

    # Process each chapter
    for chapter_index, chapter in enumerate(input_data.get('chapters', []), 1):
        chapter_name = chapter.get('chapter_name', f'Chapter {chapter_index}')
        
        # Track section number within this chapter
        chapter_section_number = 0
        
        # Temporary storage for current chapter's sections
        chapter_sections = []
        
        # Process conversations in the chapter
        current_section = None
        
        for conv_turn in chapter.get('conversations', []):
            # Check for section info marker
            if conv_turn['speaker'] == 'SECTION_INFO':
                # If we had a previous section, add it to chapter sections
                if current_section:
                    chapter_sections.append(current_section)
                
                # Increment section number
                chapter_section_number += 1
                
                # Create a new section
                current_section = {
                    "chapter_name": chapter_name,
                    "section_number": str(chapter_section_number),
                    "section_name": conv_turn['text'].replace("From ", ""),
                    "text": ""
                }
            
            # Combine dialogue text (excluding section info)
            elif current_section is not None and conv_turn['speaker'] != 'SECTION_INFO':
                # Add dialogue text with a space between turns
                current_section['text'] += conv_turn['text'] + " "
        
        # Add the last section if exists
        if current_section:
            chapter_sections.append(current_section)
        
        # Add chapter sections to overall output
        output_data.extend(chapter_sections)

    # Determine output file path
    base_path = os.path.dirname(input_file_path)
    base_filename = os.path.splitext(os.path.basename(input_file_path))[0]
    output_file_path = os.path.join(base_path, f"{base_filename}_extracted_text.json")

    # Write output to JSON file
    try:
        with open(output_file_path, 'w', encoding='utf-8') as file:
            json.dump(output_data, file, indent=2, ensure_ascii=False)
        
        console.print(f"[bold green]Text extracted successfully to {output_file_path}[/bold green]")
        return output_data
    except Exception as e:
        console.print(f"[bold red]Error writing output file: {e}[/bold red]")
        return None

def main():
    """Main function to run the text extraction script."""
    console = Console()
    
    console.print(Panel.fit(
        "[bold cyan]Text Extractor[/bold cyan]\n"
        "[dim]Extract text from podcast conversation JSON[/dim]",
        border_style="blue"
    ))

    # Get input file path
    while True:
        file_path = console.input("[bold blue]Enter the path to the input JSON file: [/bold blue]").strip()
        
        if not file_path:
            console.print("[bold yellow]Please provide a file path.[/bold yellow]")
            continue
        
        # Attempt to extract text
        result = extract_section_text(file_path)
        
        if result:
            # Optionally, print a preview of extracted text
            console.print("\n[bold green]Extraction Preview:[/bold green]")
            for section in result[:3]:  # Preview first 3 sections
                console.print(Panel(
                    f"[bold]Chapter:[/bold] {section['chapter_name']}\n"
                    f"[bold]Section Number:[/bold] {section['section_number']}\n"
                    f"[bold]Section Name:[/bold] {section['section_name']}\n"
                    f"[bold]Text Length:[/bold] {len(section['text'])} characters",
                    title="Section Overview",
                    border_style="green"
                ))
            
            break
        
        # Ask if user wants to try again
        retry = console.input("[bold yellow]Do you want to try another file? (y/n): [/bold yellow]").strip().lower()
        if retry != 'y':
            break

if __name__ == "__main__":
    main()