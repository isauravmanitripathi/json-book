#!/usr/bin/env python3
import json
import os
from rich.console import Console
from rich.panel import Panel

def extract_section_text(input_file_path, output_file_path=None):
    """
    Extract text from sections in a JSON file using the new structure.
    
    The expected JSON structure is:
    {
        "New item": {
            "chapters": [
                {
                    "chapter_id": <int>,
                    "chapter_name": <string>,
                    "chapter_path": <string>,
                    "sections": [
                        {
                            "section_id": <float>,
                            "section_name": <string>,
                            "section_path": <string>,
                            "images": [<string>],
                            "code_images": [],
                            "status": <string>,
                            "errors": [],
                            "extracted-text": <string>,
                            "extracted-code": <string>
                        }
                    ]
                }
            ]
        }
    }
    
    For each section, the function extracts the "extracted-text" and creates an output dictionary
    with the following keys: chapter_name, chapter_id, section_number (a combination of chapter_id
    and section_id), section_name, and text.
    
    If output_file_path is provided, the extracted data is written to that file.
    
    Args:
        input_file_path (str): Path to the input JSON file.
        output_file_path (str, optional): Path to save the extracted text JSON.
    
    Returns:
        list: A list of dictionaries with the extracted chapter and section details.
    """
    console = Console()

    if not os.path.exists(input_file_path):
        console.print(f"[bold red]Error: File not found at {input_file_path}[/bold red]")
        return None

    try:
        with open(input_file_path, 'r', encoding='utf-8') as file:
            input_data = json.load(file)
    except json.JSONDecodeError:
        console.print("[bold red]Error: Invalid JSON file[/bold red]")
        return None
    except Exception as e:
        console.print(f"[bold red]Error reading file: {e}[/bold red]")
        return None

    # If the JSON is wrapped under "New item", use its content
    if "New item" in input_data:
        input_data = input_data["New item"]

    if "chapters" not in input_data:
        console.print("[bold red]Error: Could not find chapters in the JSON file[/bold red]")
        return None

    output_data = []
    for chapter in input_data.get("chapters", []):
        chapter_name = chapter.get("chapter_name", "Unnamed Chapter")
        chapter_id = str(chapter.get("chapter_id", ""))
        for section in chapter.get("sections", []):
            text = section.get("extracted-text", "").strip()
            if text:
                section_id = section.get("section_id", "")
                section_number = f"{chapter_id}.{section_id}"
                output_item = {
                    "chapter_name": chapter_name,
                    "chapter_id": chapter_id,
                    "section_number": section_number,
                    "section_name": section.get("section_name", "Unnamed Section"),
                    "text": text
                }
                output_data.append(output_item)

    if output_file_path:
        try:
            with open(output_file_path, 'w', encoding='utf-8') as file:
                json.dump(output_data, file, indent=2, ensure_ascii=False)
            console.print(f"[bold green]Text extracted successfully to {output_file_path}[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Error writing output file: {e}[/bold red]")

    return output_data

def main():
    console = Console()
    
    console.print(Panel.fit(
        "[bold cyan]Text Extractor[/bold cyan]\n"
        "[dim]Extract text from JSON with chapter and section details[/dim]",
        border_style="blue"
    ))

    while True:
        file_path = console.input("[bold blue]Enter the path to the input JSON file: [/bold blue]").strip()
        if not file_path:
            console.print("[bold yellow]Please provide a file path.[/bold yellow]")
            continue
        
        result = extract_section_text(file_path)
        
        if result:
            console.print("\n[bold green]Extraction Preview:[/bold green]")
            for section in result[:3]:
                console.print(Panel(
                    f"[bold]Chapter:[/bold] {section.get('chapter_name', 'N/A')} (ID: {section.get('chapter_id', 'N/A')})\n"
                    f"[bold]Section Number:[/bold] {section.get('section_number', 'N/A')}\n"
                    f"[bold]Section Name:[/bold] {section.get('section_name', 'N/A')}\n"
                    f"[bold]Text Length:[/bold] {len(section.get('text', ''))} characters",
                    title="Section Overview",
                    border_style="green"
                ))
            break
        
        retry = console.input("[bold yellow]Do you want to try another file? (y/n): [/bold yellow]").strip().lower()
        if retry != 'y':
            break

if __name__ == "__main__":
    main()
