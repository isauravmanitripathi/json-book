import json
import logging
from collections import defaultdict

class ContentExtractor:
    """Extracts and organizes content from JSON files for front matter generation."""
    
    def __init__(self, json_file_path):
        """
        Initialize the content extractor.
        
        Args:
            json_file_path (str): Path to the JSON file containing book content
        """
        self.json_file_path = json_file_path
        self.logger = logging.getLogger(__name__)
        self.content = None
        self._load_content()
        
    def _load_content(self):
        """Load content from the JSON file."""
        try:
            with open(self.json_file_path, 'r') as file:
                self.content = json.load(file)
            self.logger.info(f"Successfully loaded content from {self.json_file_path}")
        except Exception as e:
            self.logger.error(f"Error loading content from {self.json_file_path}: {str(e)}")
            raise
            
    def get_chapter_structure(self):
        """
        Extract chapter and section structure from the content.
        
        Returns:
            dict: Dictionary with chapters and their sections
        """
        if not self.content:
            return {}
            
        # Group sections by chapter
        chapters = defaultdict(list)
        chapter_names = {}
        
        for section in self.content:
            chapter_id = section.get('chapter_id', '')
            chapter_name = section.get('chapter_name', 'Unnamed Chapter')
            section_name = section.get('section_name', 'Unnamed Section')
            section_number = section.get('section_number', '')
            
            # Store chapter name
            chapter_names[chapter_id] = chapter_name
            
            # Store section
            chapters[chapter_id].append({
                'name': section_name,
                'number': section_number
            })
            
        # Format the structure
        structure = {}
        for chapter_id, sections in chapters.items():
            structure[chapter_id] = {
                'name': chapter_names[chapter_id],
                'sections': sections
            }
            
        return structure
        
    def get_book_summary(self):
        """
        Generate a summary of the book based on chapter and section names.
        
        Returns:
            dict: Contains book overview information
        """
        if not self.content:
            return {}
            
        chapter_structure = self.get_chapter_structure()
        
        # Count chapters and sections
        num_chapters = len(chapter_structure)
        num_sections = sum(len(chapter['sections']) for chapter in chapter_structure.values())
        
        # Get a sample of chapter names (up to 5)
        chapter_samples = list(chapter_structure.values())[:5]
        chapter_samples = [chapter['name'] for chapter in chapter_samples]
        
        # Check if any sections have sample code
        has_code = any('```' in section.get('text', '') for section in self.content)
        
        # Get approximate word count
        total_words = sum(len(section.get('text', '').split()) for section in self.content)
        
        return {
            'num_chapters': num_chapters,
            'num_sections': num_sections,
            'chapter_samples': chapter_samples,
            'has_code': has_code,
            'word_count': total_words,
            'chapter_structure': chapter_structure
        }
    
    def get_sample_content(self, max_sections=3):
        """
        Get sample content from the book for context.
        
        Args:
            max_sections (int): Maximum number of sections to include
            
        Returns:
            list: List of sample section text
        """
        if not self.content or len(self.content) == 0:
            return []
            
        samples = []
        
        # Take samples from different parts of the book
        indices = [0]  # Always include first section
        
        if len(self.content) > 1:
            indices.append(len(self.content) // 2)  # Middle section
            
        if len(self.content) > 2:
            indices.append(len(self.content) - 1)  # Last section
            
        # Get sample text from each index
        for idx in indices[:max_sections]:
            section = self.content[idx]
            text = section.get('text', '')
            
            # Truncate long sections
            if len(text) > 500:
                text = text[:500] + "..."
                
            if text:
                samples.append({
                    'chapter': section.get('chapter_name', ''),
                    'section': section.get('section_name', ''),
                    'text': text
                })
                
        return samples