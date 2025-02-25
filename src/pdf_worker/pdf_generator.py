import os
import json
import re
import yaml
import markdown
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER, LEGAL
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Paragraph, Spacer, PageBreak, Frame, PageTemplate, Flowable, Table, TableStyle
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus.doctemplate import BaseDocTemplate

def convert_markdown_to_rl_markup(md_text):
    """Convert markdown text to ReportLab markup."""
    html = markdown.markdown(md_text)
    html = re.sub(r'<ul>(.*?)</ul>', r'<br/><br/>\1<br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h1>(.*?)</h1>', r'<font size="18"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h2>(.*?)</h2>', r'<font size="16"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h3>(.*?)</h3>', r'<font size="14"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h4>(.*?)</h4>', r'<font size="12"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h5>(.*?)</h5>', r'<font size="10"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<h6>(.*?)</h6>', r'<font size="9"><b>\1</b></font><br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<p>(.*?)</p>', r'\1<br/><br/>', html, flags=re.DOTALL)
    html = re.sub(r'<li>(.*?)</li>', r'&nbsp;&nbsp;&nbsp;&nbsp;• \1<br/>', html, flags=re.DOTALL)
    html = html.replace('<ul>', '').replace('</ul>', '')
    html = html.replace('<ol>', '').replace('</ol>', '')
    return html

class VerticalSpace(Flowable):
    """Flowable that adds vertical space."""
    def __init__(self, space):
        self.space = space
    def wrap(self, *args):
        return (0, self.space)
    def draw(self):
        pass

class DottedLineFlowable(Flowable):
    """Draws a dotted (dashed) horizontal line across the given width."""
    def __init__(self, width, line_width=1, dash=(1,2), color=colors.black):
        super().__init__()
        self.width = width
        self.line_width = line_width
        self.dash = dash
        self.color = color
    def wrap(self, available_width, available_height):
        return (self.width, self.line_width)
    def draw(self):
        self.canv.saveState()
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.line_width)
        self.canv.setDash(self.dash)
        self.canv.line(0, 0, self.width, 0)
        self.canv.restoreState()

class SolidLineFlowable(DottedLineFlowable):
    """Draws a solid horizontal line across the given width."""
    def __init__(self, width, line_width=1, color=colors.black):
        # Don't pass None as dash pattern - use empty tuple instead
        super().__init__(width, line_width=line_width, dash=(), color=color)

class PageNumCanvas(canvas.Canvas):
    """Canvas that draws page numbers."""
    def __init__(self, *args, **kwargs):
        self.page_number_settings = kwargs.pop('page_number_settings', {})
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        
    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()
        
    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            # Get settings from style
            show_page_numbers = self.page_number_settings.get('show', True)
            start_page = self.page_number_settings.get('start_page', 2)
            
            if show_page_numbers and self._pageNumber >= start_page:
                self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
        
    def draw_page_number(self, page_count):
        # Get settings from style
        font_name = self.page_number_settings.get('font', 'Helvetica')
        font_size = self.page_number_settings.get('size', 9)
        position = self.page_number_settings.get('position', 'bottom-right')
        format_string = self.page_number_settings.get('format', '{current} of {total}')
        
        # Set font
        self.setFont(font_name, font_size)
        
        # Format the text
        text = format_string.format(current=self._pageNumber, total=page_count)
        
        # Position the text based on the specified position
        if position == 'bottom-right':
            self.drawRightString(self._pagesize[0] - 30, 30, text)
        elif position == 'bottom-center':
            self.drawCentredString(self._pagesize[0] / 2, 30, text)
        elif position == 'bottom-left':
            self.drawString(30, 30, text)
        elif position == 'top-right':
            self.drawRightString(self._pagesize[0] - 30, self._pagesize[1] - 30, text)
        elif position == 'top-center':
            self.drawCentredString(self._pagesize[0] / 2, self._pagesize[1] - 30, text)
        elif position == 'top-left':
            self.drawString(30, self._pagesize[1] - 30, text)

class MyDocTemplate(BaseDocTemplate):
    """Custom document template with table of contents."""
    def __init__(self, filename, toc_settings=None, **kwargs):
        super().__init__(filename, **kwargs)
        self.allowSplitting = 1
        self.toc = TableOfContents()
        
        # Configure TOC based on settings
        if toc_settings:
            # Create level styles based on settings
            self.toc.levelStyles = []
            for i, level_style in enumerate(toc_settings.get('level_styles', [])):
                self.toc.levelStyles.append(
                    ParagraphStyle(
                        name=f'TOCHeading{i+1}',
                        fontSize=level_style.get('font_size', 12 - i),
                        leftIndent=level_style.get('indent', 20 + i*20),
                        leading=level_style.get('leading', 14 - i*2),
                        fontName=level_style.get('font_name', 'Helvetica'),
                        textColor=self._parse_color(level_style.get('text_color', '#000000'))
                    )
                )
        else:
            # Default TOC styles
            self.toc.levelStyles = [
                ParagraphStyle(name='TOCHeading1', fontSize=12, leftIndent=20, leading=14),
                ParagraphStyle(name='TOCHeading2', fontSize=10, leftIndent=40, leading=12),
            ]
    
    def _parse_color(self, color_value):
        """Parse color from string or hex value."""
        if isinstance(color_value, str):
            if color_value.startswith('#'):
                return colors.HexColor(color_value)
            else:
                return getattr(colors, color_value, colors.black)
        return colors.black
        
    def afterFlowable(self, flowable):
        """Adds entries to the table of contents."""
        if isinstance(flowable, Paragraph):
            style_name = flowable.style.name
            text = flowable.getPlainText()
            
            # Add chapter and section titles to TOC
            if style_name == 'ChapterTitleStyle':
                self.notify('TOCEntry', (0, text, self.page))
            elif style_name == 'CustomSectionTitle':
                self.notify('TOCEntry', (1, text, self.page))

class StyleManager:
    """Manages PDF style templates."""
    def __init__(self, styles_dir='styles'):
        self.styles_dir = styles_dir
        self.available_styles = self._find_available_styles()
        
    def _find_available_styles(self):
        """Find all available style templates in the styles directory."""
        styles = {}
        
        # Create styles directory if it doesn't exist
        if not os.path.exists(self.styles_dir):
            os.makedirs(self.styles_dir, exist_ok=True)
        
        # Create a default style if the directory is empty
        if not os.listdir(self.styles_dir):
            self._create_default_style()
        
        # Try to load each style file
        for filename in os.listdir(self.styles_dir):
            if filename.endswith(('.json', '.yaml', '.yml')):
                style_name = os.path.splitext(filename)[0]
                file_path = os.path.join(self.styles_dir, filename)
                
                # Verify the file is valid before adding it
                try:
                    if os.path.getsize(file_path) == 0:
                        print(f"Warning: Style file {filename} is empty, skipping")
                        continue
                        
                    with open(file_path, 'r') as f:
                        content = f.read().strip()
                        if not content:
                            print(f"Warning: Style file {filename} is empty, skipping")
                            continue
                            
                        if filename.endswith('.json'):
                            json.loads(content)  # Test if valid JSON
                        elif filename.endswith(('.yaml', '.yml')):
                            yaml.safe_load(content)  # Test if valid YAML
                        
                        styles[style_name] = file_path
                        print(f"Successfully loaded style: {style_name}")
                except Exception as e:
                    print(f"Warning: Could not load style file {filename}: {str(e)}")
        
        # If no valid styles found, create default and add it
        if not styles:
            print("No valid styles found. Creating default style.")
            self._create_default_style()
            
            # Add the default style
            default_path = os.path.join(self.styles_dir, 'classic.json')
            if os.path.exists(default_path):
                styles['classic'] = default_path
        
        return styles
    
    def _create_default_style(self):
        """Create a default style template."""
        default_style = {
            "name": "Classic",
            "description": "A clean, professional book layout with classic typography",
            "page": {
                "size": "A4",
                "margins": {"left": 72, "right": 72, "top": 72, "bottom": 72}
            },
            "fonts": [],
            "page_numbers": {
                "show": True,
                "format": "{current} of {total}",
                "position": "bottom-right",
                "font": "Helvetica",
                "size": 9,
                "start_page": 2
            },
            "title_page": {
                "title": {
                    "font": "Helvetica-Bold",
                    "size": 32,
                    "color": "#2E4053",
                    "spacing": "words",
                    "alignment": "center",
                    "case": "upper"
                },
                "author": {
                    "font": "Helvetica",
                    "size": 16,
                    "color": "#2E4053",
                    "prefix": "By",
                    "alignment": "center"
                },
                "spacing": {
                    "top": 0.4,
                    "between": 0.3
                }
            },
            "table_of_contents": {
                "title": {
                    "text": "Table of Contents",
                    "font": "Helvetica-Bold",
                    "size": 18,
                    "alignment": "center"
                },
                "level_styles": [
                    {
                        "font_name": "Helvetica",
                        "font_size": 12,
                        "indent": 20,
                        "leading": 14,
                        "text_color": "#000000"
                    },
                    {
                        "font_name": "Helvetica",
                        "font_size": 10,
                        "indent": 40,
                        "leading": 12,
                        "text_color": "#333333"
                    }
                ]
            },
            "chapter": {
                "number": {
                    "prefix": "CHAPTER",
                    "font": "Helvetica-Bold",
                    "size": 14,
                    "color": "#000000",
                    "alignment": "center",
                    "case": "upper"
                },
                "title": {
                    "font": "Helvetica-Bold",
                    "size": 16,
                    "color": "#000000",
                    "alignment": "center",
                    "case": "upper"
                },
                "divider": {
                    "type": "dotted",
                    "width": 1,
                    "color": "#000000",
                    "spacing": {"before": 6, "after": 12}
                },
                "page_break": {
                    "before": true,
                    "after": true
                }
            },
            "section": {
                "title": {
                    "font": "Helvetica-Bold",
                    "size": 16,
                    "color": "#566573",
                    "alignment": "center",
                    "space_before": 30,
                    "space_after": 20
                },
                "divider": {
                    "type": "dotted",
                    "width": 1,
                    "color": "#000000",
                    "spacing": {"before": 6, "after": 12}
                }
            },
            "body_text": {
                "font": "Helvetica",
                "size": 12,
                "leading": 14,
                "alignment": "justified",
                "space_after": 12
            }
        }
        
        # Make sure the directory exists
        os.makedirs(self.styles_dir, exist_ok=True)
        
        # Save the default style
        default_path = os.path.join(self.styles_dir, 'classic.json')
        with open(default_path, 'w') as f:
            json.dump(default_style, f, indent=2)
        
        print(f"Created default style template at {default_path}")
    
    def get_style_names(self):
        """Get a list of available style names."""
        return list(self.available_styles.keys())
    
    def load_style(self, style_name):
        """Load a style template from file."""
        if style_name not in self.available_styles:
            print(f"Style '{style_name}' not found. Falling back to default style.")
            # Attempt to create and use default
            self._create_default_style()
            style_name = 'classic'
            
        file_path = self.available_styles.get(style_name)
        if not file_path:
            raise ValueError(f"No valid style found for '{style_name}'")
        
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'r') as f:
                    return json.load(f)
            elif file_path.endswith(('.yaml', '.yml')):
                with open(file_path, 'r') as f:
                    return yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported file format: {file_path}")
        except Exception as e:
            print(f"Error loading style {style_name}: {str(e)}")
            # As a fallback, create an in-memory default style
            print("Using in-memory default style as fallback")
            return {
                "name": "Fallback",
                "description": "Default fallback style",
                "page": {"size": "A4", "margins": {"left": 72, "right": 72, "top": 72, "bottom": 72}},
                "fonts": [],
                "page_numbers": {"show": True, "format": "{current}", "position": "bottom-right", "font": "Helvetica", "size": 9},
                "title_page": {
                    "title": {"font": "Helvetica-Bold", "size": 24, "color": "#000000", "spacing": "none", "alignment": "center", "case": "none"},
                    "author": {"font": "Helvetica", "size": 12, "color": "#000000", "prefix": "By", "alignment": "center"},
                    "spacing": {"top": 0.4, "between": 0.2}
                },
                "table_of_contents": {
                    "title": {"text": "Contents", "font": "Helvetica-Bold", "size": 14, "alignment": "center"},
                    "level_styles": []
                },
                "chapter": {
                    "number": {"prefix": "Chapter", "font": "Helvetica-Bold", "size": 14, "color": "#000000", "alignment": "center"},
                    "title": {"font": "Helvetica-Bold", "size": 16, "color": "#000000", "alignment": "center"},
                    "divider": {"type": "none", "width": 0, "color": "#000000", "spacing": {"before": 0, "after": 0}},
                    "page_break": {"before": True, "after": False}
                },
                "section": {
                    "title": {"font": "Helvetica-Bold", "size": 14, "color": "#000000", "alignment": "left", "space_before": 12, "space_after": 6},
                    "divider": {"type": "none", "width": 0, "color": "#000000", "spacing": {"before": 0, "after": 0}}
                },
                "body_text": {"font": "Helvetica", "size": 12, "leading": 14, "alignment": "justified", "space_after": 12}
            }

class PDFGenerator:
    """Generates PDF books from JSON content using style templates."""
    def __init__(self):
        self.style_manager = StyleManager()
        self.styles = getSampleStyleSheet()
        
    def _register_fonts(self, fonts_config):
        """Register custom fonts specified in the style template."""
        for font in fonts_config:
            font_name = font.get('name')
            font_file = font.get('file')
            font_alias = font.get('alias', font_name)
            
            # Check if font exists in fonts directory
            font_path = os.path.join('fonts', font_file)
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont(font_alias, font_path))
    
    def _parse_color(self, color_value):
        """Parse color from string or hex value."""
        if isinstance(color_value, str):
            if color_value.startswith('#'):
                return colors.HexColor(color_value)
            else:
                return getattr(colors, color_value, colors.black)
        return colors.black
    
    def _create_custom_styles(self, style_config):
        """Create custom styles based on the style template."""
        # Reset styles
        self.styles = getSampleStyleSheet()
        
        # Create book title style
        title_config = style_config['title_page']['title']
        self.styles.add(ParagraphStyle(
            name='BookTitle',
            parent=self.styles['Heading1'],
            fontSize=title_config.get('size', 32),
            spaceAfter=0,
            spaceBefore=0,
            textColor=self._parse_color(title_config.get('color', '#2E4053')),
            alignment=1 if title_config.get('alignment') == 'center' else 0,
            fontName=title_config.get('font', 'Helvetica-Bold'),
            leading=title_config.get('size', 32) + 8
        ))
        
        # Create author name style
        author_config = style_config['title_page']['author']
        self.styles.add(ParagraphStyle(
            name='AuthorName',
            parent=self.styles['Normal'],
            fontSize=author_config.get('size', 16),
            spaceAfter=30,
            spaceBefore=0,
            textColor=self._parse_color(author_config.get('color', '#2E4053')),
            alignment=1 if author_config.get('alignment') == 'center' else 0,
            fontName=author_config.get('font', 'Helvetica')
        ))
        
        # Create chapter number style
        chapter_num_config = style_config['chapter']['number']
        self.styles.add(ParagraphStyle(
            name='ChapterNumberStyle',
            parent=self.styles['Heading1'],
            fontSize=chapter_num_config.get('size', 14),
            leading=chapter_num_config.get('size', 14) + 2,
            alignment=1 if chapter_num_config.get('alignment') == 'center' else 0,
            textColor=self._parse_color(chapter_num_config.get('color', '#000000')),
            fontName=chapter_num_config.get('font', 'Helvetica-Bold')
        ))
        
        # Create chapter title style
        chapter_title_config = style_config['chapter']['title']
        self.styles.add(ParagraphStyle(
            name='ChapterTitleStyle',
            parent=self.styles['Heading1'],
            fontSize=chapter_title_config.get('size', 16),
            leading=chapter_title_config.get('size', 16) + 2,
            alignment=1 if chapter_title_config.get('alignment') == 'center' else 0,
            textColor=self._parse_color(chapter_title_config.get('color', '#000000')),
            fontName=chapter_title_config.get('font', 'Helvetica-Bold')
        ))
        
        # Create section title style
        section_config = style_config['section']['title']
        self.styles.add(ParagraphStyle(
            name='CustomSectionTitle',
            parent=self.styles['Heading2'],
            fontSize=section_config.get('size', 16),
            spaceAfter=section_config.get('space_after', 20),
            spaceBefore=section_config.get('space_before', 30),
            textColor=self._parse_color(section_config.get('color', '#566573')),
            alignment=1 if section_config.get('alignment') == 'center' else 0,
            fontName=section_config.get('font', 'Helvetica-Bold')
        ))
        
        # Create body text style
        body_config = style_config['body_text']
        alignment_map = {
            'left': 0,
            'center': 1,
            'right': 2,
            'justified': 4
        }
        alignment = alignment_map.get(body_config.get('alignment', 'justified'), 4)
        
        self.styles.add(ParagraphStyle(
            name='CustomBodyText',
            parent=self.styles['Normal'],
            fontSize=body_config.get('size', 12),
            leading=body_config.get('leading', 14),
            spaceAfter=body_config.get('space_after', 12),
            alignment=alignment,
            fontName=body_config.get('font', 'Helvetica')
        ))
        
        # Create TOC title style
        toc_title_config = style_config['table_of_contents']['title']
        self.styles.add(ParagraphStyle(
            name='TOCTitle',
            fontSize=toc_title_config.get('size', 18),
            leading=toc_title_config.get('size', 18) + 4,
            alignment=1 if toc_title_config.get('alignment') == 'center' else 0,
            spaceAfter=20,
            fontName=toc_title_config.get('font', 'Helvetica-Bold')
        ))
    
    def _get_page_size(self, size_name):
        """Get page size from name."""
        size_map = {
            'A4': A4,
            'LETTER': LETTER,
            'LEGAL': LEGAL
        }
        return size_map.get(size_name.upper(), A4)
    
    def _add_centered_title_page(self, story, book_name, author_name, style_config):
        """Add the title page to the story."""
        title_config = style_config['title_page']
        spacing = title_config['spacing']
        
        # Add top spacing
        story.append(VerticalSpace(A4[1] * spacing.get('top', 0.4)))
        
        # Format title based on style
        title_style = title_config['title']
        case_format = title_style.get('case', 'upper')
        spacing_format = title_style.get('spacing', 'words')
        
        # Apply case formatting
        if case_format == 'upper':
            formatted_title = book_name.upper()
        elif case_format == 'lower':
            formatted_title = book_name.lower()
        elif case_format == 'title':
            formatted_title = book_name.title()
        else:
            formatted_title = book_name
        
        # Apply spacing formatting
        if spacing_format == 'words':
            words = formatted_title.split()
            spaced_title = '<br/>'.join(words)
        elif spacing_format == 'lines':
            spaced_title = formatted_title.replace(' ', '<br/>')
        else:
            spaced_title = formatted_title
        
        story.append(Paragraph(spaced_title, self.styles['BookTitle']))
        
        # Add spacing between title and author
        story.append(VerticalSpace(A4[1] * spacing.get('between', 0.3)))
        
        # Add author with optional prefix
        author_style = title_config['author']
        author_prefix = author_style.get('prefix', '')
        if author_prefix:
            author_text = f"{author_prefix}<br/>{author_name}"
        else:
            author_text = author_name
            
        story.append(Paragraph(author_text, self.styles['AuthorName']))
        story.append(PageBreak())

    def _add_centered_chapter_page(self, story, chapter_id, chapter_name, style_config):
        """Add a chapter page to the story."""
        chapter_config = style_config['chapter']
        
        # Add page break before chapter if configured
        if chapter_config['page_break'].get('before', True):
            story.append(PageBreak())
        
        # Add spacing at top of page
        story.append(Spacer(1, A4[1] * 0.25))
        
        # Format chapter number
        number_config = chapter_config['number']
        number_prefix = number_config.get('prefix', 'CHAPTER')
        chapter_number_text = f"{number_prefix} {chapter_id}"
        if number_config.get('case', '') == 'upper':
            chapter_number_text = chapter_number_text.upper()
            
        story.append(Paragraph(chapter_number_text, self.styles['ChapterNumberStyle']))
        
        # Add divider if configured
        divider_config = chapter_config['divider']
        if divider_config.get('type') != 'none':
            # Add spacing before divider
            story.append(Spacer(1, divider_config['spacing'].get('before', 6)))
            
            # Add the divider line
            dotted_line_width = A4[0] - 2 * 72
            
            if divider_config.get('type') == 'dotted':
                story.append(DottedLineFlowable(
                    dotted_line_width,
                    line_width=divider_config.get('width', 1),
                    color=self._parse_color(divider_config.get('color', '#000000'))
                ))
            elif divider_config.get('type') == 'solid':
                story.append(SolidLineFlowable(
                    dotted_line_width,
                    line_width=divider_config.get('width', 1),
                    color=self._parse_color(divider_config.get('color', '#000000'))
                ))
        
        # Add page break after chapter if configured
        if chapter_config['page_break'].get('after', True):
            story.append(PageBreak())

    def _add_section(self, story, section_name, section_text, style_config):
        """Add a section to the story."""
        section_config = style_config['section']
        
        if section_name:
            story.append(Paragraph(section_name, self.styles['CustomSectionTitle']))
            
            # Add divider if configured
            divider_config = section_config['divider']
            if divider_config.get('type') != 'none':
                # Add spacing before divider
                story.append(Spacer(1, divider_config['spacing'].get('before', 6)))
                
                # Add the divider line
                dotted_line_width = A4[0] - 2 * 72
                
                if divider_config.get('type') == 'dotted':
                    story.append(DottedLineFlowable(
                        dotted_line_width,
                        line_width=divider_config.get('width', 1),
                        color=self._parse_color(divider_config.get('color', '#000000'))
                    ))
                elif divider_config.get('type') == 'solid':
                    story.append(SolidLineFlowable(
                        dotted_line_width,
                        line_width=divider_config.get('width', 1),
                        color=self._parse_color(divider_config.get('color', '#000000'))
                    ))
                
                # Add spacing after divider
                story.append(Spacer(1, divider_config['spacing'].get('after', 12)))
        
        # Convert markdown to ReportLab markup
        rl_text = convert_markdown_to_rl_markup(section_text)
        
        # Add the text with the body text style
        story.append(Paragraph(rl_text, self.styles['CustomBodyText']))
        story.append(Spacer(1, style_config['body_text'].get('space_after', 12)))

    def generate_pdf(self, input_json_path, book_name, author_name, style_name='classic', output_dir='results/pdfs'):
        """Generate a PDF from JSON content using the specified style template."""
        try:
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Create a safe filename based on the book name
            safe_filename = "".join(x for x in book_name if x.isalnum() or x in (' ', '-', '_')).rstrip()
            output_pdf_path = os.path.join(output_dir, f"{safe_filename}.pdf")
            
            # Load the style template
            style_config = self.style_manager.load_style(style_name)
            print(f"Loaded style: {style_name}")
            
            # Register custom fonts
            self._register_fonts(style_config.get('fonts', []))
            
            # Create custom styles
            self._create_custom_styles(style_config)
            
            # Get page size and margins
            page_config = style_config['page']
            page_size = self._get_page_size(page_config.get('size', 'A4'))
            margins = page_config.get('margins', {'left': 72, 'right': 72, 'top': 72, 'bottom': 72})
            
            # Create document template with TOC settings
            doc = MyDocTemplate(
                output_pdf_path,
                pagesize=page_size,
                rightMargin=margins.get('right', 72),
                leftMargin=margins.get('left', 72),
                topMargin=margins.get('top', 72),
                bottomMargin=margins.get('bottom', 72),
                toc_settings=style_config.get('table_of_contents', {})
            )
            
            # Set up page template
            frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
            template = PageTemplate(id='main', frames=frame)
            doc.addPageTemplates([template])
            
            # Load content from JSON
            with open(input_json_path, 'r') as file:
                sections = json.load(file)
            
            print(f"Loaded JSON with {len(sections)} sections")
            
            # Sort sections by chapter and section number
            try:
                # Try to sort numerically first
                sections.sort(key=lambda x: (int(x.get('chapter_id', 0)), float(x.get('section_number', 0))))
                print("Sorted sections numerically")
            except (ValueError, TypeError) as e:
                # Fallback sorting if numeric conversion fails
                print(f"Numeric sorting failed: {e}, using string sorting as fallback")
                sections.sort(key=lambda x: (str(x.get('chapter_id', '')), str(x.get('section_number', ''))))
            
            # Build the story
            story = []
            
            # Add title page
            self._add_centered_title_page(story, book_name, author_name, style_config)
            print("Added title page")
            
            # Add table of contents
            toc_title_config = style_config['table_of_contents']['title']
            story.append(Paragraph(toc_title_config.get('text', 'Table of Contents'), self.styles['TOCTitle']))
            story.append(doc.toc)
            story.append(PageBreak())
            print("Added table of contents")
            
            # Process sections and chapters
            current_chapter = None
            for section in sections:
                chapter_id = section.get('chapter_id', '')
                chapter_name = section.get('chapter_name', '').strip()
                
                # Add chapter page if this is a new chapter
                if chapter_id != current_chapter:
                    print(f"Processing chapter {chapter_id}: {chapter_name}")
                    self._add_centered_chapter_page(story, chapter_id, chapter_name, style_config)
                    current_chapter = chapter_id
                
                # Add this section
                section_name = section.get('section_name', '').strip()
                section_text = section.get('text', '').strip()
                print(f"  - Section: {section_name}")
                
                self._add_section(story, section_name, section_text, style_config)
            
            # Build the PDF with page numbers
            print("Building PDF...")
            doc.multiBuild(story, canvasmaker=lambda *args, **kwargs: PageNumCanvas(*args, page_number_settings=style_config.get('page_numbers', {}), **kwargs))
            
            print(f"PDF generated successfully: {output_pdf_path}")
            return output_pdf_path
            
        except Exception as e:
            print(f"Error generating PDF: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
            
            # Add spacing after divider
            story.append(Spacer(1, divider_config['spacing'].get('after', 12)))
        
        # Format chapter title
        title_config = chapter_config['title']
        if title_config.get('case', '') == 'upper':
            chapter_name = chapter_name.upper()
        elif title_config.get('case', '') == 'lower':
            chapter_name = chapter_name.lower()
        elif title_config.get('case', '') == 'title':
            chapter_name = chapter_name.title()
            
        story.append(Paragraph(chapter_name, self.styles['ChapterTitleStyle']))
        
        # Add bottom divider if needed
        if divider_config.get('type') != 'none':
            story.append(Spacer(1, divider_config['spacing'].get('before', 6)))
            
            dotted_line_width = A4[0] - 2 * 72
            
            if divider_config.get('type') == 'dotted':
                story.append(DottedLineFlowable(
                    dotted_line_width,
                    line_width=divider_config.get('width', 1),
                    color=self._parse_color(divider_config.get('color', '#000000'))
                ))
            elif divider_config.get('type') == 'solid':
                story.append(SolidLineFlowable(
                    dotted_line_width,
                    line_width=divider_config.get('width', 1),
                    color=self._parse_color(divider_config.get('color', '#000000'))
                ))