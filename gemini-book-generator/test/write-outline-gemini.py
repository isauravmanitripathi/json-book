"""
Run using:
python write-outline-gemini.py --input_file path/to/your/input.json --output_dir results/Outlines

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
from typing import Dict, List, Any, Deque # Import Deque
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import sys
import traceback
import re
from collections import deque # Use deque

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
    """Generate a prompt for creating a chapter writing outline with content points and search terms."""

    # Define the new desired JSON structure
    json_template = """{
  "chapter_title_suggestion": "A concise, engaging title based on the input, potentially refining the original.",
  "writing_sections": [
    {
      "section_title": "Proposed Title for Section 1 (Descriptive and Clear)",
      "content_points_to_cover": [
        "Detailed point 1: Specify what core concept/topic/event to explain or analyze here. Be specific about the angle or focus derived from the description.",
        "Detailed point 2: Elaborate on another key aspect mentioned in the description relevant to this section.",
        "Detailed point 3: Suggest connections or comparisons to make within this section."
      ],
      "Google Search_terms": [
        "Specific search query for researching point 1",
        "Broader search term for the core topic of Section 1",
        "Keyword phrase for finding examples/case studies for Section 1"
      ]
    },
    {
      "section_title": "Proposed Title for Section 2",
      "content_points_to_cover": [
        "Detailed point 2.1: Break down the next logical part of the description.",
        "Detailed point 2.2: Suggest specific arguments or evidence to include.",
        "..."
      ],
      "Google Search_terms": [
        "Search query relevant to Section 2 content",
        "Alternative phrasing for Section 2 research",
        "..."
      ]
    }
    // Add more section objects dynamically. Create as many sections as needed to comprehensively cover the chapter_description. Do not limit the number arbitrarily.
  ]
}"""

    # Construct the prompt
    prompt = f"""You are an expert academic writer and editor creating a detailed *writing guide* for a book chapter on "India's International Relations: A Comprehensive Analysis for UPSC Aspirants". Your goal is to structure the writing process for an author.

CONTEXT:
- Book Part: "{part_name}"
- Proposed Chapter Title: "{chapter_title}"
- Chapter Description/Goal: "{chapter_description}"

TASK:
Based *only* on the provided Chapter Title and Description, generate a comprehensive writing outline focused specifically on India's international relations for UPSC aspirants. This outline should break down the chapter into logical sections and provide actionable guidance on the content for each section, including suggested Google search terms for further research by the author. Write as many sections as needed to cover the chapter description thoroughly.

ALL CONTENT MUST BE FOCUSED ON INDIA'S INTERNATIONAL RELATIONS . Stay focused on the diplomatic, strategic, economic, and political aspects of India's relationships with other countries and international organizations.

You should write in detail.

Adhere strictly to the following JSON structure:

OUTPUT JSON STRUCTURE:
{json_template}

INSTRUCTIONS FOR FILLING THE JSON:
- You can write as many section titles you need to cover the chapter description.
- Under section cover all relevant detail, every aspect of it. Write detailed guide on what to write in that, what topic to dicuss, everything
- `chapter_title_suggestion`: Refine the input title for clarity/impact, or use the original.
- `writing_sections`:
    - This MUST be a JSON array `[]`.
    - Determine the logical number of sections needed to cover the `chapter_description`. Create one JSON object {{}} within the array for each section. Create as many sections as needed for comprehensive coverage.
    - For each section object:
        - `section_title`: Propose a clear and descriptive title.
        - `content_points_to_cover`: This MUST be a JSON array `[]`. List *detailed, actionable points* instructing the author on what specific concepts, arguments, analyses, or information derived from the `chapter_description` should be included in this section. Think "What should the author write about here?". Write a very detailed guide on what to write in that, what topic to dicuss, everything.
        - `Google Search_terms`: This MUST be a JSON array `[]`. Provide as many relevant Google search query strings that the author could use to research the topics covered in this section more deeply. These should be practical and focused on India's international relations in the context of UPSC preparation.


**CRITICAL JSON VALIDITY RULES:**
1.  Your *entire* response MUST be a single, valid JSON object conforming exactly to the structure above.
2.  Do NOT include any introductory text, explanations, comments, or markdown formatting (like ```json) outside of the JSON object itself.
3.  **Ensure correct comma usage:** All elements in JSON arrays (lists) must be separated by commas, except for the last element. All key-value pairs in JSON objects must be separated by commas, except for the last pair. Missing commas are a common error.
    - Correct list example: `"key": ["item1", "item2", "item3"]`
    - Correct object example: `"key": {{ "prop1": "value1", "prop2": "value2" }}`
4.  Ensure all strings are properly enclosed in double quotes and any double quotes *within* a string value are correctly escaped (e.g., `"He said \\"Hello\\""`).

Adherence to valid JSON syntax is paramount. Double-check your response for validity before outputting.
"""
    return prompt


# --- Gemini API Interaction ---

# << MODIFIED test_gemini_api to accept model_name >>
def test_gemini_api(api_key: str, model_name: str = "gemini-2.0-flash"):
    """Quick test of the Gemini API with a simple prompt"""
    simple_prompt = "Return a JSON object with one key 'status' and value 'ok'."
    try:
        console.print(f"Testing Gemini API connection with model: {model_name}...")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name) # Use passed model name
        response = model.generate_content(simple_prompt)
        console.print(f"Test response received: {response.text[:100]}...")
        # Basic validation (still attempt parse)
        try:
            fixed_text = fix_json_string(response.text)
            data = json.loads(fixed_text)
            if data.get("status") == "ok":
                console.print("[green]API test successful (parsed response).[/green]")
                return True
            else:
                console.print("[yellow]API test warning: Response received but content unexpected after parse.[/yellow]")
                # Still return True as API call worked
                return True
        except Exception as parse_err:
            console.print(f"[yellow]API test warning: Could not parse test response as JSON: {parse_err}[/yellow]")
            console.print(f"Raw response: {response.text}")
            # Return True here because the API call itself worked, even if output wasn't the expected JSON
            console.print("[yellow]API call succeeded, but response was not the expected simple JSON.[/yellow]")
            return True
    except Exception as e:
        console.print(f"[bold red]API test failed for model {model_name}: {e}[/bold red]")
        console.print(traceback.format_exc())
        return False

def call_gemini_api(prompt: str, api_key: str, log_data: Dict, model_name: str, retry_count: int = 2, exponential_backoff: bool = True) -> Dict:
    """Call the Gemini API with retry logic and return the parsed JSON response"""
    # Note: model_name is now passed explicitly
    genai.configure(api_key=api_key)
    request_time = datetime.now().isoformat()

    # Configuration for Gemini model
    generation_config = {
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
        # "response_mime_type": "application/json", # Removed as it caused errors with some models
    }

    # Safety settings
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
    ]

    # Fallback response structure
    fallback_response = {
        "error": f"Failed to generate outline after {retry_count + 1} attempts.",
        "chapter_title_suggestion": "Error: Outline Generation Failed",
        "writing_sections": [
            {
            "section_title": "Error",
            "content_points_to_cover": ["API call failed to produce outline content."],
            "Google Search_terms": ["error retrieving data"] # Corrected key name
            }
        ],
    }

    current_prompt = prompt
    max_attempts = retry_count + 1

    for attempt in range(max_attempts):
        current_attempt_num = attempt + 1
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "model": model_name,
            "attempt": current_attempt_num,
            "status": "pending"
        }
        try:
            # --- Backoff ---
            if attempt > 0:
                backoff_time = min(30, (2 ** attempt) + random.uniform(0, 1))
                console.print(f"Retrying (attempt {current_attempt_num}/{max_attempts}) after {backoff_time:.2f}s delay...")
                time.sleep(backoff_time)

            # --- API Call ---
            model = genai.GenerativeModel(
                model_name=model_name, # Use passed model_name
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            console.print(f"Sending request to Gemini API using {model_name} (Attempt {current_attempt_num}/{max_attempts})...")
            response = model.generate_content(current_prompt)

            # --- Response Processing ---
            response_text = ""
            try:
                 if response.parts:
                    response_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                 elif hasattr(response, 'text'):
                     response_text = response.text
                 else:
                      response_text = str(response)

                 if not response_text or not response_text.strip():
                    if response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason'):
                         raise Exception(f"API call blocked. Reason: {response.prompt_feedback.block_reason}")
                    else:
                         raise Exception("API returned an empty response.")

                 # Attempt to parse the response text as JSON
                 console.print(f"Attempt {current_attempt_num}: Raw response snippet: {repr(response_text[:150])}...")
                 fixed_json_str = fix_json_string(response_text)

                 try:
                     parsed_response = json.loads(fixed_json_str)
                     log_entry.update({"status": "success_parsed_json"})
                     log_data["api_calls"].append(log_entry)
                     gc.collect()
                     return parsed_response # SUCCESS
                 except json.JSONDecodeError as e:
                     error_msg = f"JSON parsing error on attempt {current_attempt_num} after fix_json_string: {e}"
                     console.print(f"[red]JSON PARSING ERROR: {error_msg}[/red]")
                     log_entry.update({"status": "json_error_after_fix", "error": str(e), "raw_response_snippet": fixed_json_str[:200]})
                     log_data["api_calls"].append(log_entry)
                     if current_attempt_num < max_attempts:
                          console.print("[yellow]Continuing to next attempt despite parsing error, hoping for better format.[/yellow]")
                          continue
                     else:
                          console.print("[red]Parsing failed on final attempt.[/red]")
                          break

            except Exception as text_extract_err:
                 error_msg = f"Response processing error on attempt {current_attempt_num}: {text_extract_err}"
                 console.print(f"[yellow]API WARNING: {error_msg}[/yellow]")
                 log_entry.update({"status": "response_processing_error", "error": str(text_extract_err)})
                 log_data["api_calls"].append(log_entry)
                 if current_attempt_num < max_attempts:
                    continue
                 else:
                    break

        except Exception as e:
            # Handle broader API errors
            error_msg = f"API call exception on attempt {current_attempt_num} using model {model_name}: {e}" # Added model name
            console.print(f"[bold red]API ERROR: {error_msg}[/bold red]")
            console.print(traceback.format_exc())
            log_entry.update({"status": "exception", "error": str(e)})
            is_error_logged = any(log.get("timestamp") == log_entry["timestamp"] for log in log_data.get("errors",[])) # Check if already logged via other means
            if not is_error_logged:
                 log_data["errors"].append({
                    "timestamp": log_entry["timestamp"], "item_key": "N/A", "error": str(e),
                    "traceback": traceback.format_exc(), "attempt": current_attempt_num, "status": "api_exception", "model_used": model_name
                 })
            log_data["api_calls"].append(log_entry)
            if current_attempt_num < max_attempts:
                continue
            else:
                break

    # --- Failure Fallback ---
    console.print(f"[bold red]All {max_attempts} API attempts failed or final response unparsable. Using fallback response.[/bold red]")
    if "timestamp" not in log_entry:
         log_entry = {"timestamp": datetime.now().isoformat(), "model": model_name, "attempt": 0, "status": "failed_before_loop"}
    log_entry["status"] = "failed_all_attempts_or_unparsable"
    is_final_status_logged = any(call.get("timestamp") == log_entry["timestamp"] and call.get("status") == log_entry["status"] for call in log_data.get("api_calls", []))
    if not is_final_status_logged:
        log_data["api_calls"].append(log_entry)
    is_final_error_logged = any(err.get("item_key") == "N/A" and err.get("attempt") == max_attempts for err in log_data.get("errors", []))
    if not is_final_error_logged:
        log_data["errors"].append({
            "timestamp": log_entry["timestamp"], "item_key": "N/A",
            "error": f"All {max_attempts} attempts failed or final response unparsable.",
            "traceback": None, "attempt": max_attempts, "status": "final_failure", "model_used": model_name
        })
    gc.collect()
    return fallback_response


# --- Main Processing Logic ---

# << MODIFIED: Accept model_name_arg >>
def process_input_json(input_file: str, api_key: str, output_dir: Path, model_name_arg: str):
    """
    Process the input JSON file, generating chapter outlines using Gemini API.
    """
    console.print(f"Starting processing for input file: {input_file}")
    input_data = load_json_file(input_file)

    log_file_path, log_data, _ = check_log_file(input_file, output_dir)

    book_title = input_data.get('bookTitle', 'Unknown Book')
    console.print(f"Processing book: [cyan]{book_title}[/cyan]")
    console.print(f"Using model: [cyan]{model_name_arg}[/cyan]") # Log the model being used

    total_chapters = 0
    for part in input_data.get('parts', []):
        total_chapters += len(part.get('chapters', []))

    if total_chapters == 0:
        console.print("[bold red]Error: No chapters found in the input file structure.[/bold red]")
        sys.exit(1)

    processed_chapters_count = 0
    processed_items_set = set(log_data.get("processed_items", []))
    error_items_for_retry = []

    output_file_stem = Path(input_file).stem
    interim_filename = output_dir / f"{output_file_stem}_outlined_interim.json"
    final_filename = output_dir / f"{output_file_stem}_outlined_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    final_log_filename = Path(log_file_path)

    console.print(f"Total chapters to process: {total_chapters}")
    console.print(f"Output will be saved to: {final_filename}")
    console.print(f"Log file: {final_log_filename}")

    api_call_timestamps: Deque[float] = deque(maxlen=9)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        disable=not rich_available
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
                item_key = f"{part_idx}-{chapter_idx}"

                if item_key in processed_items_set:
                    console.print(f"Skipping already processed: Part {part_idx+1}, Chapter {chapter_idx+1} ('{chapter_title[:30]}...')")
                    # Corrected logic: count success only if outline exists
                    # processed_chapters_count += 1 # Don't count here, count based on final set
                    progress.update(overall_task, advance=1, description=f"Skipped {part_idx+1}-{chapter_idx+1}")
                    continue

                if not chapter_title or not chapter_description:
                    warning_msg = f"Skipping invalid chapter data at Part {part_idx+1}, Chapter {chapter_idx+1}. "
                    if not chapter_title: warning_msg += "Missing title. "
                    if not chapter_description: warning_msg += "Missing description."
                    console.print(f"[yellow]Warning: {warning_msg}[/yellow]")
                    log_data["errors"].append({
                        "timestamp": datetime.now().isoformat(), "item_key": item_key,
                        "error": "Missing title or description in input data", "part_name": part_name,
                        "chapter_title": chapter_title or "MISSING", "status": "skipped_data_error"
                    })
                    save_json_file(log_data, str(final_log_filename))
                    progress.update(overall_task, advance=1, description=f"Data Error {part_idx+1}-{chapter_idx+1}")
                    continue

                progress.update(overall_task, description=f"Processing P{part_idx+1}-Ch{chapter_idx+1}: '{chapter_title[:30]}...'")
                console.print(f"\nProcessing: Part {part_idx+1} ('{part_name}'), Chapter {chapter_idx+1} ('{chapter_title}')")

                try:
                    # --- Rate Limiting ---
                    now = time.monotonic()
                    while api_call_timestamps and now - api_call_timestamps[0] > 60.0:
                        api_call_timestamps.popleft()
                    if len(api_call_timestamps) >= 9:
                        time_since_oldest_in_window = now - api_call_timestamps[0]
                        wait_time = 60.0 - time_since_oldest_in_window
                        if wait_time > 0:
                            console.print(f"[yellow]Rate limit (9 calls/min) hit. Waiting for {wait_time:.2f}s...[/yellow]")
                            time.sleep(wait_time)
                            now = time.monotonic()
                    random_delay = random.uniform(3.0, 8.0)
                    console.print(f"Applying random delay of {random_delay:.2f}s...")
                    time.sleep(random_delay)
                    api_call_timestamps.append(time.monotonic())
                    # --- End Rate Limiting ---

                    prompt = generate_chapter_outline_prompt(part_name, chapter_title, chapter_description)
                    # << Pass the model name from arg >>
                    outline_response = call_gemini_api(prompt, api_key, log_data, model_name=model_name_arg, retry_count=2)

                    # --- Process Response ---
                    if isinstance(outline_response, dict) and outline_response.get("error"):
                         console.print(f"[bold red]ERROR: API call failed after all {2 + 1} attempts for P{part_idx+1}-Ch{chapter_idx+1}. Details in log.[/bold red]")
                         for err_entry in reversed(log_data.get("errors", [])):
                             if err_entry.get("item_key") == "N/A" and "attempts failed" in err_entry.get("error", ""):
                                 err_entry["item_key"] = item_key
                                 err_entry["part_name"] = part_name
                                 err_entry["chapter_title"] = chapter_title
                                 err_entry["status"] = "api_final_failure"
                                 break
                         # Add to retry list
                         if item_key not in processed_items_set:
                             error_items_for_retry.append({
                                "part_idx": part_idx, "chapter_idx": chapter_idx, "part_name": part_name,
                                "chapter_title": chapter_title, "chapter_description": chapter_description,
                                "item_key": item_key, "error": outline_response.get("error")
                             })
                         progress.update(overall_task, description=f"Error P{part_idx+1}-Ch{chapter_idx+1} (will retry)")
                         continue # Skip rest of try block, move to next chapter

                    # Success Path
                    chapter['generated_outline'] = outline_response
                    console.print(f"[green]Successfully generated outline for P{part_idx+1}-Ch{chapter_idx+1}[/green]")

                    log_data["processed_items"].append(item_key)
                    processed_items_set.add(item_key)
                    save_json_file(log_data, str(final_log_filename))
                    save_json_file(input_data, str(interim_filename))

                    # processed_chapters_count += 1 # Don't need separate counter
                    progress.update(overall_task, advance=1)
                    gc.collect()

                except Exception as e:
                    # << MODIFIED: Corrected error message construction >>
                    base_error_intro = f"Error processing Part {part_idx+1}, Chapter {chapter_idx+1} ('{chapter_title}'): "
                    full_error_msg = base_error_intro + str(e)
                    console.print(f"[bold red]ERROR (will add to retry list): {full_error_msg}[/bold red]")
                    # console.print(traceback.format_exc()) # Optionally uncomment for full traceback during debugging

                    if item_key not in processed_items_set:
                        error_items_for_retry.append({
                            "part_idx": part_idx, "chapter_idx": chapter_idx, "part_name": part_name,
                            "chapter_title": chapter_title, "chapter_description": chapter_description,
                            "item_key": item_key, "error": str(e)
                        })
                        is_api_final_failure = any(
                            err.get("item_key") == item_key and err.get("status") == "api_final_failure"
                            for err in log_data.get("errors", [])
                        )
                        if not is_api_final_failure:
                             log_data["errors"].append({
                                "timestamp": datetime.now().isoformat(), "item_key": item_key,
                                "error": str(e), "part_name": part_name, "chapter_title": chapter_title,
                                "status": "processing_loop_error_pending_retry",
                                "traceback": traceback.format_exc() # Log traceback here for debugging
                             })
                             save_json_file(log_data, str(final_log_filename))

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

                if item_key in processed_items_set:
                    console.print(f"Skipping retry for already processed item: {item_key}")
                    progress.update(retry_task, advance=1)
                    continue

                progress.update(retry_task, description=f"Retrying P{part_idx+1}-Ch{chapter_idx+1}", advance=0)
                console.print(f"\nRetrying {retry_idx+1}/{len(error_items_for_retry)}: Part {part_idx+1}, Chapter {chapter_idx+1} ('{chapter_title}')")

                try:
                    # --- Rate Limiting ---
                    now = time.monotonic()
                    while api_call_timestamps and now - api_call_timestamps[0] > 60.0:
                        api_call_timestamps.popleft()
                    if len(api_call_timestamps) >= 9:
                        time_since_oldest_in_window = now - api_call_timestamps[0]
                        wait_time = 60.0 - time_since_oldest_in_window
                        if wait_time > 0:
                            console.print(f"[yellow]Rate limit (9 calls/min) hit. Waiting for {wait_time:.2f}s...[/yellow]")
                            time.sleep(wait_time)
                            now = time.monotonic()
                    random_delay = random.uniform(3.0, 8.0)
                    console.print(f"Applying random delay of {random_delay:.2f}s...")
                    time.sleep(random_delay)
                    api_call_timestamps.append(time.monotonic())
                    # --- End Rate Limiting ---

                    prompt = generate_chapter_outline_prompt(part_name, chapter_title, chapter_description)
                    # << Pass the model name from arg >>
                    # Retry with retry_count=4 (5 attempts total)
                    outline_response = call_gemini_api(prompt, api_key, log_data, model_name=model_name_arg, retry_count=4)

                    # --- Process Response ---
                    if isinstance(outline_response, dict) and outline_response.get("error"):
                         console.print(f"[bold red]RETRY FAILED: API call failed after all {4 + 1} retry attempts for P{part_idx+1}-Ch{chapter_idx+1}. Details in log.[/bold red]")
                         for log_err in log_data.get("errors", []):
                             if log_err.get("item_key") == item_key and log_err.get("status") in ["api_final_failure", "processing_loop_error_pending_retry", "pending_retry"]:
                                 log_err["status"] = "retry_final_failure"
                                 log_err["final_error"] = outline_response.get("error")
                                 log_err["resolved_timestamp"] = datetime.now().isoformat()
                                 break
                         input_data['parts'][part_idx]['chapters'][chapter_idx]['generated_outline'] = fallback_response
                         save_json_file(input_data, str(interim_filename))
                         save_json_file(log_data, str(final_log_filename))
                         progress.update(retry_task, advance=1, description=f"Retry Failed P{part_idx+1}-Ch{chapter_idx+1}")
                         continue # Move to next retry item

                    # Retry Success Path
                    input_data['parts'][part_idx]['chapters'][chapter_idx]['generated_outline'] = outline_response
                    console.print(f"[green]Successfully generated outline on retry for P{part_idx+1}-Ch{chapter_idx+1}[/green]")

                    for log_err in log_data.get("errors", []):
                        if log_err.get("item_key") == item_key and log_err.get("status") in ["api_final_failure", "processing_loop_error_pending_retry", "pending_retry"]:
                            log_err["status"] = "retry_success"
                            log_err["resolved_timestamp"] = datetime.now().isoformat()
                            break

                    log_data["processed_items"].append(item_key)
                    processed_items_set.add(item_key)
                    save_json_file(log_data, str(final_log_filename))
                    save_json_file(input_data, str(interim_filename))

                    retry_successes += 1
                    # processed_chapters_count += 1 # Don't need separate counter
                    progress.update(overall_task, advance=1)
                    progress.update(retry_task, advance=1)
                    gc.collect()

                except Exception as e:
                    # << MODIFIED: Corrected error message construction >>
                    base_error_intro = f"Unexpected error during retry for P{part_idx+1}, Chapter {chapter_idx+1} ('{chapter_title}'): "
                    full_error_msg = base_error_intro + str(e)
                    console.print(f"[bold red]RETRY FAILED (Loop Error): {full_error_msg}[/bold red]")
                    # console.print(traceback.format_exc()) # Optionally uncomment for debugging

                    # Update log status to final failure
                    for log_err in log_data.get("errors", []):
                         if log_err.get("item_key") == item_key and log_err.get("status") in ["api_final_failure", "processing_loop_error_pending_retry", "pending_retry"]:
                            log_err["status"] = "retry_loop_error_failed"
                            log_err["final_error"] = str(e)
                            log_err["final_traceback"] = traceback.format_exc()
                            log_err["resolved_timestamp"] = datetime.now().isoformat()
                            break
                    # Assign fallback error outline
                    input_data['parts'][part_idx]['chapters'][chapter_idx]['generated_outline'] = fallback_response
                    save_json_file(input_data, str(interim_filename))
                    save_json_file(log_data, str(final_log_filename))
                    progress.update(retry_task, advance=1, description=f"Retry Failed P{part_idx+1}-Ch{chapter_idx+1}")
                    continue # Move to next retry item

            console.print(f"\n[bold yellow]Retry Summary: {retry_successes}/{len(error_items_for_retry)} items successfully processed on retry.[/bold yellow]")


    # --- Finalization ---
    console.print("\n[bold green]=== Processing Complete ===[/bold green]")
    save_json_file(input_data, str(final_filename))
    log_data["end_time"] = datetime.now().isoformat()
    log_data["total_chapters_in_input"] = total_chapters
    final_processed_count = len(processed_items_set)
    log_data["successfully_processed_chapters"] = final_processed_count
    skipped_data_errors = len([e for e in log_data.get("errors",[]) if e.get("status") == "skipped_data_error"])
    # Calculate final errors accurately
    final_api_errors = 0
    all_item_keys = set()
    for p_idx, p in enumerate(input_data.get('parts', [])):
        for c_idx, c in enumerate(p.get('chapters',[])):
             all_item_keys.add(f"{p_idx}-{c_idx}")

    processed_or_skipped_keys = processed_items_set.union(
        {e["item_key"] for e in log_data.get("errors", []) if e.get("status") == "skipped_data_error"}
    )
    final_api_errors = len(all_item_keys - processed_or_skipped_keys)

    log_data["chapters_with_final_errors"] = final_api_errors
    log_data["chapters_skipped_data_error"] = skipped_data_errors
    log_data["retry_pass_attempts_made"] = len(error_items_for_retry)
    log_data["retry_pass_success_count"] = retry_successes
    log_data["output_file"] = str(final_filename)
    log_data["model_used"] = model_name_arg # Log the model used for the run
    save_json_file(log_data, str(final_log_filename))
    console.print(f"Successfully processed {final_processed_count}/{total_chapters} chapters.")
    if log_data["chapters_with_final_errors"] > 0:
         console.print(f"[bold red]Note: {log_data['chapters_with_final_errors']} chapters encountered API/processing errors that could not be resolved after retries.[/bold red]")
         console.print("Check the log file for details.")
    if skipped_data_errors > 0:
         console.print(f"[yellow]Note: {skipped_data_errors} chapters were skipped due to missing title/description in the input file.[/yellow]")
    console.print(f"\nFinal outlined content saved to: [link=file://{os.path.abspath(final_filename)}]{final_filename}[/link]")
    console.print(f"Detailed log saved to: [link=file://{os.path.abspath(final_log_filename)}]{final_log_filename}[/link]")
    gc.collect()


# --- Main Execution ---
def main():
    print(f"\n--- Script Execution Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    print(f"Current Directory: {os.getcwd()}")

    try:
        load_dotenv()
        print("Attempted to load environment variables from .env file.")
    except Exception as e:
        print(f"Could not load .env file (this is optional): {e}")

    parser = argparse.ArgumentParser(description='Generate chapter outlines using Google Gemini API based on input JSON.')
    parser.add_argument('--input_file', type=str, required=True, help='Path to the input JSON file containing book structure (parts and chapters).')
    parser.add_argument('--output_dir', type=str, default='results/Outlines', help='Directory to save output JSON and log files (default: results/Outlines)')
    parser.add_argument('--test', action='store_true', help='Run a quick API test before processing.')
    # << Add argument for model name >>
    parser.add_argument('--model', type=str, default='gemini-2.0-flash', help='Name of the Gemini model to use (default: gemini-2.0-flash)')

    args = parser.parse_args()

    print(f"Arguments received: input_file='{args.input_file}', output_dir='{args.output_dir}', test={args.test}, model='{args.model}'") # Log model name

    output_dir = Path(args.output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Output directory ensured: {output_dir.resolve()}")
    except Exception as e:
        console.print(f"[bold red]Fatal Error: Could not create output directory '{output_dir}'. Please check permissions. Error: {e}[/bold red]")
        sys.exit(1)

    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        console.print("[bold red]Fatal Error: GOOGLE_API_KEY not found in environment variables or .env file.[/bold red]")
        console.print("Please set the GOOGLE_API_KEY environment variable.")
        sys.exit(1)
    else:
        console.print(f"Found API key (starts with: {api_key[:5]}..., ends with: ...{api_key[-4:]})")

    if args.test:
        print("\n--- Running API Test ---")
        # Pass the chosen model name to the test function
        if not test_gemini_api(api_key, model_name=args.model):
            console.print("[bold red]API test failed. Exiting. Please check your API key, billing status, model name, and internet connection.[/bold red]")
            sys.exit(1)
        print("--- API Test Complete ---")

    if not Path(args.input_file).is_file():
         console.print(f"[bold red]Fatal Error: Input file not found at '{args.input_file}'[/bold red]")
         sys.exit(1)
    else:
         print(f"Input file found: {args.input_file}")

    print("\n--- Starting Main Processing ---")
    try:
        # << Pass model name to processing function >>
        process_input_json(
            input_file=args.input_file,
            api_key=api_key,
            output_dir=output_dir,
            model_name_arg=args.model # Pass the argument here
        )
        print("\n--- Script Execution Finished Successfully ---")
    except KeyboardInterrupt:
        print("\n[bold yellow]Process interrupted by user. Exiting gracefully...[/bold yellow]")
        sys.exit(0)
    except SystemExit as e:
         print(f"\n[bold red]Exiting due to error (Code: {e.code}).[/bold red]")
         sys.exit(e.code)
    except Exception as e:
        print(f"\n[bold red]An unexpected critical error occurred during processing:[/bold red]")
        print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()