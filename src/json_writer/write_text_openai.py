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
    def __init__(self, model_name: str = "gpt-4o-mini-2024-07-18", temperature: float = 0.7):
        """
        Initialize a minimal conversation generator that extracts short, 
        non-rewritten bullet points of key ideas. 
        """
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
        
        # Save initial JSON structure
        self._save_json()

    def clean_text(self, text: str) -> str:
        """Minimal text cleaning."""
        if not text:
            return ""
        text = str(text)
        text = text.replace('{', '').replace('}', '')
        text = text.replace('[', '').replace(']', '')
        text = text.replace('\\', '')
        text = text.replace('`', '')
        text = text.replace('|', '')
        text = re.sub(r'[^\w\s\.,;:!?"\'-]', ' ', text)
        text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
        text = ' '.join(text.split())
        return text.strip()

    def _save_json(self) -> bool:
        """Save the JSON data to a file."""
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

    def generate_prompt(self, text: str) -> str:
        """
        Prompt instructing the model to:
         - Identify key ideas.
         - Avoid restating or rewriting the text's phrases.
         - Exclude examples, definitions, or any unneeded details.
         - Provide only short bullet points describing each core idea.
        """
        return f"""You will see a passage of text. 
Your task is to list only the key ideas in concise bullet points.

IMPORTANT:
• Do not reuse or rephrase entire sentences from the text.
• Avoid examples, definitions, and explanations. 
• Omit any 'fluff' or descriptive language; just label the main ideas.

Text:
{text}

Please respond with only the bullet points of the essential ideas, 
using neutral, minimal wording (no rewriting or examples). 
"""

    def process_sections(self, data: List[Dict]) -> bool:
        """Process each section, extracting minimal bullet points."""
        try:
            total_sections = len(data)
            print(f"Found {total_sections} sections to process")
            
            for i, section in enumerate(data, 1):
                print(f"\nProcessing section {i}/{total_sections}")
                
                try:
                    # Convert string to dict if needed
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
                    raw_text = str(section.get('text', ''))

                    print(f"Chapter: {chapter_name}")
                    print(f"Section: {section_name}")

                    # Skip if no text
                    if not raw_text.strip():
                        print(f"Skipping section {i} - No text content")
                        continue

                    # Clean text
                    cleaned_text = self.clean_text(raw_text)
                    if not cleaned_text.strip():
                        print(f"Skipping section {i} - No content after cleaning")
                        continue

                    # Build the prompt
                    prompt = self.generate_prompt(cleaned_text)

                    # Create ChatPromptTemplate and run
                    chat_prompt = ChatPromptTemplate.from_template(prompt)
                    chain = chat_prompt | self.llm
                    response = chain.invoke({"text": cleaned_text}).content

                    # Save bullet points
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
    Extract minimal key bullet points from each chunk of text.
    Returns path to the output file if successful, otherwise None.
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # If data is not a list, try searching for a nested list
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

        generator = ConversationGenerator()
        if generator.process_sections(data):
            return generator.output_file
        return None

    except Exception as e:
        print(f"Error processing JSON file: {str(e)}")
        print("\nDebug info:")
        if 'data' in locals():
            print(f"Data type: {type(data)}")
            if isinstance(data, dict):
                print(f"Available keys: {list(data.keys())}")
        return None
