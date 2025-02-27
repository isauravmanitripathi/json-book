import logging
import os
from dotenv import load_dotenv
from .front_matter import (
    AnthropicClient,
    ContentExtractor,
    CopyrightPageGenerator,
    EpigraphGenerator,
    PrefaceGenerator,
    LetterToReaderGenerator,
    IntroductionGenerator,
    CopyrightComponent,
    CenteredTextComponent,
    StandardTextComponent
)

class FrontMatterManager:
    """Manages the generation and rendering of front matter for books."""
    
    def __init__(self, style_config, api_key=None):
        """
        Initialize the front matter manager.
        
        Args:
            style_config (dict): Style configuration
            api_key (str, optional): Anthropic API key. If not provided, will look for ANTHROPIC_API_KEY in env.
        """
        load_dotenv()  # Load .env file if it exists
        self.logger = logging.getLogger(__name__)
        self.style_config = style_config
        
        # Set up API client
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.api_client = AnthropicClient(api_key=self.api_key) if self.api_key else None
        
        # Set up generators
        self.copyright_generator = CopyrightPageGenerator(api_client=self.api_client)
        self.epigraph_generator = EpigraphGenerator(api_client=self.api_client)
        self.preface_generator = PrefaceGenerator(api_client=self.api_client)
        self.letter_generator = LetterToReaderGenerator(api_client=self.api_client)
        self.intro_generator = IntroductionGenerator(api_client=self.api_client)
        
    def add_front_matter(self, story, book_info, json_file_path=None):
        """
        Generate and add front matter components to the document story.
        
        Args:
            story (list): ReportLab story to add components to
            book_info (dict): Book information including:
                - title: Book title
                - author: Author name
                - front_matter (dict): Components to include and their info
            json_file_path (str): Path to JSON file with book content
                
        Returns:
            bool: Success status
        """
        try:
            self.logger.info("Adding front matter components")
            
            # Extract book content structure for context
            book_summary = None
            if json_file_path:
                try:
                    extractor = ContentExtractor(json_file_path)
                    book_summary = extractor.get_book_summary()
                except Exception as e:
                    self.logger.warning(f"Could not extract book summary: {str(e)}")
            
            # Get front matter options
            front_matter_options = book_info.get('front_matter', {})
            
            # Process each front matter component if requested
            if front_matter_options.get('copyright', False):
                self._add_copyright_page(story, book_info)
                
            if front_matter_options.get('epigraph', False):
                self._add_epigraph(story, book_info, json_file_path, book_summary)
                
            if front_matter_options.get('preface', False):
                self._add_preface(story, book_info, json_file_path, book_summary)
                
            if front_matter_options.get('letter_to_reader', False):
                self._add_letter_to_reader(story, book_info, json_file_path, book_summary)
                
            if front_matter_options.get('introduction', False):
                self._add_introduction(story, book_info, json_file_path, book_summary)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding front matter: {str(e)}")
            return False
            
    def _add_copyright_page(self, story, book_info):
        """Add copyright page to story."""
        try:
            self.logger.info("Generating copyright page")
            
            # Generate copyright content
            copyright_content = self.copyright_generator.generate(book_info)
            
            # Create component
            component = CopyrightComponent(self.style_config, copyright_content)
            
            # Add to story
            component.add_to_story(story)
            self.logger.info("Added copyright page")
            
        except Exception as e:
            self.logger.error(f"Error adding copyright page: {str(e)}")
            
    def _add_epigraph(self, story, book_info, json_file_path, book_summary):
        """Add epigraph to story."""
        try:
            self.logger.info("Generating epigraph")
            
            # Generate epigraph content
            epigraph_content = self.epigraph_generator.generate(
                book_info.get('title', ''),
                book_info.get('author', ''),
                json_file_path,
                book_summary
            )
            
            # Create component
            component = CenteredTextComponent(self.style_config, epigraph_content)
            
            # Add to story
            component.add_to_story(story)
            self.logger.info("Added epigraph")
            
        except Exception as e:
            self.logger.error(f"Error adding epigraph: {str(e)}")
            
    def _add_preface(self, story, book_info, json_file_path, book_summary):
        """Add preface to story."""
        try:
            self.logger.info("Generating preface")
            
            # Generate preface content
            preface_content = self.preface_generator.generate(
                book_info.get('title', ''),
                book_info.get('author', ''),
                json_file_path,
                book_summary
            )
            
            # Create component
            component = StandardTextComponent(self.style_config, "Preface", preface_content)
            
            # Add to story
            component.add_to_story(story)
            self.logger.info("Added preface")
            
        except Exception as e:
            self.logger.error(f"Error adding preface: {str(e)}")
            
    def _add_letter_to_reader(self, story, book_info, json_file_path, book_summary):
        """Add letter to reader to story."""
        try:
            self.logger.info("Generating letter to reader")
            
            # Generate letter content
            letter_content = self.letter_generator.generate(
                book_info.get('title', ''),
                book_info.get('author', ''),
                json_file_path,
                book_summary
            )
            
            # Create component
            component = StandardTextComponent(self.style_config, "To the Reader", letter_content)
            
            # Add to story
            component.add_to_story(story)
            self.logger.info("Added letter to reader")
            
        except Exception as e:
            self.logger.error(f"Error adding letter to reader: {str(e)}")
            
    def _add_introduction(self, story, book_info, json_file_path, book_summary):
        """Add introduction to story."""
        try:
            self.logger.info("Generating introduction")
            
            # Generate introduction content
            intro_content = self.intro_generator.generate(
                book_info.get('title', ''),
                book_info.get('author', ''),
                json_file_path,
                book_summary
            )
            
            # Create component
            component = StandardTextComponent(self.style_config, "Introduction", intro_content)
            
            # Add to story
            component.add_to_story(story)
            self.logger.info("Added introduction")
            
        except Exception as e:
            self.logger.error(f"Error adding introduction: {str(e)}")