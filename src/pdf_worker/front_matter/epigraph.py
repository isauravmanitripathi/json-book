import logging
import json
from .api_client import AnthropicClient
from .content_extractor import ContentExtractor

class EpigraphGenerator:
    """Generates an epigraph (quote, poem) based on book content."""
    
    def __init__(self, api_client=None):
        """
        Initialize the epigraph generator.
        
        Args:
            api_client (AnthropicClient, optional): API client for text generation
        """
        self.logger = logging.getLogger(__name__)
        self.api_client = api_client or AnthropicClient()
        
    def generate(self, book_title, author_name, json_file_path=None, book_summary=None):
        """
        Generate an epigraph for the book.
        
        Args:
            book_title (str): Title of the book
            author_name (str): Name of the author
            json_file_path (str, optional): Path to JSON file with book content
            book_summary (dict, optional): Book summary information
                
        Returns:
            str: Generated epigraph content in markdown format
        """
        try:
            self.logger.info("Generating epigraph content")
            
            # Extract book structure if JSON path provided
            if json_file_path and not book_summary:
                extractor = ContentExtractor(json_file_path)
                book_summary = extractor.get_book_summary()
                # Extract topics for better thematic targeting
                topics = extractor.get_sample_content(max_sections=5, sample_lines=1)
                book_summary['topics'] = [sample.get('section', '') for sample in topics]
            elif json_file_path and book_summary and 'topics' not in book_summary:
                # We have summary but still need topics
                extractor = ContentExtractor(json_file_path)
                topics = extractor.get_sample_content(max_sections=5, sample_lines=1)
                book_summary['topics'] = [sample.get('section', '') for sample in topics]
            
            # Create prompt
            prompt = self._create_prompt(book_title, author_name, book_summary)
            
            # Generate content
            epigraph_content = self.api_client.generate_text(
                prompt=prompt, 
                max_tokens=400,
                temperature=0.8  # Higher temperature for creativity
            )
            
            self.logger.info("Successfully generated epigraph content")
            return epigraph_content
            
        except Exception as e:
            self.logger.error(f"Error generating epigraph: {str(e)}")
            # Provide a fallback if API generation fails
            return self._create_fallback_content(book_title)
    
    def _create_prompt(self, book_title, author_name, book_summary):
        """Create enhanced prompt for epigraph generation."""
        # Format chapter information for the prompt
        chapter_info = ""
        if book_summary and 'chapter_structure' in book_summary:
            chapters = []
            for chapter_id, chapter in book_summary['chapter_structure'].items():
                chapters.append(f"- {chapter['name']}")
            
            if chapters:
                chapter_info = "Book chapters include:\n" + "\n".join(chapters[:7])
                if len(chapters) > 7:
                    chapter_info += "\n(and more...)"
        
        # Include topics if available
        topics_info = ""
        if book_summary and 'topics' in book_summary:
            topics = book_summary['topics']
            if topics:
                topics_str = ", ".join(topics[:10])
                topics_info = f"Key topics/themes: {topics_str}"
        
        prompt = f"""Create a meaningful, thought-provoking epigraph (a short quotation or saying at the beginning of a book) for a book with the following details:

Title: {book_title}
Author: {author_name}
{chapter_info}
{topics_info}

The epigraph should:
1. Be a short quote, poem, or saying (4-8 lines maximum)
2. Relate thematically to the book's content and title
3. Be profound and meaningful
4. Include attribution if it's a quote (you can create a fictional attribution if needed)
5. Be formatted in MARKDOWN

The epigraph should capture the essence of the book and provide readers with a thoughtful entry point to the material.

Make sure the output is properly formatted in Markdown to render correctly in the PDF.
Use *italic* for the quotation text itself.
Include proper attribution on a separate line.

DO NOT use extremely common or cliché quotes.
DO NOT prefix the response with "Here's an epigraph:" or similar explanatory text.
"""
        return prompt
    
    def _create_fallback_content(self, book_title):
        """Create fallback epigraph content if API fails."""
        return f"""
*"The journey of a thousand miles begins with a single page."*

— Anonymous
"""