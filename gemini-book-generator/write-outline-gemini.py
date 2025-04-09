"""
Run using:
python your_script_name.py --input_file path/to/your/input.json --output_dir results/Outlines

Ensure a .env file exists in the same directory with:
GOOGLE_API_KEY=YOUR_ACTUAL_API_KEY
"""

import json
import os
import google.generativeai as genai
import argparse
import time
import random
import gc
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import sys
import traceback
import re

# Rich library for enhanced terminal display
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
    rich_available = True
except ImportError:
    rich_available = False
    # Simple console replacement if rich is not available
    class SimpleConsole:
        def print(self, message, **kwargs):
            message = re.sub(r'\[.*?\]', '', message) # Remove rich formatting
            print(message)

        def status(self, message):
            class DummyContext:
                def __enter__(self):
                    print(message)
                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass
            return DummyContext()

# Configure console for rich output or fallback
console = Console() if rich_available else SimpleConsole()

# --- File Handling ---

def load_json_file(file_path: str) -> Dict:
    """Load and parse JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file: # Specify encoding
            return json.load(file)
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Error loading JSON file: Invalid JSON format.[/bold red]")
        console.print(f"File: {file_path}")
        console.print(f"Error: {e}")
        # Provide more context if possible
        try:
            with open(file_path, 'r', encoding='utf-8') as file_check:
                content = file_check.read()
                line, col = e.lineno, e.colno
                lines = content.splitlines()
                if 0 < line <= len(lines):
                    console.print(f"Problem near line {line}, column {col}:")
                    console.print(lines[line-1])
                    console.print(" " * (col - 1) + "^")
        except Exception as read_err:
             console.print(f"Could not read file to show error location: {read_err}")
        sys.exit(1)
    except FileNotFoundError:
        console.print(f"[bold red]Error: Input file not found at {file_path}[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error loading JSON file: {e}[/bold red]")
        console.print(traceback.format_exc())
        sys.exit(1)

def save_json_file(data: Dict, file_path: str):
    """Save data to a JSON file"""
    try:
        # Ensure the directory exists before saving
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as file: # Specify encoding
            json.dump(data, file, indent=2, ensure_ascii=False) # ensure_ascii=False for broader char support
    except Exception as e:
        console.print(f"[bold red]Error saving JSON file: {e}[/bold red]")
        console.print(f"Path: {file_path}")
        console.print(traceback.format_exc())

# --- JSON Fixing ---

def fix_json_string(json_str: str) -> str:
    """Attempt to fix common issues with malformed JSON responses"""
    if not json_str or not json_str.strip():
        return '{}' # Return empty object if string is empty

    # Remove markdown code block markers (```json ... ``` or ``` ... ```)
    json_str = re.sub(r'^```json\s*', '', json_str.strip())
    json_str = re.sub(r'\s*```$', '', json_str)
    json_str = re.sub(r'^```\s*', '', json_str.strip()) # Handle plain ``` blocks too
    json_str = json_str.strip() # Re-strip after potential removals

    # Basic check if it looks like JSON (starts with { ends with })
    if not (json_str.startswith('{') and json_str.endswith('}')):
       # Attempt to find the first '{' and last '}'
       start_brace = json_str.find('{')
       end_brace = json_str.rfind('}')
       if start_brace != -1 and end_brace != -1 and start_brace < end_brace:
           json_str = json_str[start_brace:end_brace+1]
       else:
           # If we can't find valid braces, it's unlikely to be fixable JSON
           console.print("[yellow]Warning: Response doesn't seem to start/end with braces after cleaning. Returning raw cleaned string.[/yellow]")
           return json_str # Return the cleaned string, parsing will likely fail later but gives a chance

    # Remove trailing commas (before } or ])
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)

    # Attempt to balance braces (simple heuristic, might not always work)
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
    elif close_braces > open_braces:
        # Removing closing braces is riskier, maybe just warn
        console.print(f"[yellow]Warning: More closing braces ({close_braces}) than opening ({open_braces}). Proceeding with caution.[/yellow]")


    return json_str

# --- Logging ---

def check_log_file(input_file_name: str, output_dir: Path) -> tuple:
    """Check if a log file exists for the given input file"""
    log_file_name = f"{Path(input_file_name).stem}_log.json"
    log_file_path = output_dir / log_file_name

    if log_file_path.exists():
        console.print(f"Found existing log file: {log_file_path}")
        try:
            log_data = load_json_file(str(log_file_path))
            # Basic validation of log structure
            if isinstance(log_data.get("processed_items"), list) and isinstance(log_data.get("errors"), list):
                 console.print(f"Log file loaded successfully. {len(log_data['processed_items'])} items previously processed.")
                 return str(log_file_path), log_data, False
            else:
                 console.print("[yellow]Warning: Existing log file has unexpected structure. Creating new log.[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Warning: Error reading existing log file, creating new log: {e}[/yellow]")

    # Create new log structure if no valid log exists
    console.print("Creating new log file.")
    log_data = {
        "input_file": input_file_name,
        "start_time": datetime.now().isoformat(), # Use ISO format
        "processed_items": [], # List of strings like "partidx-chapteridx"
        "errors": [], # List of error detail dicts
        "api_calls": [] # List of API call attempt dicts
    }
    return str(log_file_path), log_data, True

# --- Prompt Generation ---

def generate_chapter_outline_prompt(part_name: str, chapter_title: str, chapter_description: str) -> str:
    """Generate a prompt for creating a chapter outline."""

    # Define the desired JSON structure for the outline
    json_template = """{
  "chapter_title_suggestion": "A concise, engaging title based on the input, potentially refining the original.",
  "introduction": {
    "hook": "Suggest 1-2 sentences for an engaging opening to grab the reader's attention.",
    "context_setting": "Briefly explain what background knowledge is assumed or what this chapter connects to.",
    "thesis_or_purpose": "State the main argument, question, or objective this chapter will address (based on the description).",
    "roadmap": "List the main sections or topics that will be covered in the chapter."
  },
  "main_sections": [
    {
      "section_title": "Title for Section 1 (should be descriptive)",
      "key_points_to_cover": [
        "Identify the first major theme/subtopic from the description and list 2-4 key points, concepts, or arguments to elaborate on within this section.",
        "Point 2...",
        "Point 3..."
      ],
      "suggested_examples_or_case_studies": ["Suggest 1-2 relevant examples, case studies, or data points if applicable."],
      "connections_to_other_concepts": ["Mention any direct links to concepts discussed in previous chapters or other parts of the book (use context provided)."]
    },
    {
      "section_title": "Title for Section 2",
      "key_points_to_cover": [
        "Identify the second major theme/subtopic and list 2-4 key points...",
        "Point 2...",
        "Point 3..."
      ],
      "suggested_examples_or_case_studies": [],
      "connections_to_other_concepts": []
    }
    // Add more section objects as needed to logically structure the content described in the input. Aim for 3-5 sections unless the description is very short/long.
  ],
  "conclusion": {
    "summary_of_key_arguments": "Briefly recap the main points or findings covered in the sections.",
    "implications_or_takeaways": "State the main conclusions or what the reader should understand after reading the chapter.",
    "link_to_next_chapter": "Suggest a sentence or two to bridge to the likely topic of the next chapter, if appropriate."
  },
  "keywords_for_indexing": ["List 5-7 relevant keywords based on the chapter content."]
}"""

    # Construct the prompt
    prompt = f"""You are an expert academic editor and curriculum designer tasked with creating a detailed chapter outline for a book, likely for UPSC aspirants.

CONTEXT:
- Book Part: "{part_name}"
- Proposed Chapter Title: "{chapter_title}"
- Chapter Description/Goal: "{chapter_description}"

TASK:
Based *only* on the provided Chapter Title and Description, generate a comprehensive and logically structured outline for writing this chapter. The outline should guide an author on what content to include and how to organize it effectively. Adhere strictly to the following JSON structure. Fill in each field with specific, actionable guidance derived from the input description and title.

OUTPUT JSON STRUCTURE:
{json_template}

INSTRUCTIONS FOR FILLING THE JSON:
- `chapter_title_suggestion`: Refine the input title if needed for clarity or impact, otherwise use the original.
- `introduction`: Provide guidance for writing an engaging intro covering hook, context, purpose, and roadmap.
- `main_sections`:
    - Break down the `chapter_description` into logical subtopics or themes. Create one JSON object per subtopic.
    - For each section, provide a clear `section_title`.
    - List specific `key_points_to_cover` derived directly from the `chapter_description`. Be concrete.
    - Suggest relevant `examples_or_case_studies` if the description implies them.
    - Note any `connections_to_other_concepts` based on the part/book context (if inferrable).
- `conclusion`: Guide the writing of a summary, state key takeaways, and suggest a transition.
- `keywords_for_indexing`: Extract relevant terms from the description and title.

IMPORTANT: Your entire response MUST be a single, valid JSON object matching the structure above. Do NOT include any introductory text, explanations, comments, or markdown formatting (like ```json) outside of the JSON object itself.
"""
    return prompt

# --- Gemini API Interaction ---

def test_gemini_api(api_key: str): # <-- Accept generic api_key
    """Quick test of the Gemini API with a simple prompt"""
    simple_prompt = "Return a JSON object with one key 'status' and value 'ok'."
    try:
        console.print("Testing Gemini API connection...")
        genai.configure(api_key=api_key) # <-- Use passed api_key
        model = genai.GenerativeModel("gemini-1.5-flash") # Use a recent model
        response = model.generate_content(simple_prompt)
        console.print(f"Test response received: {response.text[:100]}...")
        # Basic validation
        try:
            data = json.loads(response.text.strip())
            if data.get("status") == "ok":
                console.print("[green]API test successful.[/green]")
                return True
            else:
                console.print("[yellow]API test warning: Response received but content unexpected.[/yellow]")
                return False
        except Exception as parse_err:
            console.print(f"[yellow]API test warning: Could not parse test response as JSON: {parse_err}[/yellow]")
            console.print(f"Raw response: {response.text}")
            return False
    except Exception as e:
        console.print(f"[bold red]API test failed: {e}[/bold red]")
        console.print(traceback.format_exc())
        return False

def call_gemini_api(prompt: str, api_key: str, log_data: Dict, model_name: str = "gemini-1.5-flash", retry_count: int = 5, exponential_backoff: bool = True) -> Dict: # <-- Accept generic api_key
    """Call the Gemini API with retry logic and return the parsed JSON response"""
    genai.configure(api_key=api_key) # <-- Use passed api_key
    request_time = datetime.now().isoformat()

    # Configuration for Gemini model
    generation_config = {
        "temperature": 0.7, # Slightly creative but grounded
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192, # Increased for potentially longer outlines
        "response_mime_type": "application/json", # Request JSON directly
    }

    # Safety settings (adjust as needed)
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
    ]

    # Fallback response structure (matches expected outline structure)
    fallback_response = {
        "error": "Failed to generate outline after multiple retries.",
        "chapter_title_suggestion": "Error: Outline Generation Failed",
        "introduction": {"hook": "N/A", "context_setting": "N/A", "thesis_or_purpose": "N/A", "roadmap": "N/A"},
        "main_sections": [{"section_title": "Error", "key_points_to_cover": ["API call failed."], "suggested_examples_or_case_studies": [], "connections_to_other_concepts": []}],
        "conclusion": {"summary_of_key_arguments": "N/A", "implications_or_takeaways": "N/A", "link_to_next_chapter": "N/A"},
        "keywords_for_indexing": ["error", "failed"]
    }

    current_prompt = prompt # Initial prompt

    for attempt in range(retry_count):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "model": model_name,
            "attempt": attempt + 1,
            "status": "pending"
        }
        try:
            # Exponential backoff
            if attempt > 0:
                backoff_time = min(30, (2 ** attempt) + random.uniform(0, 1)) # Add jitter
                console.print(f"Retrying (attempt {attempt+1}/{retry_count}) after {backoff_time:.2f}s delay...")
                time.sleep(backoff_time)

            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            # Make API request
            response = model.generate_content(current_prompt)

            # Try to extract text (even if mime type is JSON, text might be available)
            response_text = ""
            try:
                 # Accessing parts is safer if response format varies
                 if response.parts:
                    response_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                 elif hasattr(response, 'text'):
                     response_text = response.text
                 else:
                     # Fallback if structure is unexpected
                      response_text = str(response)

                 if not response_text or not response_text.strip():
                    if response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason'):
                         raise Exception(f"API call blocked. Reason: {response.prompt_feedback.block_reason}")
                    else:
                         raise Exception("API returned an empty response.")

                 # Since we requested JSON, try parsing directly first
                 try:
                     parsed_response = json.loads(response_text)
                     log_entry.update({"status": "success"})
                     log_data["api_calls"].append(log_entry)
                     gc.collect()
                     return parsed_response
                 except json.JSONDecodeError as json_err_direct:
                     console.print(f"[yellow]Warning: Failed to parse direct JSON response (Attempt {attempt+1}). Trying fix_json_string. Error: {json_err_direct}[/yellow]")
                     # Fall through to fix_json_string

            except Exception as text_extract_err:
                 # Handle potential block reason or other errors during access
                 error_msg = f"Response processing error on attempt {attempt+1}: {text_extract_err}"
                 console.print(f"[yellow]API WARNING: {error_msg}[/yellow]")
                 log_entry.update({"status": "response_processing_error", "error": str(text_extract_err)})
                 log_data["api_calls"].append(log_entry)
                 if attempt < retry_count - 1:
                    continue # Retry
                 else:
                    break # Max retries reached for this error type


            # If direct parsing failed, try fixing the raw text
            console.print(f"Attempt {attempt+1}: Raw response snippet: {repr(response_text[:150])}...")
            fixed_json_str = fix_json_string(response_text)

            # Attempt to parse the fixed JSON string
            try:
                parsed_response = json.loads(fixed_json_str)
                log_entry.update({"status": "success_after_fix"})
                log_data["api_calls"].append(log_entry)
                gc.collect()
                return parsed_response
            except json.JSONDecodeError as e:
                error_msg = f"JSON parsing error even after fix_json_string on attempt {attempt+1}: {e}"
                console.print(f"[red]JSON PARSING ERROR: {error_msg}[/red]")
                log_entry.update({"status": "json_error_after_fix", "error": str(e), "fixed_snippet": fixed_json_str[:200]})
                log_data["api_calls"].append(log_entry)
                if attempt < retry_count - 1:
                     console.print("[yellow]Retrying, hoping for better format next time.[/yellow]")
                     continue # Go to next attempt
                else:
                     break # Max retries reached

        except Exception as e:
            # Handle API connection errors, block reasons etc.
            error_msg = f"API call exception on attempt {attempt+1}: {e}"
            console.print(f"[bold red]API ERROR: {error_msg}[/bold red]")
            console.print(traceback.format_exc()) # Print full traceback for API errors
            log_entry.update({"status": "exception", "error": str(e)})
            # Add error to main errors list as well for tracking persistent issues
            log_data["errors"].append({
                "timestamp": log_entry["timestamp"],
                "item_key": "N/A", # We don't have item key context here, add in calling function if needed
                "error": str(e),
                "traceback": traceback.format_exc(),
                "attempt": attempt + 1
            })
            log_data["api_calls"].append(log_entry)
            if attempt < retry_count - 1:
                continue # Retry
            else:
                break # Max retries reached

    # If loop finishes without returning, all retries failed
    console.print("[bold red]All API retries failed. Using fallback response.[/bold red]")
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model_name,
        "attempt": retry_count,
        "status": "failed_all_retries"
    }
    log_data["api_calls"].append(log_entry)
    # Add a final error entry
    log_data["errors"].append({
        "timestamp": log_entry["timestamp"],
         "item_key": "N/A",
        "error": "All retries failed for API call.",
        "traceback": None,
        "attempt": retry_count
    })
    gc.collect()
    return fallback_response

# --- Main Processing Logic ---

def process_input_json(input_file: str, api_key: str, output_dir: Path): # <-- Accept generic api_key
    """
    Process the input JSON file, generating chapter outlines using Gemini API.
    """
    console.print(f"Starting processing for input file: {input_file}")
    input_data = load_json_file(input_file) # load_json_file handles exit on error

    log_file_path, log_data, _ = check_log_file(input_file, output_dir)

    book_title = input_data.get('bookTitle', 'Unknown Book')
    console.print(f"Processing book: [cyan]{book_title}[/cyan]")

    # Prepare tracking variables
    total_chapters = 0
    for part in input_data.get('parts', []):
        total_chapters += len(part.get('chapters', []))

    if total_chapters == 0:
        console.print("[bold red]Error: No chapters found in the input file structure.[/bold red]")
        console.print("Expected structure: { 'parts': [ { 'chapters': [ ... ] } ] }")
        sys.exit(1)

    processed_chapters_count = 0
    processed_items_set = set(log_data.get("processed_items", [])) # Set of "partidx-chapteridx" strings
    error_items_for_retry = [] # List of dicts: {part_idx, chapter_idx, part_name, chapter_title, chapter_description}

    # Determine where to save interim and final files
    output_file_stem = Path(input_file).stem
    interim_filename = output_dir / f"{output_file_stem}_outlined_interim.json"
    final_filename = output_dir / f"{output_file_stem}_outlined_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    final_log_filename = Path(log_file_path) # Use the path determined by check_log_file

    console.print(f"Total chapters to process: {total_chapters}")
    console.print(f"Output will be saved to: {final_filename}")
    console.print(f"Log file: {final_log_filename}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console, # Use the configured console
        disable=not rich_available # Disable if rich is not installed
    ) as progress:

        overall_task = progress.add_task(f"Generating outlines for [cyan]{book_title}[/cyan]", total=total_chapters)

        # --- FIRST PASS ---
        console.print("\n[bold blue]=== Starting First Pass ===[/bold blue]")
        for part_idx, part in enumerate(input_data.get('parts', [])):
            part_name = part.get('name', f'Part {part_idx + 1}')
            chapters = part.get('chapters', [])

            if not chapters:
                console.print(f"[yellow]Warning: Skipping Part '{part_name}' (index {part_idx}) as it contains no chapters.[/yellow]")
                continue

            for chapter_idx, chapter in enumerate(chapters):
                chapter_title = chapter.get('title')
                chapter_description = chapter.get('description')
                item_key = f"{part_idx}-{chapter_idx}" # Unique key for this chapter

                # Check if already processed
                if item_key in processed_items_set:
                    console.print(f"Skipping already processed: Part {part_idx+1}, Chapter {chapter_idx+1} ('{chapter_title[:30]}...')")
                    processed_chapters_count += 1
                    progress.update(overall_task, advance=1, description=f"Skipped {part_idx+1}-{chapter_idx+1}")
                    continue

                # Validate chapter data
                if not chapter_title or not chapter_description:
                    warning_msg = f"Skipping invalid chapter data at Part {part_idx+1}, Chapter {chapter_idx+1}. "
                    if not chapter_title: warning_msg += "Missing title. "
                    if not chapter_description: warning_msg += "Missing description."
                    console.print(f"[yellow]Warning: {warning_msg}[/yellow]")
                    # Log this as a data error, not an API error
                    log_data["errors"].append({
                        "timestamp": datetime.now().isoformat(),
                        "item_key": item_key,
                        "error": "Missing title or description in input data",
                        "part_name": part_name,
                        "chapter_title": chapter_title or "MISSING",
                        "status": "skipped_data_error"
                    })
                    save_json_file(log_data, str(final_log_filename)) # Save log immediately
                    progress.update(overall_task, advance=1, description=f"Data Error {part_idx+1}-{chapter_idx+1}") # Advance progress even on data error
                    continue # Skip to next chapter

                progress.update(overall_task, description=f"Processing P{part_idx+1}-Ch{chapter_idx+1}: '{chapter_title[:30]}...'")
                console.print(f"\nProcessing: Part {part_idx+1} ('{part_name}'), Chapter {chapter_idx+1} ('{chapter_title}')")

                try:
                    # Generate prompt for this chapter
                    prompt = generate_chapter_outline_prompt(part_name, chapter_title, chapter_description)

                    # Call Gemini API << Pass the generic api_key >>
                    console.print(f"Sending request to Gemini API...")
                    outline_response = call_gemini_api(prompt, api_key, log_data) # <-- Use api_key

                    # Check if response indicates an error state from the API call itself
                    if isinstance(outline_response, dict) and outline_response.get("error"):
                         raise Exception(f"API call failed internally: {outline_response.get('error')}")

                    # Add outline to the chapter object
                    chapter['generated_outline'] = outline_response
                    console.print(f"[green]Successfully generated outline for P{part_idx+1}-Ch{chapter_idx+1}[/green]")

                    # Add to processed items in log data
                    log_data["processed_items"].append(item_key)
                    processed_items_set.add(item_key) # Update set as well

                    # Save log and interim file after successful processing
                    save_json_file(log_data, str(final_log_filename))
                    save_json_file(input_data, str(interim_filename)) # Save the whole structure

                    processed_chapters_count += 1
                    progress.update(overall_task, advance=1)

                    # Small delay to prevent rate limiting
                    time.sleep(random.uniform(0.8, 1.5)) # Slightly longer, randomized delay

                    # Run garbage collection
                    gc.collect()

                except Exception as e:
                    error_msg = f"Error processing Part {part_idx+1}, Chapter {chapter_idx+1} ('{chapter_title}'): {e}"
                    console.print(f"[bold red]ERROR (will retry later): {error_msg}[/bold red]")

                    # Add to error list for retry pass
                    error_items_for_retry.append({
                        "part_idx": part_idx,
                        "chapter_idx": chapter_idx,
                        "part_name": part_name,
                        "chapter_title": chapter_title,
                        "chapter_description": chapter_description,
                        "item_key": item_key,
                        "error": str(e) # Store first pass error
                    })

                    # Log the error, marking for retry
                    log_data["errors"].append({
                        "timestamp": datetime.now().isoformat(),
                        "item_key": item_key,
                        "error": str(e),
                        "part_name": part_name,
                        "chapter_title": chapter_title,
                        "status": "pending_retry",
                        "traceback": traceback.format_exc()
                    })
                    save_json_file(log_data, str(final_log_filename))

                    # Don't advance progress here, it will be handled in retry pass or marked as final failure
                    progress.update(overall_task, description=f"Error P{part_idx+1}-Ch{chapter_idx+1} (will retry)")


        # --- SECOND PASS (RETRY) ---
        retry_successes = 0
        if error_items_for_retry:
            console.print(f"\n[bold yellow]=== Starting Second Pass: Retrying {len(error_items_for_retry)} failed items ===[/bold yellow]")
            retry_task = progress.add_task("Retrying failed items", total=len(error_items_for_retry))

            for retry_idx, error_item in enumerate(error_items_for_retry):
                part_idx = error_item["part_idx"]
                chapter_idx = error_item["chapter_idx"]
                part_name = error_item["part_name"]
                chapter_title = error_item["chapter_title"]
                chapter_description = error_item["chapter_description"]
                item_key = error_item["item_key"]

                progress.update(retry_task, description=f"Retrying P{part_idx+1}-Ch{chapter_idx+1}", advance=0) # Show current retry item
                console.print(f"\nRetrying {retry_idx+1}/{len(error_items_for_retry)}: Part {part_idx+1}, Chapter {chapter_idx+1} ('{chapter_title}')")

                try:
                    # Generate the same prompt again
                    prompt = generate_chapter_outline_prompt(part_name, chapter_title, chapter_description)

                    # Try API call again << Pass the generic api_key >>
                    console.print(f"Sending retry request to Gemini API...")
                    outline_response = call_gemini_api(
                        prompt,
                        api_key, # <-- Use api_key
                        log_data,
                        retry_count=7 # Use slightly more retries for the second pass
                        )

                    # Check if response indicates an error state
                    if isinstance(outline_response, dict) and outline_response.get("error"):
                         raise Exception(f"API retry call failed internally: {outline_response.get('error')}")

                    # Update the chapter object in the main data structure
                    input_data['parts'][part_idx]['chapters'][chapter_idx]['generated_outline'] = outline_response
                    console.print(f"[green]Successfully generated outline on retry for P{part_idx+1}-Ch{chapter_idx+1}[/green]")


                    # Update log: Find the original error and mark as resolved
                    for log_err in log_data.get("errors", []):
                        if log_err.get("item_key") == item_key and log_err.get("status") == "pending_retry":
                            log_err["status"] = "retry_success"
                            log_err["resolved_timestamp"] = datetime.now().isoformat()
                            break

                    # Add to processed items ONLY IF retry was successful
                    log_data["processed_items"].append(item_key)
                    processed_items_set.add(item_key)

                    # Save log and interim file
                    save_json_file(log_data, str(final_log_filename))
                    save_json_file(input_data, str(interim_filename))

                    retry_successes += 1
                    processed_chapters_count += 1
                    progress.update(overall_task, advance=1) # Advance overall progress on successful retry
                    progress.update(retry_task, advance=1) # Advance retry progress

                    # Longer delay between retries
                    time.sleep(random.uniform(1.5, 2.5))
                    gc.collect()

                except Exception as e:
                    error_msg = f"Error during retry for P{part_idx+1}-Ch{chapter_idx+1}: {e}"
                    console.print(f"[bold red]RETRY FAILED: {error_msg}[/bold red]")

                    # Update log: Mark original error as failed retry
                    for log_err in log_data.get("errors", []):
                         if log_err.get("item_key") == item_key and log_err.get("status") == "pending_retry":
                            log_err["status"] = "retry_failed"
                            log_err["final_error"] = str(e)
                            log_err["final_traceback"] = traceback.format_exc()
                            log_err["resolved_timestamp"] = datetime.now().isoformat()
                            break
                    save_json_file(log_data, str(final_log_filename))

                    # Advance retry task progress, but not overall progress
                    progress.update(retry_task, advance=1, description=f"Retry Failed P{part_idx+1}-Ch{chapter_idx+1}")

                    # Assign a minimal error outline to the chapter so the structure is consistent
                    input_data['parts'][part_idx]['chapters'][chapter_idx]['generated_outline'] = {
                        "error": f"Failed to generate outline after retry. Last error: {str(e)}",
                        "chapter_title_suggestion": chapter_title + " (Outline Generation Failed)",
                         # Add other keys with placeholder values if needed for schema consistency
                    }
                    # Save the interim file even on retry failure to capture the error state
                    save_json_file(input_data, str(interim_filename))

                    continue # Continue to the next error item

            console.print(f"\n[bold yellow]Retry Summary: {retry_successes}/{len(error_items_for_retry)} items successfully processed on retry.[/bold yellow]")


    # --- Finalization ---
    console.print("\n[bold green]=== Processing Complete ===[/bold green]")

    # Save the final JSON with all outlines (or errors)
    save_json_file(input_data, str(final_filename))

    # Update and save final log
    log_data["end_time"] = datetime.now().isoformat()
    log_data["total_chapters_in_input"] = total_chapters
    # Count final processed based on the set, which includes successful first pass and successful retries
    final_processed_count = len(processed_items_set)
    log_data["successfully_processed_chapters"] = final_processed_count
    log_data["chapters_with_final_errors"] = total_chapters - final_processed_count - len([e for e in log_data.get("errors",[]) if e.get("status") == "skipped_data_error"]) # Subtract data errors too
    log_data["retry_attempts_made"] = len(error_items_for_retry)
    log_data["retry_success_count"] = retry_successes
    log_data["output_file"] = str(final_filename)
    save_json_file(log_data, str(final_log_filename))

    console.print(f"Successfully processed {final_processed_count}/{total_chapters} chapters.")
    if log_data["chapters_with_final_errors"] > 0:
         console.print(f"[bold red]Note: {log_data['chapters_with_final_errors']} chapters encountered errors that could not be resolved after retries.[/bold red]")
         console.print("Check the log file for details.")
    if len([e for e in log_data.get("errors",[]) if e.get("status") == "skipped_data_error"]) > 0:
         console.print(f"[yellow]Note: {len([e for e in log_data.get('errors',[]) if e.get('status') == 'skipped_data_error'])} chapters were skipped due to missing title/description in the input file.[/yellow]")

    console.print(f"\nFinal outlined content saved to: [link=file://{os.path.abspath(final_filename)}]{final_filename}[/link]")
    console.print(f"Detailed log saved to: [link=file://{os.path.abspath(final_log_filename)}]{final_log_filename}[/link]")

    # Final garbage collection
    gc.collect()


# --- Main Execution ---

def main():
    print(f"\n--- Script Execution Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    print(f"Current Directory: {os.getcwd()}")

    # Load environment variables (.env file)
    try:
        load_dotenv()
        print("Attempted to load environment variables from .env file.")
    except Exception as e:
        print(f"Could not load .env file (this is optional): {e}")

    # Setup argument parser
    parser = argparse.ArgumentParser(description='Generate chapter outlines using Google Gemini API based on input JSON.')
    parser.add_argument('--input_file', type=str, required=True, help='Path to the input JSON file containing book structure (parts and chapters).')
    parser.add_argument('--output_dir', type=str, default='results/Outlines', help='Directory to save output JSON and log files (default: results/Outlines)')
    parser.add_argument('--test', action='store_true', help='Run a quick API test before processing.')
    args = parser.parse_args()

    print(f"Arguments received: input_file='{args.input_file}', output_dir='{args.output_dir}', test={args.test}")

    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Output directory ensured: {output_dir.resolve()}")
    except Exception as e:
        print(f"[bold red]Fatal Error: Could not create output directory '{output_dir}'. Please check permissions. Error: {e}[/bold red]")
        sys.exit(1)


    # Get Google API key << CHANGED VARIABLE NAME HERE >>
    api_key = os.environ.get('GOOGLE_API_KEY') # <-- Changed from GEMINI_API_KEY
    if not api_key:
        # <-- Updated error message >>
        console.print("[bold red]Fatal Error: GOOGLE_API_KEY not found in environment variables or .env file.[/bold red]")
        console.print("Please set the GOOGLE_API_KEY environment variable.")
        sys.exit(1)
    else:
        # Mask the key for security
        console.print(f"Found API key (starts with: {api_key[:5]}..., ends with: ...{api_key[-4:]})")

    # Optional: Run API test << Pass the renamed variable >>
    if args.test:
        print("\n--- Running API Test ---")
        if not test_gemini_api(api_key): # <-- Use api_key
            console.print("[bold red]API test failed. Exiting. Please check your API key, billing status, and internet connection.[/bold red]")
            sys.exit(1)
        print("--- API Test Complete ---")


    # Check input file existence *before* calling load_json_file
    if not Path(args.input_file).is_file():
         console.print(f"[bold red]Fatal Error: Input file not found at '{args.input_file}'[/bold red]")
         sys.exit(1)
    else:
         print(f"Input file found: {args.input_file}")

    # Process the input file << Pass the renamed variable >>
    print("\n--- Starting Main Processing ---")
    try:
        process_input_json(
            input_file=args.input_file,
            api_key=api_key, # <-- Use api_key
            output_dir=output_dir
        )
        print("\n--- Script Execution Finished Successfully ---")
    except KeyboardInterrupt:
        print("\n[bold yellow]Process interrupted by user. Exiting gracefully...[/bold yellow]")
        sys.exit(0)
    except SystemExit as e:
         # Catch sys.exit calls from helper functions (like load_json)
         print(f"\n[bold red]Exiting due to error (Code: {e.code}).[/bold red]")
         sys.exit(e.code)
    except Exception as e:
        print(f"\n[bold red]An unexpected critical error occurred during processing:[/bold red]")
        print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()