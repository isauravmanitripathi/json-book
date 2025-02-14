# src/json_writer/write_text_gemini.py
import os
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from datetime import datetime

# Load environment variables
load_dotenv()

class GeminiGenerator:
    def __init__(self, model_name: str = "gemini-1.5-flash-8b", temperature: float = 0.3):
        """Initialize the Gemini generator."""
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=temperature,
            convert_system_message_to_human=True
        )
        
        # Create output directory
        self.output_dir = "./generated_conversations"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create output file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = os.path.join(self.output_dir, f"article_gemini_{timestamp}.json")
        
        # Initialize the output data structure
        self.output_data = {
            "metadata": {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "model": model_name
            },
            "articles": []
        }
        
        # Save initial structure
        self._save_json()

    def clean_text(self, text: str) -> str:
        """Clean and format the text."""
        return ' '.join(text.split())

    def format_name(self, name: str) -> str:
        """Format chapter or section name by removing unnecessary prefixes."""
        name = str(name).strip()
        prefixes = ['Chapter:', 'Section:', 'CHAPTER', 'SECTION']
        for prefix in prefixes:
            if name.upper().startswith(prefix.upper()):
                name = name[len(prefix):].strip()
        return name

    def _save_json(self) -> bool:
        """Save the current state of output_data to JSON file."""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.output_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving JSON: {str(e)}")
            return False

    def get_previous_chunks(self, current_chapter: str, current_section: str) -> List[Dict]:
        """Get up to 5 previous chunks from the same chapter."""
        previous_chunks = []
        
        try:
            # Get all articles from the current chapter
            chapter_articles = [
                article for article in self.output_data["articles"]
                if article["chapter_name"] == current_chapter
            ]
            
            # Sort them by section number if available
            chapter_articles.sort(
                key=lambda x: float(x["section_number"]) 
                if x["section_number"].replace(".", "").isdigit() 
                else float('inf')
            )
            
            # Find current section's index
            current_index = next(
                (i for i, article in enumerate(chapter_articles) 
                 if article["section_name"] == current_section),
                -1
            )
            
            # If we found the current section and it's not the first one
            if current_index > 0:
                # Get up to 5 previous chunks
                start_index = max(0, current_index - 5)
                previous_chunks = chapter_articles[start_index:current_index]
                
        except Exception as e:
            print(f"Error getting previous chunks: {str(e)}")
            
        return previous_chunks

    def format_previous_chunks(self, chunks: List[Dict]) -> str:
        """Format previous chunks for inclusion in the prompt."""
        if not chunks:
            return ""
            
        formatted_chunks = "\nPrevious sections from this chapter:\n\n"
        for chunk in chunks:
            formatted_chunks += f"Section {chunk['section_number']}: {chunk['section_name']}\n"
            formatted_chunks += f"Key points:\n{chunk['text']}\n\n"
        
        return formatted_chunks

    def generate_prompt(self, text: str, chapter_name: str, section_name: str, section_number: str = "") -> str:
        """
        Generate the conversation prompt with explicit instructions to avoid repeating old content
        and focus on adding new insights.
        """
        chapter_name = self.format_name(chapter_name)
        section_name = self.format_name(section_name)

        # Get previous chunks only if this isn't the first section
        previous_chunks = []
        if section_number and section_number != "1" and section_number != "1.0":
            previous_chunks = self.get_previous_chunks(chapter_name, section_name)

        previous_context = self.format_previous_chunks(previous_chunks)

        return f"""You are an information organizers. You are taked with proper formatting of this text. Arrange it nicely, with bullet points and proper headings. Don't use headings such as introduction or conclusion. Don't delete or add any other information keep what is there. just format it properly.

Current Text to Analyze:
{self.clean_text(text)}
"""

    def save_article(self, article_data: Dict) -> bool:
        """Save a new article entry to the output JSON."""
        try:
            standardized_article = {
                "chapter_name": article_data.get("chapter_name", ""),
                "chapter_id": article_data.get("chapter_id", ""),
                "section_number": article_data.get("section_number", ""),
                "section_name": article_data.get("section_name", ""),
                "text": article_data.get("text", "")
            }
            
            self.output_data["articles"].append(standardized_article)
            return self._save_json()
        except Exception as e:
            print(f"Error saving article: {str(e)}")
            return False

    def process_sections(self, data: List[Dict]) -> bool:
        """Process all sections from the JSON data."""
        try:
            total_sections = len(data)
            print(f"Found {total_sections} sections to process")
            
            for i, section in enumerate(data, 1):
                print(f"\nProcessing section {i}/{total_sections}")
                
                try:
                    if isinstance(section, str):
                        try:
                            section = json.loads(section)
                        except json.JSONDecodeError:
                            section = {"text": section}
                    
                    # Extract fields
                    chapter_name = str(section.get('chapter_name', 'Chapter'))
                    chapter_id = str(section.get('chapter_id', ''))
                    section_name = str(section.get('section_name', 'Section'))
                    section_number = str(section.get('section_number', ''))
                    text = str(section.get('text', ''))

                    print(f"Chapter: {chapter_name}")
                    print(f"Section: {section_name}")
                    
                    if not text.strip():
                        print(f"Skipping section {i} - No text content")
                        continue
                    
                    # Generate article with context awareness
                    prompt = self.generate_prompt(
                        text=text,
                        chapter_name=chapter_name,
                        section_name=section_name,
                        section_number=section_number
                    )
                    
                    response = self.llm.invoke(prompt)
                    
                    # Save article
                    article_data = {
                        "chapter_name": chapter_name,
                        "chapter_id": chapter_id,
                        "section_number": section_number,
                        "section_name": section_name,
                        "text": response.content
                    }
                    
                    if not self.save_article(article_data):
                        print(f"Failed to save section {i}")
                        return False
                    
                    print(f"✓ Processed and saved section {i}/{total_sections}")
                    
                except Exception as e:
                    print(f"Error processing section {i}: {str(e)}")
                    print(f"Section content: {section}")
                    continue
            
            return True
            
        except Exception as e:
            print(f"Error in process_sections: {str(e)}")
            return False

def generate_conversations_gemini(json_path: str) -> Optional[str]:
    """Generate articles using Gemini."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            if isinstance(data, dict):
                for key in data:
                    if isinstance(data[key], list):
                        data = data[key]
                        break
                    elif isinstance(data[key], dict):
                        for subkey in data[key]:
                            if isinstance(data[key][subkey], list):
                                data = data[key][subkey]
                                break
        
        if not isinstance(data, list):
            raise ValueError("Could not find a valid list of sections in the JSON file")
            
        generator = GeminiGenerator()
        
        if generator.process_sections(data):
            return generator.output_file
        
        return None
        
    except Exception as e:
        print(f"Error processing JSON file: {str(e)}")
        print("\nDebug info:")
        print(f"JSON structure: {type(data)}")
        if isinstance(data, dict):
            print(f"Available keys: {list(data.keys())}")
        return None
