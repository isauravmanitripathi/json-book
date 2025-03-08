#!/usr/bin/env python3
import os
import logging
from pathlib import Path
import re
from datetime import datetime

logger = logging.getLogger(__name__)

def generate_output_filename(input_file, output_dir):
    """
    Generate an output PDF filename based on the input file path.
    
    Args:
        input_file (str): Path to input file
        output_dir (str): Directory for output PDF
        
    Returns:
        str: Path to output PDF file
    """
    # Get input file name and extension
    file_path = Path(input_file)
    file_name = file_path.stem
    
    # Create a clean filename without special characters
    clean_name = re.sub(r'[^\w\s-]', '', file_name).strip().replace(' ', '_')
    
    # Add timestamp to ensure uniqueness
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f"{clean_name}_{timestamp}.pdf"
    
    # Create full output path
    output_path = os.path.join(output_dir, output_filename)
    
    return output_path

def sort_files_naturally(file_list):
    """
    Sort files in natural order (e.g., chapter1, chapter2, chapter10).
    
    Args:
        file_list (list): List of file paths
        
    Returns:
        list: Sorted list of file paths
    """
    def natural_key(file_path):
        """Generate key for natural sort."""
        path = Path(file_path)
        name = path.stem
        
        # Extract numbers from filename for natural sorting
        def atoi(text):
            return int(text) if text.isdigit() else text
            
        return [atoi(c) for c in re.split(r'(\d+)', name)]
    
    return sorted(file_list, key=natural_key)

def ensure_dir_exists(directory):
    """
    Ensure that a directory exists, creating it if necessary.
    
    Args:
        directory (str): Directory path
        
    Returns:
        str: Directory path
    """
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Created directory: {directory}")
    
    return directory

def is_file_type(file_path, extension):
    """
    Check if a file has the specified extension.
    
    Args:
        file_path (str): Path to file
        extension (str): File extension (e.g., '.md', '.html')
        
    Returns:
        bool: True if file has the specified extension
    """
    return Path(file_path).suffix.lower() == extension.lower()