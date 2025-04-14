# config.py
"""
Configuration constants for the Gemini processing script.
"""
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- Gemini API Configuration ---
DEFAULT_GEMINI_MODEL = os.environ.get("DEFAULT_GEMINI_MODEL", "gemini-2.0-flash") # Model for content generation
OUTLINE_GEMINI_MODEL = os.environ.get("OUTLINE_GEMINI_MODEL", "gemini-2.0-flash") # Model for outline generation (can be same or different)
API_RETRY_COUNT = 3 # Number of retries for API calls
API_CALL_LIMIT_PER_MINUTE = 15 # Rate limit (adjust based on the specific model's limits)
API_MAX_OUTPUT_TOKENS_OUTLINE = 8192 # Max tokens for outline generation response
API_MAX_OUTPUT_TOKENS_CONTENT = 4096 # Max tokens for content generation response
API_TEMPERATURE_OUTLINE = 0.6 # Generation temperature for outlines (slightly more creative)
API_TEMPERATURE_CONTENT = 0.75 # Generation temperature for content (balance creativity/accuracy)

# --- Processing Configuration ---
INTERIM_SAVE_FREQUENCY_CONTENT = 5 # Save content progress every N items
MAX_CONTEXT_SUMMARY_LENGTH = 2500 # Character limit for context summary sent to content generation prompt

# --- Logging Configuration ---
LOG_FILENAME_SUFFIX = "_combined_log.json"
OUTLINE_FILENAME_SUFFIX = "_outlined.json"
CONTENT_FILENAME_SUFFIX_TEMPLATE = "_content_{timestamp}.json" # Timestamp will be added

# --- Status Markers for Log File ---
STATUS_PENDING_OUTLINE = "pending_outline"
STATUS_OUTLINE_COMPLETE = "outline_complete"
STATUS_PENDING_CONTENT = "pending_content"
STATUS_CONTENT_COMPLETE = "content_complete"
STATUS_ERROR = "error"