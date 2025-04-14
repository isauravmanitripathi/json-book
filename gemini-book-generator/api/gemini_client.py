# api/gemini_client.py
"""
Handles interactions with the Google Gemini API, including configuration,
API calls, retries, rate limiting, and basic JSON fixing.
"""

import google.generativeai as genai
import time
import random
import json
import re
import os
import traceback
from datetime import datetime
from collections import deque
from typing import Optional, Tuple, Dict, Deque

# Assuming config.py is in the parent directory or accessible via PYTHONPATH
# If running directly, adjust path or structure
try:
    import config # If running main.py from the root directory
except ImportError:
    # Handle case where script might be run directly or modules aren't found easily
    # This is a fallback, proper project structure and running from root is preferred
    print("Warning: Could not import config directly. Attempting relative import.")
    try:
        from .. import config # Relative import if this file is treated as part of a package
    except ImportError:
         print("Error: Unable to import config.py. Ensure it's accessible.")
         # Define minimal fallbacks if config cannot be imported
         config = type('obj', (object,), {
             'DEFAULT_GEMINI_MODEL': 'gemini-2.0-flash',
             'API_RETRY_COUNT': 3,
             'API_CALL_LIMIT_PER_MINUTE': 15,
             'API_MAX_OUTPUT_TOKENS_CONTENT': 4096,
             'API_TEMPERATURE_CONTENT': 0.75
             })() # Dummy config object

# Assuming console_utils.py will be in ../utils/
try:
    from utils.console_utils import get_console
except ImportError:
    print("Warning: Could not import console_utils. Using basic print.")
    # Define a dummy console if rich isn't available or utils aren't set up
    class SimpleConsole:
        def print(self, message, **kwargs):
            print(re.sub(r'\[/?.*?\]', '', str(message))) # Basic tag removal
    console = SimpleConsole()
else:
    console = get_console() # Get the rich console instance


# --- JSON Fixing Utility ---
def fix_json_string(json_str: str) -> str:
    """Attempt to fix common issues with malformed JSON responses from LLMs."""
    if not json_str or not json_str.strip(): return '{}'
    # Remove markdown code fences (more robustly)
    json_str = re.sub(r'^```(json)?\s*', '', json_str.strip(), flags=re.IGNORECASE | re.DOTALL)
    json_str = re.sub(r'\s*```$', '', json_str, flags=re.IGNORECASE | re.DOTALL)
    json_str = json_str.strip()

    # Ensure it starts/ends with braces (find first '{' and last '}')
    start_brace = json_str.find('{')
    end_brace = json_str.rfind('}')

    if start_brace == -1 or end_brace == -1 or start_brace >= end_brace:
        # If no valid braces, return cleaned string; parsing will likely fail later.
        # Or, if it looks like just the *value* was returned, let the caller handle it.
        return json_str

    json_str = json_str[start_brace : end_brace + 1]

    # Remove trailing commas before closing braces/brackets
    # Matches comma, optional whitespace, followed by } or ]
    json_str = re.sub(r'(?<=[}\]"\'\w\d\s]),\s*(?=[}\]])', '', json_str)

    # Basic brace balancing (add missing closing braces) - Use with caution
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    if open_braces > close_braces:
        # console.print(f"[yellow]Warning: Adding {open_braces - close_braces} closing braces '}}' to potentially fix JSON.[/yellow]")
        json_str += '}' * (open_braces - close_braces)
    elif close_braces > open_braces:
         console.print(f"[yellow]Warning: More closing braces ({close_braces}) than opening ({open_braces}). JSON might be malformed.[/yellow]")

    return json_str

# --- API Test Function ---
def test_gemini_api(api_key: str, model_name: str = config.DEFAULT_GEMINI_MODEL) -> bool:
    """Quick test of the Gemini API with a simple prompt, expecting JSON."""
    simple_prompt = "Return ONLY a valid JSON object with one key 'status' and value 'ok'."
    response_text = ""
    try:
        console.print(f"Testing Gemini API connection with model: [cyan]{model_name}[/cyan]...")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        generation_config = genai.types.GenerationConfig(temperature=0.1) # Low temp for predictable test

        # Set safety settings to allow most content for the test, but block severe harm
        safety_settings = [
            {"category": c, "threshold": "BLOCK_ONLY_HIGH"}
            for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
        ]

        response = model.generate_content(
            simple_prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        if response.prompt_feedback and response.prompt_feedback.block_reason:
             reason = response.prompt_feedback.block_reason
             console.print(f"[bold red]API test failed: Prompt blocked. Reason: {reason}[/bold red]")
             return False

        response_text = response.text
        console.print(f"Test response received (raw snippet): {response_text[:100]}...")

        fixed_text = fix_json_string(response_text)
        data = json.loads(fixed_text) # Attempt parse

        if isinstance(data, dict) and data.get("status") == "ok":
            console.print("[green]API test successful (parsed expected JSON response).[/green]")
            return True
        else:
            console.print(f"[yellow]API test warning: Response received but content unexpected after parse: {data}[/yellow]")
            return True # API call worked, even if content wasn't perfect JSON
    except json.JSONDecodeError as json_err:
        console.print(f"[yellow]API test warning: Could not parse test response as JSON: {json_err}[/yellow]")
        console.print(f"Raw response: {response_text}")
        return True # API call likely worked, response format issue
    except Exception as e:
        console.print(f"[bold red]API test failed for model {model_name}: {e}[/bold red]")
        if "API key not valid" in str(e): console.print("[bold red]Check GOOGLE_API_KEY in your .env file or environment.[/bold red]")
        elif "billing" in str(e).lower(): console.print("[bold red]Check Google Cloud project billing status.[/bold red]")
        elif "model" in str(e).lower() and "not found" in str(e).lower(): console.print(f"[bold red]Model '{model_name}' might be invalid or unavailable in your region.[/bold red]")
        # console.print(traceback.format_exc()) # Uncomment for more detailed debugging if needed
        return False


# --- Main API Call Function ---
def call_gemini_api(
    prompt: str,
    api_key: str,
    model_name: str,
    temperature: float,
    max_output_tokens: int,
    api_call_timestamps_deque: Deque[float], # Pass the deque for rate limiting
    retry_count: int = config.API_RETRY_COUNT,
    item_key_for_log: str = "unknown_item", # For logging context
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Calls the Gemini API, handles retries, rate limiting, basic JSON fixing.

    Args:
        prompt: The prompt string to send to the API.
        api_key: The Google API Key.
        model_name: The specific Gemini model to use.
        temperature: The generation temperature.
        max_output_tokens: The maximum number of tokens for the response.
        api_call_timestamps_deque: Deque object shared across calls for rate limiting.
        retry_count: Number of retries to attempt on failure.
        item_key_for_log: An identifier for the item being processed (for logs).

    Returns:
        A tuple: (parsed_json_dict, error_message).
        - If successful and JSON is parsed: (dict, None)
        - If failed after retries or non-JSON response: (None, error_message)
    """
    genai.configure(api_key=api_key)

    generation_config = {
        "temperature": temperature,
        "top_p": 0.95, # Standard values, adjust if needed
        "top_k": 40,
        "max_output_tokens": max_output_tokens,
    }
    # Standard safety settings - adjust thresholds if needed
    safety_settings = [
        {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
        for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
    ]

    max_attempts = retry_count + 1
    last_error = None

    for attempt in range(max_attempts):
        current_attempt_num = attempt + 1

        # --- Rate Limiting ---
        now = time.monotonic()
        # Remove timestamps older than 60 seconds
        while api_call_timestamps_deque and now - api_call_timestamps_deque[0] >= 60.0:
            api_call_timestamps_deque.popleft()
        # Check if limit reached
        if len(api_call_timestamps_deque) >= config.API_CALL_LIMIT_PER_MINUTE:
            time_since_oldest = now - api_call_timestamps_deque[0]
            wait_time = 60.0 - time_since_oldest + random.uniform(0.1, 0.5) # Add slight buffer
            console.print(f"[yellow]Rate limit ({config.API_CALL_LIMIT_PER_MINUTE}/min) hit. Waiting for {wait_time:.2f}s...[/yellow]")
            time.sleep(wait_time)
            # Re-evaluate after wait
            now = time.monotonic()
            while api_call_timestamps_deque and now - api_call_timestamps_deque[0] >= 60.0:
                 api_call_timestamps_deque.popleft()

        # --- Backoff Delay ---
        if attempt > 0:
            backoff_time = min(30, (2 ** attempt) + random.uniform(0, 1)) # Exponential backoff capped at 30s
            console.print(f"[yellow]Retrying '{item_key_for_log}' (attempt {current_attempt_num}/{max_attempts}) after {backoff_time:.2f}s delay...[/yellow]")
            time.sleep(backoff_time)

        try:
            # --- API Call ---
            api_call_timestamps_deque.append(time.monotonic()) # Log call time *before* making the call
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            console.print(f"Sending request to Gemini ({model_name}) for '{item_key_for_log}' (Attempt {current_attempt_num}/{max_attempts})...")
            response = model.generate_content(prompt)
            # --- End API Call ---

            # --- Response Processing ---
            response_text = ""
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                reason = response.prompt_feedback.block_reason
                raise Exception(f"API call blocked for item '{item_key_for_log}'. Reason: {reason}.")

            if response.parts: response_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
            elif hasattr(response, 'text'): response_text = response.text
            else: response_text = str(response) # Fallback

            if not response_text or not response_text.strip():
                 raise Exception(f"API returned empty response for '{item_key_for_log}'.")

            # --- JSON Parsing ---
            # console.print(f"Attempt {current_attempt_num}: Raw response snippet: {repr(response_text[:150])}...") # Debug
            fixed_json_str = fix_json_string(response_text)

            try:
                parsed_response = json.loads(fixed_json_str)
                if not isinstance(parsed_response, dict):
                    # Handle cases where API might return just a string or list
                    if isinstance(parsed_response, str):
                         # If expecting dict, maybe wrap it? Depends on expected structure.
                         # For now, treat as error if dict is expected implicitly.
                         raise json.JSONDecodeError("Parsed JSON is not a dictionary", fixed_json_str, 0)
                    # Allow lists if that's a possible valid output for some prompts? Unlikely for current use case.

                # SUCCESS!
                return parsed_response, None

            except json.JSONDecodeError as e:
                error_msg = f"JSON parsing error on attempt {current_attempt_num} after fix: {e}. Item: '{item_key_for_log}'"
                console.print(f"[red]JSON ERROR: {error_msg}[/red]")
                # console.print(f"Content that failed parsing:\n---\n{fixed_json_str}\n---") # Debug
                last_error = error_msg
                # Don't retry on JSON error, as the content is likely bad format. Let the loop finish.
                # If it was the last attempt, the loop will exit and return the error.
                if current_attempt_num == max_attempts:
                     return None, f"Final attempt failed JSON parsing: {e}. Raw Text Snippet: {fixed_json_str[:200]}"
                else:
                    # Continue to next attempt only if NOT a JSON error?
                    # Let's retry even on JSON error, maybe next attempt gives better format.
                    continue


        except Exception as e:
            error_msg = f"API call exception on attempt {current_attempt_num} for '{item_key_for_log}' using {model_name}: {e}"
            console.print(f"[bold red]API ERROR: {error_msg}[/bold red]")
            # console.print(traceback.format_exc()) # Deeper debug if needed
            last_error = error_msg
            # Continue to next retry attempt
            if current_attempt_num == max_attempts:
                 return None, f"Final attempt failed with API exception: {e}"


    # --- Failure Fallback ---
    fail_message = f"All {max_attempts} API attempts failed for '{item_key_for_log}'. Last error: {last_error}"
    console.print(f"[bold red]{fail_message}[/bold red]")
    return None, fail_message