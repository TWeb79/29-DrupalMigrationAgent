"""
DrupalMind — AnalyzerAgent
Scrapes source URL, extracts layout/content/design tokens,
produces a Site Blueprint stored in shared memory.
"""
import json
import re
import asyncio
import logging
import os
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from base_agent import BaseAgent

# Configure logging for AnalyzerAgent
logger = logging.getLogger("drupalmind.analyzer")


class AnalyzerAgent(BaseAgent):
    def __init__(self):
        super().__init__("analyzer", "AnalyzerAgent")

    # ── Entry point ───────────────────────────────────────────

    async def analyze(self, source: str, mode: str = "url") -> dict:
        """
        Analyze the source (URL or description) and return a Site Blueprint.
        mode: "url" | "description"
        """
        logger.info(f"══════════════════════════════════════════════════════════════")
        logger.info(f"║ ANALYZER AGENT START")
        logger.info(f"║ Mode: {mode} | Source: {source[:100]}...")
        logger.info(f"══════════════════════════════════════════════════════════════")
        await self.log("Starting analysis...", detail=f"Source: {source}")
        
        # Log analysis start with extended event
        await self.log_extended("analysis_start", {
            "source": source[:200],
            "mode": mode,
        })

        if mode == "description":
            logger.info("Using LLM to analyze description...")
            blueprint = await asyncio.to_thread(self._analyze_description, source)
        else:
            logger.info("Scraping URL for analysis...")
            blueprint = await asyncio.to_thread(self._analyze_url, source)

        # Log extracted content elements in detail
        pages = blueprint.get("pages", [])
        sections = blueprint.get("sections", [])
        navigation = blueprint.get("navigation", [])
        design_tokens = blueprint.get("design_tokens", {})
        
        await self.log_data("content_elements", {
            "pages": [{"title": p.get("title"), "path": p.get("path"), "content_type": p.get("content_type")} for p in pages],
            "sections": [{"type": s.get("type"), "heading": s.get("heading", "")[:50], "has_images": s.get("has_images"), "has_links": s.get("has_links")} for s in sections],
            "navigation": [{"title": n.get("title"), "path": n.get("path")} for n in navigation[:10]],
            "design_tokens": {
                "colors": design_tokens.get("colors", [])[:5],
                "fonts": design_tokens.get("fonts", [])[:3],
                "primary_color": design_tokens.get("primary_color"),
            },
            "counts": {
                "total_pages": len(pages),
                "total_sections": len(sections),
                "nav_items": len(navigation),
                "colors_found": len(design_tokens.get("colors", [])),
                "fonts_found": len(design_tokens.get("fonts", [])),
            }
        }, summary=f"Found {len(pages)} pages, {len(sections)} sections, {len(navigation)} nav items")
        
        # Log section breakdown by type
        section_types = {}
        for s in sections:
            t = s.get("type", "unknown")
            section_types[t] = section_types.get(t, 0) + 1
        
        await self.log_extended("sections_breakdown", {
            "section_types": section_types,
            "total": len(sections),
        })
        
        # Log each section in detail
        for i, section in enumerate(sections[:10]):
            await self.log_data("section", {
                "index": i,
                "type": section.get("type"),
                "heading": section.get("heading", "")[:100],
                "text_preview": section.get("text_preview", "")[:150],
                "has_images": section.get("has_images", False),
                "has_links": section.get("has_links", False),
                "has_form": section.get("has_form", False),
                "drupal_component": section.get("drupal_component", ""),
            }, summary=f"Section {i}: {section.get('type')} - {section.get('heading', 'No heading')[:30]}")
        
        # Capture reference screenshots for key pages
        if blueprint.get("source_url"):
            await self.log("Capturing reference screenshots...")
            screenshots = await self._capture_reference_screenshots(blueprint)
            blueprint["reference_screenshots"] = screenshots
            
            # Log screenshot results
            await self.log_extended("screenshots_captured", {
                "home_captured": screenshots.get("home") is not None,
                "pages_captured": len(screenshots.get("pages", [])),
            })
            
            # Log each screenshot as an image event
            if screenshots.get("home"):
                await self.log_image(
                    screenshots["home"], 
                    "Homepage reference screenshot", 
                    100
                )

        self.memory.set_blueprint(blueprint)
        
        # Log final blueprint summary
        await self.log_extended("analysis_complete", {
            "source_url": blueprint.get("source_url"),
            "title": blueprint.get("title"),
            "pages_count": len(pages),
            "sections_count": len(sections),
            "content_types_needed": blueprint.get("content_types_needed", []),
            "has_seo": bool(blueprint.get("seo")),
        })
        
        # Log metrics
        await self.log_metric("pages_found", len(pages), "", "analysis")
        await self.log_metric("sections_found", len(sections), "", "analysis")
        await self.log_metric("nav_items_found", len(navigation), "", "analysis")
        
        await self.log_done(
            f"Site Blueprint ready — {len(pages)} pages, "
            f"{len(sections)} sections detected",
            detail=f"Blueprint saved to memory"
        )
        return blueprint

    # ── Screenshot capture (v2) ─────────────────────────────────

    async def _capture_reference_screenshots(self, blueprint: dict) -> dict:
        """Capture reference screenshots of key pages for VisualDiffAgent."""
        screenshots = {"home": None, "pages": []}
        source_url = blueprint.get("source_url", "")
        
        if not source_url:
            return screenshots
        
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("Playwright not installed, skipping screenshots")
            self.memory.set("screenshot_error", "Playwright not installed")
            return screenshots
        
        try:
            import base64
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                
                # Capture homepage
                try:
                    page.goto(source_url, wait_until="domcontentloaded", timeout=10000)
                    
                    # Get screenshot as base64
                    home_screenshot_b64 = page.screenshot(full_page=False, type="png")
                    home_screenshot_base64 = base64.b64encode(home_screenshot_b64).decode('utf-8')
                    screenshots["home"] = f"data:image/png;base64,{home_screenshot_base64}"
                    logger.info(f"Captured homepage screenshot as base64 ({len(home_screenshot_base64)} chars)")
                except Exception as e:
                    logger.warning(f"Failed to capture homepage screenshot: {e}")
                
                # Capture key pages
                for page_info in blueprint.get("pages", [])[:5]:
                    page_url = page_info.get("url")
                    if page_url and page_url != source_url:
                        try:
                            page.goto(page_url, wait_until="domcontentloaded", timeout=10000)
                            
                            page_b64 = page.screenshot(full_page=False, type="png")
                            page_base64 = base64.b64encode(page_b64).decode('utf-8')
                            
                            screenshots["pages"].append({
                                "path": page_info.get("path"),
                                "screenshot": f"data:image/png;base64,{page_base64}"
                            })
                        except Exception as e:
                            logger.warning(f"Failed to capture screenshot for {page_url}: {e}")
                
                browser.close()
        except Exception as e:
            logger.warning(f"Screenshot capture failed: {e}")
        
        return screenshots

    # ── URL analysis ──────────────────────────────────────────

    def _analyze_url(self, url: str) -> dict:
        headers = {
            "User-Agent": "Mozilla/5.0 (DrupalMind/1.0 +https://github.com/drupalmind)"
        }
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            return self._empty_blueprint(url, error=str(e))

        blueprint = {
            "source_url": url,
            "source_mode": "url",
            "title": self._extract_title(soup),
            "description": self._extract_meta_description(soup),
            "design_tokens": self._extract_design_tokens(r.text, soup),
            "navigation": self._extract_navigation(soup, url),
            "sections": self._extract_sections(soup),
            "pages": self._discover_pages(soup, url),
            "content_types_needed": [],
            "seo": self._extract_seo(soup),
            "raw_html_sample": r.text[:3000],
        }

        blueprint["content_types_needed"] = self._infer_content_types(blueprint)
        return blueprint

    def _analyze_description(self, description: str) -> dict:
        """Use the LLM to turn a text description into a blueprint."""
        messages = [
            {
                "role": "user",
                "content": (
                    f"A user wants to build this website in Drupal:\n\n{description}\n\n"
                    "Return a JSON site blueprint with these fields:\n"
                    "title, description, navigation (list of menu items with title+url),\n"
                    "sections (list of section objects with: type, title, content, layout),\n"
                    "pages (list of pages with: title, path, content_type, sections),\n"
                    "design_tokens (colors: list of hex, fonts: list of names),\n"
                    "content_types_needed (list of drupal content type names).\n"
                    "Return ONLY valid JSON, no explanation."
                ),
            }
        ]
        raw = self.client.messages.create(
            model=self.MODEL,
            max_tokens=2048,
            messages=messages,
        )
        text = raw.content[0].text.strip()
        # Strip markdown code fences if present
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
        try:
            blueprint = json.loads(text)
            blueprint["source_mode"] = "description"
            blueprint["source_url"] = ""
            return blueprint
        except Exception:
            return self._empty_blueprint("", description=description)

    # ── Extraction helpers ────────────────────────────────────

    def _extract_title(self, soup: BeautifulSoup) -> str:
        og = soup.find("meta", property="og:title")
        if og:
            return og.get("content", "")
        if soup.title:
            return soup.title.string or ""
        h1 = soup.find("h1")
        return h1.get_text(strip=True) if h1 else "Untitled Site"

    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        og = soup.find("meta", property="og:description")
        if og:
            return og.get("content", "")
        meta = soup.find("meta", attrs={"name": "description"})
        return meta.get("content", "") if meta else ""

    def _extract_design_tokens(self, html: str, soup: BeautifulSoup) -> dict:
        # Extract colors from inline styles and style tags
        color_pattern = re.compile(r'#([0-9a-fA-F]{3,6})\b')
        colors = list(dict.fromkeys(color_pattern.findall(html)))[:20]
        colors = ["#" + c for c in colors]

        # Extract font families
        font_pattern = re.compile(r"font-family\s*:\s*([^;\"']+)", re.IGNORECASE)
        fonts_raw = font_pattern.findall(html)
        fonts = []
        for f in fonts_raw:
            for name in f.split(","):
                name = name.strip().strip("'\"")
                if name and name not in fonts:
                    fonts.append(name)
        fonts = fonts[:5]

        # Check for Google Fonts link
        google_fonts = []
        for link in soup.find_all("link", href=True):
            href = link["href"]
            if "fonts.googleapis.com" in href:
                family_match = re.findall(r"family=([^&]+)", href)
                for f in family_match:
                    google_fonts.append(f.split(":")[0].replace("+", " "))

        return {
            "colors": colors[:10],
            "fonts": list(set(fonts + google_fonts))[:6],
            "primary_color": colors[0] if colors else "#1a1a2e",
            "secondary_color": colors[1] if len(colors) > 1 else "#e94560",
        }

    def _extract_navigation(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        nav_items = []
        nav = soup.find("nav") or soup.find(attrs={"role": "navigation"})
        if nav:
            for a in nav.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                if text and not href.startswith(("javascript:", "mailto:", "tel:")):
                    abs_href = urljoin(base_url, href)
                    if urlparse(abs_href).netloc == urlparse(base_url).netloc:
                        nav_items.append({"title": text, "url": abs_href, "path": urlparse(abs_href).path})
        return nav_items[:12]

    def _extract_sections(self, soup: BeautifulSoup) -> list[dict]:
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
            
            # Enhanced classification with position awareness
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

    def _classify_section_v5(self, tag: str, classes: str, id_attr: str, text: str, position: int, total_sections: int) -> dict:
        """
        V5: Enhanced section classification with content hierarchy and semantic analysis
        Returns: {type: str, confidence: float, is_primary_content: bool, consolidation_group: str}
        """
        
        # 1. Position-based classification
        likely_header = position == 0
        likely_footer = position == total_sections - 1
        likely_content = not (likely_header or likely_footer)
        
        # 2. Content volume analysis
        content_density = len(text.strip()) / max(len(text), 1)
        has_substantial_content = len(text.strip()) > 200
        
        # 3. Semantic keyword analysis
        navigation_keywords = ["nav", "menu", "header", "footer", "sidebar"]
        content_keywords = ["article", "main", "content", "section", "post", "story", "about", "feature", "service"]
        
        keyword_score = 0
        text_lower = text.lower()
        classes_lower = classes.lower()
        id_lower = id_attr.lower()
        combined_lower = f"{text_lower} {classes_lower} {id_lower}"
        
        for kw in navigation_keywords:
            if kw in combined_lower:
                keyword_score -= 0.3
        
        for kw in content_keywords:
            if kw in combined_lower:
                keyword_score += 0.3
        
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
        
        # Apply classification rules
        
        # Hero/banner detection (highest priority)
        if any(w in combined_lower for w in ["hero", "banner", "jumbotron", "intro"]):
            classification["type"] = "hero"
            classification["confidence"] = 0.9
            classification["is_primary_content"] = True
            classification["reasoning"].append("Detected hero/banner pattern")
        
        # Navigation detection
        elif is_navigation_element or any(w in combined_lower for w in ["nav", "menu", "navigation"]):
            classification["type"] = "navigation"
            classification["confidence"] = min(0.9, 0.6 + keyword_score)
            classification["consolidation_group"] = "navigation"
            classification["reasoning"].append("Navigation element detected")
        
        # Header (first section) - likely hero or navigation
        elif likely_header and has_substantial_content:
            classification["type"] = "hero"
            classification["confidence"] = 0.7
            classification["is_primary_content"] = True
            classification["reasoning"].append("First section with substantial content - classified as hero")
        
        # Footer (last section)
        elif likely_footer:
            classification["type"] = "footer"
            classification["confidence"] = 0.7
            classification["consolidation_group"] = "navigation"
            classification["reasoning"].append("Last section - classified as footer")
        
        # Content section based on semantic HTML
        elif is_semantic_content and has_substantial_content:
            classification["type"] = "content"
            classification["confidence"] = 0.8
            classification["is_primary_content"] = True
            classification["reasoning"].append("Semantic content element with substantial text")
        
        # Content type specific detection
        elif any(w in combined_lower for w in ["feature", "service", "card", "grid"]):
            classification["type"] = "features"
            classification["confidence"] = 0.8
            classification["is_primary_content"] = True
            classification["reasoning"].append("Features section detected")
        elif any(w in combined_lower for w in ["about", "mission", "vision", "story"]):
            classification["type"] = "about"
            classification["confidence"] = 0.8
            classification["is_primary_content"] = True
            classification["reasoning"].append("About section detected")
        elif any(w in combined_lower for w in ["blog", "news", "article", "post"]):
            classification["type"] = "blog"
            classification["confidence"] = 0.8
            classification["reasoning"].append("Blog section detected")
        elif any(w in combined_lower for w in ["contact", "form", "reach", "touch"]):
            classification["type"] = "contact"
            classification["confidence"] = 0.8
            classification["reasoning"].append("Contact section detected")
        elif any(w in combined_lower for w in ["testimonial", "review", "quote"]):
            classification["type"] = "testimonials"
            classification["confidence"] = 0.8
            classification["reasoning"].append("Testimonials section detected")
        elif any(w in combined_lower for w in ["team", "staff", "people", "member"]):
            classification["type"] = "team"
            classification["confidence"] = 0.8
            classification["reasoning"].append("Team section detected")
        elif any(w in combined_lower for w in ["pricing", "plan", "package"]):
            classification["type"] = "pricing"
            classification["confidence"] = 0.8
            classification["reasoning"].append("Pricing section detected")
        
        # Default: content section with content-based confidence
        else:
            classification["confidence"] = 0.6 + keyword_score
            if has_substantial_content:
                classification["is_primary_content"] = True
                classification["reasoning"].append("Substantial content section")
        
        # Ensure confidence is in valid range
        classification["confidence"] = max(0.3, min(1.0, classification["confidence"]))
        
        return classification

    def _extract_structured_content(self, tag) -> dict:
        """
        V5: Extract structured content elements from a section
        """
        # Get full HTML content (preserving structure)
        full_html = str(tag)
        
        # Get clean text content (full, not truncated)
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
        """Extract table structure and data"""
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
        """Extract list structure and items"""
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
        """Calculate content complexity score (0-1)"""
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
        """Detect programming language from code block"""
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
        V5: Enhanced mapping considering structured content complexity
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
        if structured_content.get("has_tables"):
            base_component += " + table formatting"
        
        if structured_content.get("has_media"):
            base_component += " + media gallery"
        
        if structured_content.get("has_code"):
            base_component += " + code highlighting"
        
        if structured_content.get("complexity_score", 0) > 0.7:
            base_component += " + custom layout"
        
        return base_component

    def _map_to_drupal_component(self, section_type: str) -> str:
        mapping = {
            "hero": "page with full-width body content + image field",
            "navigation": "Drupal menu block",
            "features": "view or article nodes with card display",
            "about": "basic page with text and image",
            "blog": "views block showing article nodes",
            "contact": "Drupal contact form",
            "footer": "footer menu + custom block",
            "testimonials": "article nodes with testimonial content type",
            "team": "article nodes with team member content type",
            "pricing": "basic page with pricing table HTML",
            "content": "basic page",
        }
        return mapping.get(section_type, "basic page")

    def _discover_pages(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        pages = [{"title": "Home", "path": "/", "content_type": "page", "is_front": True}]
        seen_paths = {"/"}

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if not text or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            abs_href = urljoin(base_url, href)
            parsed = urlparse(abs_href)
            if parsed.netloc != urlparse(base_url).netloc:
                continue
            path = parsed.path or "/"
            if path in seen_paths:
                continue
            seen_paths.add(path)
            pages.append({
                "title": text,
                "path": path,
                "url": abs_href,
                "content_type": self._infer_page_content_type(path, text),
                "is_front": False,
            })
            if len(pages) >= 10:
                break
        return pages

    def _infer_page_content_type(self, path: str, title: str) -> str:
        combined = f"{path} {title}".lower()
        if any(w in combined for w in ["blog", "news", "article", "post"]):
            return "article"
        return "page"

    def _infer_content_types(self, blueprint: dict) -> list[str]:
        types = set(["page"])
        for page in blueprint.get("pages", []):
            types.add(page.get("content_type", "page"))
        for section in blueprint.get("sections", []):
            stype = section.get("type", "")
            if stype in ("blog", "team", "testimonials"):
                types.add("article")
        return list(types)

    def _extract_seo(self, soup: BeautifulSoup) -> dict:
        canonical = ""
        link = soup.find("link", rel="canonical")
        if link:
            canonical = link.get("href", "")
        return {
            "canonical": canonical,
            "title": self._extract_title(soup),
            "description": self._extract_meta_description(soup),
        }

    def _empty_blueprint(self, url: str, error: str = "", description: str = "") -> dict:
        return {
            "source_url": url,
            "source_mode": "url",
            "title": "Unknown Site",
            "description": description,
            "error": error,
            "design_tokens": {"colors": ["#1a1a2e", "#e94560"], "fonts": ["sans-serif"], "primary_color": "#1a1a2e", "secondary_color": "#e94560"},
            "navigation": [],
            "sections": [],
            "pages": [{"title": "Home", "path": "/", "content_type": "page", "is_front": True}],
            "content_types_needed": ["page"],
            "seo": {},
        }
