# src/json_writer/write_text_openai.py
import os
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from datetime import datetime

# Load environment variables
load_dotenv()

class ConversationGenerator:
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 1.0):
        """Initialize the conversation generator."""
        self.llm = ChatOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            model=model_name,
            temperature=temperature
        )
        
        # Create output directory
        self.output_dir = "./generated_conversations"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create output file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = os.path.join(self.output_dir, f"article_{timestamp}.json")
        
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
        # Remove multiple newlines and extra spaces
        text = ' '.join(text.split())
        return text

    def format_name(self, name: str) -> str:
        """Format chapter or section name by removing unnecessary prefixes."""
        name = str(name).strip()
        # Remove common prefixes
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

    def save_article(self, article_data: Dict) -> bool:
        """Save a new article entry to the output JSON."""
        try:
            # Standardize the article structure
            standardized_article = {
                "chapter_name": article_data.get("chapter_name", ""),
                "chapter_id": article_data.get("chapter_id", ""),
                "section_number": article_data.get("section_number", ""),
                "section_name": article_data.get("section_name", ""),
                "text": article_data.get("text", "")
            }
            
            # Add to articles list
            self.output_data["articles"].append(standardized_article)
            
            # Save the updated JSON
            return self._save_json()
        except Exception as e:
            print(f"Error saving article: {str(e)}")
            return False

    def generate_prompt(self, text: str, chapter_name: str, section_name: str) -> str:
        """Generate the conversation prompt."""
        # Clean and format names
        chapter_name = self.format_name(chapter_name)
        section_name = self.format_name(section_name)
        
        return f"""<instruction>
    Transform this text into a well-written article passage.

    <context>
    Chapter: {chapter_name}
    Section: {section_name}

    Input Text:
    {self.clean_text(text)}
    </context>

    <scratchpad>
    First, identify the main points being discussed in simple, clear statements:
    - What are the key concepts?
    - What are the main relationships or processes described?
    - What are the important components mentioned?

    List these as simple bullet points.
    </scratchpad>

    <discussion>
    Using the points from the scratchpad:
    - How should these points flow together?
    - What is the most logical order?
    - How do these points connect to each other?
    </discussion>

    <writing_guidelines>
    1. Write directly and clearly
    2. Connect the points naturally
    3. Maintain academic tone
    4. Avoid meta-references or phrases like "in this context"
    5. Focus on clear explanation of concepts
    </writing_guidelines>

    <output_format>
    Write a single, clear paragraph that explains these concepts in a natural, flowing way. Use the points from the scratchpad as your foundation.
    </output_format>
    </instruction>"""

    def process_sections(self, data: List[Dict]) -> bool:
        """Process all sections from the JSON data."""
        try:
            total_sections = len(data)
            print(f"Found {total_sections} sections to process")
            
            for i, section in enumerate(data, 1):
                print(f"\nProcessing section {i}/{total_sections}")
                
                try:
                    # Handle both string and dict inputs
                    if isinstance(section, str):
                        try:
                            section = json.loads(section)
                        except json.JSONDecodeError:
                            section = {"text": section}
                    
                    # Extract all possible fields with defaults
                    chapter_name = str(section.get('chapter_name', 'Chapter'))
                    chapter_id = str(section.get('chapter_id', ''))
                    section_name = str(section.get('section_name', 'Section'))
                    section_number = str(section.get('section_number', ''))
                    text = str(section.get('text', ''))

                    print(f"Chapter: {chapter_name}")
                    print(f"Section: {section_name}")
                    
                    # Skip if no text content
                    if not text.strip():
                        print(f"Skipping section {i} - No text content")
                        continue
                    
                    # Generate article
                    prompt = self.generate_prompt(
                        text=text,
                        chapter_name=chapter_name,
                        section_name=section_name
                    )
                    
                    chat_prompt = ChatPromptTemplate.from_template(prompt)
                    chain = chat_prompt | self.llm
                    response = chain.invoke({"text": text}).content
                    
                    # Save article in JSON format
                    article_data = {
                        "chapter_name": chapter_name,
                        "chapter_id": chapter_id,
                        "section_number": section_number,
                        "section_name": section_name,
                        "text": response
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

def generate_conversations(json_path: str) -> Optional[str]:
    """
    Generate conversations from the provided JSON file.
    Returns the path to the output file if successful, None otherwise.
    """
    try:
        # Read JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if data is a list
        if not isinstance(data, list):
            # If it's not a list, try to find the relevant data
            if isinstance(data, dict):
                # Handle nested structure if present
                for key in data:
                    if isinstance(data[key], list):
                        data = data[key]
                        break
                    elif isinstance(data[key], dict):
                        # Look for nested lists
                        for subkey in data[key]:
                            if isinstance(data[key][subkey], list):
                                data = data[key][subkey]
                                break
        
        # Ensure data is a list
        if not isinstance(data, list):
            raise ValueError("Could not find a valid list of sections in the JSON file")
            
        # Initialize generator
        generator = ConversationGenerator()
        
        # Process all sections
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