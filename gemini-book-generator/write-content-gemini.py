import json
import os
import google.generativeai as genai
import argparse
import time
import random
import gc
from typing import Dict, List, Any, Set, Optional # Import Set, Optional
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import sys
import traceback
import re
from collections import deque

# Rich library for enhanced terminal display
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, TimeElapsedColumn
    rich_available = True
except ImportError:
    rich_available = False
    # Simple console replacement if rich is not available
    class SimpleConsole:
        def print(self, message, **kwargs):
            # Basic removal of rich tags for plain printing
            message = re.sub(r'\[/?.*?\]', '', str(message))
            print(message)

        def status(self, message):
            class DummyContext:
                def __enter__(self):
                    # Basic removal of rich tags for plain printing
                    message_plain = re.sub(r'\[/?.*?\]', '', str(message))
                    print(f"... {message_plain}")
                    return self
                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass
                def update(self, text):
                    # Basic removal of rich tags for plain printing
                    text_plain = re.sub(r'\[/?.*?\]', '', str(text))
                    print(f"... {text_plain}")

            return DummyContext()

    class SimpleProgress:
         def __init__(self, console=None, disable=False, *args, **kwargs):
             self.console = console if console else SimpleConsole()
             self.disable = disable
             self.tasks = {}
             self.task_id_counter = 0

         def add_task(self, description, total=None, **kwargs):
              if self.disable: return None
              task_id = self.task_id_counter
              self.tasks[task_id] = {'description': description, 'total': total, 'completed': 0}
              self.task_id_counter += 1
              self.console.print(f"Starting task: {description}")
              return task_id

         def update(self, task_id, advance=None, description=None, **kwargs):
             if self.disable or task_id not in self.tasks: return
             task = self.tasks[task_id]
             if advance:
                 task['completed'] += advance
             if description:
                 task['description'] = description
             progress_percent = ""
             if task['total']:
                 percent = (task['completed'] / task['total']) * 100 if task['total'] > 0 else 0
                 progress_percent = f" ({percent:.1f}%)"
             # Limit frequency of updates for simple progress
             if random.random() < 0.1 or advance == task.get('total', 0): # Print every 10% or on completion
                self.console.print(f"Progress: {task['description']}{progress_percent} [{task['completed']}/{task['total']}]")


         def __enter__(self):
              return self
         def __exit__(self, exc_type, exc_val, exc_tb):
              if not self.disable:
                  self.console.print("Progress finished.")


# Configure console and progress bar
console = Console() if rich_available else SimpleConsole()
Progress = Progress if rich_available else SimpleProgress


# --- Constants ---
DEFAULT_MODEL = "gemini-1.5-flash-8b" # Or consider "gemini-1.5-pro-latest" for potentially higher quality
API_CALL_LIMIT_PER_MINUTE = 15 # Adjust based on Gemini model limits (Flash often has higher limits)
API_RETRY_COUNT = 3
INTERIM_SAVE_FREQUENCY = 5 # Save after every N points processed

# --- File Handling ---

def load_json_file(file_path: str) -> Optional[Dict]:
    """Load and parse JSON file, returning None on error."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
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
        return None # Indicate failure
    except FileNotFoundError:
        console.print(f"[bold red]Error: Input file not found at {file_path}[/bold red]")
        return None # Indicate failure
    except Exception as e:
        console.print(f"[bold red]Error loading JSON file: {e}[/bold red]")
        console.print(traceback.format_exc())
        return None # Indicate failure

def save_json_file(data: Dict, file_path: str) -> bool:
    """Save data to a JSON file, returning True on success, False on error."""
    try:
        # Ensure the directory exists before saving
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        console.print(f"[bold red]Error saving JSON file: {e}[/bold red]")
        console.print(f"Path: {file_path}")
        console.print(traceback.format_exc())
        return False

# --- JSON Fixing ---

def fix_json_string(json_str: str) -> str:
    """Attempt to fix common issues with malformed JSON responses from LLMs."""
    if not json_str or not json_str.strip():
        return '{}'

    # Remove markdown code block markers
    json_str = re.sub(r'^```json\s*', '', json_str.strip(), flags=re.IGNORECASE)
    json_str = re.sub(r'\s*```$', '', json_str)
    json_str = re.sub(r'^```\s*', '', json_str.strip()) # Handle plain ``` blocks too
    json_str = json_str.strip()

    # Find the first '{' and last '}'
    start_brace = json_str.find('{')
    end_brace = json_str.rfind('}')

    if start_brace == -1 or end_brace == -1 or start_brace >= end_brace:
        # If we can't find valid braces, return original cleaned string hoping it's just the content
        console.print(f"[yellow]Warning: Response doesn't seem to contain valid JSON braces after cleaning. Raw cleaned string: {json_str[:100]}...[/yellow]")
        # Attempt to wrap in a generic key if it's just plain text
        # This is heuristic - might need adjustment based on typical API errors
        if not json_str.startswith('"'): # Avoid double-quoting already quoted strings
             escaped_str = json.dumps(json_str) # Properly escape the string
        else:
             escaped_str = json_str # Assume it's already a valid JSON string literal

        # Heuristic: Assume the API failed to provide JSON structure and just gave text.
        # Let's try to wrap it in the *expected* structure for the calling function.
        # This requires knowing the context (intro vs point), which fix_json_string doesn't have.
        # Let's return the raw cleaned string and handle the wrapping in the API call function.
        return json_str # Return cleaned string, let caller handle wrapping if needed

    # Extract content between the first '{' and last '}'
    json_str = json_str[start_brace : end_brace + 1]

    # Remove trailing commas (before } or ]) - be careful not to break valid JSON
    # This regex is safer than the previous one
    json_str = re.sub(r'(?<=[}\]"\'\w]),\s*(?=[}\]])', '', json_str)

    # Basic brace balancing (less aggressive)
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
        console.print(f"[yellow]Warning: Added {open_braces - close_braces} closing braces.[/yellow]")
    elif close_braces > open_braces:
         console.print(f"[yellow]Warning: More closing braces ({close_braces}) than opening ({open_braces}). Proceeding cautiously.[/yellow]")


    return json_str

# --- Logging ---

def check_content_log_file(input_file_name: str, output_dir: Path) -> tuple[str, Dict, Set[str]]:
    """Check/create a log file for content generation, tracking processed points."""
    log_file_name = f"{Path(input_file_name).stem}_content_log.json"
    log_file_path = output_dir / log_file_name
    processed_points_set = set()

    if log_file_path.exists():
        console.print(f"Found existing content log file: {log_file_path}")
        try:
            log_data = load_json_file(str(log_file_path))
            # Basic validation of log structure
            if isinstance(log_data, dict) and isinstance(log_data.get("processed_points"), list) and isinstance(log_data.get("errors"), list):
                 processed_points_set = set(log_data["processed_points"])
                 console.print(f"Log file loaded successfully. {len(processed_points_set)} items previously processed.")
                 return str(log_file_path), log_data, processed_points_set
            else:
                 console.print("[yellow]Warning: Existing log file has unexpected structure. Creating new log.[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Warning: Error reading existing log file, creating new log: {e}[/yellow]")

    # Create new log structure if no valid log exists
    console.print("Creating new content log file.")
    log_data = {
        "input_file": input_file_name,
        "start_time": datetime.now().isoformat(),
        "processed_points": [], # List of strings like "p0-c0-intro", "p0-c0-s0-p0"
        "errors": [], # List of error detail dicts
        "api_calls": [], # List of API call attempt dicts
        "model_used": None # Will be set later
    }
    # Convert list to set for efficient lookup, will convert back on save
    processed_points_set = set(log_data["processed_points"])
    return str(log_file_path), log_data, processed_points_set

# --- Prompt Generation ---

def generate_intro_prompt(book_title: str, part_name: str, chapter_title: str, chapter_desc: str, outline_data: Dict) -> str:
    """Generates the prompt for writing a chapter introduction."""

    # Create a summary of the outline for context
    outline_summary = f"The chapter '{chapter_title}' within Part '{part_name}' covers the following sections:\n"
    for i, section in enumerate(outline_data.get('writing_sections', [])):
        outline_summary += f"{i+1}. {section.get('section_title', 'Untitled Section')}\n"
        # Optionally add first few points for more context:
        # points_preview = section.get('content_points_to_cover', [])[:2]
        # for point in points_preview:
        #     outline_summary += f"   - {point[:80]}...\n" # Truncate long points

    prompt = f"""You are an expert academic writer specializing in content for UPSC (Union Public Service Commission) aspirants in India. Your task is to write a compelling and informative introduction for a specific chapter in a book.

BOOK CONTEXT:
- Book Title: "{book_title}"
- Focus: India's International Relations for UPSC Aspirants

CHAPTER DETAILS:
- Part Name: "{part_name}"
- Chapter Title: "{chapter_title}"
- Chapter Description/Goal: "{chapter_desc}"

CHAPTER OUTLINE SUMMARY:
{outline_summary}

TASK:
Based on the provided context, chapter details, and outline summary, write an engaging introduction for this chapter.
- The introduction should clearly state the chapter's purpose and scope.
- It should briefly preview the key topics or sections that will be covered (referencing the outline summary).
- Set the stage for the reader, highlighting the importance of this chapter's content for understanding India's International Relations in the context of the UPSC exam.
- Maintain an academic, clear, and concise tone suitable for UPSC preparation material.
- Aim for a well-structured paragraph or two.

OUTPUT FORMAT:
Your *entire* response MUST be a single, valid JSON object containing only one key, "introduction_text", with the generated introduction as its string value.

Example JSON Output:
{{
  "introduction_text": "This chapter delves into the foundational concepts of foreign policy, examining how states formulate and execute their external strategies. We will explore the core objectives driving India's foreign policy, such as national security and economic prosperity, and analyze the key instruments employed, including diplomacy and economic measures. Understanding these elements is crucial for UPSC aspirants seeking a comprehensive grasp of India's role in the international arena."
}}

CRITICAL INSTRUCTIONS:
1. Respond ONLY with the valid JSON object as specified.
2. Do NOT include any introductory text, explanations, comments, or markdown formatting (like ```json) outside the JSON object itself.
3. Ensure the generated text directly addresses the task of writing the chapter introduction based *only* on the provided information.
"""
    return prompt


def generate_point_prompt(book_title: str, part_name: str, chapter_title: str, section_title: str, point_text: str) -> str:
    """Generates the prompt for elaborating on a specific content point."""

    prompt = f"""You are an expert academic writer specializing in content for UPSC (Union Public Service Commission) aspirants in India. Your task is to elaborate on a *single specific point* within a book chapter section.

BOOK CONTEXT:
- Book Title: "{book_title}"
- Focus: India's International Relations for UPSC Aspirants

CURRENT LOCATION IN BOOK:
- Part Name: "{part_name}"
- Chapter Title: "{chapter_title}"
- Section Title: "{section_title}"

SPECIFIC POINT TO ELABORATE ON:
"{point_text}"

TASK:
Write a detailed and informative paragraph (or more if necessary) that elaborates *only* on the specific point mentioned above.
- Assume this content will follow previous points and precede subsequent points within the section.
- Provide accurate, relevant information, analysis, examples, and context suitable for a UPSC aspirant studying India's International Relations.
- Ensure the generated content directly addresses the instruction given in the specific point.
- Maintain an academic, clear, and objective tone. Use precise language.
- Focus solely on elaborating the given point. Do not introduce unrelated topics or summarize the section/chapter.

OUTPUT FORMAT:
Your *entire* response MUST be a single, valid JSON object containing only one key, "point_content", with the generated elaboration as its string value.

Example JSON Output (if the point was "Define foreign policy..."):
{{
  "point_content": "Foreign policy can be defined as the sum total of principles, strategies, and actions adopted by a state to safeguard its national interests and achieve its objectives in the international arena. For UPSC aspirants, understanding foreign policy is crucial as it represents the external dimension of a nation's governance, encompassing its interactions with other states, international organizations, and non-state actors. It is a dynamic process shaped by both domestic compulsions and the global geopolitical environment, involving decisions on diplomacy, defense, trade, and international cooperation."
}}

CRITICAL INSTRUCTIONS:
1. Respond ONLY with the valid JSON object as specified.
2. Do NOT include any introductory text, explanations, comments, or markdown formatting (like ```json) outside the JSON object itself.
3. Ensure the generated text directly and exclusively elaborates on the single `SPECIFIC POINT TO ELABORATE ON` provided above.
"""
    return prompt


# --- Gemini API Interaction ---

def test_gemini_api(api_key: str, model_name: str = DEFAULT_MODEL):
    """Quick test of the Gemini API with a simple prompt, expecting JSON."""
    simple_prompt = "Return a JSON object with one key 'status' and value 'ok'."
    try:
        console.print(f"Testing Gemini API connection with model: [cyan]{model_name}[/cyan]...")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        # Specify JSON response type if supported and desired
        generation_config = genai.types.GenerationConfig(
             # response_mime_type="application/json" # Enable if model reliably supports it
             temperature=0.1 # Low temp for predictable test
        )
        response = model.generate_content(simple_prompt, generation_config=generation_config)
        response_text = response.text

        console.print(f"Test response received (raw snippet): {response_text[:100]}...")
        fixed_text = fix_json_string(response_text)
        data = json.loads(fixed_text)
        if isinstance(data, dict) and data.get("status") == "ok":
            console.print("[green]API test successful (parsed expected JSON response).[/green]")
            return True
        else:
            console.print(f"[yellow]API test warning: Response received but content unexpected after parse: {data}[/yellow]")
            return True # API call worked, even if content wasn't perfect JSON 'ok'

    except json.JSONDecodeError as json_err:
        console.print(f"[yellow]API test warning: Could not parse test response as JSON: {json_err}[/yellow]")
        console.print(f"Raw response: {response_text}")
        console.print("[yellow]API call likely succeeded, but response wasn't the expected simple JSON. Check model compatibility/output.[/yellow]")
        return True # API call itself likely worked.
    except Exception as e:
        console.print(f"[bold red]API test failed for model {model_name}: {e}[/bold red]")
        if "API key not valid" in str(e):
             console.print("[bold red]Check if your GOOGLE_API_KEY is correct and valid.[/bold red]")
        elif "billing" in str(e).lower():
             console.print("[bold red]Check if billing is enabled for your Google Cloud project.[/bold red]")
        else:
             console.print(traceback.format_exc())
        return False

def call_gemini_api_for_content(
    prompt: str,
    api_key: str,
    log_data: Dict,
    model_name: str,
    expected_key: str, # Key expected in the response JSON (e.g., "introduction_text")
    retry_count: int = API_RETRY_COUNT,
    item_key_for_log: str = "unknown_item", # e.g., "p0-c1-intro" or "p0-c1-s2-p3"
) -> Optional[Dict]:
    """
    Calls the Gemini API, expecting a JSON response with a specific key,
    handles retries, basic JSON fixing, and logging. Returns the parsed JSON dict on success, None on failure.
    """
    genai.configure(api_key=api_key)
    request_time = datetime.now().isoformat()

    # More appropriate settings for creative/generative writing
    generation_config = {
        "temperature": 0.75,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 4096, # Adjust as needed for content length
        # "response_mime_type": "application/json", # Enable cautiously
    }

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
    ]

    max_attempts = retry_count + 1

    for attempt in range(max_attempts):
        current_attempt_num = attempt + 1
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "item_key": item_key_for_log,
            "model": model_name,
            "attempt": current_attempt_num,
            "status": "pending",
            "prompt_length": len(prompt),
            "error": None,
            "response_snippet": None,
        }

        try:
            # --- Backoff ---
            if attempt > 0:
                backoff_time = min(30, (2 ** attempt) + random.uniform(0, 1))
                console.print(f"[yellow]Retrying '{item_key_for_log}' (attempt {current_attempt_num}/{max_attempts}) after {backoff_time:.2f}s delay...[/yellow]")
                time.sleep(backoff_time)

            # --- API Call ---
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            # Use a status spinner for the API call itself
            status_msg = f"API Call {item_key_for_log} (Attempt {current_attempt_num}/{max_attempts})"
            with console.status(f"[bold blue]{status_msg}[/]", spinner="dots") as status:
                response = model.generate_content(prompt)

            # --- Response Processing ---
            response_text = ""
            try:
                # Handle potential blocking or empty responses
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    reason = response.prompt_feedback.block_reason
                    block_details = response.prompt_feedback.block_reason_message if hasattr(response.prompt_feedback, 'block_reason_message') else "No details provided."
                    raise Exception(f"API call blocked for item '{item_key_for_log}'. Reason: {reason}. Details: {block_details}")

                # Extract text content safely
                if response.parts:
                    response_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                elif hasattr(response, 'text'):
                    response_text = response.text
                else: # Fallback if structure is unexpected
                     response_text = str(response)

                if not response_text or not response_text.strip():
                     raise Exception(f"API returned an empty response for item '{item_key_for_log}'.")

                log_entry["response_snippet"] = response_text[:200].replace('\n', ' ') # Log snippet

                # --- JSON Parsing and Validation ---
                fixed_json_str = fix_json_string(response_text)

                try:
                    parsed_response = json.loads(fixed_json_str)
                    if not isinstance(parsed_response, dict):
                         raise json.JSONDecodeError(f"Parsed JSON is not a dictionary (type: {type(parsed_response)})", fixed_json_str, 0)

                    # Check if the expected key exists
                    if expected_key in parsed_response:
                        log_entry.update({"status": "success_parsed_json", "response_length": len(str(parsed_response.get(expected_key)))})
                        log_data["api_calls"].append(log_entry)
                        gc.collect()
                        return parsed_response # SUCCESS
                    else:
                        # If expected key is missing, but it *is* JSON, treat as error but log structure
                        error_msg = f"Parsed JSON for '{item_key_for_log}', but expected key '{expected_key}' is missing. Found keys: {list(parsed_response.keys())}"
                        raise json.JSONDecodeError(error_msg, fixed_json_str, 0)

                except json.JSONDecodeError as e:
                    error_msg = f"JSON parsing error for '{item_key_for_log}' on attempt {current_attempt_num}: {e}"
                    console.print(f"[red]JSON PARSING ERROR: {error_msg}[/red]")
                    console.print(f"--- Fixed Response Snippet ---\n{fixed_json_str[:500]}\n----------------------------")
                    log_entry.update({"status": "json_error_after_fix", "error": str(e), "raw_response_snippet": fixed_json_str[:200]})
                    # Heuristic: If parsing fails, maybe the API just returned the raw text?
                    # Let's wrap it in the expected structure IF it looks like plain text
                    if not fixed_json_str.strip().startswith('{'):
                         console.print("[yellow]Attempting to wrap raw text response in expected JSON structure...[/yellow]")
                         try:
                            wrapped_response = {expected_key: fixed_json_str.strip()}
                            log_entry.update({"status": "success_heuristic_wrap", "response_length": len(fixed_json_str.strip())})
                            log_data["api_calls"].append(log_entry)
                            gc.collect()
                            return wrapped_response # SUCCESS (heuristically wrapped)
                         except Exception as wrap_err:
                              console.print(f"[red]Failed to wrap raw text heuristically: {wrap_err}[/red]")
                              # Fall through to retry/fail logic

                    if current_attempt_num < max_attempts:
                         console.print("[yellow]Proceeding to next retry attempt...[/yellow]")
                         log_data["api_calls"].append(log_entry) # Log failed attempt
                         continue # Go to next attempt
                    else:
                         console.print("[red]JSON parsing failed on final attempt.[/red]")
                         log_entry["status"] = "json_error_final_attempt"
                         # Do not return here, break and handle failure below
                         break # Exit retry loop

            except Exception as proc_err:
                 # Catch errors from block reason or empty response checks
                 error_msg = f"Response processing error for '{item_key_for_log}' on attempt {current_attempt_num}: {proc_err}"
                 console.print(f"[red]RESPONSE PROCESSING ERROR: {error_msg}[/red]")
                 log_entry.update({"status": "response_processing_error", "error": str(proc_err)})
                 if current_attempt_num < max_attempts:
                     log_data["api_calls"].append(log_entry) # Log failed attempt
                     continue # Go to next attempt
                 else:
                     log_entry["status"] = "response_error_final_attempt"
                     break # Exit retry loop

        except Exception as api_err:
            # Handle broader API call errors (network, config, etc.)
            error_msg = f"API call exception for '{item_key_for_log}' on attempt {current_attempt_num} using {model_name}: {api_err}"
            console.print(f"[bold red]API ERROR: {error_msg}[/bold red]")
            # console.print(traceback.format_exc()) # Verbose
            log_entry.update({"status": "api_exception", "error": str(api_err)})
            if current_attempt_num < max_attempts:
                log_data["api_calls"].append(log_entry) # Log failed attempt
                continue # Go to next attempt
            else:
                log_entry["status"] = "api_exception_final_attempt"
                break # Exit retry loop

    # --- Failure Fallback ---
    console.print(f"[bold red]All {max_attempts} API attempts failed for '{item_key_for_log}'. Returning None.[/bold red]")
    if log_entry.get("status") == "pending": # Should have been updated, but safety check
         log_entry["status"] = "failed_all_attempts"
         log_entry["error"] = log_entry.get("error", "Unknown error after all retries")

    # Ensure the final failed attempt is logged if loop was exited via 'break'
    is_final_status_logged = any(
        call.get("item_key") == item_key_for_log and call.get("attempt") == max_attempts and call.get("status") == log_entry["status"]
        for call in log_data.get("api_calls", [])
    )
    if not is_final_status_logged:
         log_data["api_calls"].append(log_entry) # Log the final failed state

    # Add to main error log for this specific item
    is_error_logged = any(err.get("item_key") == item_key_for_log for err in log_data.get("errors", []))
    if not is_error_logged:
        log_data["errors"].append({
            "timestamp": log_entry["timestamp"],
            "item_key": item_key_for_log,
            "error": log_entry.get("error", "Failure after retries"),
            "status": log_entry["status"],
            "model_used": model_name,
            "final_attempt": max_attempts
        })

    gc.collect()
    return None # Indicate failure


# --- Main Processing Logic ---

def process_outlined_json(input_file: str, api_key: str, output_dir: Path, model_name_arg: str):
    """
    Processes the outlined JSON file, generating content for each point using Gemini API.
    """
    console.print(f"Starting content generation for input file: [cyan]{input_file}[/cyan]")
    input_data = load_json_file(input_file)
    if input_data is None:
        console.print("[bold red]Failed to load input file. Exiting.[/bold red]")
        sys.exit(1)

    log_file_path, log_data, processed_points_set = check_content_log_file(input_file, output_dir)
    log_data["model_used"] = model_name_arg # Store model name in log

    book_title = input_data.get('bookTitle', 'Unknown Book')
    console.print(f"Processing book: [cyan]{book_title}[/cyan]")
    console.print(f"Using model: [cyan]{model_name_arg}[/cyan]")
    console.print(f"Resuming from log. {len(processed_points_set)} items previously processed.")

    # Calculate total points for progress bar
    total_points_to_process = 0
    items_to_process_list = [] # Store tuples (part_idx, chapter_idx, type, section_idx, point_idx)
    for p_idx, part in enumerate(input_data.get('parts', [])):
        for c_idx, chapter in enumerate(part.get('chapters', [])):
            if 'generated_outline' in chapter and isinstance(chapter['generated_outline'], dict):
                # Add 1 for the introduction
                intro_key = f"p{p_idx}-c{c_idx}-intro"
                if intro_key not in processed_points_set:
                    total_points_to_process += 1
                    items_to_process_list.append({'type': 'intro', 'key': intro_key, 'p_idx': p_idx, 'c_idx': c_idx})

                # Add points from sections
                sections = chapter['generated_outline'].get('writing_sections', [])
                if isinstance(sections, list):
                     for s_idx, section in enumerate(sections):
                          points = section.get('content_points_to_cover', [])
                          if isinstance(points, list):
                             for pt_idx, point_text in enumerate(points):
                                 point_key = f"p{p_idx}-c{c_idx}-s{s_idx}-p{pt_idx}"
                                 if point_key not in processed_points_set:
                                     total_points_to_process += 1
                                     items_to_process_list.append({
                                         'type': 'point', 'key': point_key, 'p_idx': p_idx, 'c_idx': c_idx,
                                         's_idx': s_idx, 'pt_idx': pt_idx, 'point_text': point_text,
                                         'section_title': section.get('section_title', 'Unknown Section')
                                     })
            else:
                console.print(f"[yellow]Warning: Skipping Chapter {p_idx+1}-{c_idx+1} ('{chapter.get('title', 'N/A')[:30]}...') - Missing 'generated_outline'.[/yellow]")


    if total_points_to_process == 0:
        console.print("[bold green]No new content points or introductions found to process based on the log file.[/bold green]")
        console.print("If this is unexpected, check the input file structure and the log file.")
        return # Nothing to do

    console.print(f"Total items (intros + points) to process: {total_points_to_process}")

    output_file_stem = Path(input_file).stem
    interim_filename = output_dir / f"{output_file_stem}_content_interim.json"
    final_filename = output_dir / f"{output_file_stem}_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    final_log_filename = Path(log_file_path)

    console.print(f"Output will be saved incrementally to: {interim_filename}")
    console.print(f"Final output will be named like: {output_file_stem}_content_YYYYMMDD_HHMMSS.json")
    console.print(f"Log file: {final_log_filename}")

    api_call_timestamps: Deque[float] = deque(maxlen=API_CALL_LIMIT_PER_MINUTE) # Track timestamps for rate limiting
    processed_count_session = 0 # Counter for interim saving

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("({task.completed}/{task.total})"),
        TimeRemainingColumn(),
        TimeElapsedColumn(),
        console=console,
        disable=not rich_available or total_points_to_process == 0 # Disable if rich not available or nothing to process
    ) as progress:

        task_id = progress.add_task(f"Generating content for [cyan]{book_title}[/cyan]", total=total_points_to_process)

        for item_info in items_to_process_list:
            item_key = item_info['key']
            p_idx, c_idx = item_info['p_idx'], item_info['c_idx']

            # --- Rate Limiting ---
            now = time.monotonic()
            while len(api_call_timestamps) >= API_CALL_LIMIT_PER_MINUTE:
                time_since_oldest = now - api_call_timestamps[0]
                if time_since_oldest < 60.0:
                    wait_time = 60.0 - time_since_oldest
                    console.print(f"[yellow]Rate limit (~{API_CALL_LIMIT_PER_MINUTE}/min) potentially hit. Waiting for {wait_time:.2f}s...[/yellow]")
                    time.sleep(wait_time)
                    now = time.monotonic() # Update time after waiting
                else:
                    api_call_timestamps.popleft() # Remove old timestamp

            # Add small random delay to distribute calls
            random_delay = random.uniform(0.5, 2.0)
            # console.print(f"Applying random delay of {random_delay:.2f}s...") # Can be noisy
            time.sleep(random_delay)
            # --- End Rate Limiting ---


            part = input_data['parts'][p_idx]
            chapter = part['chapters'][c_idx]
            part_name = part.get('name', f'Part {p_idx + 1}')
            chapter_title = chapter.get('title', f'Chapter {c_idx + 1}')
            chapter_desc = chapter.get('description', '')
            outline_data = chapter.get('generated_outline', {})

            # Ensure generated_content structure exists
            if 'generated_content' not in chapter:
                chapter['generated_content'] = {'introduction': None, 'sections': []}

            api_response = None
            try:
                if item_info['type'] == 'intro':
                    progress.update(task_id, description=f"Intro P{p_idx+1}-Ch{c_idx+1}")
                    console.print(f"\nProcessing: [bold]Introduction[/] for P{p_idx+1}-Ch{c_idx+1} ('{chapter_title[:30]}...')")
                    prompt = generate_intro_prompt(book_title, part_name, chapter_title, chapter_desc, outline_data)
                    api_response = call_gemini_api_for_content(prompt, api_key, log_data, model_name_arg, expected_key="introduction_text", item_key_for_log=item_key)

                    if api_response and "introduction_text" in api_response:
                        chapter['generated_content']['introduction'] = api_response["introduction_text"]
                        console.print(f"[green] -> Introduction generated successfully.[/green]")
                    else:
                         chapter['generated_content']['introduction'] = f"ERROR: Failed to generate content for introduction ({item_key}). Check log."
                         console.print(f"[bold red] -> Failed to generate introduction. See log.[/bold red]")

                elif item_info['type'] == 'point':
                    s_idx, pt_idx = item_info['s_idx'], item_info['pt_idx']
                    section_title = item_info['section_title']
                    point_text = item_info['point_text']

                    progress.update(task_id, description=f"Point P{p_idx+1}-Ch{c_idx+1}-S{s_idx+1}-Pt{pt_idx+1}")
                    console.print(f"\nProcessing: Point {pt_idx+1}/{len(outline_data['writing_sections'][s_idx]['content_points_to_cover'])} in Section {s_idx+1} ('{section_title[:30]}...')")
                    console.print(f"   Point: '{point_text[:100]}...'")

                    prompt = generate_point_prompt(book_title, part_name, chapter_title, section_title, point_text)
                    api_response = call_gemini_api_for_content(prompt, api_key, log_data, model_name_arg, expected_key="point_content", item_key_for_log=item_key)

                    # Ensure section/point structure exists in generated_content
                    while len(chapter['generated_content']['sections']) <= s_idx:
                        chapter['generated_content']['sections'].append({'title': 'Placeholder Title', 'points': []})
                    if chapter['generated_content']['sections'][s_idx]['title'] == 'Placeholder Title':
                         chapter['generated_content']['sections'][s_idx]['title'] = section_title

                    while len(chapter['generated_content']['sections'][s_idx]['points']) <= pt_idx:
                         chapter['generated_content']['sections'][s_idx]['points'].append({'original_point': None, 'content': None})

                    chapter['generated_content']['sections'][s_idx]['points'][pt_idx]['original_point'] = point_text
                    if api_response and "point_content" in api_response:
                        chapter['generated_content']['sections'][s_idx]['points'][pt_idx]['content'] = api_response["point_content"]
                        console.print(f"[green] -> Point content generated successfully.[/green]")
                    else:
                        chapter['generated_content']['sections'][s_idx]['points'][pt_idx]['content'] = f"ERROR: Failed to generate content for point ({item_key}). Check log."
                        console.print(f"[bold red] -> Failed to generate point content. See log.[/bold red]")

                # --- Post-processing for the item ---
                api_call_timestamps.append(time.monotonic()) # Add timestamp after successful call attempt
                processed_points_set.add(item_key)
                log_data["processed_points"] = sorted(list(processed_points_set)) # Keep log list sorted
                processed_count_session += 1
                progress.update(task_id, advance=1)

                # --- Incremental Saving ---
                if processed_count_session % INTERIM_SAVE_FREQUENCY == 0:
                    console.print(f"[dim]Saving interim progress ({processed_count_session} items processed this session)...[/dim]")
                    if not save_json_file(input_data, str(interim_filename)):
                         console.print("[bold red]FATAL: Failed to save interim data. Exiting to prevent data loss.[/bold red]")
                         sys.exit(1)
                    if not save_json_file(log_data, str(final_log_filename)):
                         console.print("[bold red]Warning: Failed to save log file incrementally.[/bold red]") # Non-fatal

                gc.collect()

            except KeyboardInterrupt:
                 console.print("\n[bold yellow]Keyboard interrupt detected. Saving progress before exiting...[/bold yellow]")
                 save_json_file(input_data, str(interim_filename))
                 log_data["processed_points"] = sorted(list(processed_points_set))
                 save_json_file(log_data, str(final_log_filename))
                 console.print("Progress saved. Exiting.")
                 sys.exit(0)
            except Exception as e:
                 console.print(f"[bold red]An unexpected error occurred processing item {item_key}: {e}[/bold red]")
                 console.print(traceback.format_exc())
                 # Log this major error
                 log_data["errors"].append({
                     "timestamp": datetime.now().isoformat(),
                     "item_key": item_key,
                     "error": f"Unexpected loop error: {e}",
                     "traceback": traceback.format_exc(),
                     "status": "unexpected_error",
                     "model_used": model_name_arg
                 })
                 # Attempt to save progress despite error
                 save_json_file(input_data, str(interim_filename))
                 log_data["processed_points"] = sorted(list(processed_points_set))
                 save_json_file(log_data, str(final_log_filename))
                 # Decide whether to continue or exit? For now, let's try to continue.
                 console.print("[yellow]Attempting to continue processing next item...[/yellow]")
                 # Mark the current item as processed to avoid retrying it in this run
                 if item_key not in processed_points_set:
                     processed_points_set.add(item_key)
                     log_data["processed_points"] = sorted(list(processed_points_set))
                 progress.update(task_id, advance=1) # Advance progress bar even on error to avoid stall

    # --- Finalization ---
    console.print("\n[bold green]=== Content Generation Complete ===[/bold green]")

    # Final save - rename interim to final
    try:
        final_save_path = Path(final_filename)
        interim_path = Path(interim_filename)
        if interim_path.exists():
             interim_path.rename(final_save_path)
             console.print(f"Final content saved to: [link=file://{os.path.abspath(final_save_path)}]{final_save_path}[/link]")
        else:
             # If interim somehow doesn't exist, save directly to final (shouldn't happen often)
              if not save_json_file(input_data, str(final_save_path)):
                   console.print("[bold red]Error saving final output file directly.[/bold red]")
              else:
                   console.print(f"Final content saved to: [link=file://{os.path.abspath(final_save_path)}]{final_save_path}[/link]")

    except Exception as e:
        console.print(f"[bold red]Error renaming interim file to final output file: {e}[/bold red]")
        console.print(f"Interim data might still be available at: {interim_filename}")

    log_data["end_time"] = datetime.now().isoformat()
    log_data["total_items_processed_in_log"] = len(processed_points_set)
    # Calculate errors more accurately from the log's error list
    final_errors = [e for e in log_data.get("errors", []) if e.get("status") != "resolved"] # Example filter if resolution status is added
    log_data["items_with_final_errors"] = len(final_errors)

    if not save_json_file(log_data, str(final_log_filename)):
         console.print("[bold red]Error saving final log file.[/bold red]")
    else:
         console.print(f"Detailed log saved to: [link=file://{os.path.abspath(final_log_filename)}]{final_log_filename}[/link]")

    if log_data["items_with_final_errors"] > 0:
         console.print(f"[bold red]Note: {log_data['items_with_final_errors']} items encountered errors during generation. Check the log file for details.[/bold red]")

    gc.collect()


# --- Main Execution ---
def main():
    print(f"\n--- Script Execution Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    # print(f"Current Directory: {os.getcwd()}") # Less critical now

    try:
        load_dotenv()
        # print("Attempted to load environment variables from .env file.")
    except Exception as e:
        print(f"Could not load .env file (this is optional): {e}")

    parser = argparse.ArgumentParser(description='Generate chapter content using Google Gemini API based on an outlined JSON.')
    parser.add_argument('--input_file', type=str, required=True, help='Path to the input JSON file containing book structure and generated outlines.')
    parser.add_argument('--output_dir', type=str, default='results/Content', help='Directory to save output content JSON and log files (default: results/Content)')
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL, help=f'Name of the Gemini model to use (default: {DEFAULT_MODEL})')
    parser.add_argument('--test', action='store_true', help='Run a quick API test before processing.')

    args = parser.parse_args()

    console.print(f"Arguments received: input_file='{args.input_file}', output_dir='{args.output_dir}', model='{args.model}', test={args.test}")

    output_dir = Path(args.output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        # console.print(f"Output directory ensured: {output_dir.resolve()}")
    except Exception as e:
        console.print(f"[bold red]Fatal Error: Could not create output directory '{output_dir}'. Please check permissions. Error: {e}[/bold red]")
        sys.exit(1)

    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        console.print("[bold red]Fatal Error: GOOGLE_API_KEY not found in environment variables or .env file.[/bold red]")
        console.print("Please set the GOOGLE_API_KEY environment variable or create a .env file.")
        sys.exit(1)
    else:
        # console.print(f"Found API key (starts with: {api_key[:5]}..., ends with: ...{api_key[-4:]})")
        pass

    if args.test:
        console.print("\n--- Running API Test ---")
        if not test_gemini_api(api_key, model_name=args.model):
            console.print("[bold red]API test failed. Exiting. Please check your API key, billing status, model name, and internet connection.[/bold red]")
            sys.exit(1)
        console.print("--- API Test Complete ---")

    input_file_path = Path(args.input_file)
    if not input_file_path.is_file():
         console.print(f"[bold red]Fatal Error: Input file not found at '{args.input_file}'[/bold red]")
         sys.exit(1)
    # else:
         # print(f"Input file found: {args.input_file}")

    console.print("\n--- Starting Content Generation Processing ---")
    try:
        process_outlined_json(
            input_file=str(input_file_path),
            api_key=api_key,
            output_dir=output_dir,
            model_name_arg=args.model
        )
        console.print("\n--- Script Execution Finished ---")
    except KeyboardInterrupt:
        # Already handled in process_outlined_json, but catch here just in case
        console.print("\n[bold yellow]Process interrupted by user (main block). Exiting.[/bold yellow]")
        sys.exit(0)
    except SystemExit as e:
         # Raised by sys.exit() calls within the script
         console.print(f"\n[bold red]Exiting due to error (Code: {e.code}).[/bold red]")
         sys.exit(e.code)
    except Exception as e:
        console.print(f"\n[bold red]An unexpected critical error occurred outside the main processing loop:[/bold red]")
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()