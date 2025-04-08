import json
import os

def parse_course_content(input_file_path):
    """
    Parse the input JSON file and extract specific information to create a new JSON structure.
    
    Args:
        input_file_path (str): Path to the input JSON file
        
    Returns:
        list: List of dictionaries with the extracted information
    """
    try:
        # Read the input JSON file
        with open(input_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        # Initialize an empty list to store the extracted information
        result = []
        
        # Access the root structure which might vary
        root_data = data
        if "New item" in data:
            root_data = data["New item"]
        
        # Process each chapter in the data
        for chapter in root_data.get("chapters", []):
            chapter_name = chapter.get("chapter_name", "Unnamed Chapter")
            chapter_id = chapter.get("chapter_id", "No ID")
            
            # Process each section in the chapter
            for section in chapter.get("sections", []):
                section_name = section.get("section_name", "Unnamed Section")
                section_number = section.get("section_id", "No ID")
                
                # Extract text from api_response if it exists, or from ordered_content
                text = section.get("api_response", "")
                
                # If api_response is empty, try to get content from ordered_content
                if not text and "ordered_content" in section and section["ordered_content"]:
                    for content_item in section["ordered_content"]:
                        if "content" in content_item:
                            content_text = content_item.get("content", "")
                            if isinstance(content_text, str) and content_text.strip():
                                if text:
                                    text += "\n\n" + content_text
                                else:
                                    text = content_text
                
                # If we still don't have any text, include a placeholder
                if not text:
                    text = "No content available for this section"
                
                # Create a dictionary with the extracted information
                entry = {
                    "chapter_name": chapter_name,
                    "chapter_id": chapter_id,
                    "section_number": section_number,
                    "section_name": section_name,
                    "text": text
                }
                
                # Add the entry to the result list
                result.append(entry)
        
        return result
    
    except Exception as e:
        print(f"Error occurred while parsing the JSON file: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    """
    Main function to execute the JSON parsing and file generation logic.
    """
    # Ask for the input file path
    input_file_path = input("Enter the path to the input JSON file: ")
    
    # Check if the file exists
    if not os.path.isfile(input_file_path):
        print(f"Error: The file '{input_file_path}' does not exist.")
        return
    
    # Parse the input file
    result = parse_course_content(input_file_path)
    
    if not result:
        print("No data was extracted from the file.")
        return
    
    # Generate the output file path
    input_filename = os.path.basename(input_file_path)
    output_filename = f"processed_{input_filename}"
    output_dir = "results/json-combined"
    
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    output_file_path = os.path.join(output_dir, output_filename)
    
    # Write the result to the output file
    try:
        with open(output_file_path, 'w', encoding='utf-8') as file:
            json.dump(result, file, indent=2)
        
        print(f"Successfully generated '{output_file_path}'")
    
    except Exception as e:
        print(f"Error occurred while writing the output file: {e}")

if __name__ == "__main__":
    main()