import json
import os
import google.generativeai as genai
import argparse
import time
import random
import gc
from typing import Dict, List, Any, Set, Optional
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import sys
import traceback
import re
from collections import deque
from decimal import Decimal # For accurate sorting of numbers like 1.1, 1.10, 1.2

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
            message = re.sub(r'\[/?.*?\]', '', str(message)) # Basic removal of rich tags
            print(message)

        def status(self, message): # Keep dummy status for compatibility if called elsewhere
            class DummyContext:
                def __enter__(self): return self
                def __exit__(self, exc_type, exc_val, exc_tb): pass
                def update(self, text): pass # No op
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

         def update(self, task_id, advance=None, description=None, total=None, **kwargs):
             if self.disable or task_id not in self.tasks: return
             task = self.tasks[task_id]
             if advance: task['completed'] = min(task.get('total', task['completed'] + advance), task['completed'] + advance) # Ensure completed doesn't exceed total
             if description: task['description'] = description
             if total is not None: task['total'] = total # Allow updating total if needed

             progress_percent = ""
             current_total = task.get('total')
             if current_total:
                 percent = (task['completed'] / current_total) * 100 if current_total > 0 else 0
                 progress_percent = f" ({percent:.1f}%)"

             # Limit frequency of updates for simple progress
             if random.random() < 0.1 or task['completed'] == current_total : # Print roughly every 10% or on completion
                self.console.print(f"Progress: {task['description']}{progress_percent} [{task['completed']}/{current_total or '?'}]")


         def __enter__(self): return self
         def __exit__(self, exc_type, exc_val, exc_tb):
              if not self.disable: self.console.print("Progress finished.")

# Configure console and progress bar
console = Console() if rich_available else SimpleConsole()
Progress = Progress if rich_available else SimpleProgress

# --- Constants ---
DEFAULT_MODEL = "gemini-1.5-flash-8b" # Fallback default
API_CALL_LIMIT_PER_MINUTE = 15 # Adjust based on Gemini model limits
API_RETRY_COUNT = 3
INTERIM_SAVE_FREQUENCY = 5 # Save after every N items processed
MAX_CONTEXT_SUMMARY_LENGTH = 2000 # Limit for context summary sent to API

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
        try: # Try to show context
            with open(file_path, 'r', encoding='utf-8') as file_check:
                content = file_check.read()
                if hasattr(e, 'lineno') and hasattr(e, 'colno'):
                    line, col = e.lineno, e.colno
                    lines = content.splitlines()
                    if 0 < line <= len(lines):
                        console.print(f"Problem near line {line}, column {col}:")
                        console.print(lines[line-1])
                        console.print(" " * (col - 1) + "^")
        except Exception as read_err:
             console.print(f"Could not read file to show error location: {read_err}")
        return None
    except FileNotFoundError:
        console.print(f"[bold red]Error: Input file not found at {file_path}[/bold red]")
        return None
    except Exception as e:
        console.print(f"[bold red]Error loading JSON file: {e}[/bold red]")
        console.print(traceback.format_exc())
        return None

def save_json_file(data: Dict, file_path: str) -> bool:
    """Save data to a JSON file, returning True on success, False on error."""
    try:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        console.print(f"[bold red]Error saving JSON file: {e}[/bold red]")
        console.print(f"Path: {file_path}")
        return False

# --- JSON Fixing ---
def fix_json_string(json_str: str) -> str:
    """Attempt to fix common issues with malformed JSON responses from LLMs."""
    if not json_str or not json_str.strip(): return '{}'
    # Remove markdown code fences
    json_str = re.sub(r'^```json\s*', '', json_str.strip(), flags=re.IGNORECASE)
    json_str = re.sub(r'\s*```$', '', json_str)
    json_str = re.sub(r'^```\s*', '', json_str.strip()) # Handle case with no 'json' identifier
    json_str = json_str.strip()
    # Ensure it starts/ends with braces (basic check)
    start_brace = json_str.find('{')
    end_brace = json_str.rfind('}')
    if start_brace == -1 or end_brace == -1 or start_brace >= end_brace:
        return json_str # Return cleaned string, let caller handle wrapping or parsing error
    json_str = json_str[start_brace : end_brace + 1]
    # Remove trailing commas before closing braces/brackets
    json_str = re.sub(r'(?<=[}\]"\'\w\d]),\s*(?=[}\]])', '', json_str)
    # Basic brace balancing (add missing closing braces)
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
    return json_str

# --- Logging ---
def check_content_log_file(input_file_name: str, output_dir: Path) -> tuple[str, Dict, Set[str]]:
    """Check/create a log file for content generation, tracking processed points."""
    log_file_name = f"{Path(input_file_name).stem}_content_log.json"
    log_file_path = output_dir / log_file_name
    processed_points_set = set()
    log_data = {}

    if log_file_path.exists():
        console.print(f"Found existing content log file: {log_file_path}")
        log_data = load_json_file(str(log_file_path))
        if isinstance(log_data, dict) and isinstance(log_data.get("processed_points"), list):
             processed_points_set = set(log_data["processed_points"])
             console.print(f"Log file loaded. {len(processed_points_set)} items previously processed.")
             log_data.setdefault("errors", [])
             log_data.setdefault("api_calls", [])
             return str(log_file_path), log_data, processed_points_set
        else:
             console.print("[yellow]Warning: Existing log file has unexpected structure or failed to load. Creating new log.[/yellow]")
             log_data = {}

    console.print("Creating new content log file.")
    log_data = {
        "input_file": input_file_name,
        "start_time": datetime.now().isoformat(),
        "processed_points": [], # List of unique item keys (e.g., "p0_ch1_intro", "p0_ch1_pt0")
        "errors": [],
        "api_calls": [],
        "model_used": None
    }
    processed_points_set = set()
    return str(log_file_path), log_data, processed_points_set

# --- Prompt Generation ---
def generate_chapter_intro_prompt(book_title: str, part_name: str, chapter_title: str, chapter_points: List[str]) -> str:
    """Generates the prompt for writing an introduction for a chapter (derived from section_title)."""
    points_summary = "\n".join(f"- {point}" for point in chapter_points)
    prompt = f"""You are an expert academic writer specializing in content for UPSC (Union Public Service Commission) aspirants in India. Your task is to write a compelling and informative introduction for a specific chapter in a book.

BOOK CONTEXT: - Book Title: "{book_title}" - Focus: India's International Relations for UPSC Aspirants
CHAPTER DETAILS: - Part Name: "{part_name}" - Chapter Title: "{chapter_title}"
POINTS COVERED IN THIS CHAPTER:
{points_summary}

TASK: Based on the provided context, chapter title, and the summary of points to be covered, write an engaging introduction for this specific chapter.
- The introduction should clearly state the chapter's purpose and scope, as indicated by its title and the points it will cover.
- It should briefly preview the key topics (points) that will be discussed within this chapter.
- Set the stage for the reader, highlighting the importance of this chapter's content for understanding India's International Relations in the context of the UPSC exam.
- Maintain an academic, clear, and concise tone suitable for UPSC preparation material.
- Aim for a well-structured paragraph or two.
- This introduction will be labeled as item '.1' within the chapter.

OUTPUT FORMAT: Your *entire* response MUST be a single, valid JSON object containing only one key, "introduction_text", with the generated introduction as its string value.
Example JSON Output:
{{
  "introduction_text": "This chapter focuses on defining foreign policy..."
}}

CRITICAL INSTRUCTIONS: 1. Respond ONLY with the valid JSON object. 2. Do NOT include any text outside the JSON object. 3. Ensure the text addresses the task based *only* on the provided information.
"""
    return prompt


def generate_point_prompt(
    book_title: str,
    part_name: str,
    chapter_title: str,
    point_text: str,
    point_number: str,
    previous_content_summary: Optional[str] = None
) -> str:
    """Generates the prompt for elaborating on a specific content point within a numbered chapter, providing preceding context."""

    context_section = ""
    if previous_content_summary and previous_content_summary.strip():
        summary_trimmed = previous_content_summary.strip()
        if len(summary_trimmed) > MAX_CONTEXT_SUMMARY_LENGTH:
             summary_trimmed = "... (trimmed) ..." + summary_trimmed[-MAX_CONTEXT_SUMMARY_LENGTH:]

        context_section = f"""
PRECEDING CONTENT SUMMARY (From item {point_number.split('.')[0]}.1 up to the previous item in this chapter):
---
{summary_trimmed}
---
"""

    prompt = f"""You are an expert academic writer specializing in content for UPSC (Union Public Service Commission) aspirants in India. Your task is to elaborate on a *single specific point* within a book chapter, ensuring coherence with preceding text.

BOOK CONTEXT: - Book Title: "{book_title}" - Focus: India's International Relations for UPSC Aspirants
CURRENT LOCATION IN BOOK: - Part Name: "{part_name}" - Chapter Title: "{chapter_title}" - Current Item Number: {point_number}
SPECIFIC POINT TO ELABORATE ON: "{point_text}"
{context_section}
TASK: Write a detailed and informative paragraph (or more if necessary) that elaborates *only* on the specific point mentioned above ({point_number}).
- **CRITICAL INSTRUCTION:** Read the 'PRECEDING CONTENT SUMMARY' provided above (if any). **DO NOT REPEAT** information already covered in that summary. Instead, build upon that context and focus *exclusively* on providing new, relevant details, analysis, and examples for the `SPECIFIC POINT TO ELABORATE ON`.
- Assume this content follows the preceding items and precedes subsequent points within the chapter.
- Provide accurate, relevant information suitable for a UPSC aspirant.
- Maintain an academic, clear, and objective tone. Use precise language.

OUTPUT FORMAT: Your *entire* response MUST be a single, valid JSON object containing only one key, "point_content", with the generated elaboration as its string value.
Example JSON Output (if the point was "Define foreign policy..."):
{{
  "point_content": "Foreign policy can be defined as the sum total of principles..."
}}

CRITICAL INSTRUCTIONS: 1. Respond ONLY with the valid JSON object. 2. Do NOT include any text outside the JSON object. 3. Ensure the generated text directly and exclusively elaborates on the single `SPECIFIC POINT TO ELABORATE ON`, avoiding repetition from the provided context summary.
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
        generation_config = genai.types.GenerationConfig(temperature=0.1)
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
            return True # API call worked
    except json.JSONDecodeError as json_err:
        console.print(f"[yellow]API test warning: Could not parse test response as JSON: {json_err}[/yellow]")
        console.print(f"Raw response: {response_text}")
        return True # API call likely worked
    except Exception as e:
        console.print(f"[bold red]API test failed for model {model_name}: {e}[/bold red]")
        if "API key not valid" in str(e): console.print("[bold red]Check GOOGLE_API_KEY.[/bold red]")
        elif "billing" in str(e).lower(): console.print("[bold red]Check billing status.[/bold red]")
        return False


def call_gemini_api_for_content(
    prompt: str,
    api_key: str,
    log_data: Dict,
    model_name: str,
    expected_key: str,
    retry_count: int = API_RETRY_COUNT,
    item_key_for_log: str = "unknown_item",
) -> Optional[Dict]:
    """
    Calls the Gemini API, expecting a JSON response with a specific key.
    Handles retries, basic JSON fixing, and logging. Returns parsed JSON on success, None on failure.
    """
    genai.configure(api_key=api_key)
    generation_config = {"temperature": 0.75, "top_p": 0.95, "top_k": 40, "max_output_tokens": 4096}
    safety_settings = [
        {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
        for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
    ]
    max_attempts = retry_count + 1

    for attempt in range(max_attempts):
        current_attempt_num = attempt + 1
        log_entry = {
            "timestamp": datetime.now().isoformat(), "item_key": item_key_for_log, "model": model_name,
            "attempt": current_attempt_num, "status": "pending", "prompt_length": len(prompt),
            "error": None, "response_snippet": None,
        }
        try:
            if attempt > 0:
                backoff_time = min(30, (2 ** attempt) + random.uniform(0, 1))
                console.print(f"[yellow]Retrying '{item_key_for_log}' (attempt {current_attempt_num}/{max_attempts}) after {backoff_time:.2f}s delay...[/yellow]")
                time.sleep(backoff_time)

            # --- API Call ---
            model = genai.GenerativeModel(model_name=model_name, generation_config=generation_config, safety_settings=safety_settings)
            response = model.generate_content(prompt)
            # --- End API Call ---

            response_text = ""
            try: # Response Processing Block
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    reason = response.prompt_feedback.block_reason
                    raise Exception(f"API call blocked for item '{item_key_for_log}'. Reason: {reason}.")
                if response.parts: response_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                elif hasattr(response, 'text'): response_text = response.text
                else: response_text = str(response) # Fallback
                if not response_text or not response_text.strip(): raise Exception(f"API returned empty response for '{item_key_for_log}'.")

                log_entry["response_snippet"] = response_text[:200].replace('\n', ' ')
                fixed_json_str = fix_json_string(response_text)

                try: # JSON Parsing Block
                    parsed_response = json.loads(fixed_json_str)
                    if not isinstance(parsed_response, dict): raise json.JSONDecodeError(f"Parsed JSON is not a dict", fixed_json_str, 0)
                    if expected_key in parsed_response:
                        log_entry.update({"status": "success_parsed_json", "response_length": len(str(parsed_response.get(expected_key)))})
                        log_data.setdefault("api_calls", []).append(log_entry)
                        gc.collect()
                        return parsed_response # SUCCESS
                    else:
                        raise json.JSONDecodeError(f"Expected key '{expected_key}' missing. Found: {list(parsed_response.keys())}", fixed_json_str, 0)
                except json.JSONDecodeError as e:
                    error_msg = f"JSON parsing error for '{item_key_for_log}' attempt {current_attempt_num}: {e}"
                    log_entry.update({"status": "json_error_after_fix", "error": str(e), "raw_response_snippet": fixed_json_str[:200]})
                    # Heuristic wrap attempt
                    if not fixed_json_str.strip().startswith('{'):
                        try:
                            wrapped_response = {expected_key: fixed_json_str.strip()}
                            log_entry.update({"status": "success_heuristic_wrap", "response_length": len(fixed_json_str.strip())})
                            log_data.setdefault("api_calls", []).append(log_entry)
                            gc.collect()
                            return wrapped_response # SUCCESS (heuristic)
                        except Exception as wrap_err: pass
                    if current_attempt_num < max_attempts:
                        log_data.setdefault("api_calls", []).append(log_entry)
                        continue
                    else:
                        log_entry["status"] = "json_error_final_attempt"
                        break
            except Exception as proc_err:
                 error_msg = f"Response processing error for '{item_key_for_log}' attempt {current_attempt_num}: {proc_err}"
                 log_entry.update({"status": "response_processing_error", "error": str(proc_err)})
                 if current_attempt_num < max_attempts:
                     log_data.setdefault("api_calls", []).append(log_entry)
                     continue
                 else:
                     log_entry["status"] = "response_error_final_attempt"
                     break
        except Exception as api_err:
            error_msg = f"API call exception for '{item_key_for_log}' attempt {current_attempt_num} using {model_name}: {api_err}"
            console.print(f"[bold red]API ERROR: {error_msg}[/bold red]")
            log_entry.update({"status": "api_exception", "error": str(api_err)})
            if current_attempt_num < max_attempts:
                log_data.setdefault("api_calls", []).append(log_entry)
                continue
            else:
                log_entry["status"] = "api_exception_final_attempt"
                break

    # --- Failure Fallback ---
    console.print(f"[bold red]All {max_attempts} API attempts failed for '{item_key_for_log}'. Returning None.[/bold red]")
    if log_entry.get("status") == "pending": log_entry["status"] = "failed_all_attempts"
    log_entry["error"] = log_entry.get("error", "Unknown error after all retries")

    final_log_list = log_data.setdefault("api_calls", [])
    if not any(c.get("item_key") == item_key_for_log and c.get("attempt") == max_attempts for c in final_log_list):
        final_log_list.append(log_entry)

    error_log_list = log_data.setdefault("errors", [])
    if not any(err.get("item_key") == item_key_for_log for err in error_log_list):
        error_log_list.append({
            "timestamp": log_entry["timestamp"], "item_key": item_key_for_log,
            "error": log_entry["error"], "status": log_entry["status"],
            "model_used": model_name, "final_attempt": max_attempts
        })
    gc.collect()
    return None # Indicate failure


# --- Main Processing Logic ---

def process_outlined_json(input_file: str, api_key: str, output_dir: Path, model_name_arg: str):
    """
    Processes outlined JSON, generates introductions (X.1) and points (X.2, X.3...)
    for each chapter (derived from section_title), providing context to points,
    and saves incrementally.
    """
    console.print(f"Starting content generation for input file: [cyan]{input_file}[/cyan]")
    input_data = load_json_file(input_file)
    if input_data is None:
        console.print("[bold red]Failed to load input file. Exiting.[/bold red]")
        sys.exit(1)

    log_file_path, log_data, processed_points_set = check_content_log_file(input_file, output_dir)
    log_data["model_used"] = model_name_arg

    book_title = input_data.get('bookTitle', 'Unknown Book')
    console.print(f"Processing book: [cyan]{book_title}[/cyan]")
    console.print(f"Using model: [cyan]{model_name_arg}[/cyan]")
    console.print(f"Resuming from log. {len(processed_points_set)} items previously processed.")

    # --- Initialize NEW Output Data Structure (Revised Structure with Content List) ---
    output_data = {
        "bookTitle": book_title,
        "generation_model": model_name_arg,
        "generation_timestamp": datetime.now().isoformat(),
        "parts": []
    }
    # Load previous interim output
    output_file_stem = Path(input_file).stem
    interim_filename = output_dir / f"{output_file_stem}_content_interim.json"
    if processed_points_set and interim_filename.exists():
        console.print(f"Loading existing interim output file: {interim_filename}")
        interim_data = load_json_file(str(interim_filename))
        if interim_data and interim_data.get('bookTitle') == book_title:
            output_data = interim_data
            output_data["generation_model"] = model_name_arg
            output_data["generation_timestamp"] = datetime.now().isoformat()
            output_data.setdefault("parts", [])
            console.print("Successfully loaded data from interim file.")
        else:
            console.print("[yellow]Warning: Interim file found but seems invalid or for a different book. Starting fresh.[/yellow]")
            output_data = {"bookTitle": book_title, "generation_model": model_name_arg, "generation_timestamp": datetime.now().isoformat(), "parts": []}


    # --- Identify Items to Process (Intros & Points) & Build Skeleton ---
    total_items_to_process = 0
    items_to_process_list = []
    original_total_items = 0 # Count potential intros + points

    # Helper function for sorting content items numerically by item_number
    def get_sort_key(item):
        try:
            return Decimal(item.get('item_number', '0.0'))
        except:
            return Decimal('0.0') # Fallback for invalid numbers

    for p_idx, input_part in enumerate(input_data.get('parts', [])):
        part_name = input_part.get('name', f'Part {p_idx + 1}')
        part_number_str = f"A{p_idx + 1}"

        # Ensure corresponding part exists in output_data
        output_part = next((p for p in output_data['parts'] if p.get('name') == part_name), None)
        if output_part is None:
            output_part = {'part_number': part_number_str, 'name': part_name, 'chapters': []}
            output_data['parts'].append(output_part)
        else:
            output_part.setdefault('part_number', part_number_str)
            output_part.setdefault('chapters', [])

        chapter_counter_in_part = 0
        for c_idx_orig, input_chapter_orig in enumerate(input_part.get('chapters', [])):
            # Use original chapter title for context if needed, but section title defines output chapter
            # original_chapter_title = input_chapter_orig.get('title', '') # Could be useful later

            if 'generated_outline' in input_chapter_orig and isinstance(input_chapter_orig['generated_outline'], dict):
                for s_idx, input_section in enumerate(input_chapter_orig['generated_outline'].get('writing_sections', [])):
                    chapter_counter_in_part += 1
                    current_chapter_number = chapter_counter_in_part
                    chapter_title = input_section.get('section_title', f'Chapter {current_chapter_number}') # This is the output chapter title
                    points_to_cover = input_section.get('content_points_to_cover', [])
                    if not isinstance(points_to_cover, list): points_to_cover = []

                    # Ensure corresponding chapter exists in output_part
                    output_chapter = next((ch for ch in output_part['chapters'] if ch.get('title') == chapter_title and ch.get('chapter_number') == current_chapter_number), None)
                    if output_chapter is None:
                        output_chapter = {
                            'chapter_number': current_chapter_number,
                            'title': chapter_title,
                            'content': [] # Content list holds intro and points
                        }
                        output_part['chapters'].append(output_chapter)
                        # Keep chapters sorted by number within the part
                        output_part['chapters'].sort(key=lambda x: x.get('chapter_number', 0))
                    else:
                        # Ensure structure exists if loaded from interim
                        output_chapter.setdefault('chapter_number', current_chapter_number)
                        output_chapter.setdefault('content', [])
                        # Sort existing content when loading from interim
                        output_chapter['content'].sort(key=get_sort_key)


                    # --- Check Intro Item ---
                    intro_number_str = f"{current_chapter_number}.1"
                    intro_key = f"p{p_idx}-c{c_idx_orig}-s{s_idx}-intro" # Unique log key
                    original_total_items += 1

                    intro_already_generated = any(
                        item.get('item_number') == intro_number_str and item.get('type') == 'introduction' and item.get('text') and "ERROR:" not in item.get('text','')
                        for item in output_chapter['content'] if isinstance(item, dict)
                    )

                    if intro_key not in processed_points_set and not intro_already_generated:
                        total_items_to_process += 1
                        items_to_process_list.append({
                            'type': 'intro', 'key': intro_key,
                            'p_idx': p_idx, 'c_idx_orig': c_idx_orig, 's_idx': s_idx, # Indices for log key uniqueness
                            'part_name': part_name, 'chapter_title': chapter_title,
                            'chapter_points': points_to_cover, # Pass points for context
                            'item_number_to_assign': intro_number_str
                        })

                    # --- Check Point Items ---
                    for pt_idx, point_text in enumerate(points_to_cover):
                        point_number_str = f"{current_chapter_number}.{pt_idx + 2}" # Points start at .2
                        point_key = f"p{p_idx}-c{c_idx_orig}-s{s_idx}-p{pt_idx}" # Unique log key
                        original_total_items += 1

                        point_already_generated = any(
                            item.get('item_number') == point_number_str and item.get('type') == 'point' and item.get('text') and "ERROR:" not in item.get('text','')
                            for item in output_chapter['content'] if isinstance(item, dict)
                        )

                        if point_key not in processed_points_set and not point_already_generated:
                            total_items_to_process += 1
                            items_to_process_list.append({
                                'type': 'point', 'key': point_key,
                                'p_idx': p_idx, 'c_idx_orig': c_idx_orig, 's_idx': s_idx, 'pt_idx': pt_idx,
                                'part_name': part_name, 'chapter_title': chapter_title,
                                'point_text': point_text,
                                'item_number_to_assign': point_number_str
                            })
            else:
                 console.print(f"[yellow]Warning: Skipping input structure Part {p_idx+1}-OrigChapter {c_idx_orig+1} - Missing 'generated_outline'.[/yellow]")

    # --- End Item Identification & Skeleton Build ---


    if total_items_to_process == 0:
        console.print("[bold green]No new introductions or points found to process based on the log file and existing interim data.[/bold green]")
        if original_total_items > 0:
             console.print(f"(Total potential items in input: {original_total_items}, Processed items in log: {len(processed_points_set)})")
        # Don't exit early, ensure final save occurs

    console.print(f"Total items (intros + points) to process in this run: {total_items_to_process}")

    final_filename = output_dir / f"{output_file_stem}_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    final_log_filename = Path(log_file_path)

    console.print(f"Output will be saved incrementally to: {interim_filename}")
    console.print(f"Final output will be named like: {output_file_stem}_content_YYYYMMDD_HHMMSS.json")
    console.print(f"Log file: {final_log_filename}")

    api_call_timestamps: Deque[float] = deque(maxlen=API_CALL_LIMIT_PER_MINUTE)
    processed_count_session = 0

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(),
        TaskProgressColumn(), TextColumn("({task.completed}/{task.total})"), TimeRemainingColumn(), TimeElapsedColumn(),
        console=console, disable=not rich_available or total_items_to_process == 0
    ) as progress:

        task_id = progress.add_task(f"Generating content for [cyan]{book_title}[/cyan]", total=total_items_to_process)

        for item_info in items_to_process_list:
            item_key = item_info['key']
            item_type = item_info['type']
            item_number_to_assign = item_info['item_number_to_assign']

            # --- Rate Limiting ---
            now = time.monotonic()
            while len(api_call_timestamps) >= API_CALL_LIMIT_PER_MINUTE:
                time_since_oldest = now - api_call_timestamps[0]
                if time_since_oldest < 60.0:
                    wait_time = 60.0 - time_since_oldest
                    time.sleep(wait_time)
                    now = time.monotonic()
                else:
                    api_call_timestamps.popleft()
            random_delay = random.uniform(0.5, 1.5)
            time.sleep(random_delay)
            # --- End Rate Limiting ---

            # Retrieve context
            part_name = item_info['part_name']
            chapter_title = item_info['chapter_title']
            p_idx = item_info['p_idx']

            # Derive chapter number from the item number string "Chap.Item" -> Chap
            try:
                current_chapter_number = int(item_number_to_assign.split('.')[0])
                current_item_num_decimal = Decimal(item_number_to_assign) # For comparison
            except Exception as e:
                console.print(f"[bold red]Error parsing chapter/item number from '{item_number_to_assign}' for item {item_key}: {e}. Skipping.[/bold red]")
                processed_points_set.add(item_key); log_data["processed_points"] = sorted(list(processed_points_set)); progress.update(task_id, advance=1)
                continue

            api_response = None
            try:
                # Find the correct output Part and Chapter from the current state of output_data
                output_part = next((p for p in output_data['parts'] if p.get('part_number') == f"A{p_idx + 1}"), None)
                if not output_part:
                     console.print(f"[bold red]Internal Error: Output part A{p_idx + 1} not found for item {item_key}. Skipping.[/bold red]")
                     processed_points_set.add(item_key); log_data["processed_points"] = sorted(list(processed_points_set)); progress.update(task_id, advance=1)
                     continue
                output_chapter = next((ch for ch in output_part['chapters'] if ch.get('chapter_number') == current_chapter_number and ch.get('title') == chapter_title), None)
                if not output_chapter:
                     console.print(f"[bold red]Internal Error: Output chapter {current_chapter_number} ('{chapter_title}') not found for item {item_key}. Skipping.[/bold red]")
                     processed_points_set.add(item_key); log_data["processed_points"] = sorted(list(processed_points_set)); progress.update(task_id, advance=1)
                     continue
                output_chapter.setdefault('content', []) # Ensure content list exists

                # --- Generate Content based on Type ---
                if item_type == 'intro':
                    progress.update(task_id, description=f"Intro {item_number_to_assign} '{chapter_title[:20]}...'")
                    chapter_points = item_info['chapter_points']
                    prompt = generate_chapter_intro_prompt(book_title, part_name, chapter_title, chapter_points)
                    api_response = call_gemini_api_for_content(prompt, api_key, log_data, model_name_arg, expected_key="introduction_text", item_key_for_log=item_key)

                    # Store Intro
                    item_entry = {
                        'item_number': item_number_to_assign,
                        'type': 'introduction',
                        'text': None
                    }
                    if api_response and "introduction_text" in api_response:
                        item_entry['text'] = api_response["introduction_text"]
                    else:
                        item_entry['text'] = f"ERROR: Failed to generate introduction ({item_key}). See log."
                        console.print(f"[bold red]\n -> Failed intro generation for {item_key} ({item_number_to_assign}). See log.[/bold red]")


                elif item_type == 'point':
                    progress.update(task_id, description=f"Point {item_number_to_assign} '{chapter_title[:15]}...'")
                    point_text = item_info['point_text']

                    # Gather preceding content from the *current* state of output_data
                    previous_content_summary = ""
                    try:
                        preceding_items = []
                        # Ensure content list is sorted before filtering
                        output_chapter['content'].sort(key=get_sort_key)
                        for item in output_chapter.get('content', []):
                            # Check if item is valid, has text, is not an error, and comes numerically before current item
                            if isinstance(item, dict) and 'item_number' in item and 'text' in item and item['text'] and "ERROR:" not in item['text']:
                                try:
                                    item_num_decimal = Decimal(item['item_number'])
                                    if item_num_decimal < current_item_num_decimal:
                                        preceding_items.append(item)
                                except Exception:
                                    continue # Skip items with invalid numbers
                        # No need to sort again here as we iterated through the sorted list
                        previous_content_summary = "\n\n---\n\n".join(item['text'] for item in preceding_items)
                    except Exception as e:
                         console.print(f"[yellow]Warning: Could not gather preceding content for {item_key}: {e}[/yellow]")

                    # Pass summary to prompt function
                    prompt = generate_point_prompt(
                        book_title, part_name, chapter_title, point_text,
                        item_number_to_assign, previous_content_summary
                    )
                    api_response = call_gemini_api_for_content(prompt, api_key, log_data, model_name_arg, expected_key="point_content", item_key_for_log=item_key)

                    # Store Point
                    item_entry = {
                        'item_number': item_number_to_assign,
                        'type': 'point',
                        'original_point': point_text, # Keep original text for reference
                        'text': None
                    }
                    if api_response and "point_content" in api_response:
                        item_entry['text'] = api_response["point_content"]
                    else:
                        item_entry['text'] = f"ERROR: Failed to generate point ({item_key}). See log."
                        console.print(f"[bold red]\n -> Failed point generation for {item_key} ({item_number_to_assign}). See log.[/bold red]")


                # --- Add or Update Item in Content List ---
                existing_item_index = next((i for i, item in enumerate(output_chapter['content']) if isinstance(item, dict) and item.get('item_number') == item_number_to_assign), -1)
                if existing_item_index != -1:
                    # Update existing item placeholder or previous failed attempt
                    output_chapter['content'][existing_item_index] = item_entry
                else:
                    # Append new item if not found (should usually be found due to skeleton build)
                    output_chapter['content'].append(item_entry)


                # --- Post-processing for the item ---
                api_call_timestamps.append(time.monotonic())
                processed_points_set.add(item_key)
                log_data["processed_points"] = sorted(list(processed_points_set))
                processed_count_session += 1

                # Sort content within the chapter after potentially adding/updating item
                output_chapter['content'].sort(key=get_sort_key)

                progress.update(task_id, advance=1)

                # --- Incremental Saving ---
                if processed_count_session % INTERIM_SAVE_FREQUENCY == 0 or processed_count_session == total_items_to_process:
                   if not save_json_file(output_data, str(interim_filename)):
                        console.print("[bold red]FATAL: Failed to save interim data. Exiting.[/bold red]")
                        sys.exit(1)
                   if not save_json_file(log_data, str(final_log_filename)):
                        console.print("[bold red]Warning: Failed to save log file incrementally.[/bold red]")


                gc.collect()

            except KeyboardInterrupt:
                 console.print("\n[bold yellow]Keyboard interrupt detected. Saving progress before exiting...[/bold yellow]")
                 # Ensure content is sorted before final save
                 for p in output_data.get('parts', []):
                     for ch in p.get('chapters', []):
                         ch.get('content', []).sort(key=get_sort_key)
                 save_json_file(output_data, str(interim_filename))
                 log_data["processed_points"] = sorted(list(processed_points_set))
                 save_json_file(log_data, str(final_log_filename))
                 console.print("Progress saved. Exiting.")
                 sys.exit(0)
            except Exception as e:
                 console.print(f"[bold red]\nAn unexpected error occurred processing item {item_key}: {e}[/bold red]")
                 console.print(traceback.format_exc())
                 log_data.setdefault("errors", []).append({
                     "timestamp": datetime.now().isoformat(), "item_key": item_key,
                     "error": f"Unexpected loop error: {e}", "traceback": traceback.format_exc(),
                     "status": "unexpected_error", "model_used": model_name_arg
                 })
                 # Ensure content is sorted before saving progress on error
                 for p in output_data.get('parts', []):
                     for ch in p.get('chapters', []):
                         ch.get('content', []).sort(key=get_sort_key)
                 save_json_file(output_data, str(interim_filename))
                 log_data["processed_points"] = sorted(list(processed_points_set))
                 save_json_file(log_data, str(final_log_filename))
                 console.print("[yellow]Attempting to continue processing next item...[/yellow]")
                 if item_key not in processed_points_set:
                     processed_points_set.add(item_key)
                     log_data["processed_points"] = sorted(list(processed_points_set))
                 progress.update(task_id, advance=1) # Advance progress bar even on error

    # --- Finalization ---
    console.print("\n[bold green]=== Content Generation Complete ===[/bold green]")

    # Ensure final sort before saving
    for p in output_data.get('parts', []):
        p.get('chapters', []).sort(key=lambda x: x.get('chapter_number', 0))
        for ch in p.get('chapters', []):
            ch.get('content', []).sort(key=get_sort_key)

    # Final save - rename interim to final
    try:
        final_save_path = Path(final_filename)
        interim_path = Path(interim_filename)

        if not save_json_file(output_data, str(interim_path)):
            console.print("[bold red]Error performing final save to interim file before rename.[/bold red]")
            if not save_json_file(output_data, str(final_save_path)):
                 console.print("[bold red]Error saving final output file directly.[/bold red]")
            else:
                 console.print(f"Final content saved to: [link=file://{os.path.abspath(final_save_path)}]{final_save_path}[/link]")
        elif interim_path.exists():
             # Ensure interim path exists before trying to rename
             try:
                 interim_path.rename(final_save_path)
                 console.print(f"Final content saved to: [link=file://{os.path.abspath(final_save_path)}]{final_save_path}[/link]")
             except Exception as rename_err:
                 console.print(f"[bold red]Error renaming interim file to final: {rename_err}[/bold red]")
                 console.print(f"Output might still be in: {interim_filename}")
                 # As a fallback, try saving directly to final path
                 if not save_json_file(output_data, str(final_save_path)):
                      console.print("[bold red]Error saving final output file directly after rename failed.[/bold red]")
                 else:
                      console.print(f"Final content saved directly to: [link=file://{os.path.abspath(final_save_path)}]{final_save_path}[/link] (Rename failed)")

        else:
             # If interim never existed (e.g., no items processed or first save failed)
             if not save_json_file(output_data, str(final_save_path)):
                  console.print("[bold red]Error saving final output file directly (interim file did not exist).[/bold red]")
             else:
                  console.print(f"Final content saved to: [link=file://{os.path.abspath(final_save_path)}]{final_save_path}[/link]")
    except Exception as e:
        console.print(f"[bold red]Error during final file finalization: {e}[/bold red]")
        console.print(f"Data might still be available at: {interim_filename}")

    # Final log save
    log_data["end_time"] = datetime.now().isoformat()
    log_data["total_items_processed_in_log"] = len(processed_points_set)
    final_errors = [e for e in log_data.get("errors", [])]
    log_data["items_with_final_errors"] = len(final_errors)

    if not save_json_file(log_data, str(final_log_filename)):
         console.print("[bold red]Error saving final log file.[/bold red]")
    else:
         console.print(f"Detailed log saved to: [link=file://{os.path.abspath(final_log_filename)}]{final_log_filename}[/link]")

    if log_data["items_with_final_errors"] > 0:
         console.print(f"[bold red]Note: {len(final_errors)} items encountered errors during generation. Check the log file.[/bold red]")

    gc.collect()


# --- Main Execution ---
def main():
    print(f"\n--- Script Execution Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    load_dotenv() # Attempt to load .env

    effective_default_model = os.environ.get("DEFAULT_GEMINI_MODEL", DEFAULT_MODEL)

    parser = argparse.ArgumentParser(description='Generate chapter introductions (X.1) and points (X.2+) with context using Google Gemini API based on an outlined JSON.') # Updated description
    parser.add_argument('--input_file', type=str, required=True, help='Path to the input JSON file containing book structure and generated outlines.')
    parser.add_argument('--output_dir', type=str, default='results/Content', help='Directory to save output content JSON and log files (default: results/Content)')
    parser.add_argument('--model', type=str, default=effective_default_model, help=f'Name of the Gemini model to use (default: {effective_default_model})')
    parser.add_argument('--test', action='store_true', help='Run a quick API test before processing.')
    args = parser.parse_args()

    console.print(f"Arguments: input='{args.input_file}', output='{args.output_dir}', model='{args.model}', test={args.test}")

    output_dir = Path(args.output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        console.print(f"[bold red]Fatal Error creating output directory '{output_dir}': {e}[/bold red]")
        sys.exit(1)

    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        console.print("[bold red]Fatal Error: GOOGLE_API_KEY not found in environment variables or .env file.[/bold red]")
        sys.exit(1)

    if args.test:
        console.print("\n--- Running API Test ---")
        if not test_gemini_api(api_key, model_name=args.model):
            console.print("[bold red]API test failed. Exiting.[/bold red]")
            sys.exit(1)
        console.print("--- API Test Complete ---")

    input_file_path = Path(args.input_file)
    if not input_file_path.is_file():
         console.print(f"[bold red]Fatal Error: Input file not found at '{args.input_file}'[/bold red]")
         sys.exit(1)

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
        console.print("\n[bold yellow]Process interrupted by user (main block). Exiting.[/bold yellow]")
        sys.exit(0)
    except SystemExit as e:
         # Avoid printing traceback for SystemExit, just show the code
         console.print(f"\n[bold red]Exiting due to error (Code: {e.code}).[/bold red]")
         sys.exit(e.code)
    except Exception as e:
        console.print(f"\n[bold red]An unexpected critical error occurred outside the main processing loop:[/bold red]")
        console.print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()