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
import json # Added for escaping input strings
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
    # Provide default for config attributes needed in this file if import fails
    config = type('obj', (object,), {
        'API_RETRY_COUNT': 3,
        'INTERIM_SAVE_FREQUENCY_CONTENT': 1, # Not used directly here but good practice
        'MAX_CONTEXT_SUMMARY_LENGTH': 2000
    })()
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
    # Try to find a reasonable break point near the desired length
    preferred_end = len(text) - max_length
    # Look for sentence endings first
    sentence_break = text.rfind(". ", max(0, preferred_end - 100), preferred_end + 100)
    # Then look for paragraph breaks
    para_break = text.rfind("\n\n", max(0, preferred_end - 100), preferred_end + 100)

    start_index = preferred_end # Default if no good break found nearby

    # Choose the break point closest to the preferred end, favoring paragraph breaks
    if para_break != -1 and (sentence_break == -1 or abs(para_break - preferred_end) <= abs(sentence_break - preferred_end)):
        start_index = para_break + 2 # Start after the double newline
    elif sentence_break != -1:
        start_index = sentence_break + 2 # Start after the period and space

    # Ensure start_index is within bounds
    start_index = min(start_index, len(text) - 1)
    start_index = max(0, start_index)

    # Construct the summary
    summary = text[start_index:].strip()
    if start_index > 0:
        # Add ellipsis only if text was actually trimmed
        summary = "... (trimmed preceding content) ...\n\n" + summary

    return summary

# --- Prompt Generation Functions (MODIFIED - Efficient, In-Depth Main Writer) ---

def generate_chapter_intro_prompt(book_title: str, part_name: str, chapter_title: str, chapter_points: List[str]) -> str:
    """
    Generates the prompt for writing an engaging, context-setting, and concise
    introduction for a chapter section.
    """
    # Escape inputs
    escaped_book_title = json.dumps(book_title)[1:-1]
    escaped_part_name = json.dumps(part_name)[1:-1]
    escaped_chapter_title = json.dumps(chapter_title)[1:-1]

    # Create a summary string from the points
    points_summary = "\n".join(f"{i+1}. {point}" for i, point in enumerate(chapter_points) if point)
    if not points_summary: points_summary = "(No specific points listed in outline)"
    # Escape the entire block of points for safe inclusion
    escaped_points_summary = json.dumps(points_summary)[1:-1]

    prompt = f"""You are an gemini-2.0-flashExpert Academic Writergemini-2.0-flash crafting an engaging, informative, and concise introduction for a specific chapter section.

BOOK CONTEXT:
- Book Title: "{escaped_book_title}"

CURRENT SECTION DETAILS:
- Part Name: "{escaped_part_name}"
- Chapter Section Title: "{escaped_chapter_title}"

OUTLINE OF POINTS COVERED IN THIS SECTION:
(Note: These points are detailed explanations outlining the core content.)
---
{escaped_points_summary}
---

TASK:
Write a compelling introduction for this chapter section that effectively sets the stage. Write in detail and depth. Make the text long and engaging. Cover every aspect in introduction.

OUTPUT FORMAT:
Your *entire* response MUST be a single, valid JSON object containing only one key, "introduction_text".
Example JSON Output:
{{
  "introduction_text": "Building on the established framework, this section critically examines the real-world application of Theory X across diverse cultures, assessing its practical challenges and enduring relevance. We analyze implementation hurdles, explore successful adaptations via case studies, and evaluate the theory's overall predictive power in contemporary management."
}}

CRITICAL INSTRUCTIONS:
1. Respond ONLY with the valid JSON object.
2. Do NOT include any text outside the JSON object.
3. Ensure the introduction is engaging, informative, previews key themes efficiently, and highlights significance concisely.
"""
    return prompt

def generate_point_prompt(
    book_title: str, part_name: str, chapter_section_title: str, point_text: str,
    point_number: str, previous_content_summary: Optional[str] = None
) -> str:
    """
    Generates the prompt for the main AI writer to create a detailed, enriched,
    and efficient elaboration of a content point, focusing on substantive depth.
    """
    # Escape inputs
    escaped_book_title = json.dumps(book_title)[1:-1]
    escaped_part_name = json.dumps(part_name)[1:-1]
    escaped_chapter_section_title = json.dumps(chapter_section_title)[1:-1]
    escaped_point_text = json.dumps(point_text)[1:-1] # The detailed outline point/directive
    escaped_point_number = json.dumps(point_number)[1:-1]

    context_section = "This is the first main content point in this chapter section following the introduction."
    if previous_content_summary and previous_content_summary.strip():
        summary_trimmed = _summarize_context(previous_content_summary.strip(), config.MAX_CONTEXT_SUMMARY_LENGTH)
        # Escape the potentially multi-line summary block
        escaped_summary = json.dumps(summary_trimmed)[1:-1]
        context_section = f"""PRECEDING CONTENT SUMMARY (Represents the flow of text generated so far in this section):
---
{escaped_summary}
---
"""
    else:
        # Escape the default context string
        context_section = json.dumps(context_section)[1:-1]

    prompt = f"""You are an expert on writing in depth, long, detailed, insightful, and efficiently written content for a book chapter. Your goal is to write on a specific directive, ensuring the reader gains a deep understanding ("understands everything") of the critical information without unnecessary verbosity. You main aim to explain every in length and detail.

    Important - Right Now you are writing for international relations of india/International polity/ Foregin policy of india. So cater to the audience accordingly.

BOOK CONTEXT:
- Book Title: "{escaped_book_title}"

CURRENT LOCATION IN BOOK:
- Part Name: "{escaped_part_name}"
- Chapter Section Title: "{escaped_chapter_section_title}"
- Current Item Number: {escaped_point_number} (Indicates position in the section's flow)

CORE DIRECTIVE / DETAILED OUTLINE POINT FOR THIS SEGMENT:
(This provides the central theme, concepts, and explanations to cover and expand upon)
---
"{escaped_point_text}"
---

CONTEXT FROM EARLIER IN THIS SECTION:
(Ensure your writing flows logically from this preceding text and avoids repetition)
{context_section}

TASK:
Write a gemini-2.0-flashthorough, detailed, enriched, AND efficient elaborationgemini-2.0-flash based *primarily* on the `CORE DIRECTIVE / DETAILED OUTLINE POINT FOR THIS SEGMENT` ({escaped_point_number}). Aim for depth and clarity worthy of publication.
- gemini-2.0-flashExpand Core Ideas Insightfully:gemini-2.0-flash Fully develop the concepts, arguments, and explanations from the Core Directive into clear, well-structured paragraphs. Focus on insightful explanations.
- gemini-2.0-flashEnrich with gemini-2.0-flashEssentialgemini-2.0-flash Detail:gemini-2.0-flash Actively add gemini-2.0-flashrelevantgemini-2.0-flash details crucial for deep understanding. Prioritize:
    - Necessary background context or precise definitions.
    - Clear explanations of important mechanisms, processes, or principles.
    - Highly relevant illustrative examples (generic types acceptable).
    - Key nuances, implications, or connections that significantly enhance comprehension.
- gemini-2.0-flashWrite Efficiently and Substantively:gemini-2.0-flash Explain concepts thoroughly but gemini-2.0-flashavoid unnecessary repetition or verbose phrasing.gemini-2.0-flash Focus on conveying gemini-2.0-flashimportant information and explanations directly and clearly.gemini-2.0-flash Maximize the substance delivered per sentence.
- gemini-2.0-flashEnsure Coherence:gemini-2.0-flash Critically analyze the 'PRECEDING CONTENT SUMMARY'. Your generated text MUST flow logically from it and gemini-2.0-flashstrictly avoid repeatinggemini-2.0-flash concepts already explained. Use transitions effectively.
- gemini-2.0-flashMaintain Focus:gemini-2.0-flash While enriching, ensure all added details are gemini-2.0-flashdirectly relevantgemini-2.0-flash to explaining or supporting the specific theme of the `CORE DIRECTIVE`. Do not introduce unrelated topics.
- gemini-2.0-flashAchieve Depth and Clarity:gemini-2.0-flash Produce writing that is precise, accurate, and sufficiently detailed for a comprehensive understanding of this segment.

OUTPUT FORMAT:
Your *entire* response MUST be a single, valid JSON object containing only one key, "point_content", with the generated detailed and efficient text as its string value.
Example JSON Output (Focusing on substance for Theory X assumptions):
{{
  "point_content": "McGregor's Theory X rests on specific assumptions about worker motivation that drive authoritarian management styles. Its first tenet is the inherent dislike of work: the average person avoids effort and responsibility. This necessitates external pressure, leading to the second assumption: coercion and control (e.g., threats, close supervision) are required for adequate organizational effort. This contrasts sharply with Theory Y's view of work as potentially fulfilling... [Explains implications for management structure concisely]. These assumptions, while criticized for oversimplification, highlight a control-oriented paradigm influencing... [Connects to broader management thought efficiently]."
}}

CRITICAL INSTRUCTIONS:
1. Respond ONLY with the valid JSON object.
2. Do NOT include any text outside the JSON object.
3. Ensure the generated text offers gemini-2.0-flashsubstantive depth and clarity without unnecessary verbositygemini-2.0-flash, faithfully elaborating and enriching the Core Directive while maintaining coherence and focus. Avoid redundancy.
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
            processed_items_set.clear() # Clear processed set if starting fresh


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
             # Skip if outline is missing, not a dict, or marked with an error
             if not isinstance(generated_outline, dict) or generated_outline.get("error"):
                 # Optionally log skipping this original chapter?
                 # console.print(f"[dim]Skipping content generation for original chapter {c_idx_orig} due to missing/invalid outline.[/dim]")
                 continue

             writing_sections = generated_outline.get('writing_sections', [])
             if not isinstance(writing_sections, list): writing_sections = []

             for s_idx, input_section in enumerate(writing_sections):
                 # Treat each writing section as a chapter in the output
                 chapter_counter_in_part += 1
                 current_chapter_number = chapter_counter_in_part # Unique chapter number within the part
                 output_chapter_title = input_section.get('section_title')
                 # Handle potentially missing section titles
                 if not output_chapter_title:
                      # Try to derive from original chapter title if possible, or use a placeholder
                      orig_ch_title = input_chapter_orig.get('title', f'Original Chapter {c_idx_orig+1}')
                      output_chapter_title = f"{orig_ch_title} - Section {s_idx+1}"
                      console.print(f"[warning]Outline section {s_idx} in original chapter {c_idx_orig} missing title. Using derived title: '{output_chapter_title}'[/warning]")


                 points_to_cover = input_section.get('content_points_to_cover', [])
                 if not isinstance(points_to_cover, list): points_to_cover = []

                 # Find or create the output chapter structure
                 output_chapter = chapter_map.get(output_chapter_title)
                 if output_chapter is None:
                      output_chapter = {'chapter_number': current_chapter_number, 'title': output_chapter_title, 'content': []}
                      # Add to the correct part's chapters list
                      output_part['chapters'].append(output_chapter)
                      # Update the map for potential reuse if titles aren't unique (though they should be)
                      chapter_map[output_chapter_title] = output_chapter
                 else:
                      output_chapter.setdefault('content', []) # Ensure content list exists

                 # Sort existing content for context gathering
                 output_chapter['content'].sort(key=get_sort_key)
                 content_map = {item.get('item_number'): item for item in output_chapter.get('content', [])}

                 # --- Check and add Intro item ---
                 intro_item_number_str = f"{current_chapter_number}.1"
                 intro_key = f"p{p_idx}-c{c_idx_orig}-s{s_idx}-intro" # Unique key based on original outline structure
                 log_key = f"{stage_name}:{intro_key}"
                 total_items_identified += 1
                 # Check if already processed (in log) OR exists validly in loaded data
                 intro_already_generated = log_key in processed_items_set or \
                     (intro_item_number_str in content_map and content_map[intro_item_number_str].get('text') and "ERROR:" not in content_map[intro_item_number_str]['text'])

                 if not intro_already_generated:
                      items_to_process.append({
                          'type': 'intro',
                          'key': intro_key,
                          'part_name': part_name,
                          'chapter_title': output_chapter_title, # Use the final output title
                          'chapter_points': [pt for pt in points_to_cover if pt], # Pass the actual points
                          'item_number_to_assign': intro_item_number_str,
                          'output_chapter_ref': output_chapter # Direct reference to modify
                      })

                 # --- Check and add Point items ---
                 for pt_idx, point_text in enumerate(points_to_cover):
                      if not point_text or not isinstance(point_text, str) or not point_text.strip():
                           # console.print(f"[dim]Skipping empty point at index {pt_idx} in section {s_idx} of original chapter {c_idx_orig}[/dim]")
                           continue # Skip empty or invalid points

                      point_item_number_str = f"{current_chapter_number}.{pt_idx + 2}" # Start points from .2
                      point_key = f"p{p_idx}-c{c_idx_orig}-s{s_idx}-p{pt_idx}" # Unique key
                      log_key = f"{stage_name}:{point_key}"
                      total_items_identified += 1
                      # Check if already processed OR exists validly in loaded data
                      point_already_generated = log_key in processed_items_set or \
                         (point_item_number_str in content_map and content_map[point_item_number_str].get('text') and "ERROR:" not in content_map[point_item_number_str]['text'])

                      if not point_already_generated:
                          items_to_process.append({
                              'type': 'point',
                              'key': point_key,
                              'part_name': part_name,
                              'chapter_title': output_chapter_title, # Use the final output title
                              'point_text': point_text, # The detailed point from outline
                              'item_number_to_assign': point_item_number_str,
                              'output_chapter_ref': output_chapter # Direct reference
                          })

        # Ensure chapters within each part are sorted numerically after identification
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
            output_chapter_ref = item_info['output_chapter_ref'] # Direct reference to the chapter dict

            progress.update(task_id, description=f"Content {item_number_to_assign} ({item_type})...")

            prompt = None
            expected_api_key = None
            try:
                # --- Generate Prompt using the MODIFIED functions ---
                if item_type == 'intro':
                    expected_api_key = "introduction_text"
                    prompt = generate_chapter_intro_prompt(
                        final_output_data['bookTitle'],
                        item_info['part_name'],
                        item_info['chapter_title'],
                        item_info['chapter_points']
                    )
                elif item_type == 'point':
                    expected_api_key = "point_content"
                    # --- Gather Preceding Context (Improved Robustness) ---
                    previous_content_summary = ""
                    try:
                         current_item_num_decimal = Decimal(item_number_to_assign)
                         preceding_items_text = []
                         # Ensure content list exists and is sorted before gathering context
                         output_chapter_ref.setdefault('content', [])
                         output_chapter_ref['content'].sort(key=get_sort_key)

                         for item in output_chapter_ref.get('content', []):
                             # Check item validity more carefully
                             if isinstance(item, dict) and \
                                item.get('item_number') and \
                                isinstance(item.get('text'), str) and \
                                item['text'] and \
                                "ERROR:" not in item['text']:
                                 try:
                                     item_num_decimal = Decimal(item['item_number'])
                                     # Only include items strictly before the current one
                                     if item_num_decimal < current_item_num_decimal:
                                         preceding_items_text.append(item['text'])
                                 except (InvalidOperation, TypeError, ValueError):
                                     # Ignore items with invalid numbers
                                     # console.print(f"[dim]Skipping item with invalid number '{item.get('item_number')}' during context gathering for {log_key}[/dim]")
                                     continue
                         # Join the valid preceding texts
                         previous_content_summary = "\n\n---\n\n".join(preceding_items_text)
                    except Exception as e:
                        # Log specific error during context gathering
                        console.print(f"[warning]Could not gather preceding content for {log_key} due to error: {e}[/warning]")
                        # Proceed without context summary if gathering fails
                        previous_content_summary = "" # Ensure it's reset

                    prompt = generate_point_prompt(
                        final_output_data['bookTitle'],
                        item_info['part_name'],
                        item_info['chapter_title'],
                        item_info['point_text'],
                        item_number_to_assign,
                        previous_content_summary
                    )
                else:
                    # Should not happen if item identification is correct
                    raise ValueError(f"Unknown item type encountered: {item_type}")

            except Exception as e:
                 # (Error handling for prompt generation remains same)
                 error_msg = f"Error generating prompt for {log_key}: {e}"
                 console.print(f"[error]{error_msg}[/error]")
                 log_handler.log_error(log_data, stage_name, item_key, {"error": error_msg, "status": "prompt_error"})
                 # --- Update content with error (Improved) ---
                 error_entry = {'item_number': item_number_to_assign, 'type': item_type, 'text': f"ERROR: Prompt generation failed. {error_msg}"}
                 if item_type == 'point': error_entry['original_point'] = item_info.get('point_text', 'N/A') # Add original point if available
                 # Ensure content list exists
                 output_chapter_ref.setdefault('content', [])
                 # Remove any previous entry for this item number before adding error
                 output_chapter_ref['content'] = [item for item in output_chapter_ref['content'] if not (isinstance(item, dict) and item.get('item_number') == item_number_to_assign)]
                 output_chapter_ref['content'].append(error_entry)
                 output_chapter_ref['content'].sort(key=get_sort_key)
                 # --- End Update content with error ---
                 overall_success = False
                 log_handler.save_log(log_data, log_file_path) # Save log after prompt error
                 if task_id is not None: progress.update(task_id, advance=1)
                 continue # Skip API call for this item

            # --- Call API (Logic remains same) ---
            parsed_response, error_message = gemini_client.call_gemini_api(
                prompt=prompt, api_key=api_key, model_name=model_name,
                temperature=temperature, max_output_tokens=max_tokens,
                api_call_timestamps_deque=api_call_timestamps_deque,
                retry_count=config.API_RETRY_COUNT, item_key_for_log=log_key
            )

            # --- Process API Response ---
            # Prepare basic item entry structure
            item_entry = { 'item_number': item_number_to_assign, 'type': item_type, 'text': None }
            if item_type == 'point':
                item_entry['original_point'] = item_info.get('point_text', 'N/A')

            # Check response validity
            if parsed_response and expected_api_key and isinstance(parsed_response.get(expected_api_key), str):
                generated_text = parsed_response[expected_api_key].strip()
                if generated_text:
                    item_entry['text'] = generated_text
                    log_status = "api_success"
                else:
                     # Handle cases where API returns the key but with empty/whitespace string
                     warn_msg = f"API returned empty content for key '{expected_api_key}' for {log_key}."
                     console.print(f"[warning]{warn_msg}[/warning]")
                     item_entry['text'] = f"WARNING: {warn_msg}"
                     log_status = "api_empty_response"
                     log_handler.log_error(log_data, stage_name, item_key, {"warning": warn_msg, "status": log_status})

                # --- Add/Update Item in chapter content (Improved) ---
                output_chapter_ref.setdefault('content', [])
                # Remove previous entry for this item number
                output_chapter_ref['content'] = [item for item in output_chapter_ref['content'] if not (isinstance(item, dict) and item.get('item_number') == item_number_to_assign)]
                output_chapter_ref['content'].append(item_entry)
                output_chapter_ref['content'].sort(key=get_sort_key)
                # --- End Add/Update Item ---

                # Log success only if content was non-empty
                if log_status == "api_success":
                    log_handler.log_item_success(log_data, stage_name, item_key)
                processed_items_set.add(log_key) # Mark as processed even if warning/empty
                processed_in_stage += 1
                if task_id is not None: progress.update(task_id, advance=1, description=f"Done {item_number_to_assign}")

                # --- SAVE AFTER SUCCESS/Warning ---
                # Save interim content data and log immediately
                if not file_handler.save_json_file(final_output_data, interim_content_path):
                    console.print(f"[error]CRITICAL: Failed to save interim content data to {interim_content_path} after processing {log_key}! Potential data loss.[/error]")
                    # Consider stopping if save fails: return None, False
                if not log_handler.save_log(log_data, log_file_path):
                    console.print(f"[warning]Failed to save log file after processing {log_key}.[/warning]")
                # --- END SAVE AFTER SUCCESS/Warning ---

            else:
                # Handle API failure or invalid response format
                 final_error_msg = error_message or f"API response invalid or missing expected key '{expected_api_key}'"
                 console.print(f"[error]Failed to generate content for {log_key}. Error: {final_error_msg}[/error]")
                 log_handler.log_error(log_data, stage_name, item_key, {"error": final_error_msg, "status": "api_failure_or_bad_format"})
                 item_entry['text'] = f"ERROR: Generation failed. {final_error_msg}"
                 # --- Add/Update Item with error (Improved) ---
                 output_chapter_ref.setdefault('content', [])
                 output_chapter_ref['content'] = [item for item in output_chapter_ref['content'] if not (isinstance(item, dict) and item.get('item_number') == item_number_to_assign)]
                 output_chapter_ref['content'].append(item_entry)
                 output_chapter_ref['content'].sort(key=get_sort_key)
                 # --- End Add/Update Item with error ---
                 overall_success = False
                 # Save log immediately after error
                 log_handler.save_log(log_data, log_file_path)
                 if task_id is not None: progress.update(task_id, advance=1) # Advance past failed item

            gc.collect() # Garbage collection remains the same


    # --- Finalization ---
    console.print("Ensuring final content structure and sorting...")
    # (Sorting logic remains same)
    for part in final_output_data.get('parts', []):
        part.get('chapters', []).sort(key=lambda x: x.get('chapter_number', 0))
        for chapter in part.get('chapters', []):
             # Ensure content exists before sorting
             chapter.setdefault('content', [])
             chapter['content'].sort(key=get_sort_key)

    # Save final content data
    console.print(f"Saving final content data state to [path]{final_content_path}[/path]...")
    if not file_handler.save_json_file(final_output_data, final_content_path):
        console.print(f"[error]CRITICAL: Failed to save FINAL content data to {final_content_path}! Potential data loss.[/error]")
        overall_success = False
        log_handler.log_error(log_data, stage_name, "final_save", {"error": f"Failed to save final content data to {final_content_path}"})
    else:
        # Clean up interim file only on successful final save
        if interim_content_path.exists():
            try:
                interim_content_path.unlink()
                # console.print(f"Cleaned up interim file: [path]{interim_content_path}[/path]")
            except OSError as e:
                 console.print(f"[warning]Could not remove interim content file {interim_content_path}: {e}[/warning]")


    # Save final log state (important to capture final state)
    log_handler.save_log(log_data, log_file_path)

    return final_output_data, overall_success