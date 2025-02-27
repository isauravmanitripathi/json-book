# PDF Generator

A versatile PDF generation tool for creating books, manuals, and documents from structured JSON content. Supports custom styles, images, multi-part documents, and more.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Usage](#usage)
- [JSON Input Format](#json-input-format)
- [Style Templates](#style-templates)
- [Image Support](#image-support)
- [Project Structure](#project-structure)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

## Overview

This tool converts structured content in JSON format into professionally formatted PDF documents. Key features include:

- Customizable style templates
- Image integration with captions
- Chapter and section organization
- Table of contents generation
- Title page creation
- Multi-part document support for large books
- Markdown-to-PDF conversion

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/pdf-generator.git
   cd pdf-generator
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

Run the main script to access all functionality:

```
python main.py
```

The interactive menu provides the following options:

1. **Extract Chapter Text from JSON**: Process and organize raw JSON content
2. **Generate Articles with OpenAI**: Create content using OpenAI API
3. **Generate Articles with Gemini**: Create content using Google's Gemini API
4. **Generate PDF from JSON**: Convert structured JSON to PDF
5. **List Available PDF Styles**: View and explore style templates
6. **Create New PDF Style**: Generate a custom style interactively
7. **Exit**: Quit the application

### Basic Workflow

1. Prepare your content in the required JSON format
2. Choose a style template or create a custom one
3. Generate the PDF
4. Find the output in the `results/pdfs` directory

## JSON Input Format

The tool accepts JSON files with the following structure:

```json
[
  {
    "chapter_name": "Introduction",
    "chapter_id": "1",
    "section_number": "1.1",
    "section_name": "Getting Started",
    "text": "Your section content goes here. This can include markdown formatting.",
    "images": [
      {
        "image_path": "chapter1/diagram1.jpg",
        "caption": "System Architecture Diagram"
      }
    ]
  },
  {
    "chapter_name": "Introduction",
    "chapter_id": "1",
    "section_number": "1.2",
    "section_name": "Key Concepts",
    "text": "More content...",
    "images": []
  }
]
```

### Fields Explained

- `chapter_name`: Title of the chapter
- `chapter_id`: Unique identifier for the chapter (used for ordering)
- `section_number`: Section number within the chapter (e.g., "1.1", "1.2")
- `section_name`: Title of the section
- `text`: Content of the section (supports Markdown formatting)
- `images`: Array of images to include in this section (optional)
  - `image_path`: Path to the image file (relative to the images directory)
  - `caption`: Caption text for the image

## Style Templates

Style templates control the appearance of your generated PDFs. They are stored as JSON files in the `styles` directory.

### Creating Custom Styles

You can create custom styles in three ways:

1. **Interactive Style Generator**: Use option 6 in the main menu to create a style template through a series of prompts.
2. **Manual JSON Creation**: Create a JSON file in the `styles` directory following the structure below.
3. **Modifying Existing Styles**: Copy and modify an existing style template.

### Style Template Structure

```json
{
  "name": "My Custom Style",
  "description": "A professional style for technical documents",
  "page": {
    "size": "A4",
    "margins": {"left": 72, "right": 72, "top": 72, "bottom": 72}
  },
  "fonts": [],
  "page_numbers": {
    "show": true,
    "format": "Page {current}",
    "position": "bottom-center",
    "font": "Helvetica",
    "size": 9,
    "start_page": 1
  },
  "title_page": {
    "title": {
      "font": "Helvetica-Bold",
      "size": 28,
      "color": "#000000",
      "spacing": "none",
      "alignment": "center",
      "case": "upper"
    },
    "author": {
      "font": "Helvetica",
      "size": 16,
      "color": "#000000",
      "prefix": "By",
      "alignment": "center"
    },
    "spacing": {
      "top": 0.4,
      "between": 0.2
    }
  },
  "table_of_contents": {
    "title": {
      "text": "CONTENTS",
      "font": "Helvetica-Bold",
      "size": 16,
      "alignment": "center"
    },
    "level_styles": [
      {
        "font_name": "Helvetica-Bold",
        "font_size": 12,
        "indent": 0,
        "leading": 16,
        "text_color": "#000000"
      },
      {
        "font_name": "Helvetica",
        "font_size": 11,
        "indent": 20,
        "leading": 14,
        "text_color": "#333333"
      }
    ]
  },
  "chapter": {
    "number": {
      "prefix": "Chapter",
      "font": "Helvetica-Bold",
      "size": 16,
      "color": "#000000",
      "alignment": "left",
      "case": "none"
    },
    "title": {
      "font": "Helvetica-Bold",
      "size": 24,
      "color": "#000000",
      "alignment": "left",
      "case": "title"
    },
    "divider": {
      "type": "solid",
      "width": 1,
      "color": "#000000",
      "spacing": {"before": 6, "after": 12}
    },
    "page_break": {
      "before": true,
      "after": false
    }
  },
  "section": {
    "title": {
      "font": "Helvetica-Bold",
      "size": 14,
      "color": "#000000",
      "alignment": "left",
      "space_before": 18,
      "space_after": 12
    },
    "divider": {
      "type": "none",
      "width": 0,
      "color": "#000000",
      "spacing": {"before": 0, "after": 0}
    }
  },
  "body_text": {
    "font": "Helvetica",
    "size": 10,
    "leading": 14,
    "alignment": "justified",
    "space_after": 10
  },
  "images": {
    "max_width": 450,
    "space_before": 10,
    "space_after": 10,
    "full_page_threshold": 0.7,
    "full_page_break": false,
    "caption": {
      "font": "Helvetica",
      "size": 9,
      "leading": 11,
      "color": "#000000",
      "space_after": 10
    }
  }
}
```

### Key Style Settings

- **Page Settings**: Control page size, margins
- **Fonts**: Specify typefaces, sizes, and colors
- **Alignments**: Set text alignment for different elements
- **Spacing**: Control space between elements
- **Dividers**: Add decorative lines between sections
- **Images**: Configure image positioning and caption appearance

## Image Support

The tool supports embedding images in your PDFs with captions and automatic figure numbering.

### Image Setup

1. Place your images in the `images` directory (or a custom directory)
2. Reference images in your JSON content using the `images` array
3. Images will be automatically sized, placed, and captioned

### Image Configuration

The image handling settings in style templates control:

- Maximum width
- Spacing before and after images
- Full-page threshold (when to give an image its own page)
- Caption font, size, and styling

### Image Placement Logic

- **Single Image**: Placed approximately 1/3 through the section text
- **Multiple Images**: Distributed evenly throughout the section
- **Large Images**: May be placed on their own page based on the `full_page_threshold` setting

## Project Structure

The project is organized into the following components:

### Core Files

- `main.py`: Main entry point with interactive menu
- `style_generator.py`: Interactive utility for creating style templates

### Source Directories

- `src/pdf_worker/`: PDF generation components
  - `core.py`: Main PDF generation engine
  - `style_manager.py`: Handles style templates
  - `image_handler.py`: Processes and positions images
  - `flowables.py`: Custom ReportLab flowable elements
  - `components/`: Document components (title page, chapters, sections)
  - `templates/`: Document templates and layout

- `src/json_writer/`: JSON processing utilities
  - `chapter_extractor.py`: Processes JSON input
  - `write_text_*.py`: Content generation scripts

### Output Directories

- `styles/`: Style template JSON files
- `images/`: Image storage directory
- `results/pdfs/`: Generated PDF output
- `results/json-combined/`: Processed JSON files

## Advanced Usage

### Multi-part Documents

For very large books, you can enable multi-part generation:

1. Select option 4 (Generate PDF from JSON)
2. Answer 'y' to "Generate multi-part PDFs for large books?"
3. Enter your preferred maximum page count per part

The tool will split the document into multiple PDF files while maintaining proper chapter organization.

### Custom Fonts

To use custom fonts:

1. Place font files in the `fonts` directory
2. Register them in your style template's `fonts` array
3. Reference them by name in your style settings

### Markdown Support

The `text` field in your JSON supports Markdown formatting, including:

- **Bold text**: `**bold**`
- *Italic text*: `*italic*`
- Headings: `# Heading 1`, `## Heading 2`, etc.
- Lists: `- Item 1`, `1. Item 1`
- And more...

## Troubleshooting

### Common Issues

**Problem**: Images not appearing in PDF
**Solution**: Check that image paths are correctly specified relative to the images directory and that the images exist

**Problem**: Fonts not working correctly
**Solution**: Stick to standard fonts (Helvetica, Times-Roman, Courier) or ensure custom fonts are properly registered

**Problem**: Content is cut off or overflows pages
**Solution**: Adjust page margins in your style template or consider enabling multi-part document generation

**Problem**: Style template not loading
**Solution**: Validate your JSON syntax (all quotes, commas, brackets must be correct)

### Getting Help

If you encounter issues:

1. Check the error messages in the console
2. Verify your JSON input format
3. Make sure your style template follows the correct structure
4. Try using a built-in style template to test your content