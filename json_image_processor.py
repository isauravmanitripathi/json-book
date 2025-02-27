import json
import os
import shutil
from pathlib import Path
import sys

def load_json_file(file_path):
    """Load and parse JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: {file_path} is not a valid JSON file.")
        sys.exit(1)

def save_json_file(data, file_path):
    """Save data as JSON to specified file path."""
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"JSON file saved to {file_path}")
    except Exception as e:
        print(f"Error saving JSON file: {e}")

def display_section(section):
    """Display section information in a formatted way."""
    print("\n" + "=" * 80)
    print(f"Chapter: {section['chapter_name']} (ID: {section['chapter_id']})")
    print(f"Section: {section['section_number']} - {section['section_name']}")
    print("-" * 80)
    print(f"Text: {section['text']}")
    
    if 'images' in section and section['images']:
        print("\nImages:")
        for i, img in enumerate(section['images'], 1):
            print(f"  {i}. {img['image_path']}")
            print(f"     Caption: {img['caption']}")
    print("=" * 80)

def display_all_sections(data):
    """Display a list of all sections."""
    print("\n" + "=" * 80)
    print("SECTIONS LIST")
    print("-" * 80)
    
    for i, section in enumerate(data, 1):
        print(f"{i}. Chapter {section['chapter_id']}: {section['chapter_name']}")
        print(f"   Section {section['section_number']}: {section['section_name']}")
        
    print("=" * 80)

def create_folder_structure(chapter_id):
    """Create folder structure for saving images."""
    base_dir = Path("/Users/sauravtripathi/Downloads/generate-pdf/images")
    chapter_dir = base_dir / chapter_id
    
    # Create directories if they don't exist
    chapter_dir.mkdir(parents=True, exist_ok=True)
    
    return chapter_dir

def copy_image(source_path, chapter_id, image_number):
    """Copy image to appropriate folder with proper naming."""
    try:
        source_path = Path(source_path)
        if not source_path.exists():
            print(f"Error: Image file {source_path} not found.")
            return None
            
        # Get file extension
        file_extension = source_path.suffix
        
        # Create destination path
        chapter_dir = create_folder_structure(chapter_id)
        dest_filename = f"diagram{image_number}{file_extension}"
        dest_path = chapter_dir / dest_filename
        
        # Copy the file
        shutil.copy2(source_path, dest_path)
        
        # Return relative path to save in JSON
        return str(Path(chapter_id) / dest_filename)
    except Exception as e:
        print(f"Error copying image: {e}")
        return None

def process_section(section, data, output_path):
    """Process a single section allowing user to add images."""
    display_section(section)
    
    # Initialize images list if not present
    if 'images' not in section:
        section['images'] = []
    
    image_count = len(section['images'])
    
    while True:
        print("\nOptions:")
        print("1. Add an image")
        print("2. Move to another section")
        print("3. Finish and save")
        
        choice = input("Enter your choice (1-3): ").strip()
        
        if choice == '1':
            # Add an image
            image_path = input("Enter image path (or press Enter to skip): ").strip()
            if not image_path:
                continue
                
            # Copy image to appropriate folder
            relative_path = copy_image(image_path, section['chapter_id'], image_count + 1)
            if not relative_path:
                continue
                
            # Ask for caption
            caption = input("Enter caption (or press Enter to skip): ").strip()
            
            # Add to section's images
            section['images'].append({
                "image_path": relative_path,
                "caption": caption
            })
            
            # Increment image count
            image_count += 1
            
            # Save progress
            save_json_file(data, output_path)
            
        elif choice == '2':
            # Move to another section
            return True
            
        elif choice == '3':
            # Finish and save
            save_json_file(data, output_path)
            return False
            
        else:
            print("Invalid choice. Please try again.")

def main():
    """Main function to run the script."""
    # Ask for input JSON file path
    input_path = input("Enter the path to your JSON file: ").strip()
    
    # Load JSON data
    data = load_json_file(input_path)
    
    # Determine output path (in the same folder as input)
    input_file = Path(input_path)
    output_file = input_file.with_name(f"{input_file.stem}_updated{input_file.suffix}")
    output_path = str(output_file)
    
    # Save initial copy
    save_json_file(data, output_path)
    
    while True:
        # Display all sections
        display_all_sections(data)
        
        # Ask which section to process
        try:
            section_index = int(input("\nEnter section number to process (or 0 to finish): ").strip()) - 1
            
            if section_index == -1:  # User entered 0
                break
                
            if section_index < 0 or section_index >= len(data):
                print("Invalid section number. Please try again.")
                continue
                
            # Process the selected section
            continue_processing = process_section(data[section_index], data, output_path)
            if not continue_processing:
                break
                
        except ValueError:
            print("Please enter a valid number.")
    
    print(f"\nProcessing complete. Updated JSON saved to {output_path}")

if __name__ == "__main__":
    main()