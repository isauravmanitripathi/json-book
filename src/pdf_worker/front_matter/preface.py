import logging
import json
from .api_client import AnthropicClient
from .content_extractor import ContentExtractor

class PrefaceGenerator:
    """Generates a preface based on book content."""
    
    def __init__(self, api_client=None):
        """
        Initialize the preface generator.
        
        Args:
            api_client (AnthropicClient, optional): API client for text generation
        """
        self.logger = logging.getLogger(__name__)
        self.api_client = api_client or AnthropicClient()
        
    def generate(self, book_title, author_name, json_file_path=None, book_summary=None):
        """
        Generate a preface for the book.
        
        Args:
            book_title (str): Title of the book
            author_name (str): Name of the author
            json_file_path (str, optional): Path to JSON file with book content
            book_summary (dict, optional): Book summary information
                
        Returns:
            str: Generated preface content in markdown format
        """
        try:
            self.logger.info("Generating preface content")
            
            # Extract book structure if JSON path provided
            sample_content = []
            if json_file_path and not book_summary:
                extractor = ContentExtractor(json_file_path)
                book_summary = extractor.get_book_summary()
                # Get comprehensive samples from throughout the book
                sample_content = extractor.get_sample_content(max_sections=10, sample_lines=2)
            elif json_file_path and book_summary:
                # We have summary but still need samples
                extractor = ContentExtractor(json_file_path)
                sample_content = extractor.get_sample_content(max_sections=10, sample_lines=2)
            
            # Create prompt
            prompt = self._create_prompt(book_title, author_name, book_summary, sample_content)
            
            # Generate content
            preface_content = self.api_client.generate_text(
                prompt=prompt, 
                max_tokens=1500,  # Increased for more comprehensive content
                temperature=0.7
            )
            
            self.logger.info("Successfully generated preface content")
            return preface_content
            
        except Exception as e:
            self.logger.error(f"Error generating preface: {str(e)}")
            # Provide a fallback if API generation fails
            return self._create_fallback_content(book_title, author_name)
    
    def _create_prompt(self, book_title, author_name, book_summary, sample_content):
        """Create enhanced prompt for preface generation."""
        # Format chapter information for the prompt
        chapter_info = ""
        if book_summary and 'chapter_structure' in book_summary:
            chapters = []
            for chapter_id, chapter in book_summary['chapter_structure'].items():
                chapter_desc = f"- {chapter['name']}"
                if chapter['sections'] and len(chapter['sections']) > 0:
                    section_samples = [s['name'] for s in chapter['sections'][:3]]
                    if section_samples:
                        chapter_desc += f" (includes sections on: {', '.join(section_samples)}"
                        if len(chapter['sections']) > 3:
                            chapter_desc += " and more"
                        chapter_desc += ")"
                chapters.append(chapter_desc)
            
            if chapters:
                chapter_info = "The book contains the following chapters:\n" + "\n".join(chapters)
        
        # Include sample content snippets if available
        content_samples = ""
        if sample_content:
            content_samples = "\nHere are brief excerpts from various sections of the book:\n\n"
            for i, sample in enumerate(sample_content, 1):
                content_samples += f"Sample {i} (from {sample.get('chapter', 'Chapter')}, {sample.get('section', 'Section')}):\n"
                content_samples += f"\"{sample.get('text', '')}...\"\n\n"
        
        prompt = f"""Write a professional preface for a book with the following information:

Title: {book_title}
Author: {author_name}
{chapter_info}
{content_samples}

The preface should:
1. Be approximately 600-800 words
2. Explain the purpose and value of the book
3. Outline what readers will learn
4. Provide context for why this book was written
5. Use a professional but engaging tone
6. Be formatted in MARKDOWN with appropriate paragraphs, headings, etc.

The preface should represent the author's voice, discussing their motivation for writing the book, the intended audience, the approach taken, and any acknowledgments to people or resources that contributed to the creation of the book.

Make sure the output is properly formatted in Markdown to render correctly in the PDF. 
Use ## for subheadings, * for emphasis, and proper paragraph breaks.

DO NOT include the title "Preface" at the top - that will be added separately.
"""
        return prompt
    
    def _create_fallback_content(self, book_title, author_name):
        """Create fallback preface content if API fails."""
        return f"""
## About This Book

*{book_title}* represents countless hours of work and a passion for sharing knowledge. My goal in writing this book was to create a comprehensive resource that would serve both beginners and those with more experience in the field.

Throughout these pages, you'll find practical information, theoretical foundations, and real-world applications that will help you understand the subject matter deeply and apply it effectively.

## Approach and Structure

I've structured the content to build progressively, starting with fundamental concepts and moving toward more advanced topics. Each chapter is designed to be both self-contained and part of a larger narrative, allowing you to either read from beginning to end or focus on specific sections of interest.

## Who This Book Is For

Whether you're a student, a professional, or simply someone with curiosity about the subject, I hope this book serves as a valuable companion on your learning journey.

## Acknowledgments

I'd like to express my gratitude to everyone who supported me during the writing process. Your encouragement, feedback, and patience made this book possible.

*{author_name}*
"""