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

    # Write output to JSON file if output path is provided
    if output_file_path:
        try:
            with open(output_file_path, 'w', encoding='utf-8') as file:
                json.dump(output_data, file, indent=2, ensure_ascii=False)
        except Exception as e:
            console.print(f"[bold red]Error writing output file: {e}[/bold red]")
            return None

    return output_data

def preview_extracted_text(extracted_text):
    """
    Preview the extracted text sections.
    
    Args:
    extracted_text (list): List of extracted text sections
    """
    console = Console()
    
    if not extracted_text:
        console.print("[bold yellow]No text to preview.[/bold yellow]")
        return

    # Optionally, print a preview of extracted text
    console.print("\n[bold green]Extraction Preview:[/bold green]")
    for section in extracted_text[:3]:  # Preview first 3 sections
        console.print(Panel(
            f"[bold]Chapter:[/bold] {section['chapter_name']}\n"
            f"[bold]Section Number:[/bold] {section.get('section_number', 'N/A')}\n"
            f"[bold]Section Name:[/bold] {section.get('section_name', 'N/A')}\n"
            f"[bold]Text Length:[/bold] {len(section.get('text', ''))} characters",
            title="Section Overview",
            border_style="green"
        ))