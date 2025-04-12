
# Gemini Book Content Generator

## Overview

This Python script automates the generation of detailed book content using the Google Gemini API. It takes a structured JSON file containing a book outline (organized into parts and sections that define chapters) and generates:

1.  An **Introduction** for each defined chapter.
2.  Detailed **Elaborations** for specific points listed within each chapter.

A key feature is its **contextual awareness**: when generating content for a point, it considers the introduction and preceding points within the same chapter to improve coherence and minimize repetition. It's designed for tasks like creating academic material or detailed guides from an outline.

**Key Features:**

* **AI Content Generation:** Uses the Google Gemini API (configurable model).
* **Structured Processing:** Works with a specific input JSON format.
* **Contextual Prompts:** Provides preceding text to the AI when generating points to avoid redundancy.
* **Hierarchical Numbering:** Outputs content with clear numbering (Part `A1`, Chapter `1`, Items `1.1` (Intro), `1.2`, `1.3`...).
* **Resumption:** Tracks progress via a log file and can resume generation if interrupted.
* **Incremental Saving:** Saves progress periodically to an interim file.
* **Rate Limiting:** Manages API calls to stay within limits.
* **Error Handling:** Includes retries for API calls and attempts to fix malformed JSON responses.
* **Rich Output:** Uses the `rich` library (if available) for enhanced terminal display and progress bars.

## How it Works (Conceptual Flow)

1.  **Parse Arguments:** Reads command-line arguments for input file, output directory, model name, and optional API test flag.
2.  **Load Input:** Reads and validates the input JSON outline file.
3.  **Initialize/Load State:**
    * Checks for an existing log file (`*_content_log.json`) to identify already processed items.
    * Checks for an existing interim output file (`*_content_interim.json`) to load previously generated content.
    * Initializes a new output data structure or uses the loaded interim data.
4.  **Identify Work & Build Skeleton:**
    * Iterates through the input structure (`parts` -> original `chapters` -> `writing_sections`).
    * **Crucially, treats each `writing_section` object from the input as a distinct Chapter for the output.**
    * Creates the basic structure (Parts and Chapters with numbers) in the `output_data` if it doesn't exist (e.g., when starting fresh or adding new sections to the input).
    * For each output Chapter (derived from `writing_section`):
        * Identifies the **Introduction** item (numbered `ChapterNum.1`).
        * Identifies each **Point** item from `content_points_to_cover` (numbered `ChapterNum.2`, `ChapterNum.3`, etc.).
        * Compares these identified items against the log file and the loaded interim data. Only items not already successfully processed are added to a list of work items.
5.  **Process Items Loop:** Iterates through the list of work items (introductions and points).
    * **Rate Limit:** Waits if necessary to avoid exceeding the API call limit per minute.
    * **Find Output Location:** Locates the correct Part and Chapter within the `output_data` structure where the generated content should be stored.
    * **Generate Prompt:**
        * **For Intros:** Calls `generate_chapter_intro_prompt` with the chapter title (from `section_title`) and a summary of its points.
        * **For Points:** Calls `generate_point_prompt`. This involves:
            * Retrieving the already generated text for the introduction and any preceding points *within the same chapter* from the `output_data`.
            * Including this preceding text (trimmed if necessary) in the prompt.
            * Adding specific instructions to the prompt telling the AI to *avoid repetition* and build upon the provided context while focusing *only* on the current point.
    * **Call Gemini API:** Sends the generated prompt to the specified Gemini model using `call_gemini_api_for_content`, which handles retries and basic JSON response fixing.
    * **Store Result:** Adds the generated text (or an error message) to the correct chapter's `content` list in the `output_data`. Each entry includes the `item_number`, `type` ('introduction' or 'point'), and the `text`. Point entries also include the `original_point`.
    * **Sort Content:** Ensures the `content` list within the chapter remains sorted by `item_number`.
    * **Log Progress:** Adds the item's unique key to the `processed_points` set in the log data.
    * **Save Incrementally:** Periodically saves the current `output_data` to the interim file and the `log_data` to the log file.
6.  **Finalization:**
    * Performs a final sort of the generated content.
    * Saves the complete `output_data` one last time.
    * Renames the interim file to the final timestamped output file (e.g., `*_content_YYYYMMDD_HHMMSS.json`).
    * Saves the final log file.

## Input JSON Format

The script expects a JSON file with the following structure:

```json
{
  "bookTitle": "Your Book Title Here",
  "parts": [ // List of Parts
    {
      "name": "Part I: Name of the First Part",
      // List of original input chapters - used primarily to group writing sections
      "chapters": [
        {
          // These 'title' and 'description' from the input are NOT directly used
          // for output chapter titles/intros anymore but provide structure.
          "title": "Original Input Chapter Title (Contextual)",
          "description": "Original Input Chapter Description (Contextual)",
          "generated_outline": {
            // List of sections that WILL BECOME Chapters in the output
            "writing_sections": [
              {
                // This becomes the Title of an output Chapter
                "section_title": "Title of Output Chapter 1",
                // These become points within Output Chapter 1 (numbered 1.2, 1.3...)
                "content_points_to_cover": [
                  "Point 1 text for Chapter 1",
                  "Point 2 text for Chapter 1",
                  "..."
                ],
                "Google Search_terms": [ /* Optional search terms, not used by this script */ ]
              },
              {
                // This becomes the Title of Output Chapter 2
                "section_title": "Title of Output Chapter 2",
                 // These become points within Output Chapter 2 (numbered 2.2, 2.3...)
                "content_points_to_cover": [
                  "Point 1 text for Chapter 2",
                  "Point 2 text for Chapter 2",
                  "..."
                ]
              }
              // ... more writing_sections (output chapters)
            ]
          }
        }
        // ... more original input chapters if needed to organize writing_sections
      ]
    }
    // ... more parts
  ]
}
```

**Key Interpretation:** Each object inside the `"writing_sections"` array is treated as a **Chapter** by the script. Its `"section_title"` becomes the output Chapter's title, and its `"content_points_to_cover"` become the points within that Chapter.

## Output JSON Format

The script generates a new JSON file containing the processed content:

```json
{
  "bookTitle": "Your Book Title Here",
  "generation_model": "gemini-1.5-flash-8b", // Model used
  "generation_timestamp": "YYYY-MM-DDTHH:MM:SS.ssssss", // Timestamp
  "parts": [ // List of Parts
    {
      "part_number": "A1", // Part Number
      "name": "Part I: Name of the First Part",
      "chapters": [ // List of generated Chapters (from writing_sections)
        {
          "chapter_number": 1, // Chapter Number (sequential within Part)
          "title": "Title of Output Chapter 1", // From section_title
          "content": [ // Ordered list of Intro + Points for this Chapter
            {
              "item_number": "1.1", // Intro number
              "type": "introduction",
              "text": "Generated introduction text for Chapter 1..." // or ERROR message
            },
            {
              "item_number": "1.2", // First Point number
              "type": "point",
              "original_point": "Point 1 text for Chapter 1", // From input
              "text": "Generated elaboration for Point 1.2..." // or ERROR message
            },
            {
              "item_number": "1.3", // Second Point number
              "type": "point",
              "original_point": "Point 2 text for Chapter 1",
              "text": "Generated elaboration for Point 1.3..."
            }
            // ... more points for Chapter 1
          ]
        },
        {
          "chapter_number": 2,
          "title": "Title of Output Chapter 2",
          "content": [
            {
              "item_number": "2.1", // Intro for Chapter 2
              "type": "introduction",
              "text": "Generated introduction text for Chapter 2..."
            },
            {
              "item_number": "2.2", // First Point for Chapter 2
              "type": "point",
              "original_point": "Point 1 text for Chapter 2",
              "text": "Generated elaboration for Point 2.2..."
            }
            // ... more points for Chapter 2
          ]
        }
        // ... more chapters
      ]
    }
    // ... more parts (e.g., part_number: "A2")
  ]
}
```

## Setup and Requirements

1.  **Python:** Python 3.7 or higher recommended.
2.  **Libraries:** Install required libraries:
    ```bash
    pip install google-generativeai python-dotenv rich
    ```
    * `google-generativeai`: For interacting with the Gemini API.
    * `python-dotenv`: For loading the API key from a `.env` file.
    * `rich`: (Optional, but recommended) For better terminal output (progress bars, colors). The script includes a basic fallback if `rich` is not installed.
3.  **Google API Key:** You need a valid Google API key enabled for the Gemini API (e.g., via Google AI Studio). Ensure billing is enabled for your associated Google Cloud project if required by the model used.

## Configuration

1.  **API Key:** The script looks for the Google API key in an environment variable named `GOOGLE_API_KEY`. You can set this variable in your system or, more conveniently, create a file named `.env` in the same directory as the script and place the key inside it like this:
    ```
    GOOGLE_API_KEY=YOUR_API_KEY_HERE
    ```
2.  **Constants (Optional Adjustments):** You can modify these constants at the top of the script:
    * `DEFAULT_MODEL`: The default Gemini model name to use if not specified via command line.
    * `API_CALL_LIMIT_PER_MINUTE`: Adjust based on the rate limits for your chosen model (check Google's documentation).
    * `API_RETRY_COUNT`: How many times to retry a failed API call.
    * `INTERIM_SAVE_FREQUENCY`: How often (after how many items) to save progress to the interim file.
    * `MAX_CONTEXT_SUMMARY_LENGTH`: Maximum characters of preceding content to send in prompts for points (to avoid overly long prompts).

## How to Run

Execute the script from your terminal using Python.

**Syntax:**

```bash
python your_script_name.py --input_file <path_to_input.json> [options]
```

**Arguments:**

* `--input_file <path>`: **(Required)** The path to your structured input JSON file (as described in "Input JSON Format").
* `--output_dir <path>`: (Optional) The directory where the output files (content JSON, log JSON) will be saved. Defaults to `./results/Content`.
* `--model <model_name>`: (Optional) The specific Gemini model name you want to use (e.g., `gemini-1.5-pro-latest`). Defaults to the value of `DEFAULT_MODEL` in the script or the `DEFAULT_GEMINI_MODEL` environment variable if set.
* `--test`: (Optional) If included, runs a quick API connection test using your key and specified model before starting the main processing.

**Example Command:**

```bash
python generate_content.py --input_file my_book_outline.json --output_dir ./output_files --model gemini-1.5-flash-latest
```

## Files Generated

The script creates files in the specified output directory (default: `results/Content`):

1.  **Final Content File:** `*_content_YYYYMMDD_HHMMSS.json` - Contains the final generated content with numbering and structure. The initial part of the filename matches your input file's stem.
2.  **Log File:** `*_content_log.json` - Tracks the script's execution, including start/end times, which items were processed (for resumption), API call details (optional), and any errors encountered.
3.  **Interim File:** `*_content_interim.json` - Used for saving progress incrementally during a run. It is automatically renamed to the final content file upon successful completion. If the script is interrupted or fails, this file contains the progress up to that point.

