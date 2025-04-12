
# Gemini Book Outline & Content Generator

**Version:** 1.1 (Based on discussion up to April 12, 2025)

## Overview

This program automates the process of generating structured book content using Google's Gemini large language models. It takes a simple JSON input defining the book's parts and chapter goals, and performs a two-stage process:

1.  **Outline Generation:** Creates a detailed, sectioned outline for each chapter based on its title and description, including specific content points and suggested search terms.
2.  **Content Generation:** Elaborates on the generated outlines, writing an introduction and detailed paragraphs for each content point within every section, maintaining context between points.

The program is designed to be modular, resilient (with retries and logging), and allows resuming interrupted runs.

## Features

* **Two-Stage Generation:** Separates outline creation from detailed content writing.
* **Gemini API Integration:** Leverages Google's Generative AI models.
* **Modular Design:** Code is organized into logical modules (API client, stages, utilities).
* **Configuration:** Easily configure API keys, models, and other parameters via `.env` and `config.py`.
* **Logging:** Records detailed progress, API calls, and errors into a run-specific log file.
* **Resumption:** Automatically detects previous runs (via log file) and resumes processing from where it left off.
* **Incremental Saving:** Saves progress within each stage after every successfully generated item to minimize data loss on interruption.
* **Error Handling:** Includes API call retries with exponential backoff and logs errors gracefully.
* **Rich Console Output:** Provides informative progress bars and status messages (if `rich` library is installed).

## Project Structure

```
your_project_directory/
├── main.py                     # Main script - orchestrates the workflow
├── requirements.txt            # Lists Python dependencies
├── .env                        # Stores the GOOGLE_API_KEY (and optional model defaults)
├── config.py                   # Advanced configuration constants (limits, temps, defaults)
├── input_files/                # Directory for user's input JSON files
│   └── example_structure.json  # Example input file structure
├── results/                    # Default output directory
│   └── example_structure/      # Subdirectory created for each input file's results
│       ├── example_structure_outlined.json         # Intermediate outline file (Stage 1 output)
│       ├── example_structure_content_interim.json  # Temporary content file (used during Stage 2)
│       ├── example_structure_content_YYYYMMDD_HHMMSS.json # Final content file (Stage 2 output)
│       └── example_structure_combined_log.json     # Unified log file for the run
├── api/
│   └── gemini_client.py        # Handles all Gemini API calls, retries, JSON fixing, rate limiting
├── stages/
│   ├── outline_generator.py    # Logic for Stage 1: Generating the outline
│   └── content_generator.py    # Logic for Stage 2: Generating the content
└── utils/
    ├── file_handler.py         # Functions for loading/saving JSON files reliably
    ├── log_handler.py          # Functions for managing the unified log file
    └── console_utils.py        # Setup for Rich/Simple console and progress bars
```

## How it Works

The program operates in a pipeline orchestrated by `main.py`:

1.  **Initialization:** Parses command-line arguments, loads the API key, sets up paths, and initializes the logger (`log_handler.py`). It checks for an existing log file for the given input to determine if it's a new run or a resumption.
2.  **Stage 1: Outline Generation (`stages/outline_generator.py`)**
    * If starting or resuming Stage 1, it reads the input structure JSON file.
    * It iterates through each chapter defined in the input.
    * For each chapter, it constructs a specific prompt asking the Gemini API to generate a detailed outline, broken into logical sections (`writing_sections`), each with `content_points_to_cover` and `Google Search_terms`.
    * It calls the central API client (`api/gemini_client.py`) to interact with Gemini. The client handles retries, rate limiting, and basic response cleaning.
    * The generated outline (a JSON object) is added to the chapter data in memory.
    * After *each* successful outline generation, the entire updated data structure is saved to the intermediate `_outlined.json` file, and the log file is updated.
    * If an error occurs for a chapter, it's logged, an error marker is added to the data, and the process continues with the next chapter.
3.  **Stage 2: Content Generation (`stages/content_generator.py`)**
    * If Stage 1 is complete (or was completed in a previous run), this stage begins. It loads the data from the `_outlined.json` file.
    * It identifies all individual items needing generation: an introduction (`.1`) for each `writing_section` (which now acts as a chapter/sub-chapter in the output) and an elaboration (`.2`, `.3`, etc.) for each `content_point_to_cover` within those sections. It skips items marked as processed in the log file.
    * It iterates through these items:
        * **Introductions:** Generates a prompt asking Gemini to write an introduction for the specific chapter section, considering its title and points.
        * **Points:** Gathers the text generated so far within the *current* chapter section (intro + previous points), summarizes it if necessary (to manage context length), and generates a prompt asking Gemini to elaborate *only* on the current point, building upon the preceding context without repetition.
    * It calls the API client (`api/gemini_client.py`) for each item.
    * The generated text is inserted into the final output data structure being built in memory. The content for each chapter section is kept sorted by item number (e.g., `1.1`, `1.2`, `1.3`).
    * After *each* successful content generation, the *entire* current state of the final output data is saved to a temporary `_content_interim.json` file, and the log file is updated.
    * If an error occurs, it's logged, an `ERROR:` message is inserted into the content, and processing continues.
4.  **Finalization:** Once Stage 2 completes, the temporary `_content_interim.json` is renamed to the final timestamped `_content_YYYYMMDD_HHMMSS.json` file, and the log file is updated with the final status and end time.

## Input JSON Format (`input_files/*.json`)

The program expects an input JSON file containing the high-level structure of the book.

* **`bookTitle`** (String): The title of the book.
* **`parts`** (Array): A list of the main parts of the book.
    * Each element in `parts` is an **Object** with:
        * **`name`** (String): The name of the part (e.g., "Part 1: Foundations").
        * **`chapters`** (Array): A list of chapters within this part.
            * Each element in `chapters` is an **Object** with:
                * **`title`** (String): The proposed title of the chapter.
                * **`description`** (String): A detailed description of the chapter's goal, scope, and the key topics it should cover. This description is crucial for generating a good outline.

**Example (`input_files/my_book_structure.json`):**

```json
{
  "bookTitle": "Understanding Modern Diplomacy",
  "parts": [
    {
      "name": "Part 1: Core Concepts",
      "chapters": [
        {
          "title": "Introduction to Diplomacy",
          "description": "Define diplomacy and its role in international relations. Discuss its historical evolution briefly. Explain key concepts like negotiation, mediation, soft power, and public diplomacy. Outline the functions of diplomatic missions."
        },
        {
          "title": "National Interest",
          "description": "Explore the concept of national interest as a driver of foreign policy and diplomatic action. Analyze how different states define and pursue their interests. Discuss the interplay between domestic factors and national interest."
        }
      ]
    },
    {
      "name": "Part 2: Diplomatic Practice",
      "chapters": [
        {
          "title": "Bilateral Diplomacy",
          "description": "Examine the mechanisms and challenges of state-to-state diplomacy. Analyze summit diplomacy, treaties, and the role of ambassadors."
        }
      ]
    }
  ]
}
```

## Output JSON Format (`results/.../*_content_*.json`)

The final output is a JSON file containing the generated content, structured based on the outlines created in Stage 1.

* **`bookTitle`** (String): Copied from the input.
* **`generation_model_outline`** (String): The Gemini model used for Stage 1.
* **`generation_model_content`** (String): The Gemini model used for Stage 2.
* **`generation_timestamp`** (String): ISO timestamp when the content generation process (Stage 2) started or was last updated.
* **`parts`** (Array): A list of the main parts, corresponding to the input.
    * Each element is an **Object** with:
        * **`part_number`** (String): A generated identifier (e.g., "P1", "P2").
        * **`name`** (String): The name of the part, copied from the input.
        * **`chapters`** (Array): A list of chapters/sections generated within this part. **Note:** Each `writing_section` generated by the outline stage becomes a `chapter` object here.
            * Each element is an **Object** with:
                * **`chapter_number`** (Integer): The sequential number of this chapter/section *within the part*.
                * **`title`** (String): The `section_title` generated by the outline stage.
                * **`content`** (Array): A list containing the generated introduction and point elaborations for this chapter/section, sorted numerically.
                    * Each element is an **Object** with:
                        * **`item_number`** (String): The identifier within the chapter (e.g., "1.1", "1.2", "2.1", "2.10"). ".1" is always the introduction.
                        * **`type`** (String): "introduction" or "point".
                        * **`original_point`** (String, Optional): For `type: "point"`, this stores the corresponding text from the outline's `content_points_to_cover`.
                        * **`text`** (String): The actual content generated by Gemini for this item. If generation failed, this will contain an "ERROR:" message.

**Example Snippet (`results/.../my_book_structure_content_....json`):**

```json
{
  "bookTitle": "Understanding Modern Diplomacy",
  "generation_model_outline": "gemini-1.5-flash",
  "generation_model_content": "gemini-1.5-pro",
  "generation_timestamp": "2025-04-12T13:00:00.123456+05:30",
  "parts": [
    {
      "part_number": "P1",
      "name": "Part 1: Core Concepts",
      "chapters": [
        {
          "chapter_number": 1,
          "title": "Defining Diplomacy and its Functions", // Title from Outline Section 1
          "content": [
            {
              "item_number": "1.1",
              "type": "introduction",
              "text": "This initial section lays the groundwork by defining the essential nature of diplomacy within the complex web of international relations. We will explore its core meaning, trace its evolution, and delineate the primary functions it serves in facilitating interactions between states and other global actors..." // Generated Intro
            },
            {
              "item_number": "1.2",
              "type": "point",
              "original_point": "Define diplomacy and its role in international relations.", // From Outline Point 1
              "text": "Diplomacy, in its essence, refers to the art and practice of conducting negotiations between representatives of states or organizations. It is the primary mechanism through which independent global actors manage their relationships without resorting to force..." // Generated Point Elaboration
            },
            {
              "item_number": "1.3",
              "type": "point",
              "original_point": "Discuss its historical evolution briefly.", // From Outline Point 2
              "text": "While modern diplomacy has distinct features, its roots can be traced back to ancient times... The Peace of Westphalia in 1648 is often considered a pivotal moment..." // Generated Point Elaboration
            },
            // ... more points for chapter 1 ...
             {
              "item_number": "1.6",
              "type": "point",
              "original_point": "Outline the functions of diplomatic missions.",
              "text": "ERROR: Generation failed. API call blocked for item 'content:p0-c0-s0-p4'. Reason: HARM_CATEGORY_DANGEROUS_CONTENT." // Example Error
            }
          ]
        },
        {
          "chapter_number": 2,
          "title": "Understanding National Interest Paradigms", // Title from Outline Section 2
          "content": [
            {
              "item_number": "2.1",
              "type": "introduction",
              "text": "Building upon the definition of diplomacy, this section focuses on a critical driving force behind it: the concept of national interest..." // Generated Intro
            },
            // ... points for chapter 2 ...
          ]
        },
        // ... more chapters derived from outline sections ...
      ]
    },
    // ... more parts ...
  ]
}
```

## Intermediate Files

* **`_outlined.json`**: Stores the output of Stage 1. It's essentially the input structure JSON enriched with the `generated_outline` data for each chapter. This file is used as the input for Stage 2.
* **`_content_interim.json`**: A temporary file used during Stage 2 to save the progress of content generation incrementally. It gets renamed to the final `_content_*.json` upon successful completion of Stage 2.

## Log File (`_combined_log.json`)

A log file is created for each run in the `results/<input_stem>/` directory. It's crucial for:

* **Tracking Progress:** Shows the overall status (`pending_outline`, `outline_complete`, `pending_content`, `content_complete`, `error`).
* **Resumption:** Stores a list (`processed_items`) of successfully completed items (e.g., `"outline:p0-ch1"`, `"content:p0-c0-s0-intro"`). When the script restarts, it reads this list to skip already finished work.
* **Debugging:** Records errors (`errors` list) with timestamps, stages, and details. It can optionally log details of individual API calls (`api_calls`).

## Setup

1.  **Get the Code:** Download or clone the project repository.
2.  **Python Environment:** It's recommended to create a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate   # Windows
    ```
3.  **Create `requirements.txt`:** In the project root, create this file:
    ```text
    # requirements.txt
    google-generativeai
    python-dotenv
    rich
    ```
4.  **Install Dependencies:** From the project root directory, run:
    ```bash
    pip install -r requirements.txt
    ```
5.  **Create `.env` File:** In the project root, create a `.env` file and add your Google Cloud API Key:
    ```dotenv
    # .env
    GOOGLE_API_KEY=YOUR_ACTUAL_API_KEY_HERE

    # Optional: Override default models from config.py
    # DEFAULT_GEMINI_MODEL=gemini-1.5-pro
    # OUTLINE_GEMINI_MODEL=gemini-1.5-flash
    ```
    * **Important:** Ensure your Google Cloud project associated with the API key has billing enabled and the Generative AI API is enabled.
    * **Security:** Keep your `.env` file private and **do not** commit it to version control (add `.env` to your `.gitignore` file).
6.  **Prepare Input:** Create your input JSON file (following the format described above) and place it inside the `input_files/` directory.

## How to Run

Execute the `main.py` script from the **root directory** of the project.

**Basic Command:**

```bash
python main.py --input_file input_files/YOUR_INPUT_FILENAME.json
```
(Replace `YOUR_INPUT_FILENAME.json` with your actual file name).

**Command-Line Flags:**

* `--input_file <path>`: **(Required)** Path to the input JSON structure file (relative to the project root, e.g., `input_files/my_book.json`).
* `--output_dir <path>`: (Optional) Path to the base directory where results (logs, outlines, content) will be saved. A subdirectory named after the input file stem will be created inside this directory. (Default: `results`)
* `--model <model_name>`: (Optional) Specifies a general default Gemini model name (e.g., `gemini-1.5-pro`). If `--outline_model` or `--content_model` are not provided, they will inherit this value. (Default: Value from `config.DEFAULT_GEMINI_MODEL` or `.env`)
* `--outline_model <model_name>`: (Optional) Specifies the exact Gemini model to use *only* for Stage 1 (Outline Generation). (Default: Value from `config.OUTLINE_GEMINI_MODEL`, `.env`, or `--model`)
* `--content_model <model_name>`: (Optional) Specifies the exact Gemini model to use *only* for Stage 2 (Content Generation). (Default: Value from `config.DEFAULT_GEMINI_MODEL`, `.env`, or `--model`)
* `--test`: (Optional) If included, runs a quick API connection test for the specified models before starting processing and then exits. Useful for verifying API key and model validity.
* `--force-restart`: (Optional) If included, the script will ignore any existing log file for the specified input file and start the entire process from scratch (Stage 1). Useful if a previous run was corrupted.

## Configuration (`config.py`)

The `config.py` file contains constants that control the program's behavior, such as API retry counts, rate limits, generation temperatures, maximum token limits, and default model names. Advanced users can modify these values directly in the file if needed. Settings in `.env` (like `DEFAULT_GEMINI_MODEL`) can override defaults in `config.py`. Command-line arguments override both `.env` and `config.py`.

## Troubleshooting

* **API Key Errors / Billing Errors:** Check your `.env` file for the correct `GOOGLE_API_KEY`. Ensure the associated Google Cloud project has billing enabled and the Generative Language API is active.
* **Model Not Found Errors:** Verify the model names passed via command line or set in `config.py`/`.env` are correct and available in your Google Cloud region.
* **`FileNotFoundError`:** Double-check the path provided to `--input_file`. Ensure you are running the `python main.py` command from the project's root directory.
* **JSON Errors:**
    * If loading the input file fails, validate your input JSON structure carefully.
    * If errors occur during processing related to JSON parsing (often logged), it might indicate unexpected output from the Gemini API. The `fix_json_string` function tries to handle common issues, but complex malformations might still cause errors. Check the log file for details.
* **Rate Limit Errors:** The script has built-in rate limiting based on `config.API_CALL_LIMIT_PER_MINUTE`. If you still encounter rate limit errors, you might need to decrease this value or check your Gemini quota limits.
* **Content Quality:** The quality of the generated outline and content depends heavily on the quality of your input descriptions and the capabilities of the chosen Gemini model. Experiment with different models and prompt adjustments (within the `stages/*.py` files) if needed.
* **Check the Log:** The `_combined_log.json` file in the results directory is the first place to look for detailed error messages and processing status.

**Disclaimer:** Using Generative AI APIs incurs costs based on usage. Monitor your Google Cloud billing account.
