# stages/outline_generator.py
"""
Handles Stage 1 of the processing: Generating chapter outlines using the Gemini API.
(Version modified for saving after each successful item)
"""

import time
import gc
import random
import sys # Added for sys.exit
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, Set, Deque

# Assume modules are importable from the root directory context
try:
    import config
    from api import gemini_client
    from utils import file_handler, log_handler, console_utils
except ImportError:
    print("Error: Failed to import necessary modules in outline_generator.py.")
    print("Ensure config.py, api/gemini_client.py, and utils/* exist and are importable.")
    config = type('obj', (object,), {'API_RETRY_COUNT': 3})()
    sys.exit(1)

# --- Prompt Generation (Function remains the same as before) ---
def generate_chapter_outline_prompt(part_name: str, chapter_title: str, chapter_description: str) -> str:
    """Generate a prompt for creating a chapter writing outline with content points and search terms."""
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
    prompt = f"""You are an expert academic writer and editor creating a detailed *writing guide* for a book chapter. Your goal is to structure the writing process for an author.

CONTEXT:
- Book Part: "{part_name}"
- Proposed Chapter Title: "{chapter_title}"
- Chapter Description/Goal: "{chapter_description}"

TASK:
Based *only* on the provided Chapter Title and Description, generate a comprehensive writing outline. This outline should break down the chapter into logical sections ('writing_sections') and provide actionable guidance on the content for each section ('content_points_to_cover'), including suggested Google search terms ('Google Search_terms') for further research by the author. Write as many sections as needed to cover the chapter description thoroughly.

You should write in detail. Ensure all generated content aligns with the chapter's goal.

Adhere strictly to the following JSON structure:

OUTPUT JSON STRUCTURE:
{json_template}

INSTRUCTIONS FOR FILLING THE JSON:
- Create as many `writing_sections` objects as needed to cover the `chapter_description`. Do NOT limit the number arbitrarily. Each object represents a logical section of the chapter.
- `chapter_title_suggestion`: Refine the input title for clarity/impact, or use the original.
- `writing_sections`: This MUST be a JSON array `[]`.
    - `section_title`: Propose a clear and descriptive title for this section.
    - `content_points_to_cover`: This MUST be a JSON array `[]`. List *detailed, actionable points* instructing the author on what specific concepts, arguments, analyses, or information derived from the `chapter_description` should be included. Write a very detailed guide.
    - `Google Search_terms`: This MUST be a JSON array `[]`. Provide relevant Google search query strings for researching this section's topics.

**CRITICAL JSON VALIDITY RULES:**
1.  Your *entire* response MUST be a single, valid JSON object conforming exactly to the structure above.
2.  Do NOT include any introductory text, explanations, comments, or markdown formatting (like ```json) outside of the JSON object itself.
3.  Ensure correct comma usage in arrays and objects.
4.  Ensure all strings are properly enclosed in double quotes and internal double quotes are escaped (e.g., `"He said \\"Hello\\""`).

Double-check your response for validity before outputting.
"""
    return prompt


# --- Main Stage Function ---
def run_outline_stage(
    initial_data: Dict[str, Any],
    api_key: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    output_dir: Path,
    outline_file_path: Path,
    log_data: Dict[str, Any],
    log_file_path: Path,
    processed_items_set: Set[str],
    api_call_timestamps_deque: Deque[float],
    console
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Executes the outline generation stage, saving after each successful item.
    (Args documentation omitted for brevity - same as before)
    """
    stage_name = "outline"
    overall_success = True
    processed_in_stage = 0 # Keep track for potential future use, but not for saving interval

    total_chapters = 0
    for part in initial_data.get('parts', []):
        total_chapters += len(part.get('chapters', []))

    if total_chapters == 0:
        console.print("[warning]No chapters found in the input data structure.[/warning]")
        return initial_data, True

    progress = console_utils.get_progress_bar()
    task_id = None

    with progress:
        task_id = progress.add_task(f"Stage 1: Generating Outlines", total=total_chapters)

        for part_idx, part in enumerate(initial_data.get('parts', [])):
            part_name = part.get('name', f'Part {part_idx + 1}')
            chapters = part.get('chapters', [])

            if not chapters:
                # console.print(f"[info]Skipping Part '{part_name}' (index {part_idx}): No chapters.[/info]") # Less verbose
                continue

            for chapter_idx, chapter in enumerate(chapters):
                item_key = f"p{part_idx}-ch{chapter_idx}"
                log_key = f"{stage_name}:{item_key}"
                chapter_title = chapter.get('title')
                chapter_description = chapter.get('description')

                if log_key in processed_items_set:
                    progress.update(task_id, advance=1, description=f"Skipped {item_key}")
                    continue

                progress.update(task_id, description=f"Outline {item_key}...")

                if not chapter_title or not chapter_description:
                    error_msg = f"Skipping {item_key}: Missing title/description"
                    console.print(f"[warning]{error_msg}[/warning]")
                    log_handler.log_error(log_data, stage_name, item_key, {"error": error_msg, "status": "skipped_invalid_input"})
                    chapter['generated_outline'] = {"error": error_msg, "writing_sections": []}
                    log_handler.log_item_success(log_data, stage_name, item_key)
                    log_handler.save_log(log_data, log_file_path) # Save log after skipping
                    processed_items_set.add(log_key)
                    progress.update(task_id, advance=1)
                    continue

                try:
                    prompt = generate_chapter_outline_prompt(part_name, chapter_title, chapter_description)
                except Exception as e:
                     error_msg = f"Error generating prompt for {item_key}: {e}"
                     console.print(f"[error]{error_msg}[/error]")
                     log_handler.log_error(log_data, stage_name, item_key, {"error": error_msg, "status": "prompt_error"})
                     chapter['generated_outline'] = {"error": error_msg, "writing_sections": []}
                     overall_success = False
                     log_handler.save_log(log_data, log_file_path) # Save log after error
                     progress.update(task_id, advance=1)
                     continue

                parsed_response, error_message = gemini_client.call_gemini_api(
                    prompt=prompt, api_key=api_key, model_name=model_name,
                    temperature=temperature, max_output_tokens=max_tokens,
                    api_call_timestamps_deque=api_call_timestamps_deque,
                    retry_count=config.API_RETRY_COUNT, item_key_for_log=log_key
                )

                if parsed_response:
                    # Basic validation
                    if not isinstance(parsed_response.get("writing_sections"), list):
                         warn_msg = f"API response for {log_key} parsed but 'writing_sections' is not a list."
                         console.print(f"[warning]{warn_msg}[/warning]")
                         log_handler.log_error(log_data, stage_name, item_key, {"warning": warn_msg, "status": "response_format_warning"})
                         parsed_response.setdefault("writing_sections", [])
                         parsed_response["error"] = warn_msg # Add error note

                    chapter['generated_outline'] = parsed_response
                    log_handler.log_item_success(log_data, stage_name, item_key)
                    processed_items_set.add(log_key)
                    processed_in_stage += 1
                    progress.update(task_id, advance=1, description=f"Done {item_key}")

                    # --- SAVE AFTER SUCCESS ---
                    # Save both data and log state immediately after success
                    if not file_handler.save_json_file(initial_data, outline_file_path):
                         console.print(f"[error]CRITICAL: Failed to save intermediate outline data to {outline_file_path} after processing {log_key}! Potential data loss.[/error]")
                         # return None, False # Stop processing on critical save failure
                    if not log_handler.save_log(log_data, log_file_path):
                         console.print(f"[warning]Failed to save log file after processing {log_key}.[/warning]")
                    # --- END SAVE AFTER SUCCESS ---

                else:
                    console.print(f"[error]Failed to generate outline for {log_key}. Error: {error_message}[/error]")
                    log_handler.log_error(log_data, stage_name, item_key, {"error": error_message or "API call failed", "status": "api_failure"})
                    chapter['generated_outline'] = {"error": error_message or "Outline generation failed", "writing_sections": []}
                    overall_success = False
                    # Save log immediately after recording the error
                    log_handler.save_log(log_data, log_file_path)
                    progress.update(task_id, advance=1) # Advance past failed item

                gc.collect()

    # --- Final Save (optional but safe) ---
    # This ensures the very last state is saved if the loop finishes cleanly
    # console.print(f"Saving final outline data state to {outline_file_path}...")
    # if not file_handler.save_json_file(initial_data, outline_file_path):
    #     console.print(f"[error]CRITICAL: Failed to save FINAL outline data to {outline_file_path}! Potential data loss.[/error]")
    #     overall_success = False
    #     log_handler.log_error(log_data, stage_name, "final_save", {"error": f"Failed to save final outline data to {outline_file_path}"})

    # Save final log state (already saved after last item/error, but safe to save again)
    log_handler.save_log(log_data, log_file_path)

    return initial_data, overall_success