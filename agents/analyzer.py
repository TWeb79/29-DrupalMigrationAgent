"""
DrupalMind — AnalyzerAgent
Scrapes source URL, extracts layout/content/design tokens,
produces a Site Blueprint stored in shared memory.
"""
import json
import re
import asyncio
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from base_agent import BaseAgent


class AnalyzerAgent(BaseAgent):
    def __init__(self):
        super().__init__("analyzer", "AnalyzerAgent")

    # ── Entry point ───────────────────────────────────────────

    async def analyze(self, source: str, mode: str = "url") -> dict:
        """
        Analyze the source (URL or description) and return a Site Blueprint.
        mode: "url" | "description"
        """
        await self.log("Starting analysis...", detail=f"Source: {source}")

        if mode == "description":
            blueprint = await asyncio.to_thread(self._analyze_description, source)
        else:
            blueprint = await asyncio.to_thread(self._analyze_url, source)

        self.memory.set_blueprint(blueprint)
        await self.log_done(
            f"Site Blueprint ready — {len(blueprint.get('pages', []))} pages, "
            f"{len(blueprint.get('sections', []))} sections detected",
            detail=f"Blueprint saved to memory"
        )
        return blueprint

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
        sections = []
        section_tags = soup.find_all(["section", "article", "header", "footer", "main", "aside"])
        for i, tag in enumerate(section_tags[:15]):
            heading = tag.find(re.compile(r"^h[1-6]$"))
            heading_text = heading.get_text(strip=True) if heading else ""
            text_content = tag.get_text(separator=" ", strip=True)[:400]

            # Determine section type
            classes = " ".join(tag.get("class", []))
            id_attr = tag.get("id", "")
            section_type = self._classify_section(tag.name, classes, id_attr, text_content)

            sections.append({
                "index": i,
                "type": section_type,
                "tag": tag.name,
                "heading": heading_text,
                "text_preview": text_content[:200],
                "has_images": bool(tag.find("img")),
                "has_links": bool(tag.find("a")),
                "has_form": bool(tag.find("form")),
                "drupal_component": self._map_to_drupal_component(section_type),
            })
        return sections

    def _classify_section(self, tag: str, classes: str, id_attr: str, text: str) -> str:
        combined = f"{tag} {classes} {id_attr} {text}".lower()
        if any(w in combined for w in ["hero", "banner", "jumbotron", "intro"]):
            return "hero"
        if any(w in combined for w in ["nav", "menu", "navigation", "header"]):
            return "navigation"
        if any(w in combined for w in ["feature", "service", "card", "grid"]):
            return "features"
        if any(w in combined for w in ["about", "mission", "vision", "story"]):
            return "about"
        if any(w in combined for w in ["blog", "news", "article", "post"]):
            return "blog"
        if any(w in combined for w in ["contact", "form", "reach", "touch"]):
            return "contact"
        if any(w in combined for w in ["footer", "copyright"]):
            return "footer"
        if any(w in combined for w in ["testimonial", "review", "quote"]):
            return "testimonials"
        if any(w in combined for w in ["team", "staff", "people", "member"]):
            return "team"
        if any(w in combined for w in ["pricing", "plan", "package"]):
            return "pricing"
        if tag == "header":
            return "header"
        if tag == "footer":
            return "footer"
        return "content"

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
