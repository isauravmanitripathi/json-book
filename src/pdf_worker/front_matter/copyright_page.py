import logging
from datetime import datetime
from .api_client import AnthropicClient

class CopyrightPageGenerator:
    """Generates copyright page content using Anthropic API."""
    
    def __init__(self, api_client=None):
        """
        Initialize the copyright page generator.
        
        Args:
            api_client (AnthropicClient, optional): API client for text generation
        """
        self.logger = logging.getLogger(__name__)
        self.api_client = api_client or AnthropicClient()
        
    def generate(self, book_info):
        """
        Generate copyright page content.
        
        Args:
            book_info (dict): Book information including:
                - title: Book title
                - author: Author name
                - publisher: Publisher name
                - year: Publication year
                - edition: Edition information
                - isbn: ISBN number (optional)
                - copyright_holder: Copyright holder name (defaults to author)
                - additional_info: Any additional copyright information
                
        Returns:
            str: Generated copyright page content in markdown format
        """
        try:
            self.logger.info("Generating copyright page content")
            
            # Set defaults for missing values
            book_info['year'] = book_info.get('year', datetime.now().year)
            book_info['copyright_holder'] = book_info.get('copyright_holder', book_info.get('author', 'The Author'))
            
            # Create prompt
            prompt = self._create_prompt(book_info)
            
            # Generate content
            copyright_content = self.api_client.generate_text(
                prompt=prompt, 
                max_tokens=500,
                temperature=0.3  # Lower temperature for more predictable output
            )
            
            self.logger.info("Successfully generated copyright page content")
            return copyright_content
            
        except Exception as e:
            self.logger.error(f"Error generating copyright page: {str(e)}")
            # Provide a fallback if API generation fails
            return self._create_fallback_content(book_info)
    
    def _create_prompt(self, book_info):
        """Create enhanced prompt for copyright page generation."""
        prompt = f"""Generate a professional copyright page for a book with the following information:

Title: {book_info.get('title', 'Book Title')}
Author: {book_info.get('author', 'Author Name')}
Publisher: {book_info.get('publisher', 'Self-Published')}
Year: {book_info.get('year')}
Edition: {book_info.get('edition', 'First Edition')}
Copyright Holder: {book_info.get('copyright_holder')}
{"ISBN: " + book_info.get('isbn') if book_info.get('isbn') else ""}
{"Additional Info: " + book_info.get('additional_info') if book_info.get('additional_info') else ""}

Format the content as a professional copyright page that would appear in a published book. 
Include standard copyright language, rights reserved statement, and publisher information.

The output MUST be in MARKDOWN format, formatted cleanly and professionally.
Use proper paragraph breaks and formatting that will render correctly in the PDF.

DO NOT include the title "Copyright Page" at the top, just start with the copyright statement.
"""
        return prompt
    
    def _create_fallback_content(self, book_info):
        """Create fallback copyright content if API fails."""
        year = book_info.get('year', datetime.now().year)
        author = book_info.get('author', 'The Author')
        title = book_info.get('title', 'The Book')
        publisher = book_info.get('publisher', 'Self-Published')
        edition = book_info.get('edition', 'First Edition')
        isbn = book_info.get('isbn', '')
        
        isbn_text = f"\nISBN: {isbn}" if isbn else ""
        
        return f"""
**{title}**

{edition}

© {year} {author}. All rights reserved.

No part of this publication may be reproduced, distributed, or transmitted in any form or by any means, including photocopying, recording, or other electronic or mechanical methods, without the prior written permission of the publisher, except in the case of brief quotations embodied in critical reviews and certain other noncommercial uses permitted by copyright law.

{publisher}{isbn_text}

Printed in the United States of America
"""