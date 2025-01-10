import os
import json
from typing import List, Dict
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
        
        # Create output file immediately with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = os.path.join(self.output_dir, f"conversation_{timestamp}.txt")
        
        # Initialize the file with a header
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(f"Conversation Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*50 + "\n\n")

    def generate_prompt(self, text: str, chapter_name: str, section_name: str) -> str:
        """Generate the conversation prompt."""
        return f"""Create an engaging podcast conversation between host (Akash) and guest (Bharti) about the following content.
        
Current Chapter: {chapter_name}
Current Section: {section_name}

Content to discuss:
{text}

Understand the conversation and then rewrite it, like a paragraph, keep the important stuff and add things on your own. """

    def save_conversation(self, conversation: str, chapter_name: str, section_name: str):
        """Save the generated conversation immediately to the output file."""
        try:
            with open(self.output_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Chapter: {chapter_name}\n")
                f.write(f"Section: {section_name}\n")
                f.write(f"{'='*50}\n\n")
                f.write(conversation)
                f.write("\n\n")
                # Flush the buffer to ensure immediate writing
                f.flush()
                os.fsync(f.fileno())
            return True
        except Exception as e:
            print(f"Error saving conversation: {str(e)}")
            return False

    def process_json_file(self, json_path: str):
        """Process the JSON file and generate conversations."""
        print(f"Loading JSON file: {json_path}")
        
        try:
            # Read JSON file
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            total_sections = len(data)
            print(f"Found {total_sections} sections to process")
            
            # Process each section
            for i, section in enumerate(data, 1):
                print(f"\nProcessing section {i}/{total_sections}")
                print(f"Chapter: {section['chapter_name']}")
                print(f"Section: {section['section_name']}")
                
                try:
                    # Create prompt
                    prompt = self.generate_prompt(
                        text=section['text'],
                        chapter_name=section['chapter_name'],
                        section_name=section['section_name']
                    )
                    
                    # Generate conversation
                    chat_prompt = ChatPromptTemplate.from_template(prompt)
                    chain = chat_prompt | self.llm
                    response = chain.invoke({"text": section['text']}).content
                    
                    # Save conversation immediately
                    if self.save_conversation(
                        conversation=response,
                        chapter_name=section['chapter_name'],
                        section_name=section['section_name']
                    ):
                        print(f"✓ Processed and saved section {i}")
                    else:
                        print(f"× Failed to save section {i}")
                    
                except Exception as e:
                    print(f"Error processing section {i}: {str(e)}")
                    continue
            
            print(f"\nAll conversations have been saved to: {self.output_file}")
            
        except Exception as e:
            print(f"Error processing JSON file: {str(e)}")

def main():
    # Check for JSON file argument
    import sys
    if len(sys.argv) != 2:
        print("Usage: python script.py input.json")
        sys.exit(1)
        
    json_path = sys.argv[1]
    if not os.path.exists(json_path):
        print(f"Error: File not found: {json_path}")
        sys.exit(1)
        
    # Initialize and run generator
    generator = ConversationGenerator()
    generator.process_json_file(json_path)

if __name__ == "__main__":
    main()