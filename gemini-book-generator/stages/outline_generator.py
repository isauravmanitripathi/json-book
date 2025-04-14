# stages/outline_generator.py
"""
Handles Stage 1 of the processing: Generating chapter outlines using the Gemini API.
(Version modified for saving after each successful item)
"""

import time
import gc
import random
import sys # Added for sys.exit
import json # Added for escaping input strings
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

# --- Prompt Generation (V3: Expert Co-Author for Deep Understanding) ---
def generate_chapter_outline_prompt(part_name: str, chapter_title: str, chapter_description: str) -> str:
    """
    Generate a highly detailed, explanatory chapter outline, acting as an expert
    co-author providing a rich foundation for the human writer.
    """
    # Escape inputs for safe embedding
    escaped_part_name = json.dumps(part_name)[1:-1]
    escaped_chapter_title = json.dumps(chapter_title)[1:-1]
    escaped_chapter_description = json.dumps(chapter_description)[1:-1]

    # JSON template with examples reflecting deeper explanation and connections
    json_template = """{
  "chapter_title_suggestion": "A comprehensive title reflecting the core topic and its key dimensions.",
  "writing_sections": [
    {
      "section_title": "Section 1: Foundational Concepts and Context",
      "content_points_to_cover": [
        "Example: Core Concept Definition & Significance: Define [Concept from Description] precisely, explain *why* it's central to the chapter's theme, and briefly situate it within the broader field/context.",
        "Example: Essential Background Element: Explain the necessary historical/theoretical background [Related Element] required to fully grasp [Concept from Description].",
        "Example: Key Distinction/Nuance: Clarify the difference between [Concept A] and the related but distinct [Concept B], highlighting the importance of this distinction for the chapter's argument.",
        "Example: Foundational Principle Explained: Detail the underlying principle or assumption governing [Topic from Description], including its basic logic and relevance."
      ],
      "Google Search_terms": [
        "In-depth explanation of [Core Concept]",
        "Historical context of [Related Element]",
        "[Concept A] vs [Concept B] comparison",
        "Underlying principles of [Topic]"
      ]
    },
    {
      "section_title": "Section 2: Exploring Key Components / Processes",
      "content_points_to_cover": [
        "Example: Component Breakdown & Function: Detail the sub-components of [Key Element from Description] and explain the specific function or role of each part.",
        "Example: Process Walkthrough & Rationale: Outline the steps of [Process mentioned or implied in Description], explaining the logic and purpose behind each stage.",
        "Example: Causal Mechanism Explained: Analyze *how* [Factor X] influences [Factor Y] based on the description, detailing the intermediate steps or logic involved.",
        "Example: Illustrative Example & Interpretation: Provide a generic or classic type of example illustrating [Concept/Process], and explain what key insights it demonstrates."
      ],
      "Google Search_terms": [
        "Components of [Key Element]",
        "Step-by-step [Process Name]",
        "Mechanism linking [Factor X] and [Factor Y]",
        "Classic examples of [Concept/Process]"
      ]
    }
    // Add more sections dynamically, ensuring logical flow and comprehensive, deep coverage of the description and essential related context.
  ]
}"""

    # The refined prompt demanding deep co-authorship
    prompt = f"""You are an Expert Co-Author and Explainer with exceptional subject matter knowledge (derived from the context below) and a skill for creating clear, comprehensive, and insightful explanations. Your primary goal is to generate an exceptionally detailed and logically structured content outline for a book chapter, acting as a foundation for a human author.

This outline must go beyond simply listing topics from the description, right now we are writing about international relations of india/foregin relation of india. So understand the text and write accordingly, Every thing should be detailed, you should cover each point provided in input, but also add from your end, there is no limit on minimum write as much as you can.  It needs to anticipate what a reader requires for a deep "Aha! I understand everything" moment. This means including not only the core elements mentioned but also the essential related concepts, necessary background, critical definitions, nuances, implications, and explanatory details needed for thorough comprehension.

The final output should be so rich and well-explained that the human author's primary role becomes enhancing the text.

CONTEXT:
- Book Part: "{escaped_part_name}"
- Proposed Chapter Title: "{escaped_chapter_title}"
- Chapter Description/Goal: "{escaped_chapter_description}"

TASK:
1.  Deeply Analyze: Interpret the `Chapter Description/Goal` and `Proposed Chapter Title`.
2.  Identify Core & Related Essentials: Determine the central topics AND the crucial related knowledge needed for a full understanding.
3.  Structure Logically: Organize these elements into logical `writing_sections` that build understanding progressively.
4.  Generate Detailed Points: For each section, create highly detailed `content_points_to_cover`. Each point should:
    * Clearly define concepts.
    * Explain their significance and relevance ('why it matters').
    * Detail key components, processes, or arguments.
    * Explain connections between ideas.
    * Include necessary background or context.
    * Briefly note important nuances, complexities, or illustrative types of examples where appropriate.
5.  Suggest Research Terms: Provide relevant `Google Search_terms` for the human author to find specific data, case studies, or further elaboration points.
6.  Ensure Depth & Flow: Create as many sections and points as needed to provide a comprehensive and deeply explanatory foundation based on the input. Ensure a logical flow throughout.
7.  Maintain Focus: While incorporating necessary related context, ensure ALL content directly serves to illuminate and explain the core subject defined by the input title and description. Avoid unrelated tangents.

Adhere strictly to the following JSON structure:

OUTPUT JSON STRUCTURE:
{json_template}

INSTRUCTIONS FOR FILLING THE JSON:
- `chapter_title_suggestion`: Suggest a title reflecting the chapter's comprehensive scope.
- `writing_sections`: MUST be a JSON array `[]`. Create enough sections for deep coverage.
    - `section_title`: A clear title indicating the specific focus and stage of the explanation.
    - `content_points_to_cover`: MUST be a JSON array `[]`. Each string MUST be a detailed, substantive explanation covering the 'what', 'why', and 'how' of the point, including necessary context, nuances, and connections, as derived from or critically related to the input description. Aim for depth and clarity that minimizes the need for foundational research by the enhancer.
    - `Google Search_terms`: MUST be a JSON array `[]`. Specific queries for enhancement/examples.

CRITICAL JSON VALIDITY RULES:
1.  Your *entire* response MUST be a single, valid JSON object.
2.  Do NOT include any text, explanations, or markdown (like ```json) outside the JSON object itself.
3.  Ensure correct JSON syntax (commas, quotes, brackets). Escape internal double quotes (\\").

Review your response meticulously for JSON validity, depth of explanation, logical flow, and adherence to these instructions before outputting.
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
                    # Call the updated prompt generation function
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

                # The rest of the API call and processing logic remains the same
                parsed_response, error_message = gemini_client.call_gemini_api(
                    prompt=prompt, api_key=api_key, model_name=model_name,
                    temperature=temperature, max_output_tokens=max_tokens,
                    api_call_timestamps_deque=api_call_timestamps_deque,
                    retry_count=config.API_RETRY_COUNT, item_key_for_log=log_key
                )

                if parsed_response:
                    # Basic validation (remains the same)
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

                    # --- SAVE AFTER SUCCESS --- (remains the same)
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
                    # Save log immediately after recording the error (remains the same)
                    log_handler.save_log(log_data, log_file_path)
                    progress.update(task_id, advance=1) # Advance past failed item

                gc.collect() # Garbage collection remains the same

    # --- Final Save --- (remains the same)
    log_handler.save_log(log_data, log_file_path)

    return initial_data, overall_success