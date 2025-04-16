# src/style_loader.py

import os
import json
import logging
from pathlib import Path

# ReportLab font registration imports
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont, TTFError
from reportlab.lib.fonts import addMapping # For font family mapping

logger = logging.getLogger(__name__)

class StyleLoader:
    """
    Manages loading JSON style configurations and registering associated fonts
    defined within those styles.
    """
    def __init__(self, styles_dir='styles', fonts_dir='fonts'):
        """
        Initialize the StyleLoader.

        Args:
            styles_dir (str | Path): Path to the directory containing style JSON files.
            fonts_dir (str | Path): Path to the directory containing TTF font files.
        """
        self.styles_dir = Path(styles_dir)
        self.fonts_dir = Path(fonts_dir)
        # Keep track of fonts registered in this instance to avoid redundant work/warnings
        self.registered_fonts_cache = set()

        logger.info(f"StyleLoader initialized. Styles Dir: '{self.styles_dir}', Fonts Dir: '{self.fonts_dir}'")

    def list_styles(self):
        """Returns a list of available style names (basenames without .json extension)."""
        if not self.styles_dir.is_dir():
            logger.warning(f"Styles directory not found: {self.styles_dir}")
            return []
        try:
            styles = sorted([f.stem for f in self.styles_dir.glob('*.json') if f.is_file()])
            logger.debug(f"Available styles found: {styles}")
            return styles
        except OSError as e:
            logger.error(f"Error accessing styles directory '{self.styles_dir}': {e}")
            return []


    def load_style(self, style_name):
        """
        Loads a specific style JSON file and registers its fonts.

        Args:
            style_name (str): The name of the style (e.g., "default").

        Returns:
            dict: The loaded style configuration dictionary.

        Raises:
            FileNotFoundError: If the style file doesn't exist.
            ValueError: If the JSON is invalid or essential keys are missing.
            Exception: For other file reading or JSON parsing errors.
        """
        style_file = self.styles_dir / f"{style_name}.json"
        logger.info(f"Attempting to load style: {style_file}")

        if not style_file.is_file():
            logger.error(f"Style file not found: {style_file}")
            raise FileNotFoundError(f"Style file '{style_file}' not found.")

        try:
            with open(style_file, 'r', encoding='utf-8') as f:
                style_config = json.load(f)

            # --- Basic Validation ---
            if not isinstance(style_config, dict):
                 raise ValueError("Style file does not contain a valid JSON object.")
            # Check for essential top-level keys for basic functionality
            required_keys = ['style_name', 'page', 'fonts']
            for key in required_keys:
                if key not in style_config:
                     # Log warning but allow proceeding, components should handle defaults
                     logger.warning(f"Style '{style_name}' missing recommended key: '{key}'. Default behavior may apply.")

            logger.info(f"Successfully loaded style JSON for '{style_name}'.")

            # --- Register Fonts Defined in Style ---
            # Pass self.fonts_dir for resolving relative paths
            self._register_fonts(style_config.get('fonts', {})) # Pass the fonts dict

            # Inject font config into style_config for easy access by components
            # This avoids needing to pass fonts_config separately everywhere
            style_config['_fonts_config_ref'] = style_config.get('fonts', {})

            return style_config

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in style file {style_file}: {e}")
            raise ValueError(f"Invalid JSON in style file '{style_file}': {e}") from e
        except Exception as e:
            logger.error(f"Error loading style file {style_file}: {e}", exc_info=True)
            raise # Re-raise other exceptions


    def _register_fonts(self, fonts_config):
        """
        Registers fonts defined in the style configuration with ReportLab's pdfmetrics.

        Args:
            fonts_config (dict): The 'fonts' section of the style config.
                                 Maps logical font names to file paths or variant dicts.
                                 Example:
                                 {
                                     "body": "Times-Roman", // Standard font
                                     "code": "Courier",
                                     "custom_sans": { // Custom font family
                                         "normal": "MySans-Regular.ttf",
                                         "bold": "MySans-Bold.ttf",
                                         "italic": "MySans-Italic.ttf",
                                         "bold_italic": "MySans-BoldItalic.ttf"
                                     }
                                 }
        """
        if not isinstance(fonts_config, dict):
             logger.warning("'fonts' section in style config is not a dictionary. Skipping custom font registration.")
             return

        if not self.fonts_dir.is_dir():
            logger.warning(f"Fonts directory '{self.fonts_dir}' not found. Cannot register custom fonts from style.")
            return

        logger.info(f"Registering fonts defined in style, searching in: {self.fonts_dir}")

        for logical_name, font_info in fonts_config.items():
            logger.debug(f"Processing font definition for logical name: '{logical_name}'")

            # Skip standard PDF fonts (already known by ReportLab)
            standard_fonts = [
                'Courier', 'Courier-Bold', 'Courier-Oblique', 'Courier-BoldOblique',
                'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique',
                'Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic',
                'Symbol', 'ZapfDingbats'
            ]
            if logical_name in standard_fonts or (isinstance(font_info, str) and font_info in standard_fonts):
                logger.debug(f"Skipping standard PDF font: '{logical_name}'")
                continue

            registered_variants_map = {} # Track registered name for each variant type

            if isinstance(font_info, str):
                # Simple case: logical name maps directly to a TTF filename (treat as 'normal' variant)
                font_filename = font_info if font_info.lower().endswith('.ttf') else f"{font_info}.ttf"
                self._register_single_font(logical_name, font_filename, logical_name) # Register using logical name
                # No family mapping possible in this simple format

            elif isinstance(font_info, dict):
                # Preferred case: Dictionary defining variants like normal, bold, italic, bold_italic
                variants_to_register = {} # Store {registration_name: file_path}
                reportlab_family_map = {} # Store {reportlab_variant_key: registration_name}

                # Define mapping from style keys to ReportLab family keys and registration suffixes
                variant_map = {
                    'normal':      {'suffix': '',             'family_key': 'normal'},
                    'bold':        {'suffix': '-Bold',        'family_key': 'bold'},
                    'italic':      {'suffix': '-Italic',      'family_key': 'italic'},
                    'bold_italic': {'suffix': '-BoldItalic',  'family_key': 'boldItalic'}
                }

                for variant_key, details in variant_map.items():
                    ttf_filename = font_info.get(variant_key)
                    if ttf_filename and isinstance(ttf_filename, str):
                        # Construct the name ReportLab will know this font by
                        registration_name = f"{logical_name}{details['suffix']}"
                        # Store for registration attempt
                        variants_to_register[registration_name] = self.fonts_dir / ttf_filename
                        # Store for family mapping if registration succeeds
                        reportlab_family_map[details['family_key']] = registration_name

                # Attempt registration for all variants found
                successful_registrations = {}
                for reg_name, font_path in variants_to_register.items():
                    if self._register_single_font(reg_name, font_path):
                        successful_registrations[reg_name] = True

                # --- Register Font Family Mapping (if normal variant was registered) ---
                if logical_name in successful_registrations:
                     # Build the final map using only successfully registered variants
                     final_family_map = {
                         family_key: reg_name
                         for family_key, reg_name in reportlab_family_map.items()
                         if reg_name in successful_registrations
                     }

                     # Check if enough variants exist for meaningful mapping
                     if len(final_family_map) > 1 or 'normal' in final_family_map :
                         try:
                             logger.debug(f"Attempting to register font family '{logical_name}' with map: {final_family_map}")
                             # Determine bold/italic flags based on presence in map
                             is_bold = final_family_map.get('bold') == final_family_map.get('normal')
                             is_italic = final_family_map.get('italic') == final_family_map.get('normal')
                             # Register family
                             addMapping(logical_name, is_bold, is_italic, **final_family_map)
                             logger.info(f"Registered font family mapping for '{logical_name}'.")
                         except Exception as e:
                              logger.error(f"Failed to register font family mapping for '{logical_name}': {e}")
                elif variants_to_register:
                     logger.warning(f"Could not register 'normal' variant for '{logical_name}'. Skipping family mapping.")

            else:
                logger.warning(f"Invalid font definition format for logical name '{logical_name}'. Expected string or dictionary.")


    def _register_single_font(self, registration_name, font_path_obj):
        """
        Helper to register a single TTF font file if not already registered.

        Args:
            registration_name (str): The name to register the font under with ReportLab.
            font_path_obj (Path): Path object for the TTF file.

        Returns:
            bool: True if registration was successful or font was already registered, False otherwise.
        """
        if registration_name in self.registered_fonts_cache:
            logger.debug(f"Font '{registration_name}' previously processed.")
            # Check if it was successfully registered before
            try:
                 pdfmetrics.getFont(registration_name)
                 return True # Already successfully registered
            except KeyError:
                 return False # Was processed but failed previously

        self.registered_fonts_cache.add(registration_name) # Mark as processed

        if not font_path_obj.is_file():
            logger.warning(f"Font file not found: {font_path_obj}")
            return False

        try:
            logger.debug(f"Registering font: Name='{registration_name}', Path='{font_path_obj}'")
            pdfmetrics.registerFont(TTFont(registration_name, str(font_path_obj)))
            # Verify registration immediately (optional but good for debugging)
            # pdfmetrics.getFont(registration_name)
            logger.info(f"Successfully registered font '{registration_name}' from {font_path_obj.name}")
            return True
        except TTFError as e:
            logger.error(f"ReportLab TTFError registering font '{registration_name}' from {font_path_obj}: {e}")
            return False
        except KeyError: # Sometimes happens if font is invalid after registration attempt
             logger.error(f"ReportLab KeyError likely indicating invalid font file for '{registration_name}' from {font_path_obj}")
             return False
        except Exception as e:
            logger.error(f"Unexpected error registering font '{registration_name}' from {font_path_obj}: {e}")
            return False