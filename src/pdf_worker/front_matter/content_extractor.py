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
        
        # Extract topics based on section names
        topics = self._extract_topics()
        
        return {
            'num_chapters': num_chapters,
            'num_sections': num_sections,
            'chapter_samples': chapter_samples,
            'has_code': has_code,
            'word_count': total_words,
            'chapter_structure': chapter_structure,
            'topics': topics
        }
    
    def _extract_topics(self):
        """Extract potential topics/themes from section names."""
        topics = []
        if not self.content:
            return topics
            
        # Collect all unique words from section names and chapter names
        words = set()
        for section in self.content:
            section_name = section.get('section_name', '').lower()
            chapter_name = section.get('chapter_name', '').lower()
            
            # Split names into words
            if section_name:
                words.update(word.strip(',.()[]{}":;') for word in section_name.split())
            if chapter_name:
                words.update(word.strip(',.()[]{}":;') for word in chapter_name.split())
        
        # Filter out common words and very short words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about',
                     'of', 'as', 'from', 'into', 'during', 'including', 'until', 'against', 'among'}
        
        topics = [word for word in words if word not in stop_words and len(word) > 3]
        
        # Return up to 10 potential topics
        return sorted(topics)[:10]
    
    def get_sample_content(self, max_sections=None, sample_lines=2):
        """
        Get sample content from the book for context including first few lines from each section.
        
        Args:
            max_sections (int, optional): Maximum number of sections to include. If None, includes all sections.
            sample_lines (int): Number of lines to sample from each section text.
                
        Returns:
            list: List of sample section information with chapter, section, and text samples
        """
        if not self.content:
            return []
            
        samples = []
        
        # Determine how many sections to process
        sections_to_process = self.content
        if max_sections and max_sections < len(self.content):
            # Select a representative sample - beginning, middle, and end
            indices = []
            if len(self.content) > 0:
                indices.append(0)  # First section
            
            if len(self.content) > 2:
                indices.append(len(self.content) // 2)  # Middle section
                
            if len(self.content) > 1:
                indices.append(len(self.content) - 1)  # Last section
                
            # Add more indices if needed to reach max_sections
            remaining = max_sections - len(indices)
            if remaining > 0:
                step = len(self.content) // (remaining + 1)
                for i in range(1, remaining + 1):
                    idx = i * step
                    if idx not in indices:
                        indices.append(idx)
                        
            indices.sort()
            sections_to_process = [self.content[i] for i in indices]
        
        # Process selected sections
        for section in sections_to_process:
            chapter_name = section.get('chapter_name', 'Unnamed Chapter')
            section_name = section.get('section_name', 'Unnamed Section')
            section_text = section.get('text', '')
            
            # Extract first few lines
            lines = section_text.split('\n')
            sample_text = '\n'.join(lines[:sample_lines])
            
            # Ensure sample text is not too long
            if len(sample_text) > 300:
                sample_text = sample_text[:297] + '...'
                
            if sample_text:
                samples.append({
                    'chapter': chapter_name,
                    'section': section_name,
                    'text': sample_text
                })
        
        return samples