import logging
from .api_client import AnthropicClient
from .content_extractor import ContentExtractor

class LetterToReaderGenerator:
    """Generates a personal letter to the reader based on book content."""
    
    def __init__(self, api_client=None):
        """
        Initialize the letter to reader generator.
        
        Args:
            api_client (AnthropicClient, optional): API client for text generation
        """
        self.logger = logging.getLogger(__name__)
        self.api_client = api_client or AnthropicClient()
        
    def generate(self, book_title, author_name, json_file_path=None, book_summary=None):
        """
        Generate a letter to the reader.
        
        Args:
            book_title (str): Title of the book
            author_name (str): Name of the author
            json_file_path (str, optional): Path to JSON file with book content
            book_summary (dict, optional): Book summary information
                
        Returns:
            str: Generated letter content in markdown format
        """
        try:
            self.logger.info("Generating letter to reader content")
            
            # Extract book structure if JSON path provided
            if json_file_path and not book_summary:
                extractor = ContentExtractor(json_file_path)
                book_summary = extractor.get_book_summary()
            
            # Create prompt
            prompt = self._create_prompt(book_title, author_name, book_summary)
            
            # Generate content
            letter_content = self.api_client.generate_text(
                prompt=prompt, 
                max_tokens=1000,
                temperature=0.75
            )
            
            self.logger.info("Successfully generated letter to reader content")
            return letter_content
            
        except Exception as e:
            self.logger.error(f"Error generating letter to reader: {str(e)}")
            # Provide a fallback if API generation fails
            return self._create_fallback_content(book_title, author_name)
    
    def _create_prompt(self, book_title, author_name, book_summary):
        """Create prompt for letter to reader generation."""
        # Format book info for the prompt
        book_type = "technical book"
        if book_summary:
            if book_summary.get('has_code', False):
                book_type = "programming book"
            
            word_count = book_summary.get('word_count', 0)
            if word_count > 100000:
                book_size = "comprehensive"
            elif word_count > 50000:
                book_size = "substantial"
            else:
                book_size = "concise"
        else:
            book_size = "comprehensive"
        
        prompt = f"""Write a personal letter to the reader for a {book_size} {book_type} titled "{book_title}" by {author_name}.

The letter should:
1. Be around 400-500 words
2. Address the reader directly and personally
3. Convey the author's passion and excitement for the subject
4. Encourage the reader and make them feel welcomed
5. Mention challenges the reader might face and how this book will help
6. End with a positive, motivational note
7. Include a personal sign-off from the author
8. Be formatted in markdown

The tone should be warm, conversational, and encouraging - more personal than the formal preface.

DO NOT include a title at the top (like "Letter to the Reader") - that will be added separately.
DO NOT use generic platitudes or clichés.
DO finish with a sign-off that includes the author's name.
"""
        return prompt
    
    def _create_fallback_content(self, book_title, author_name):
        """Create fallback letter content if API fails."""
        return f"""
Dear Reader,

Thank you for picking up *{book_title}*. As you begin this journey through these pages, I wanted to take a moment to connect with you directly.

There's something special about the relationship between an author and a reader. While I may not know you personally, we're now connected through ideas, knowledge, and a shared curiosity about this subject. That connection is what inspired me to write this book in the first place.

I remember my own early struggles with learning this material. The concepts that seemed impenetrable, the skills that felt just out of reach, and the frustration that sometimes made me want to give up. If you're new to this field, you might experience some of those same challenges. Please know that's completely normal and part of the process.

This book is designed to guide you step by step, building your knowledge and confidence along the way. I've tried to write the book I wished I had when I was learning.

Throughout this book, I encourage you to be patient with yourself. Take your time with difficult concepts. Try the examples. Make mistakes and learn from them. That's how real mastery happens.

My greatest hope is that this book serves as a valuable companion on your learning journey, whether you're reading it cover to cover or referring to specific sections as needed.

I'd love to hear about your experience with the book and answer any questions you might have. You can reach me at [your preferred contact method].

Wishing you every success,

{author_name}
"""