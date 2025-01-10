# Generate Book from JSON

Generate PDF Book Using JSON and Gemini or OpenAI API. 


# Steps:
1. Clone the program
2. Install all of the required libraries
3. Screenshot Books, or generate a json structure (Right now ability to screenshot is there, but auto json generation is not, working on it)
4. Rewrite it, if you want using gemini, or openai or anthropic model. (working on using other models such as LLMA)
5. Pass the JSON to generate PDF.


# Step -> 1

First Clone the project using this command:

```bash
git clone https://github.com/isauravmanitripathi/json-book.git
cd json-book -> eneter the folder 
```


# Step -> 2

## Start a venv and install all of the required libraries

```bash
pythonn3.10 -m venv .venv
source .venv/bin/activate

pip3 install -r requirements.txt
```


Requires a input JSON file to start the process:

```json
{
  "metadata": {...},
  "chapters": [
    {
      "chapter_name": "Chapter 1",
      "conversations": [
        {"speaker": "SECTION_INFO", "text": "Section Name"},
        {"speaker": "Akash", "text": "First dialogue"},
        {"speaker": "Bharti", "text": "Response dialogue"}
      ]
    }
  ]
}
```
```json
{
  "New item": {
    "chapters": [
      {
        "chapter_id": 1,
        "chapter_name": "Financial System",
        "sections": [
          {
            "section_id": 1.1,
            "section_name": "Introduction",
            "extracted-text": "A financial system plays a vital role in economic growth..."
          }
        ]
      }
    ]
  }
}
```


Output JSON structure:

```json 
# When input has chapter_id (Format 1):
{
  "metadata": {
    "generated_at": "2025-01-10 12:34:56",
    "model": "gpt-4o"  // or "gemini-1.5-flash-8b"
  },
  "articles": [
    {
      "chapter_name": "Financial System",
      "chapter_id": "1",
      "section_number": "1.1",
      "section_name": "Introduction",
      "text": "The rewritten article text goes here..."
    },
    {
      "chapter_name": "Financial System",
      "chapter_id": "1",
      "section_number": "1.2",
      "section_name": "Components",
      "text": "Another rewritten article text..."
    }
  ]
}

# When input has no chapter_id (Format 2):
{
  "metadata": {
    "generated_at": "2025-01-10 12:34:56",
    "model": "gpt-4o"  // or "gemini-1.5-flash-8b"
  },
  "articles": [
    {
      "chapter_name": "Chapter 1",
      "chapter_id": "",             // Empty string for missing chapter_id
      "section_number": "1",
      "section_name": "Chapter 1",
      "text": "The rewritten article text goes here..."
    },
    {
      "chapter_name": "Chapter 2",
      "chapter_id": "",             // Empty string for missing chapter_id
      "section_number": "2",
      "section_name": "Chapter 2",
      "text": "Another rewritten article text..."
    }
  ]
}

```

So make sure both of the input JSON files are in this structure, in order to generate the pdf. 



# To Do

1. [] Generate PDF
2. [] Write the Name of Book
3. 