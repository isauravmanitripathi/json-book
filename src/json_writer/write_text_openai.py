# src/json_writer/write_text_openai.py
import os
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from datetime import datetime
import re

# Load environment variables
load_dotenv()

class ConversationGenerator:
    def __init__(self, model_name: str = "gpt-4o-mini-2024-07-18", temperature: float = 1.0):
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
        """Clean and format the text by removing special characters and formatting."""
        try:
            if not text:
                return ""
            
            # Convert to string and replace problematic characters
            text = str(text)
            text = text.replace('{', '').replace('}', '')
            text = text.replace('[', '').replace(']', '')
            text = text.replace('\\', '')
            text = text.replace('`', '')
            text = text.replace('|', '')
            
            # Remove other special characters
            text = re.sub(r'[^\w\s\.,;:!?"\'-]', ' ', text)
            
            # Remove control characters
            text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
            
            # Normalize whitespace
            text = ' '.join(text.split())
            
            return text.strip()
        except Exception as e:
            print(f"Error cleaning text: {str(e)}")
            return str(text)

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

    def get_previous_chunks(self, current_chapter: str, current_section: str) -> List[Dict]:
        """
        Get up to 5 previous chunks from the same chapter, 
        to avoid repeating already covered info.
        """
        previous_chunks = []
        try:
            # Filter articles from the same chapter
            chapter_articles = [
                article for article in self.output_data["articles"]
                if article["chapter_name"] == current_chapter
            ]
            
            # Sort them by section number if it's numeric
            chapter_articles.sort(
                key=lambda x: float(x["section_number"]) 
                if x["section_number"].replace(".", "").isdigit() 
                else float('inf')
            )
            
            # Find the current section's index
            current_index = next(
                (i for i, article in enumerate(chapter_articles) 
                 if article["section_name"] == current_section),
                -1
            )
            
            # If found and it's not the first one
            if current_index > 0:
                start_index = max(0, current_index - 5)
                previous_chunks = chapter_articles[start_index:current_index]
                
        except Exception as e:
            print(f"Error getting previous chunks: {str(e)}")
            
        return previous_chunks

    def format_previous_chunks(self, chunks: List[Dict]) -> str:
        """
        Format previous chunks for inclusion in the prompt.
        Each chunk is summarized as "Section X: <Name> / Key points: <Text>"
        """
        if not chunks:
            return ""
            
        formatted_chunks = "\nPrevious sections from this chapter:\n\n"
        for chunk in chunks:
            formatted_chunks += f"Section {chunk['section_number']}: {chunk['section_name']}\n"
            formatted_chunks += f"Key points:\n{chunk['text']}\n\n"
        
        return formatted_chunks

    def generate_prompt(self, text: str, chapter_name: str, section_name: str,
                        section_number: str = "") -> str:
        """
        Generate a conversation prompt that instructs the model:
        1. To understand the text and extract the core ideas.
        2. NOT to copy or rewrite the original text's exact wording or examples.
        3. To produce a completely new piece of writing on the same ideas.
        """
        # Clean and format names
        chapter_name = self.clean_text(self.format_name(chapter_name))
        section_name = self.clean_text(self.format_name(section_name))
        
        # Retrieve previous context if not the very first section
        previous_chunks = []
        if section_number and section_number not in ["", "1", "1.0"]:
            previous_chunks = self.get_previous_chunks(chapter_name, section_name)
        previous_context = self.format_previous_chunks(previous_chunks)
        
        # Clean the current text
        cleaned_text = self.clean_text(text)
        
        return f"""You will receive a passage of text. Your task is:
1. Read and understand the main ideas or concepts in it.
2. Summarize or note these core points *internally* (scratchpad).
3. Then, write a brand-new paragraph (or paragraphs) that:
   - Conveys the underlying ideas in your own words.
   - Does NOT copy or simply rephrase any sentences or examples from the original text.
   - If the original text uses a specific example, either skip it or create a fresh example of your own.
   - Focus on generating new content that captures the concept but does not reuse wording.

Instructions:
- Avoid direct or partial quotations from the given text.
- Do not replicate the structure or examples; provide your own unique approach or explanation.
- Incorporate ideas from previous sections only if needed for continuity, but do not repeat them verbatim.

Chapter: {chapter_name}
Section: {section_name}
Section Number: {section_number}{previous_context}

Current Text to Analyze:
{cleaned_text}

[System/Instruction to the AI Model]:
Follow these steps meticulously. 
In your final answer, present only the new piece of writing. 
Do not show intermediate notes or mention the scratchpad. 
Ensure it is an original creation inspired by the text, not a rewrite."""

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
                    
                    # Clean the text before processing
                    cleaned_text = self.clean_text(text)
                    
                    if not cleaned_text.strip():
                        print(f"Skipping section {i} - No content after cleaning")
                        continue
                    
                    # Generate prompt with context awareness
                    prompt = self.generate_prompt(
                        text=cleaned_text,
                        chapter_name=chapter_name,
                        section_name=section_name,
                        section_number=section_number
                    )
                    
                    # Build prompt chain
                    chat_prompt = ChatPromptTemplate.from_template(prompt)
                    chain = chat_prompt | self.llm
                    
                    # Run LLM with the prompt
                    response = chain.invoke({"text": cleaned_text}).content
                    
                    # Save the newly generated passage
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
