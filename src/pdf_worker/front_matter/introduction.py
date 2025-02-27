import logging
from .api_client import AnthropicClient
from .content_extractor import ContentExtractor

class IntroductionGenerator:
    """Generates a book introduction based on book content."""
    
    def __init__(self, api_client=None):
        """
        Initialize the introduction generator.
        
        Args:
            api_client (AnthropicClient, optional): API client for text generation
        """
        self.logger = logging.getLogger(__name__)
        self.api_client = api_client or AnthropicClient()
        
    def generate(self, book_title, author_name, json_file_path=None, book_summary=None):
        """
        Generate an introduction for the book.
        
        Args:
            book_title (str): Title of the book
            author_name (str): Name of the author
            json_file_path (str, optional): Path to JSON file with book content
            book_summary (dict, optional): Book summary information
                
        Returns:
            str: Generated introduction content in markdown format
        """
        try:
            self.logger.info("Generating introduction content")
            
            # Extract book structure if JSON path provided
            if json_file_path and not book_summary:
                extractor = ContentExtractor(json_file_path)
                book_summary = extractor.get_book_summary()
                # Get a couple of sample sections to help inform the introduction
                sample_content = extractor.get_sample_content(max_sections=5, sample_lines=2)
                
                # Add sample content to the book summary
                if not book_summary:
                    book_summary = {}
                book_summary['sample_content'] = sample_content
            elif json_file_path and book_summary:
                # We have summary but still need samples
                extractor = ContentExtractor(json_file_path)
                sample_content = extractor.get_sample_content(max_sections=5, sample_lines=2)
                book_summary['sample_content'] = sample_content
            
            # Create prompt
            prompt = self._create_prompt(book_title, author_name, book_summary)
            
            # Generate content
            introduction_content = self.api_client.generate_text(
                prompt=prompt, 
                max_tokens=1800,  # Increased for more comprehensive content
                temperature=0.65
            )
            
            self.logger.info("Successfully generated introduction content")
            return introduction_content
            
        except Exception as e:
            self.logger.error(f"Error generating introduction: {str(e)}")
            # Provide a fallback if API generation fails
            return self._create_fallback_content(book_title, book_summary)
    
    def _create_prompt(self, book_title, author_name, book_summary):
        """Create enhanced prompt for introduction generation."""
        # Format chapter information for the prompt
        chapter_info = ""
        if book_summary and 'chapter_structure' in book_summary:
            chapters = []
            for chapter_id, chapter in book_summary['chapter_structure'].items():
                chapter_desc = f"- {chapter['name']}"
                if chapter['sections'] and len(chapter['sections']) > 0:
                    section_samples = [s['name'] for s in chapter['sections'][:3]]
                    if section_samples:
                        chapter_desc += f" (covers: {', '.join(section_samples)}"
                        if len(chapter['sections']) > 3:
                            chapter_desc += " and more"
                        chapter_desc += ")"
                chapters.append(chapter_desc)
            
            if chapters:
                chapter_info = "The book contains the following chapters:\n" + "\n".join(chapters)
        
        # Determine book type and audience
        book_type = "technical"
        audience = "professionals and enthusiasts"
        if book_summary:
            if book_summary.get('has_code', False):
                book_type = "programming/technical"
                audience = "developers and technical professionals"
        
        # Include samples if available
        content_samples = ""
        if book_summary and 'sample_content' in book_summary:
            samples = book_summary['sample_content']
            if samples:
                content_samples = "\nHere are brief excerpts from various sections of the book:\n\n"
                for i, sample in enumerate(samples, 1):
                    content_samples += f"Sample {i} (from {sample.get('chapter', 'Chapter')}, {sample.get('section', 'Section')}):\n"
                    content_samples += f"\"{sample.get('text', '')}...\"\n\n"
        
        prompt = f"""Write a comprehensive introduction for a {book_type} book titled "{book_title}" by {author_name}.

Additional book information:
{chapter_info}
{content_samples}

The introduction should:
1. Be approximately 800-1000 words
2. Begin with a strong hook that captures the reader's interest
3. Clearly explain what the book is about and its scope
4. Identify the target audience ({audience})
5. Explain how the book is organized and structured
6. Provide guidance on how to use the book effectively
7. Highlight what makes this book unique or valuable
8. Set appropriate expectations for what readers will gain
9. Include subheadings to organize content clearly
10. Be formatted in MARKDOWN

The tone should be authoritative, clear, and engaging. The introduction should serve as a roadmap to the entire book and help readers understand why this book is worth their time.

Make sure the output is properly formatted in Markdown to render correctly in the PDF.
Use ## for subheadings, * for emphasis, and proper paragraph breaks.

DO NOT include the title "Introduction" at the top - that will be added separately.
DO use appropriate subheadings (## format in markdown) to organize the introduction.
"""
        return prompt
    
    def _create_fallback_content(self, book_title, book_summary):
        """Create fallback introduction content if API fails."""
        # Get chapter count
        num_chapters = 12
        if book_summary and 'num_chapters' in book_summary:
            num_chapters = book_summary.get('num_chapters', 12)
            
        return f"""
## About This Book

*{book_title}* is designed to provide you with a comprehensive understanding of the subject matter through a carefully structured approach. Whether you're a beginner looking to build foundational knowledge or an experienced practitioner seeking to refine your skills, this book offers valuable insights and practical guidance.

## What You'll Learn

Throughout this book, you'll explore key concepts, methodologies, and applications that are essential for mastering the subject. The content progresses logically from fundamental principles to more advanced topics, ensuring a smooth learning curve.

The book contains {num_chapters} chapters, each focusing on specific aspects of the subject matter. By the end of this book, you'll have developed a robust understanding of the field and acquired practical skills that you can apply in real-world scenarios.

## How to Use This Book

You can approach this book in several ways:

* **Sequential reading:** For beginners, reading from beginning to end provides a structured learning path that builds knowledge progressively.

* **Reference guide:** Experienced readers may prefer to focus on specific chapters or sections relevant to their current needs.

* **Practical application:** Throughout the book, you'll find examples, case studies, and exercises that help reinforce concepts through practical application.

## Who This Book Is For

This book is ideal for:

* Students seeking comprehensive learning materials
* Professionals looking to expand their knowledge or skills
* Enthusiasts interested in developing deeper understanding
* Anyone seeking a reliable reference on the subject matter

Whether you're reading this book for academic purposes, professional development, or personal interest, you'll find valuable content tailored to your needs.

## What Makes This Book Different

This book combines theoretical knowledge with practical application, ensuring you not only understand concepts but can also apply them effectively. The content is presented in a clear, accessible manner without sacrificing depth or rigor.

I've drawn from extensive experience and research to provide you with current, relevant information that reflects both established principles and emerging trends in the field.

## Let's Begin

As you embark on this learning journey, remember that mastery comes through consistent engagement with the material. Take time to absorb the concepts, work through the examples, and apply what you learn to your own projects or scenarios.

Now, let's dive into the fascinating world of *{book_title}*.
"""