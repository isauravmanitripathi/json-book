import json
import os
from rich.console import Console
from rich.panel import Panel

def extract_section_text(input_file_path, output_file_path=None):
    """
    Extract pure text from dialogues, combining all dialogue text for each section.
    
    Args:
    input_file_path (str): Path to the input JSON file
    output_file_path (str, optional): Path to save the extracted text JSON
    
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

    # Determine the correct key for chapters
    chapters_key = None
    if 'chapters' in input_data:
        chapters_key = 'chapters'
    elif input_data.get('New item', {}).get('chapters'):
        chapters_key = 'chapters'
        input_data = input_data['New item']

    if not chapters_key:
        console.print("[bold red]Error: Could not find chapters in the JSON file[/bold red]")
        return None

    # Create output structure
    output_data = []

    # Process each chapter
    for chapter in input_data.get(chapters_key, []):
        # Handle podcast conversation style
        if 'conversations' in chapter:
            # For podcast conversation JSON
            chapter_name = chapter.get('chapter_name', 'Unnamed Chapter')
            
            # Accumulate text from non-section-info conversations
            section_text = " ".join([
                conv['text'] for conv in chapter.get('conversations', []) 
                if conv['speaker'] != 'SECTION_INFO'
            ])
            
            output_data.append({
                "chapter_name": chapter_name,
                "section_number": "1",
                "section_name": chapter_name,
                "text": section_text
            })
        
        # Handle structured document style
        else:
            chapter_name = chapter.get('chapter_name', 'Unnamed Chapter')
            chapter_id = str(chapter.get('chapter_id', ''))

            # Process sections in the chapter
            for section in chapter.get('sections', []):
                # Extract text, use extracted-text if available
                text = section.get('extracted-text', '').strip()
                
                # Only add non-empty text
                if text:
                    output_item = {
                        "chapter_name": chapter_name,
                        "chapter_id": chapter_id,
                        "section_number": str(section.get('section_id', '')),
                        "section_name": section.get('section_name', 'Unnamed Section'),
                        "text": text
                    }
                    output_data.append(output_item)

    # Write output to JSON file if output path is provided
    if output_file_path:
        try:
            with open(output_file_path, 'w', encoding='utf-8') as file:
                json.dump(output_data, file, indent=2, ensure_ascii=False)
            
            console.print(f"[bold green]Text extracted successfully to {output_file_path}[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Error writing output file: {e}[/bold red]")

    return output_data

def main():
    """Main function to run the text extraction script."""
    console = Console()
    
    console.print(Panel.fit(
        "[bold cyan]Text Extractor[/bold cyan]\n"
        "[dim]Extract text from JSON with chapter and section details[/dim]",
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
                    f"[bold]Chapter:[/bold] {section.get('chapter_name', 'N/A')} (ID: {section.get('chapter_id', 'N/A')})\n"
                    f"[bold]Section Number:[/bold] {section.get('section_number', 'N/A')}\n"
                    f"[bold]Section Name:[/bold] {section.get('section_name', 'N/A')}\n"
                    f"[bold]Text Length:[/bold] {len(section.get('text', ''))} characters",
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