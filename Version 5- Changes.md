
# DrupalMind Version 5 - Content Migration Fixes

## Executive Summary

Version 5 addresses critical content splitting issues where websites with multiple sections are incorrectly migrated as separate Drupal entities instead of cohesive pages. This comprehensive plan fixes the root causes and implements intelligent content consolidation.

## Critical Issues Identified

### Issue #1: Section Misclassification
**Problem**: AnalyzerAgent incorrectly classifies all content sections as "navigation" type
**Impact**: Main content areas treated as separate navigation components
**Evidence**: Debug log shows 4 sections all classified as "navigation" instead of recognizing main content

### Issue #2: Incorrect Content Mapping
**Problem**: MappingAgent maps navigation sections to article nodes instead of page content
**Impact**: Creates multiple separate articles instead of unified pages
**Evidence**: All sections mapped to "article" with low fidelity scores (0.5)

### Issue #3: Content Agent Skips Sections
**Problem**: ContentAgent creates 0 content items, skipping navigation-classified sections
**Impact**: No actual content migration occurs
**Evidence**: Debug shows "0 items created" despite 4 sections available

### Issue #4: Incomplete Page Assembly
**Problem**: BuildAgent only creates homepage without assembling all content sections
**Impact**: Fragmented content across multiple nodes
**Evidence**: Only 1 page built out of 10 expected pages

### Issue #5: Visual Diff Disabled
**Problem**: Playwright not available, visual feedback loop broken
**Impact**: No quality control or missing piece detection
**Evidence**: "Playwright not available - skipping visual diff" in logs

### Issue #6: Structured Content Loss (CRITICAL)
**Problem**: AnalyzerAgent only extracts plain text, ignoring HTML structure
**Impact**: Tables, lists, images, and formatted content completely lost
**Evidence**: `text_content = tag.get_text(separator=" ", strip=True)[:400]` strips all HTML structure

### Issue #7: Limited Content Element Detection
**Problem**: No detection of tables, lists, code blocks, media galleries, forms
**Impact**: Rich content elements not identified or migrated
**Evidence**: Only checks for basic `has_images`, `has_links`, `has_form` flags

### Issue #8: Shallow Content Analysis
**Problem**: Only extracts first 400 characters of text, missing deep content
**Impact**: Complex content structures and detailed information lost
**Evidence**: `[:400]` truncation in `_extract_sections()` method

---

## Version 5 Implementation Plan

## Phase 1: Intelligent Section Classification (Priority: CRITICAL)

### Change 1.1: Enhanced Section Analysis Algorithm

**File**: `agents/analyzer.py`
**Method**: `_classify_section()`

**Current Issue**: 
- Over-aggressive navigation classification
- No content hierarchy understanding
- Missing semantic analysis

**Solution Algorithm**:
```python
def _classify_section_v5(self, tag: str, classes: str, id_attr: str, text: str, position: int, total_sections: int) -> dict:
    """
    Enhanced section classification with content hierarchy and semantic analysis
    Returns: {type: str, confidence: float, is_primary_content: bool, consolidation_group: str}
    """
    
    # 1. Position-based classification
    if position == 0:
        likely_header = True
    elif position == total_sections - 1:
        likely_footer = True
    else:
        likely_content = True
    
    # 2. Content volume analysis
    content_density = len(text.strip()) / max(len(text), 1)
    has_substantial_content = len(text.strip()) > 200
    
    # 3. Semantic keyword analysis
    navigation_keywords = ["nav", "menu", "header", "footer", "sidebar"]
    content_keywords = ["article", "main", "content", "section", "post", "story"]
    
    # 4. HTML structure analysis
    is_semantic_content = tag in ["main", "article", "section"]
    is_navigation_element = tag in ["nav", "header", "footer", "aside"]
    
    # 5. Classification logic with confidence scoring
    classification = {
        "type": "content",  # default
        "confidence": 0.5,
        "is_primary_content": False,
        "consolidation_group": "page_content",
        "reasoning": []
    }
    
    # Apply classification rules...
    return classification
```

**Implementation Steps**:
1. Add content density analysis
2. Implement position-based classification
3. Add semantic keyword scoring
4. Create confidence-based classification
5. Add consolidation grouping logic

### Change 1.2: Section Relationship Mapping

**File**: `agents/analyzer.py`
**Method**: `_extract_sections()` (enhanced)

**New Feature**: Section hierarchy and relationships
```python
def _build_section_hierarchy(self, sections: list) -> dict:
    """
    Build hierarchical relationships between sections
    Returns: {primary_content: [], supporting_content: [], navigation: []}
    """
    hierarchy = {
        "primary_content": [],
        "supporting_content": [],
        "navigation": [],
        "consolidation_groups": {}
    }
    
    for section in sections:
        if section["classification"]["is_primary_content"]:
            hierarchy["primary_content"].append(section)
        elif section["classification"]["type"] == "navigation":
            hierarchy["navigation"].append(section)
        else:
            hierarchy["supporting_content"].append(section)
    
    # Group sections that should be consolidated into single pages
    hierarchy["consolidation_groups"] = self._create_consolidation_groups(sections)
    
    return hierarchy
```

## Phase 1.5: Structured Content Extraction (Priority: CRITICAL)

### Change 1.5: Rich Content Element Detection

**File**: `agents/analyzer.py`
**Method**: `_extract_sections()` (complete rewrite)

**Current Issue**: Only extracts plain text, missing tables, lists, images, code blocks
**Solution**: Comprehensive structured content analysis

```python
def _extract_sections_v5(self, soup: BeautifulSoup) -> list[dict]:
    """
    V5: Enhanced section extraction with structured content analysis
    """
    sections = []
    section_tags = soup.find_all(["section", "article", "header", "footer", "main", "aside", "div"])
    
    for i, tag in enumerate(section_tags[:20]):  # Increased from 15 to 20
        # Enhanced content extraction
        structured_content = self._extract_structured_content(tag)
        
        # Get heading
        heading = tag.find(re.compile(r"^h[1-6]$"))
        heading_text = heading.get_text(strip=True) if heading else ""
        
        # Enhanced classification
        classes = " ".join(tag.get("class", []))
        id_attr = tag.get("id", "")
        classification = self._classify_section_v5(
            tag.name, classes, id_attr, 
            structured_content["text_content"], i, len(section_tags)
        )
        
        section = {
            "index": i,
            "type": classification["type"],
            "tag": tag.name,
            "heading": heading_text,
            "text_preview": structured_content["text_content"][:500],  # Increased from 200
            "full_html": structured_content["full_html"],
            "structured_elements": structured_content["elements"],
            "has_images": structured_content["has_images"],
            "has_links": structured_content["has_links"],
            "has_form": structured_content["has_form"],
            "has_tables": structured_content["has_tables"],
            "has_lists": structured_content["has_lists"],
            "has_code": structured_content["has_code"],
            "has_media": structured_content["has_media"],
            "content_complexity": structured_content["complexity_score"],
            "classification": classification,
            "drupal_component": self._map_to_drupal_component_v5(classification["type"], structured_content),
        }
        
        sections.append(section)
    
    return sections

def _extract_structured_content(self, tag) -> dict:
    """
    Extract structured content elements from a section
    """
    # Get full HTML content (preserving structure)
    full_html = str(tag)
    
    # Get clean text content
    text_content = tag.get_text(separator=" ", strip=True)
    
    # Detect structured elements
    tables = tag.find_all("table")
    lists = tag.find_all(["ul", "ol", "dl"])
    images = tag.find_all("img")
    links = tag.find_all("a", href=True)
    forms = tag.find_all("form")
    code_blocks = tag.find_all(["code", "pre"])
    media = tag.find_all(["video", "audio", "iframe"])
    blockquotes = tag.find_all("blockquote")
    
    # Extract table data
    table_data = []
    for table in tables:
        table_info = self._extract_table_structure(table)
        table_data.append(table_info)
    
    # Extract list data
    list_data = []
    for list_elem in lists:
        list_info = self._extract_list_structure(list_elem)
        list_data.append(list_info)
    
    # Extract image data
    image_data = []
    for img in images:
        img_info = {
            "src": img.get("src", ""),
            "alt": img.get("alt", ""),
            "title": img.get("title", ""),
            "width": img.get("width"),
            "height": img.get("height")
        }
        image_data.append(img_info)
    
    # Calculate complexity score
    complexity_score = self._calculate_content_complexity(
        len(tables), len(lists), len(images), len(code_blocks), len(media)
    )
    
    return {
        "full_html": full_html,
        "text_content": text_content,
        "elements": {
            "tables": table_data,
            "lists": list_data,
            "images": image_data,
            "links": [{"href": a.get("href"), "text": a.get_text(strip=True)} for a in links[:10]],
            "code_blocks": [{"language": self._detect_code_language(code), "content": code.get_text()} for code in code_blocks],
            "media": [{"type": m.name, "src": m.get("src", "")} for m in media],
            "blockquotes": [{"text": bq.get_text(strip=True)} for bq in blockquotes]
        },
        "has_images": len(images) > 0,
        "has_links": len(links) > 0,
        "has_form": len(forms) > 0,
        "has_tables": len(tables) > 0,
        "has_lists": len(lists) > 0,
        "has_code": len(code_blocks) > 0,
        "has_media": len(media) > 0,
        "complexity_score": complexity_score
    }

def _extract_table_structure(self, table) -> dict:
    """
    Extract table structure and data
    """
    headers = []
    rows = []
    
    # Extract headers
    thead = table.find("thead")
    if thead:
        header_row = thead.find("tr")
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
    
    # Extract data rows
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr")[:10]:  # Limit to first 10 rows
        row_data = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if row_data:  # Skip empty rows
            rows.append(row_data)
    
    return {
        "headers": headers,
        "rows": rows,
        "row_count": len(rows),
        "column_count": len(headers) if headers else (len(rows[0]) if rows else 0),
        "html": str(table)
    }

def _extract_list_structure(self, list_elem) -> dict:
    """
    Extract list structure and items
    """
    list_type = list_elem.name  # ul, ol, dl
    items = []
    
    if list_type in ["ul", "ol"]:
        for li in list_elem.find_all("li", recursive=False):
            items.append({
                "text": li.get_text(strip=True),
                "html": str(li)
            })
    elif list_type == "dl":
        # Definition list
        terms = list_elem.find_all("dt")
        definitions = list_elem.find_all("dd")
        for i, term in enumerate(terms):
            definition = definitions[i] if i < len(definitions) else None
            items.append({
                "term": term.get_text(strip=True),
                "definition": definition.get_text(strip=True) if definition else ""
            })
    
    return {
        "type": list_type,
        "items": items[:20],  # Limit to first 20 items
        "item_count": len(items),
        "html": str(list_elem)
    }

def _calculate_content_complexity(self, tables: int, lists: int, images: int, code: int, media: int) -> float:
    """
    Calculate content complexity score (0-1)
    """
    base_score = 0.1
    
    # Add complexity for each element type
    complexity_weights = {
        "tables": 0.3,
        "lists": 0.1,
        "images": 0.15,
        "code": 0.2,
        "media": 0.25
    }
    
    score = base_score
    score += min(tables * complexity_weights["tables"], 0.3)
    score += min(lists * complexity_weights["lists"], 0.2)
    score += min(images * complexity_weights["images"], 0.3)
    score += min(code * complexity_weights["code"], 0.2)
    score += min(media * complexity_weights["media"], 0.3)
    
    return min(score, 1.0)

def _detect_code_language(self, code_elem) -> str:
    """
    Detect programming language from code block
    """
    classes = code_elem.get("class", [])
    for cls in classes:
        if cls.startswith("language-"):
            return cls.replace("language-", "")
        elif cls.startswith("lang-"):
            return cls.replace("lang-", "")
    
    # Try to detect from content
    content = code_elem.get_text()[:100].lower()
    if "function" in content and "{" in content:
        return "javascript"
    elif "def " in content and ":" in content:
        return "python"
    elif "<?php" in content:
        return "php"
    elif "<html" in content or "<div" in content:
        return "html"
    
    return "text"

def _map_to_drupal_component_v5(self, section_type: str, structured_content: dict) -> str:
    """
    Enhanced mapping considering structured content complexity
    """
    base_mapping = {
        "hero": "page with hero paragraph + media field",
        "navigation": "Drupal menu block",
        "features": "view with custom display + structured content",
        "about": "page with rich text + media gallery",
        "blog": "article content type with rich formatting",
        "contact": "contact form + custom fields",
        "footer": "footer menu + custom block with structured content",
        "testimonials": "testimonial content type with media",
        "team": "team member content type with structured bio",
        "pricing": "page with pricing table + comparison fields",
        "content": "page with rich text formatting",
    }
    
    base_component = base_mapping.get(section_type, "page with rich text")
    
    # Enhance based on content complexity
    if structured_content["has_tables"]:
        base_component += " + table formatting"
    
    if structured_content["has_media"]:
        base_component += " + media gallery"
    
    if structured_content["has_code"]:
        base_component += " + code highlighting"
    
    if structured_content["complexity_score"] > 0.7:
        base_component += " + custom layout"
    
    return base_component
```

## Phase 2: Smart Content Consolidation (Priority: CRITICAL)

### Change 2.1: Content Assembly Engine

**File**: `agents/content_agent.py`
**New Class**: `ContentAssembler`

**Purpose**: Intelligently combine multiple sections into cohesive page content with structured element preservation

```python
class ContentAssembler:
    """
    V5: Assembles multiple content sections into unified Drupal pages
    Preserves tables, lists, images, and other structured content
    """
    
    def assemble_page_content(self, sections: list, page_info: dict) -> dict:
        """
        Combine sections into a single page body with proper structure preservation
        """
        assembled_content = {
            "title": page_info.get("title"),
            "body_html": "",
            "sections_included": [],
            "content_type": "page",
            "metadata": {},
            "structured_elements_count": 0,
            "tables_preserved": 0,
            "lists_preserved": 0,
            "images_preserved": 0
        }
        
        # 1. Identify hero/header section
        hero_section = self._find_hero_section(sections)
        if hero_section:
            assembled_content["body_html"] += self._format_hero_html_v5(hero_section)
            assembled_content["sections_included"].append(hero_section.get("index"))
        
        # 2. Assemble main content sections with structured content
        main_sections = self._filter_main_content(sections)
        for section in main_sections:
            formatted_html = self._format_section_html_v5(section)
            assembled_content["body_html"] += formatted_html
            assembled_content["sections_included"].append(section.get("index"))
            
            # Count preserved elements
            self._count_preserved_elements(section, assembled_content)
        
        # 3. Add supporting content with structure preservation
        supporting_sections = self._filter_supporting_content(sections)
        for section in supporting_sections:
            formatted_html = self._format_supporting_html_v5(section)
            assembled_content["body_html"] += formatted_html
            assembled_content["sections_included"].append(section.get("index"))
            
            # Count preserved elements
            self._count_preserved_elements(section, assembled_content)
        
        return assembled_content
    
    def _format_hero_html_v5(self, section: dict) -> str:
        """V5: Format hero section preserving structured content"""
        structured_elements = section.get("structured_elements", {})
        
        hero_html = f'<div class="hero-section">'
        
        # Add heading
        if section.get('heading'):
            hero_html += f'<h1>{section.get("heading")}</h1>'
        
        # Preserve full HTML structure instead of just text
        if section.get("full_html"):
            # Clean and preserve the original HTML structure
            cleaned_html = self._preserve_structured_content(section.get("full_html"))
            hero_html += f'<div class="hero-content">{cleaned_html}</div>'
        else:
            hero_html += f'<div class="hero-content">{section.get("text_preview", "")}</div>'
        
        hero_html += '</div>'
        return hero_html
    
    def _format_section_html_v5(self, section: dict) -> str:
        """V5: Format regular content section preserving all structured elements"""
        section_html = f'<section class="content-section {section.get("type", "")}">'
        
        # Add section heading
        if section.get('heading'):
            section_html += f'<h2>{section.get("heading")}</h2>'
        
        # Preserve structured content
        if section.get("full_html"):
            preserved_html = self._preserve_structured_content(section.get("full_html"))
            section_html += f'<div class="section-content">{preserved_html}</div>'
        else:
            section_html += f'<div class="section-content">{section.get("text_preview", "")}</div>'
        
        section_html += '</section>'
        return section_html
    
    def _format_supporting_html_v5(self, section: dict) -> str:
        """V5: Format supporting content with structure preservation"""
        return self._format_section_html_v5(section)  # Same logic for now
    
    def _preserve_structured_content(self, html_content: str) -> str:
        """
        Preserve structured content elements (tables, lists, etc.) while cleaning unsafe content
        """
        from bs4 import BeautifulSoup
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove potentially unsafe elements
        unsafe_tags = ['script', 'style', 'iframe', 'object', 'embed']
        for tag in unsafe_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Preserve important structured elements
        preserved_elements = []
        
        # Preserve tables with proper structure
        for table in soup.find_all('table'):
            preserved_elements.append(self._enhance_table_html(table))
        
        # Preserve lists with proper structure
        for list_elem in soup.find_all(['ul', 'ol', 'dl']):
            preserved_elements.append(self._enhance_list_html(list_elem))
        
        # Preserve images with proper attributes
        for img in soup.find_all('img'):
            preserved_elements.append(self._enhance_image_html(img))
        
        # Preserve code blocks with syntax highlighting
        for code in soup.find_all(['code', 'pre']):
            preserved_elements.append(self._enhance_code_html(code))
        
        # Preserve blockquotes
        for blockquote in soup.find_all('blockquote'):
            preserved_elements.append(self._enhance_blockquote_html(blockquote))
        
        # Return cleaned HTML with preserved structure
        return str(soup)
    
    def _enhance_table_html(self, table) -> str:
        """Enhance table HTML for better Drupal compatibility"""
        # Add responsive table wrapper
        table['class'] = table.get('class', []) + ['drupal-table', 'responsive-table']
        
        # Ensure proper table structure
        if not table.find('thead') and table.find('tr'):
            # Convert first row to header if no thead exists
            first_row = table.find('tr')
            if first_row:
                thead = table.new_tag('thead')
                tbody = table.new_tag('tbody')
                
                # Move first row to thead
                first_row.extract()
                thead.append(first_row)
                table.insert(0, thead)
                
                # Move remaining rows to tbody
                for row in table.find_all('tr'):
                    row.extract()
                    tbody.append(row)
                table.append(tbody)
        
        return str(table)
    
    def _enhance_list_html(self, list_elem) -> str:
        """Enhance list HTML for better presentation"""
        list_elem['class'] = list_elem.get('class', []) + ['drupal-list']
        return str(list_elem)
    
    def _enhance_image_html(self, img) -> str:
        """Enhance image HTML with responsive attributes"""
        img['class'] = img.get('class', []) + ['drupal-image', 'responsive-image']
        
        # Add loading attribute for performance
        img['loading'] = 'lazy'
        
        # Ensure alt text exists
        if not img.get('alt'):
            img['alt'] = 'Image'
        
        return str(img)
    
    def _enhance_code_html(self, code) -> str:
        """Enhance code blocks with syntax highlighting classes"""
        code['class'] = code.get('class', []) + ['drupal-code']
        
        # Wrap in pre if not already
        if code.name == 'code' and code.parent.name != 'pre':
            pre = code.new_tag('pre')
            pre['class'] = ['drupal-code-block']
            code.wrap(pre)
            return str(pre)
        
        return str(code)
    
    def _enhance_blockquote_html(self, blockquote) -> str:
        """Enhance blockquote HTML"""
        blockquote['class'] = blockquote.get('class', []) + ['drupal-blockquote']
        return str(blockquote)
    
    def _count_preserved_elements(self, section: dict, assembled_content: dict):
        """Count preserved structured elements for reporting"""
        structured_elements = section.get("structured_elements", {})
        
        if structured_elements.get("tables"):
            assembled_content["tables_preserved"] += len(structured_elements["tables"])
        
        if structured_elements.get("lists"):
            assembled_content["lists_preserved"] += len(structured_elements["lists"])
        
        if structured_elements.get("images"):
            assembled_content["images_preserved"] += len(structured_elements["images"])
        
        # Update total count
        assembled_content["structured_elements_count"] = (
            assembled_content["tables_preserved"] + 
            assembled_content["lists_preserved"] + 
            assembled_content["images_preserved"]
        )
    
    def _find_hero_section(self, sections: list) -> dict:
        """Find the hero/banner section"""
        for section in sections:
            if section.get("type") in ["hero", "banner", "header"]:
                return section
            if section.get("index") == 0 and section.get("content_complexity", 0) > 0.3:
                return section
        return None
    
    def _filter_main_content(self, sections: list) -> list:
        """Filter sections that contain main content"""
        main_sections = []
        for section in sections:
            classification = section.get("classification", {})
            if classification.get("is_primary_content") or section.get("type") in ["content", "about", "features"]:
                main_sections.append(section)
        return main_sections
    
    def _filter_supporting_content(self, sections: list) -> list:
        """Filter sections that contain supporting content"""
        supporting_sections = []
        for section in sections:
            if section.get("type") in ["testimonials", "team", "blog", "pricing"]:
                supporting_sections.append(section)
        return supporting_sections
```

### Change 2.2: Enhanced Content Migration Logic

**File**: `agents/content_agent.py`
**Method**: `_migrate_all()` (complete rewrite)

**Current Issue**: Only creates taxonomy terms, skips actual content
**Solution**: Implement page-centric content migration

```python
def _migrate_all_v5(self, blueprint: dict, envelopes: dict) -> dict:
    """
    V5: Page-centric content migration with section consolidation
    """
    created_pages = 0
    created_articles = 0
    errors = []
    
    # Initialize content assembler
    assembler = ContentAssembler()
    
    # Get section hierarchy
    sections = blueprint.get("sections", [])
    section_hierarchy = self._build_section_hierarchy(sections)
    
    # Process each page from blueprint
    pages = blueprint.get("pages", [])
    
    for page in pages:
        try:
            # Find sections that belong to this page
            page_sections = self._find_page_sections(page, sections, section_hierarchy)
            
            if not page_sections:
                # Create basic page with minimal content
                self._create_basic_page(page)
                created_pages += 1
                continue
            
            # Assemble content from multiple sections
            assembled_content = assembler.assemble_page_content(page_sections, page)
            
            # Apply field constraints
            node_data = self._apply_field_constraints_v5(
                content_type=page.get("content_type", "page"),
                assembled_content=assembled_content,
                constraints=self._get_constraints_for_type(page.get("content_type", "page"), envelopes)
            )
            
            # Create the consolidated page
            node = self.drupal.create_node(page.get("content_type", "page"), node_data)
            
            if page.get("content_type") == "article":
                created_articles += 1
            else:
                created_pages += 1
                
            logger.info(f"[CONTENT] ✓ Created consolidated {page.get('content_type')} for '{page.get('title')}' with {len(page_sections)} sections")
            
        except Exception as e:
            logger.error(f"[CONTENT] ✗ Failed to migrate page '{page.get('title')}': {e}")
            errors.append(str(e))
    
    return {
        "created_pages": created_pages,
        "created_articles": created_articles,
        "total_created": created_pages + created_articles,
        "errors": errors,
        "detail": f"Consolidated content migration: {created_pages} pages, {created_articles} articles",
        "sections_processed": len(sections),
        "consolidation_successful": True
    }
```

## Phase 3: Improved Mapping Intelligence (Priority: HIGH)

### Change 3.1: Context-Aware Mapping

**File**: `agents/mapping_agent.py`
**Method**: `_create_mappings()` (enhanced)

**Current Issue**: Maps sections individually without page context
**Solution**: Page-centric mapping with section consolidation

```python
def _create_mappings_v5(self, blueprint: dict, envelopes: dict) -> list:
    """
    V5: Create page-centric mappings with section consolidation
    """
    mappings = []
    
    # Get section hierarchy
    sections = blueprint.get("sections", [])
    section_hierarchy = self._build_section_hierarchy(sections)
    
    # Map pages (primary entities)
    pages = blueprint.get("pages", [])
    for page in pages:
        # Find sections that belong to this page
        page_sections = self._find_page_sections(page, sections, section_hierarchy)
        
        # Create consolidated page mapping
        mapping = {
            "element_id": f"page_{page.get('path', '').replace('/', '_')}",
            "element_type": "consolidated_page",
            "source_type": "page_with_sections",
            "title": page.get("title"),
            "path": page.get("path"),
            "drupal_component": page.get("content_type", "page"),
            "sections_included": [s.get("index") for s in page_sections],
            "section_count": len(page_sections),
            "confidence": self._calculate_page_confidence(page, page_sections),
            "fidelity_estimate": self._estimate_page_fidelity(page, page_sections),
            "requires_review": len(page_sections) > 5,  # Complex pages need review
            "reasoning": f"Consolidated page with {len(page_sections)} sections",
            "compromises": self._identify_page_compromises(page, page_sections)
        }
        
        mappings.append(mapping)
    
    # Map standalone sections (if any)
    standalone_sections = self._find_standalone_sections(sections, section_hierarchy)
    for section in standalone_sections:
        mapping = self._create_section_mapping(section, envelopes)
        mappings.append(mapping)
    
    return mappings

def _calculate_page_confidence(self, page: dict, sections: list) -> float:
    """Calculate confidence score for page consolidation"""
    base_confidence = 0.9  # High confidence for page-based approach
    
    # Reduce confidence for complex pages
    if len(sections) > 5:
        base_confidence -= 0.1
    
    # Reduce confidence if sections are very diverse
    section_types = set(s.get("type") for s in sections)
    if len(section_types) > 3:
        base_confidence -= 0.1
    
    return max(0.5, base_confidence)
```

### Change 3.2: Fidelity Estimation Improvements

**File**: `agents/mapping_agent.py`
**Method**: `_estimate_page_fidelity()` (new)

```python
def _estimate_page_fidelity(self, page: dict, sections: list) -> float:
    """
    Estimate how well the consolidated page will match the source
    """
    base_fidelity = 0.8
    
    # Boost fidelity for pages with clear content structure
    content_sections = [s for s in sections if s.get("classification", {}).get("is_primary_content")]
    if content_sections:
        base_fidelity += 0.1
    
    # Reduce fidelity for pages with complex navigation sections
    nav_sections = [s for s in sections if s.get("type") == "navigation"]
    if len(nav_sections) > 2:
        base_fidelity -= 0.1
    
    # Boost fidelity for pages with substantial content
    total_content_length = sum(len(s.get("text_preview", "")) for s in sections)
    if total_content_length > 1000:
        base_fidelity += 0.1
    
    return min(1.0, max(0.3, base_fidelity))
```

## Phase 4: Enhanced Build Agent (Priority: HIGH)

### Change 4.1: Complete Page Building

**File**: `agents/build_agent.py`
**Method**: `_run_build_loop()` (enhanced)

**Current Issue**: Only builds homepage, incomplete page assembly
**Solution**: Build all pages with consolidated content

```python
def _run_build_loop_v5(self, blueprint: dict) -> dict:
    """
    V5: Build all pages with proper content consolidation
    """
    # Get mapping manifest with consolidated mappings
    mapping_manifest = self.get_mapping_manifest() or {}
    consolidated_mappings = [m for m in mapping_manifest.get("mappings", []) 
                           if m.get("element_type") == "consolidated_page"]
    
    built_pages = []
    errors = []
    
    logger.info(f"[BUILD] Building {len(consolidated_mappings)} consolidated pages")
    
    for mapping in consolidated_mappings:
        try:
            # Build consolidated page
            page_result = self._build_consolidated_page(mapping, blueprint)
            
            if page_result.get("success"):
                built_pages.append({
                    "title": mapping.get("title"),
                    "id": page_result.get("node_id"),
                    "path": mapping.get("path"),
                    "content_type": mapping.get("drupal_component"),
                    "sections_count": mapping.get("section_count", 0)
                })
                logger.info(f"[BUILD] ✓ Built consolidated page: {mapping.get('title')}")
            else:
                errors.append(f"Failed to build page: {mapping.get('title')}")
                
        except Exception as e:
            logger.error(f"[BUILD] ✗ Error building page {mapping.get('title')}: {e}")
            errors.append(str(e))
    
    # Store built pages
    self.memory.set("built_pages", built_pages)
    
    return {
        "built_pages": len(built_pages),
        "errors": errors,
        "consolidation_successful": len(built_pages) > 0,
        "detail": f"Built {len(built_pages)} consolidated pages"
    }

def _build_consolidated_page(self, mapping: dict, blueprint: dict) -> dict:
    """
    Build a single consolidated page from multiple sections
    """
    # Get sections for this page
    section_indices = mapping.get("sections_included", [])
    sections = blueprint.get("sections", [])
    page_sections = [sections[i] for i in section_indices if i < len(sections)]
    
    # Assemble content
    assembler = ContentAssembler()
    assembled_content = assembler.assemble_page_content(page_sections, mapping)
    
    # Validate content
    is_valid, error = self.validate_payload({
        "data": {
            "type": f"node--{mapping.get('drupal_component')}",
            "attributes": {
                "title": mapping.get("title"),
                "body": {"value": assembled_content["body_html"], "format": "full_html"},
                "status": True
            }
        }
    }, mapping.get("drupal_component"))
    
    if not is_valid:
        return {"success": False, "error": error}
    
    # Create the node
    try:
        node = self.drupal.create_node(mapping.get("drupal_component"), {
            "title": mapping.get("title"),
            "body": {"value": assembled_content["body_html"], "format": "full_html"},
            "status": True,
            "path": {"alias": mapping.get("path")} if mapping.get("path") != "/" else {}
        })
        
        return {
            "success": True,
            "node_id": node.get("id"),
            "sections_consolidated": len(page_sections)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}
```

## Phase 5: Visual Diff and Screenshot Fixes (Priority: MEDIUM)

### Change 5.1: Fix Playwright Installation

**File**: `agents/requirements.txt`
**Addition**: Add Playwright dependency

```txt
# Add to requirements.txt
playwright==1.40.0
```

**File**: `agents/Dockerfile`
**Enhancement**: Install Playwright browsers

```dockerfile
# Add after pip install
RUN pip install playwright
RUN playwright install chromium
RUN playwright install-deps
```

### Change 5.2: Enhanced Screenshot Logging

**File**: `agents/visual_diff_agent.py`
**Method**: `diff_page()` (enhanced)

**Current Issue**: Screenshots not shown in live agent log
**Solution**: Proper base64 encoding and logging integration

```python
async def diff_page_v5(self, source_url: str, drupal_path: str) -> dict:
    """
    V5: Enhanced visual diff with proper screenshot logging
    """
    if not self.playwright_available:
        await self.log_warning("Playwright not available", {"feature": "visual_diff"})
        return {"similarity": 0, "error": "Playwright not available"}
    
    try:
        # Capture screenshots
        source_screenshot = await self._capture_screenshot(source_url, "source")
        drupal_screenshot = await self._capture_screenshot(f"{self.drupal_base_url}{drupal_path}", "drupal")
        
        # Log screenshots to agent log with proper encoding
        if source_screenshot:
            await self.log_image(source_screenshot, f"Source: {source_url}", 200)
        
        if drupal_screenshot:
            await self.log_image(drupal_screenshot, f"Drupal: {drupal_path}", 200)
        
        # Calculate similarity
        similarity = await self._calculate_similarity(source_screenshot, drupal_screenshot)
        
        # Log comparison result
        await self.log_extended("visual_diff_result", {
            "source_url": source_url,
            "drupal_path": drupal_path,
            "similarity": similarity,
            "has_source_screenshot": bool(source_screenshot),
            "has_drupal_screenshot": bool(drupal_screenshot)
        })
        
        return {
            "similarity": similarity,
            "source_screenshot": source_screenshot,
            "drupal_screenshot": drupal_screenshot,
            "comparison_successful": True
        }
        
    except Exception as e:
        await self.log_error(f"Visual diff failed: {e}")
        return {"similarity": 0, "error": str(e)}

async def _capture_screenshot(self, url: str, label: str) -> str:
    """
    Capture screenshot and return as base64 data URL
    """
    try:
        page = await self.browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Wait for content to load
        await page.wait_for_timeout(2000)
        
        # Capture screenshot
        screenshot_bytes = await page.screenshot(full_page=False, type="png")
        
        # Convert to base64 data URL
        import base64
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        data_url = f"data:image/png;base64,{screenshot_b64}"
        
        await page.close()
        
        logger.info(f"[VISUAL_DIFF] Captured {label} screenshot: {len(screenshot_b64)} chars")
        return data_url
        
    except Exception as e:
        logger.error(f"[VISUAL_DIFF] Failed to capture {label} screenshot: {e}")
        return None
```

### Change 5.3: Fix Screenshot Display in UI

**File**: `agents/base_agent.py`
**Method**: `log_image()` (enhanced)

**Current Issue**: Screenshots not properly displayed in live log
**Solution**: Ensure proper data URL format and UI integration

```python
async def log_image(self, image_data: str, caption: str, max_width: int = 300):
    """
    Log an image to the agent stream with proper formatting
    """
    # Ensure proper data URL format
    if not image_data.startswith("data:image/"):
        logger.warning(f"[{self.name}] Invalid image data format for: {caption}")
        return
    
    # Create image log entry
    log_entry = {
        "agent": self.name,
        "type": "image",
        "timestamp": time.time(),
        "caption": caption,
        "image_data": image_data,
        "max_width": max_width,
        "format": "data_url"
    }
    
    # Send to orchestrator for UI display
    if hasattr(self, 'orchestrator') and self.orchestrator:
        await self.orchestrator.stream_event(log_entry)
    
    # Also log to console for debugging
    logger.info(f"[{self.name}] 📷 Image logged: {caption} ({len(image_data)} chars)")
```

## Phase 6: Quality Assurance Improvements (Priority: MEDIUM)

### Change 6.1: Content Completeness Validation

**File**: `agents/qa_agent.py`
**Method**: `_run_qa_checks()` (enhanced)

**Addition**: Validate content consolidation success

```python
def _run_qa_checks_v5(self) -> dict:
    """
    V5: Enhanced QA with content consolidation validation
    """
    checks = []
    passed = 0
    issues = 0
    
    # Existing checks...
    
    # NEW: Content consolidation validation
    try:
        blueprint = self.memory.get_blueprint()
        built_pages = self.memory.get_or_default("built_pages", [])
        
        expected_pages = len(blueprint.get("pages", []))
        actual_pages = len(built_pages)
        
        consolidation_ratio = actual_pages / max(expected_pages, 1)
        
        if consolidation_ratio >= 0.8:  # At least 80% of pages built
            checks.append({
                "check": "Content Consolidation",
                "status": "pass",
                "detail": f"{actual_pages}/{expected_pages} pages successfully consolidated"
            })
            passed += 1
        else:
            checks.append({
                "check": "Content Consolidation",
                "status": "fail",
                "detail": f"Only {actual_pages}/{expected_pages} pages built - consolidation incomplete"
            })
            issues += 1
            
        # Check section consolidation
        total_sections_consolidated = sum(p.get("sections_count", 0) for p in built_pages)
        expected_sections = len(blueprint.get("sections", []))
        
        if total_sections_consolidated >= expected_sections * 0.8:
            checks.append({
                "check": "Section Integration",
                "status": "pass",
                "detail": f"{total_sections_consolidated} sections integrated into pages"
            })
            passed += 1
        else:
            checks.append({
                "check": "Section Integration",
                "status": "warn",
                "detail": f"Only {total_sections_consolidated}/{expected_sections} sections integrated"
            })
            
    except Exception as e:
        checks.append({
            "check": "Content Consolidation",
            "status": "error",
            "detail": f"Validation failed: {e}"
        })
        issues += 1
    
    # Continue with existing QA logic...
    return self._compile_qa_results(checks, passed, issues)
```

## Phase 7: Configuration and Environment (Priority: LOW)

### Change 7.1: Version 5 Feature Flags

**File**: `agents/config.py`
**Addition**: V5 configuration options

```python
# V5 Configuration
V5_FEATURES = {
    "ENABLE_CONTENT_CONSOLIDATION": True,
    "ENABLE_SMART_SECTION_CLASSIFICATION": True,
    "ENABLE_PAGE_CENTRIC_MAPPING": True,
    "ENABLE_ENHANCED_VISUAL_DIFF": True,
    "CONSOLIDATION_CONFIDENCE_THRESHOLD": 0.7,
    "MAX_SECTIONS_PER_PAGE": 10,
    "REQUIRE_REVIEW_FOR_COMPLEX_PAGES": True
}

# Content Assembly Configuration
CONTENT_ASSEMBLY = {
    "PRESERVE_SECTION_STRUCTURE": True,
    "ADD_SECTION_WRAPPERS": True,
    "CLEAN_HTML_CONTENT": True,
    "MAX_CONTENT_LENGTH": 100000,
    "SECTION_SEPARATOR": "\n\n"
}
```

### Change 7.2: Docker Environment Updates

**File**: `docker-compose.yml`
**Enhancement**: Add Playwright support

```yaml
services:
  drupalmind-agents:
    build: ./agents
    environment:
      - PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
    volumes:
      - playwright-cache:/ms-playwright
    # ... existing configuration

volumes:
  playwright-cache:
    driver: local
```

---

## Implementation Timeline

### Week 1: Core Fixes (Critical Priority)
- [ ] Implement enhanced section classification (Change 1.1, 1.2)
- [ ] Create content assembly engine (Change 2.1)
- [ ] Rewrite content migration logic (Change 2.2)

### Week 2: Mapping and Building (High Priority)
- [ ] Implement context-aware mapping (Change 3.1, 3.2)
- [ ] Enhance build agent for complete pages (Change 4.1)
- [ ] Add content consolidation validation

### Week 3: Visual Improvements (Medium Priority)
- [ ] Fix Playwright installation (Change 5.1)
- [ ] Implement enhanced screenshot logging (Change 5.2, 5.3)
- [ ] Add QA improvements (Change 6.1)

### Week 4: Testing and Refinement (Low Priority)
- [ ] Add configuration options (Change 7.1, 7.2)
- [ ] Comprehensive testing
- [ ] Performance optimization
- [ ] Documentation updates

---

## Success Metrics

### Before V5 (Current Issues):
- ❌ Only 1 page built out of 10 expected
- ❌ 0 content items migrated
- ❌ All sections classified as "navigation"
- ❌ Content split into separate articles
- ❌ No visual diff feedback

### After V5 (Expected Results):
- ✅ 80%+ of expected pages built successfully
- ✅ Content consolidated into cohesive pages
- ✅ Intelligent section classification
- ✅ Visual diff with screenshot comparison
- ✅ Quality validation for content completeness

---

## Risk Mitigation

### Risk 1: Complex Page Structures
**Mitigation**: Implement confidence thresholds and human review triggers for complex pages

### Risk 2: Performance Impact
**Mitigation**: Add caching for section analysis and limit processing to essential sections

### Risk 3: Backward Compatibility
**Mitigation**: Use feature flags to enable V5 features gradually, maintain V4 fallback

### Risk 4: Playwright Dependencies
**Mitigation**: Graceful degradation when Playwright unavailable, clear error messaging

---

## Testing Strategy

### Unit Tests
- Section classification accuracy
- Content assembly logic
- Mapping confidence calculations
- HTML validation and sanitization

### Integration Tests
- End-to-end migration with complex websites
- Visual diff functionality
- Content consolidation validation
- Error handling and recovery

### Performance Tests
- Large website migration (100+ sections)
- Memory usage during content assembly
- Screenshot capture performance
- Database query optimization

---

This comprehensive plan addresses all identified issues and provides a clear roadmap for implementing Version 5 improvements to fix the content splitting problems in DrupalMind.