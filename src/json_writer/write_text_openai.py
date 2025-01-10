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
        self.output_file = os.path.join(self.output_dir, f"conversation_{timestamp}.txt")
        
        # Initialize the file with a header
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(f"Article Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*50 + "\n\n")

    def generate_prompt(self, text: str, chapter_name: str, section_name: str) -> str:
        """Generate the conversation prompt."""
        return f"""<instruction>
    Transform this conversation-style text into a well-structured article paragraph.
    
    <context>
    Chapter Context: {chapter_name}
    - This chapter focuses on {chapter_name.split(':')[0]} and sets the context for understanding the broader topic.
    
    Section Focus: {section_name}
    - This section specifically deals with {section_name.replace('Section:', '').strip()} within the chapter's context.
    </context>
    
    Input Text to Transform:
    {text}
    
    <guidelines>
    1. Context Integration:
        - Begin by understanding how this section fits within the chapter's broader theme
        - Ensure the content aligns with both the chapter and section objectives
        - Maintain the hierarchical relationship between chapter and section topics
    
    2. Content Analysis:
        - Identify the main topic and key points being discussed
        - Extract important facts, examples, and explanations
        - Preserve all substantive information from the dialogue
        - Focus on the relationship between ideas and the chapter/section context
        
    3. Article Writing:
        - Write in a formal, academic style appropriate for the chapter's theme
        - Present ideas in a logical sequence that follows the chapter's flow
        - Connect related points and create smooth transitions
        - Expand on important concepts where appropriate
        - Remove conversational elements (um, well, etc.)
        - Eliminate speaker attributions and dialogue format
        
    4. Structure:
        - Begin with a topic sentence that connects to both chapter and section themes
        - Develop ideas in a coherent paragraph format
        - Use proper transitions between related points
        - Maintain professional tone throughout
        - End with a conclusion that ties back to the section's main focus
        
    5. Enhancement:
        - Add relevant context where needed
        - Clarify any ambiguous points
        - Strengthen connections between ideas
        - Ensure technical accuracy
        - Keep focus on the section's role within the chapter
    </guidelines>

    <output_format>
    Write the response as a single, well-structured paragraph that reads like a section from a professional article or textbook. 
    The content should clearly belong in this chapter and section, maintaining proper context and flow.
    Do not include any dialogue markers, speaker names, or conversational elements.
    </output_format>
    </instruction>"""

    def save_conversation(self, conversation: str, chapter_name: str, section_name: str) -> bool:
        """Save the generated conversation to the output file."""
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

    def process_sections(self, data: List[Dict]) -> bool:
        """Process all sections from the JSON data."""
        total_sections = len(data)
        print(f"Found {total_sections} sections to process")
        
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
                if not self.save_conversation(
                    conversation=response,
                    chapter_name=section['chapter_name'],
                    section_name=section['section_name']
                ):
                    print(f"Failed to save section {i}")
                    return False
                
                print(f"✓ Processed and saved section {i}/{total_sections}")
                
            except Exception as e:
                print(f"Error processing section {i}: {str(e)}")
                return False
        
        return True

def generate_conversations(json_path: str) -> Optional[str]:
    """
    Generate conversations from the provided JSON file.
    Returns the path to the output file if successful, None otherwise.
    """
    try:
        # Read JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Initialize generator
        generator = ConversationGenerator()
        
        # Process all sections
        if generator.process_sections(data):
            return generator.output_file
        
        return None
        
    except Exception as e:
        print(f"Error processing JSON file: {str(e)}")
        return None