# Generate outline and content with markdown/api response 

Generates proper file structure, writes outline and then writes content, takes a simple input and then understand it and writes outline. 



```bash
your_project_directory/
├── main.py                     # Main script - orchestrates the workflow
├── requirements.txt            # Lists dependencies (google-generativeai, python-dotenv, rich, etc.)
├── .env                        # Stores the GOOGLE_API_KEY (DO NOT COMMIT TO GIT)
├── input_files/                # Directory for user's input JSON files
│   └── example_structure.json
├── results/                    # Default output directory
│   └── example_structure/      # Subdirectory for each input file's results
│       ├── example_structure_outlined.json     # Intermediate outline file
│       ├── example_structure_content_YYYYMMDD_HHMMSS.json # Final content file
│       └── example_structure_combined_log.json # Unified log file
├── config.py                   # Configuration constants (model names, defaults, limits)
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