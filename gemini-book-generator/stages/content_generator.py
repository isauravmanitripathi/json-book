# stages/content_generator.py
"""
Handles Stage 2 of the processing: Generating detailed chapter content
(introductions and point elaborations) based on the outlines from Stage 1.
(Version modified for saving after each successful item)
"""

import time
import gc
import random
import sys # Added for sys.exit
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, Set, List, Deque
from decimal import Decimal, InvalidOperation

# Assume modules are importable from the root directory context
try:
    import config
    from api import gemini_client
    from utils import file_handler, log_handler, console_utils
except ImportError:
    print("Error: Failed to import necessary modules in content_generator.py.")
    print("Ensure config.py, api/gemini_client.py, and utils/* exist and are importable.")
    config = type('obj', (object,), {'API_RETRY_COUNT': 3, 'INTERIM_SAVE_FREQUENCY_CONTENT': 1, 'MAX_CONTEXT_SUMMARY_LENGTH': 2000})() # Provide default for frequency
    sys.exit(1)


# --- Helper Functions (get_sort_key, _summarize_context - same as before) ---
def get_sort_key(item: Dict[str, Any]) -> Decimal:
    """Helper function for sorting content items numerically by item_number."""
    try:
        return Decimal(item.get('item_number', '0.0'))
    except (InvalidOperation, TypeError):
        return Decimal('0.0')

def _summarize_context(text: str, max_length: int) -> str:
    """Basic summarization by trimming."""
    if len(text) <= max_length: return text
    start_index = len(text) - max_length
    sentence_break = text.rfind(". ", start_index - 50, start_index + 50)
    if sentence_break != -1: start_index = sentence_break + 2
    elif text.rfind("\n", start_index - 50, start_index + 50) != -1:
         start_index = text.rfind("\n", start_index - 50, start_index + 50) + 1
    return "... (trimmed) ...\n" + text[start_index:].strip()

# --- Prompt Generation Functions (generate_chapter_intro_prompt, generate_point_prompt - same as before) ---
def generate_chapter_intro_prompt(book_title: str, part_name: str, chapter_title: str, chapter_points: List[str]) -> str:
    """Generates the prompt for writing an introduction for a chapter."""
    points_summary = "\n".join(f"- {point}" for point in chapter_points if point)
    if not points_summary: points_summary = "- (No specific points listed in outline)"
    prompt = f"""You are an expert academic writer specializing in content creation. Your task is to write a compelling and informative introduction for a specific chapter section in a book.

BOOK CONTEXT:
- Book Title: "{book_title}"

CURRENT SECTION DETAILS:
- Part Name: "{part_name}"
- Chapter Section Title: "{chapter_title}" (This section acts like a sub-chapter)

POINTS COVERED IN THIS CHAPTER SECTION:
{points_summary}

TASK:
Based on the provided context, section title, and the summary of points to be covered, write an engaging introduction for this *specific chapter section*.
- The introduction should clearly state the section's purpose and scope.
- It should briefly preview the key topics (points) that will be discussed within this section.
- Set the stage for the reader, highlighting the importance of this section's content within the broader chapter/part.
- Maintain an academic, clear, and concise tone.
- Aim for a well-structured paragraph or two.
- This introduction will be the first item (e.g., '.1') within this chapter section.

OUTPUT FORMAT:
Your *entire* response MUST be a single, valid JSON object containing only one key, "introduction_text", with the generated introduction as its string value.
Example JSON Output:
{{
  "introduction_text": "This section delves into the core principles of..."
}}

CRITICAL INSTRUCTIONS:
1. Respond ONLY with the valid JSON object.
2. Do NOT include any text outside the JSON object.
3. Ensure the text addresses the task based *only* on the provided information.
"""
    return prompt

def generate_point_prompt(
    book_title: str, part_name: str, chapter_section_title: str, point_text: str,
    point_number: str, previous_content_summary: Optional[str] = None
) -> str:
    """Generates the prompt for elaborating on a specific content point, providing preceding context."""
    context_section = "This is the first elaborated point in this chapter section after the introduction."
    if previous_content_summary and previous_content_summary.strip():
        summary_trimmed = _summarize_context(previous_content_summary.strip(), config.MAX_CONTEXT_SUMMARY_LENGTH)
        context_section = f"""PRECEDING CONTENT SUMMARY (From the introduction up to the previous item in this chapter section):
---
{summary_trimmed}
---
"""
    prompt = f"""You are an expert academic writer specializing in content creation. Your task is to elaborate on a *single specific point* within a book chapter section, ensuring coherence with preceding text.

BOOK CONTEXT:
- Book Title: "{book_title}"

CURRENT LOCATION IN BOOK:
- Part Name: "{part_name}"
- Chapter Section Title: "{chapter_section_title}"
- Current Item Number: {point_number} (e.g., ChapterSection.ItemNumber)

SPECIFIC POINT TO ELABORATE ON:
"{point_text}"

CONTEXT FROM EARLIER IN THIS SECTION:
{context_section}

TASK:
Write detailed and informative content (one or more paragraphs) that elaborates *only* on the `SPECIFIC POINT TO ELABORATE ON` ({point_number}).
- **CRITICAL:** Read the 'PRECEDING CONTENT SUMMARY'. **DO NOT REPEAT** information already covered there. Build upon that context and focus *exclusively* on providing new, relevant details, analysis, examples, or explanations for the current point.
- Assume this content follows the preceding items (intro and potentially other points) and precedes subsequent points within this chapter section.
- Provide accurate, relevant information suitable for the book's audience.
- Maintain an academic, clear, and objective tone. Use precise language.

OUTPUT FORMAT:
Your *entire* response MUST be a single, valid JSON object containing only one key, "point_content", with the generated elaboration as its string value.
Example JSON Output (if the point was "Discuss historical context..."):
{{
  "point_content": "The historical context for this policy begins in the post-independence era..."
}}

CRITICAL INSTRUCTIONS:
1. Respond ONLY with the valid JSON object.
2. Do NOT include any text outside the JSON object.
3. Ensure the generated text directly and exclusively elaborates on the single `SPECIFIC POINT TO ELABORATE ON`, avoiding repetition from the provided context summary.
"""
    return prompt


# --- Main Stage Function ---
def run_content_stage(
    outline_data: Dict[str, Any],
    api_key: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    output_dir: Path,
    final_content_path: Path,
    log_data: Dict[str, Any],
    log_file_path: Path,
    processed_items_set: Set[str],
    api_call_timestamps_deque: Deque[float],
    console
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Executes the content generation stage, saving after each successful item.
    (Args documentation omitted for brevity - same as before)
    """
    stage_name = "content"
    overall_success = True
    processed_in_stage = 0
    items_to_process = []

    interim_content_path = output_dir / f"{final_content_path.stem}_interim.json"

    # --- Initialize or Load Final Output Data ---
    # (Loading logic remains the same as before)
    final_output_data = {
        "bookTitle": outline_data.get('bookTitle', 'Unknown Book'),
        "generation_model_outline": log_data.get("outline_model_used", "Unknown"),
        "generation_model_content": model_name,
        "generation_timestamp": datetime.now().isoformat(),
        "parts": []
    }
    if processed_items_set and interim_content_path.exists():
        console.print(f"Loading existing interim content data from: [path]{interim_content_path}[/path]")
        loaded_interim = file_handler.load_json_file(interim_content_path)
        if loaded_interim and loaded_interim.get('bookTitle') == final_output_data['bookTitle']:
            final_output_data = loaded_interim
            final_output_data["generation_timestamp"] = datetime.now().isoformat()
            final_output_data["generation_model_content"] = model_name
            console.print("Successfully loaded data from interim content file.")
        else:
            console.print("[warning]Interim content file found but seems invalid or for a different book. Rebuilding.[/warning]")


    # --- Build Skeleton & Identify Items to Process ---
    # (This logic remains the same as before)
    console.print("Analyzing outline and identifying content items to generate...")
    total_items_identified = 0
    part_map = {p.get('name'): p for p in final_output_data.get('parts', [])}

    for p_idx, input_part in enumerate(outline_data.get('parts', [])):
        part_name = input_part.get('name', f'Part {p_idx + 1}')
        output_part = part_map.get(part_name)
        if output_part is None:
             output_part = {'part_number': f"P{p_idx + 1}", 'name': part_name, 'chapters': []}
             final_output_data['parts'].append(output_part)
             part_map[part_name] = output_part
        else:
             output_part.setdefault('chapters', [])
        chapter_map = {ch.get('title'): ch for ch in output_part.get('chapters', [])}

        chapter_counter_in_part = 0
        for c_idx_orig, input_chapter_orig in enumerate(input_part.get('chapters', [])):
             generated_outline = input_chapter_orig.get('generated_outline')
             if not isinstance(generated_outline, dict) or generated_outline.get("error"):
                 continue
             writing_sections = generated_outline.get('writing_sections', [])
             if not isinstance(writing_sections, list): writing_sections = []

             for s_idx, input_section in enumerate(writing_sections):
                 chapter_counter_in_part += 1
                 current_chapter_number = chapter_counter_in_part
                 output_chapter_title = input_section.get('section_title', f'Chapter Section {current_chapter_number}')
                 points_to_cover = input_section.get('content_points_to_cover', [])
                 if not isinstance(points_to_cover, list): points_to_cover = []

                 output_chapter = chapter_map.get(output_chapter_title)
                 if output_chapter is None:
                      output_chapter = {'chapter_number': current_chapter_number, 'title': output_chapter_title, 'content': []}
                      output_part['chapters'].append(output_chapter)
                      chapter_map[output_chapter_title] = output_chapter
                 else:
                      output_chapter.setdefault('content', [])
                 output_chapter['content'].sort(key=get_sort_key)
                 content_map = {item.get('item_number'): item for item in output_chapter.get('content', [])}

                 intro_item_number_str = f"{current_chapter_number}.1"
                 intro_key = f"p{p_idx}-c{c_idx_orig}-s{s_idx}-intro"
                 log_key = f"{stage_name}:{intro_key}"
                 total_items_identified += 1
                 intro_already_generated = log_key in processed_items_set or \
                     (intro_item_number_str in content_map and content_map[intro_item_number_str].get('text') and "ERROR:" not in content_map[intro_item_number_str]['text'])
                 if not intro_already_generated:
                      items_to_process.append({ 'type': 'intro', 'key': intro_key, 'p_idx': p_idx, 'c_idx_orig': c_idx_orig, 's_idx': s_idx, 'part_name': part_name, 'chapter_title': output_chapter_title, 'chapter_points': [pt for pt in points_to_cover if pt], 'item_number_to_assign': intro_item_number_str, 'output_chapter_ref': output_chapter })

                 for pt_idx, point_text in enumerate(points_to_cover):
                      if not point_text: continue
                      point_item_number_str = f"{current_chapter_number}.{pt_idx + 2}"
                      point_key = f"p{p_idx}-c{c_idx_orig}-s{s_idx}-p{pt_idx}"
                      log_key = f"{stage_name}:{point_key}"
                      total_items_identified += 1
                      point_already_generated = log_key in processed_items_set or \
                         (point_item_number_str in content_map and content_map[point_item_number_str].get('text') and "ERROR:" not in content_map[point_item_number_str]['text'])
                      if not point_already_generated:
                          items_to_process.append({ 'type': 'point', 'key': point_key, 'p_idx': p_idx, 'c_idx_orig': c_idx_orig, 's_idx': s_idx, 'pt_idx': pt_idx, 'part_name': part_name, 'chapter_title': output_chapter_title, 'point_text': point_text, 'item_number_to_assign': point_item_number_str, 'output_chapter_ref': output_chapter })

        for part in final_output_data.get('parts', []):
            part.get('chapters', []).sort(key=lambda x: x.get('chapter_number', 0))
    # --- End Item Identification ---

    if not items_to_process:
        console.print("[bold green]No new content items found to process based on the log file and existing data.[/bold green]")
    else:
         console.print(f"Identified {len(items_to_process)} new content items to generate (out of {total_items_identified} total potential items).")

    # --- Processing Loop ---
    progress = console_utils.get_progress_bar()
    task_id = None

    with progress:
        if items_to_process:
            task_id = progress.add_task(f"Stage 2: Generating Content", total=len(items_to_process))

        for item_info in items_to_process:
            item_key = item_info['key']
            log_key = f"{stage_name}:{item_key}"
            item_type = item_info['type']
            item_number_to_assign = item_info['item_number_to_assign']
            output_chapter_ref = item_info['output_chapter_ref']

            progress.update(task_id, description=f"Content {item_number_to_assign} ({item_type})...")

            prompt = None
            expected_api_key = None
            try:
                # --- Generate Prompt (Logic remains same) ---
                if item_type == 'intro':
                    expected_api_key = "introduction_text"
                    prompt = generate_chapter_intro_prompt( final_output_data['bookTitle'], item_info['part_name'], item_info['chapter_title'], item_info['chapter_points'] )
                elif item_type == 'point':
                    expected_api_key = "point_content"
                    previous_content_summary = ""
                    try:
                         current_item_num_decimal = Decimal(item_number_to_assign)
                         preceding_items_text = []
                         output_chapter_ref['content'].sort(key=get_sort_key)
                         for item in output_chapter_ref.get('content', []):
                             if isinstance(item, dict) and 'item_number' in item and 'text' in item and item['text'] and "ERROR:" not in item['text']:
                                 try:
                                     item_num_decimal = Decimal(item['item_number'])
                                     if item_num_decimal < current_item_num_decimal: preceding_items_text.append(item['text'])
                                 except (InvalidOperation, TypeError): continue
                         previous_content_summary = "\n\n---\n\n".join(preceding_items_text)
                    except Exception as e: console.print(f"[warning]Could not gather preceding content for {log_key}: {e}[/warning]")
                    prompt = generate_point_prompt( final_output_data['bookTitle'], item_info['part_name'], item_info['chapter_title'], item_info['point_text'], item_number_to_assign, previous_content_summary )
                else: raise ValueError(f"Unknown item type: {item_type}")

            except Exception as e:
                 # (Error handling for prompt generation remains same)
                 error_msg = f"Error generating prompt for {log_key}: {e}"
                 console.print(f"[error]{error_msg}[/error]")
                 log_handler.log_error(log_data, stage_name, item_key, {"error": error_msg, "status": "prompt_error"})
                 error_entry = {'item_number': item_number_to_assign, 'type': item_type, 'text': f"ERROR: {error_msg}"}
                 if item_type == 'point': error_entry['original_point'] = item_info['point_text']
                 output_chapter_ref['content'] = [item for item in output_chapter_ref.get('content', []) if not (isinstance(item, dict) and item.get('item_number') == item_number_to_assign)]
                 output_chapter_ref['content'].append(error_entry)
                 output_chapter_ref['content'].sort(key=get_sort_key)
                 overall_success = False
                 log_handler.save_log(log_data, log_file_path)
                 progress.update(task_id, advance=1)
                 continue

            # --- Call API (Logic remains same) ---
            parsed_response, error_message = gemini_client.call_gemini_api(
                prompt=prompt, api_key=api_key, model_name=model_name,
                temperature=temperature, max_output_tokens=max_tokens,
                api_call_timestamps_deque=api_call_timestamps_deque,
                retry_count=config.API_RETRY_COUNT, item_key_for_log=log_key
            )

            # --- Process API Response ---
            item_entry = { 'item_number': item_number_to_assign, 'type': item_type, 'text': None }
            if item_type == 'point': item_entry['original_point'] = item_info['point_text']

            if parsed_response and expected_api_key and expected_api_key in parsed_response:
                item_entry['text'] = parsed_response[expected_api_key]
                if not item_entry['text']:
                     warn_msg = f"API returned empty content for {log_key}."
                     console.print(f"[warning]{warn_msg}[/warning]")
                     item_entry['text'] = f"WARNING: {warn_msg}"
                     log_handler.log_error(log_data, stage_name, item_key, {"warning": warn_msg, "status": "api_empty_response"})

                # Add/Update Item
                output_chapter_ref['content'] = [item for item in output_chapter_ref.get('content', []) if not (isinstance(item, dict) and item.get('item_number') == item_number_to_assign)]
                output_chapter_ref['content'].append(item_entry)
                output_chapter_ref['content'].sort(key=get_sort_key)

                log_handler.log_item_success(log_data, stage_name, item_key)
                processed_items_set.add(log_key)
                processed_in_stage += 1
                progress.update(task_id, advance=1, description=f"Done {item_number_to_assign}")

                # --- SAVE AFTER SUCCESS ---
                # Save interim content data and log immediately after success
                if not file_handler.save_json_file(final_output_data, interim_content_path):
                    console.print(f"[error]CRITICAL: Failed to save interim content data to {interim_content_path} after processing {log_key}! Potential data loss.[/error]")
                    # return None, False # Optionally stop
                if not log_handler.save_log(log_data, log_file_path):
                    console.print(f"[warning]Failed to save log file after processing {log_key}.[/warning]")
                # --- END SAVE AFTER SUCCESS ---

            else:
                # (Error handling for API failure remains same)
                 final_error_msg = error_message or f"API response missing expected key '{expected_api_key}'"
                 console.print(f"[error]Failed to generate content for {log_key}. Error: {final_error_msg}[/error]")
                 log_handler.log_error(log_data, stage_name, item_key, {"error": final_error_msg, "status": "api_failure_or_bad_format"})
                 item_entry['text'] = f"ERROR: Generation failed. {final_error_msg}"
                 # Add/Update Item with error
                 output_chapter_ref['content'] = [item for item in output_chapter_ref.get('content', []) if not (isinstance(item, dict) and item.get('item_number') == item_number_to_assign)]
                 output_chapter_ref['content'].append(item_entry)
                 output_chapter_ref['content'].sort(key=get_sort_key)
                 overall_success = False
                 # Save log immediately after error
                 log_handler.save_log(log_data, log_file_path)
                 progress.update(task_id, advance=1) # Advance past failed item

            gc.collect()


    # --- Finalization ---
    console.print("Ensuring final content structure and sorting...")
    # (Sorting logic remains same)
    for part in final_output_data.get('parts', []):
        part.get('chapters', []).sort(key=lambda x: x.get('chapter_number', 0))
        for chapter in part.get('chapters', []):
            chapter.get('content', []).sort(key=get_sort_key)

    # Save final content data
    console.print(f"Saving final content data state to [path]{final_content_path}[/path]...")
    if not file_handler.save_json_file(final_output_data, final_content_path):
        console.print(f"[error]CRITICAL: Failed to save FINAL content data to {final_content_path}! Potential data loss.[/error]")
        overall_success = False
        log_handler.log_error(log_data, stage_name, "final_save", {"error": f"Failed to save final content data to {final_content_path}"})
    else:
        # Clean up interim file on successful final save
        if interim_content_path.exists():
            try:
                interim_content_path.unlink()
                # console.print(f"Cleaned up interim file: [path]{interim_content_path}[/path]") # Less verbose
            except OSError as e:
                 console.print(f"[warning]Could not remove interim content file {interim_content_path}: {e}[/warning]")


    # Save final log state (already saved after last item/error, but safe to save again)
    log_handler.save_log(log_data, log_file_path)

    return final_output_data, overall_success