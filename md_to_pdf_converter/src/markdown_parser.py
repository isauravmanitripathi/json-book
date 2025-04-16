# src/markdown_parser.py

import markdown
from bs4 import BeautifulSoup, NavigableString, Tag
import logging
import re
import os # Import os to handle potential path issues if needed

logger = logging.getLogger(__name__)

class MarkdownParser:
    """Parses a Markdown file into a structured list of content blocks."""

    def __init__(self):
        """Initializes the Markdown parser with extensions."""
        self.md = markdown.Markdown(extensions=[
            'fenced_code',  # Handles ```python ... ``` blocks
            'tables',       # Handles pipe tables
            'nl2br',        # Converts single newlines to <br> (useful for simple breaks)
            'sane_lists'    # Improved list handling
        ])
        # Consider 'pymdownx.superfences' for more code block features later.
        # Consider 'toc' extension if needed, though we handle TOC via ReportLab.

    def parse_file(self, md_file_path):
        """
        Reads and parses a Markdown file.

        Args:
            md_file_path (pathlib.Path): Path object for the Markdown file.

        Returns:
            list: A list of dictionaries, where each dictionary represents
                  a content block (e.g., heading, paragraph, code, table, image).
                  Returns an empty list if parsing fails.
        """
        logger.info(f"Parsing Markdown file: {md_file_path}")
        try:
            with open(md_file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()

            # Convert Markdown to HTML
            html_content = self.md.convert(md_content)
            # Reset the markdown processor state
            self.md.reset()

            logger.debug(f"--- HTML Output for {md_file_path.name} ---\n{html_content[:500]}...\n--- End HTML ---")

            # Parse HTML using BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract content blocks from the parsed HTML
            blocks = self._extract_blocks_from_soup(soup)
            logger.info(f"Extracted {len(blocks)} blocks from {md_file_path.name}")
            return blocks

        except FileNotFoundError:
            logger.error(f"Markdown file not found: {md_file_path}")
            return []
        except ImportError:
             logger.error("BeautifulSoup4 is required but not installed. `pip install beautifulsoup4`")
             raise # Reraise so main script can exit
        except Exception as e:
            logger.error(f"Error parsing Markdown file {md_file_path}: {e}", exc_info=True)
            return [] # Return empty list on error

    def _extract_blocks_from_soup(self, soup):
        """
        Iterates through BeautifulSoup elements and converts them to internal block structure.

        Args:
            soup (BeautifulSoup): Parsed HTML content.

        Returns:
            list: List of structured block dictionaries.
        """
        blocks = []
        # Find top-level elements. If Markdown generates a wrapping div/body, search within it.
        content_elements = list(soup.children)
        # If the soup object only has one top-level element (like a single <div>),
        # and that element has children, parse its children instead.
        if len(content_elements) == 1 and isinstance(content_elements[0], Tag) and content_elements[0].name != 'html':
            potential_wrapper = content_elements[0]
            # Check if it seems like a wrapper (e.g. <div> without specific classes we care about)
            if potential_wrapper.name == 'div' and len(list(potential_wrapper.children)) > 0 :
                 elements = potential_wrapper.children
                 logger.debug("Parsing children of the top-level wrapper div.")
            else:
                 elements = content_elements # Parse the single element itself if not a simple div wrapper
        else:
             elements = soup.children # Parse direct children if multiple top-level elements or just text

        for element in elements:
            # Skip insignificant NavigableStrings (like newlines between tags)
            if isinstance(element, NavigableString):
                if element.strip():
                    # Treat significant stray text as a paragraph
                    blocks.append({'type': 'paragraph', 'text': str(element).strip()})
                    logger.warning(f"Found stray text converted to paragraph: '{str(element).strip()[:50]}...'")
                continue

            # Skip elements without a name (like comments)
            if not hasattr(element, 'name'):
                continue

            element_name = element.name.lower()

            # --- Headings ---
            if element_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                 level = int(element_name[1])
                 # Chapter title (H1 equivalent) is handled by filename in pdf_generator
                 # We primarily care about H2 for sections, but capture others too.
                 if level >= 2:
                     text = element.get_text(strip=True)
                     if text:
                         blocks.append({'type': 'heading', 'level': level, 'text': text})
                         logger.debug(f"Found Heading (H{level}): {text}")

            # --- Paragraphs ---
            elif element_name == 'p':
                 # Check if paragraph *only* contains an image tag
                 img = element.find('img', recursive=False)
                 # Check if the direct content is just the image tag, ignoring whitespace strings
                 is_only_image = img and all(isinstance(c, NavigableString) and not c.strip() or c == img for c in element.contents)

                 if is_only_image:
                     # Handle image directly from paragraph wrapper
                     alt_text = img.get('alt', '')
                     src = img.get('src', '')
                     if src:
                          blocks.append({'type': 'image', 'path': src, 'alt': alt_text})
                          logger.debug(f"Found Image (in P): {src}")
                 else:
                     # Process paragraph content, preserving simple inline tags
                     # Using decode_contents preserves <b>, <i>, <br/> etc.
                     inner_html = element.decode_contents()
                     text = inner_html.strip()
                     # Clean up excessive breaks that might come from nl2br
                     text = re.sub(r'(<br\s*/?>\s*){2,}', '<br/><br/>', text).strip()
                     if text:
                         blocks.append({'type': 'paragraph', 'text': text})
                         logger.debug(f"Found Paragraph: {text[:60]}...")

            # --- Code Blocks (Fenced Code Extension Output) ---
            elif element_name == 'div' and 'codehilite' in element.get('class', []):
                 # Standard markdown library often wraps fenced code in <div class="codehilite"><pre><code>...
                 pre_tag = element.find('pre', recursive=False)
                 code_tag = pre_tag.find('code') if pre_tag else None
                 if code_tag:
                     language = None
                     # Extract language from class="language-python" (might be on code or pre)
                     css_classes = code_tag.get('class', []) or pre_tag.get('class', [])
                     for css_class in css_classes:
                         if css_class.startswith('language-'):
                             language = css_class.replace('language-', '').strip()
                             break
                     content = code_tag.get_text() # Raw code
                     content = content.strip('\n\r') # Remove leading/trailing whitespace
                     blocks.append({'type': 'code', 'language': language, 'content': content})
                     logger.debug(f"Found Code Block (language: {language}): {content[:60]}...")
                 elif pre_tag: # Handle case where there's <pre> but no <code> inside div.codehilite
                      content = pre_tag.get_text().strip('\n\r')
                      blocks.append({'type': 'code', 'language': None, 'content': content})
                      logger.debug(f"Found Code Block (plain pre in codehilite): {content[:60]}...")

            elif element_name == 'pre':
                 # Handle plain <pre> tags (might contain <code> or just text)
                 code_tag = element.find('code', recursive=False)
                 content = (code_tag.get_text() if code_tag else element.get_text()).strip('\n\r')
                 language = None # Assume no language if it's just <pre>
                 if code_tag: # Check for language class on code tag inside pre
                     css_classes = code_tag.get('class', [])
                     for css_class in css_classes:
                         if css_class.startswith('language-'):
                             language = css_class.replace('language-', '').strip()
                             break
                 blocks.append({'type': 'code', 'language': language, 'content': content})
                 logger.debug(f"Found Code Block (plain pre, lang: {language}): {content[:60]}...")


            # --- Tables ---
            elif element_name == 'table':
                 logger.debug("Found Table element.")
                 headers = []
                 rows = []
                 # Header: Look in <thead> first, then fall back to first <tr>
                 header_section = element.find('thead')
                 header_row = header_section.find('tr') if header_section else element.find('tr') # Get first row as potential header
                 if header_row:
                     # Extract text, preserving simple inline html
                     headers = [cell.decode_contents().strip() for cell in header_row.find_all(['th', 'td'])]
                     logger.debug(f"  Table Headers: {headers}")

                 # Body Rows: Look in <tbody>, or just all <tr>s after the header row
                 body_section = element.find('tbody')
                 row_elements = body_section.find_all('tr') if body_section else element.find_all('tr')

                 for i, row_element in enumerate(row_elements):
                     # Skip the header row if we processed it above
                     if row_element == header_row and (header_section or i == 0) :
                         continue
                     # Extract cell text, preserving simple inline html
                     cells = [cell.decode_contents().strip() for cell in row_element.find_all('td')]
                     if cells: # Only add rows that have cells
                          rows.append(cells)

                 if headers or rows: # Add table only if it's not empty
                    blocks.append({'type': 'table', 'headers': headers, 'rows': rows})
                    logger.debug(f"  Table Rows ({len(rows)}): {rows[:2]}...") # Log first few rows
                 else:
                     logger.warning("Found table element but extracted no headers or rows.")


            # --- Lists (Basic Handling - convert to paragraphs with bullets/numbers) ---
            elif element_name in ['ul', 'ol']:
                 logger.debug(f"Found List ({element_name})")
                 list_items_markup = []
                 prefix = "• " if element_name == 'ul' else "{i}. "
                 for i, item in enumerate(element.find_all('li', recursive=False), 1):
                     # Use decode_contents to keep inline formatting (<b>, <i>, <br/>)
                     item_html = item.decode_contents().strip()
                     # Handle nested lists by replacing them with indented markers (simplification)
                     item_html = re.sub(r'<ul>.*?</ul>', '[nested list]', item_html, flags=re.DOTALL | re.IGNORECASE)
                     item_html = re.sub(r'<ol>.*?</ol>', '[nested list]', item_html, flags=re.DOTALL | re.IGNORECASE)
                     if item_html:
                         list_items_markup.append(prefix.format(i=i) + item_html)

                 if list_items_markup:
                     # Join items with ReportLab breaks, treat as single paragraph block
                     blocks.append({'type': 'paragraph', 'text': '<br/>'.join(list_items_markup)})
                     logger.debug(f"  Converted list to paragraph block.")

            # --- Blockquotes (Basic Handling - convert to italic paragraphs) ---
            elif element_name == 'blockquote':
                 logger.debug("Found Blockquote")
                 # Extract inner content, handling potential paragraphs inside
                 inner_html_parts = []
                 for child in element.children:
                     if isinstance(child, NavigableString) and child.strip():
                         inner_html_parts.append(child.strip())
                     elif hasattr(child, 'name') and child.name == 'p':
                          inner_html_parts.append(child.decode_contents().strip())
                     elif hasattr(child, 'decode_contents'): # Handle other tags if needed
                          inner_html_parts.append(child.decode_contents().strip())

                 inner_html = '<br/><br/>'.join(filter(None, inner_html_parts))
                 if inner_html:
                     # Prepend/append italics tag for styling in PDF component
                     blocks.append({'type': 'paragraph', 'text': f"<i>{inner_html}</i>"})
                     logger.debug(f"  Converted blockquote to italic paragraph block.")

            # --- Images (Directly under soup, not wrapped in <p>) ---
            elif element_name == 'img':
                alt_text = element.get('alt', '')
                src = element.get('src', '')
                if src:
                    blocks.append({'type': 'image', 'path': src, 'alt': alt_text})
                    logger.debug(f"Found Image (direct): {src}")

            # --- Horizontal Rule ---
            elif element_name == 'hr':
                 blocks.append({'type': 'horizontal_rule'})
                 logger.debug("Found Horizontal Rule")


            # --- Other elements ---
            # Add handling for other tags as needed, or log warnings
            else:
                 # Check if it contains significant text content
                 if element.get_text(strip=True):
                      logger.warning(f"Unhandled top-level HTML element type: '{element_name}'. Content: '{element.get_text(strip=True)[:50]}...'")


        return blocks