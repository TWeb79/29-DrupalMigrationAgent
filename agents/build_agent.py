"""
DrupalMind — BuildAgent
Constructs Drupal pages based on the Site Blueprint and Component Knowledge Base.
Uses the LLM tool-use loop to reason about what to build and how.
Implements payload validation, micro-loop (5 iterations per component), and meso-loop (page refinement).
"""
import json
import asyncio
import logging
import re
from typing import Any, Optional
from base_agent import BaseAgent
from memory import memory as shared_memory
from bs4 import BeautifulSoup

# Configure logging for BuildAgent
logger = logging.getLogger("drupalmind.build")

# Payload validation constants
PAYLOAD_VALIDATOR_ENABLED = True
FORBIDDEN_HTML_PATTERNS = [
    r'<script',
    r'<iframe',
    r'onerror=',
    r'onclick=',
    r'onload=',
]
FORBIDDEN_STYLE_PATTERNS = [
    r'style\s*[=:]\s*["\']?\s*position\s*:\s*fixed',
    r'style\s*[=:]\s*["\']?\s*z-index\s*:\s*9999',
]
MAX_HTML_LENGTH = 50000


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
        if not html_content:
            return ""
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove potentially unsafe elements
        unsafe_tags = ['script', 'style', 'iframe', 'object', 'embed']
        for tag in unsafe_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Return cleaned HTML with preserved structure
        return str(soup)
    
    def _enhance_table_html(self, table) -> str:
        """Enhance table HTML for better Drupal compatibility"""
        soup = BeautifulSoup("", 'html.parser')
        
        # Add responsive table wrapper
        if table.get('class'):
            table['class'] = table.get('class', []) + ['drupal-table', 'responsive-table']
        else:
            table['class'] = ['drupal-table', 'responsive-table']
        
        # Ensure proper table structure
        if not table.find('thead') and table.find('tr'):
            # Convert first row to header if no thead exists
            first_row = table.find('tr')
            if first_row:
                thead = soup.new_tag('thead')
                tbody = soup.new_tag('tbody')
                
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
        if list_elem.get('class'):
            list_elem['class'] = list_elem.get('class', []) + ['drupal-list']
        else:
            list_elem['class'] = ['drupal-list']
        return str(list_elem)
    
    def _enhance_image_html(self, img) -> str:
        """Enhance image HTML with responsive attributes"""
        if img.get('class'):
            img['class'] = img.get('class', []) + ['drupal-image', 'responsive-image']
        else:
            img['class'] = ['drupal-image', 'responsive-image']
        
        # Add loading attribute for performance
        img['loading'] = 'lazy'
        
        # Ensure alt text exists
        if not img.get('alt'):
            img['alt'] = 'Image'
        
        return str(img)
    
    def _enhance_code_html(self, code) -> str:
        """Enhance code blocks with syntax highlighting classes"""
        if code.get('class'):
            code['class'] = code.get('class', []) + ['drupal-code']
        else:
            code['class'] = ['drupal-code']
        return str(code)
    
    def _enhance_blockquote_html(self, blockquote) -> str:
        """Enhance blockquote HTML"""
        if blockquote.get('class'):
            blockquote['class'] = blockquote.get('class', []) + ['drupal-blockquote']
        else:
            blockquote['class'] = ['drupal-blockquote']
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
    
    def _find_hero_section(self, sections: list) -> Optional[dict]:
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


SYSTEM_PROMPT = """You are the BuildAgent for DrupalMind, an AI system that builds Drupal websites.

Your job is to build a Drupal site based on the Site Blueprint and Mapping Manifest.

PROCESS:
1. Read the site blueprint from memory (key: "site_blueprint")
2. Read the mapping manifest (key: "mapping_manifest") - contains component mappings with confidence scores
3. Read available component knowledge (key: "capability_envelopes/*")
4. For each page in the blueprint, create it in Drupal using the appropriate API calls
5. Use payload validator before sending any content to Drupal
6. Create navigation menu items for the main menu
7. Report what you've built

RULES:
- Create ONE page per task. Don't try to do everything at once.
- Use "basic_html" format for body fields unless you have full_html available
- For hero sections, include a prominent heading in the body HTML
- For navigation, use the "main" menu
- Always set status: true to publish content
- Store a record of what you built in memory under key "built_pages"
- ALWAYS validate payloads before sending to Drupal

IMPORTANT: Use proven component templates from the template library when available.
The TemplateLibrary has been trained on thousands of Drupal builds and knows what works.
Only generate custom HTML if no template matches the section type.

Available templates:
- hero_basic: Hero sections with heading, tagline, CTA
- features_grid: Feature grids with 3+ columns
- blog_post: Blog articles with metadata
- testimonial_card: Testimonial quotes
- team_member: Team member profiles
- content_block: Generic content sections
- features: Feature list with icons

Use these templates instead of improvising HTML!

AVAILABLE CONTENT TYPES: article (for blog/news), page (for static pages)

When creating page body content, write clean HTML including headings, paragraphs, and structure.
Make the content match what would be on the source page.
"""


class BuildAgent(BaseAgent):
    """Builds Drupal sites with payload validation and refinement loops."""
    
    # Configuration constants
    MAX_MICRO_ITERATIONS = 5
    MAX_MESO_ITERATIONS = 3
    SIMILARITY_THRESHOLD = 0.85
    MIN_SIMILARITY_THRESHOLD = 0.30  # Minimum threshold - below this, page needs major rework

    def __init__(self):
        super().__init__("build", "BuildAgent")

    # ── Payload Validator ────────────────────────────────────────
    
    def validate_payload(self, payload: dict, component: str) -> tuple[bool, str]:
        """
        Validate JSON:API payload before sending to Drupal.
        Returns (is_valid, error_message).
        """
        if not PAYLOAD_VALIDATOR_ENABLED:
            return True, ""
        
        # Check attributes
        attrs = payload.get("data", {}).get("attributes", {})
        
        # Validate body field
        body = attrs.get("body", {})
        if isinstance(body, dict):
            body_value = body.get("value", "")
        else:
            body_value = str(body)
        
        # Check for forbidden HTML
        for pattern in FORBIDDEN_HTML_PATTERNS:
            if re.search(pattern, body_value, re.IGNORECASE):
                return False, f"Forbidden HTML pattern found: {pattern}"
        
        # Check for forbidden inline styles
        for pattern in FORBIDDEN_STYLE_PATTERNS:
            if re.search(pattern, body_value, re.IGNORECASE):
                return False, f"Forbidden inline style found: {pattern}"
        
        # Check HTML length
        if len(body_value) > MAX_HTML_LENGTH:
            return False, f"Body content exceeds max length ({len(body_value)} > {MAX_HTML_LENGTH})"
        
        # Check for unknown components
        known_components = ["page", "article", "contact"]
        if component not in known_components:
            logger.warning(f"Using non-standard component: {component}")
        
        return True, ""

    def sanitize_html(self, html: str) -> str:
        """Sanitize HTML content to meet Drupal standards."""
        # Remove script tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
        # Remove iframe tags
        html = re.sub(r'<iframe[^>]*>.*?</iframe>', '', html, flags=re.IGNORECASE | re.DOTALL)
        # Remove event handlers
        html = re.sub(r'\bon\w+\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)
        return html

    # ── Mapping Manifest Reader ───────────────────────────────────
    
    def get_mapping_for_element(self, element_id: str) -> Optional[dict]:
        """Get the mapping for a specific element from the manifest."""
        return shared_memory.get_mapping_for_element(element_id)

    def get_mapping_manifest(self) -> dict:
        """Get the full mapping manifest."""
        return shared_memory.get_mapping_manifest() or {}

    # ── Micro-Loop: Component Refinement ─────────────────────────
    
    async def refine_component(self, component_scope: str, source_url: str, drupal_path: str) -> dict:
        """
        Micro-loop: Refine a single component placement.
        Up to MAX_MICRO_ITERATIONS iterations until similarity threshold met.
        """
        from visual_diff_agent import VisualDiffAgent
        
        visualdiff = VisualDiffAgent()
        await visualdiff.initialize()
        
        best_result = None
        best_similarity = 0
        
        for iteration in range(self.MAX_MICRO_ITERATIONS):
            logger.info(f"Micro-loop iteration {iteration + 1}/{self.MAX_MICRO_ITERATIONS} for {component_scope}")
            
            # Run visual diff
            diff_result = await visualdiff.diff_component(source_url, drupal_path, component_scope)
            
            similarity = diff_result.get("similarity", 0)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_result = diff_result
            
            # Check if threshold met
            if similarity >= self.SIMILARITY_THRESHOLD:
                logger.info(f"Micro-loop converged: {similarity*100:.1f}% similarity")
                break
            
            # Get refinement instructions
            instructions = diff_result.get("instructions", [])
            if instructions and instructions[0].get("action") == "refine":
                logger.info(f"Refinement needed: {instructions[0].get('message')}")
        
        await visualdiff.close()
        
        return best_result or {"iterations": 0, "similarity": 0}

    # ── Meso-Loop: Page Refinement ───────────────────────────────
    
    async def refine_page(self, page_path: str, source_url: str) -> dict:
        """
        Meso-loop: Refine a full page.
        After initial build, check page-level similarity and rebuild weak sections.
        """
        from visual_diff_agent import VisualDiffAgent
        
        visualdiff = VisualDiffAgent()
        await visualdiff.initialize()
        
        # Run full page diff
        diff_result = await visualdiff.diff_page(source_url, page_path)
        
        similarity = diff_result.get("similarity", 0)
        
        if similarity >= self.SIMILARITY_THRESHOLD:
            logger.info(f"Page {page_path} passed meso-loop: {similarity*100:.1f}%")
            await visualdiff.close()
            return {"passed": True, "similarity": similarity}
        
        # Identify weak sections
        regions = diff_result.get("regions", [])
        weak_regions = [r for r in regions if r.get("severity") == "high"]
        
        logger.info(f"Page {page_path} needs rebuild: {len(weak_regions)} weak regions")
        
        await visualdiff.close()
        
        return {
            "passed": False,
            "similarity": similarity,
            "weak_regions": weak_regions,
            "needs_remap": True
        }

    # ── Missing Piece Detection ─────────────────────────────────────
    
    async def _analyze_missing_pieces(self, page_path: str, source_url: str, blueprint: dict, diff_result: dict) -> dict:
        """
        Analyze what's missing on the migrated page compared to source.
        Triggered when visual diff shows very low similarity (< 30%).
        """
        logger.info(f"Analyzing missing pieces for {page_path}...")
        
        # Get the page info from blueprint
        source_page = None
        for p in blueprint.get("pages", []):
            if p.get("path") == page_path:
                source_page = p
                break
        
        # Get sections for this page
        page_sections = [s for s in blueprint.get("sections", [])]
        
        missing_pieces = []
        
        # Analyze what might be missing
        analysis_prompt = f"""
        The page at '{page_path}' has very low visual similarity ({diff_result.get('similarity', 0)*100:.1f}%) to the source.
        
        Source page info: {json.dumps(source_page) if source_page else 'Home page'}
        
        Blueprint sections that should be on this page:
        {json.dumps(page_sections[:5], indent=2)}
        
        Visual diff regions with differences:
        {json.dumps(diff_result.get('regions', [])[:5], indent=2)}
        
        Please analyze and identify:
        1. What content elements might be missing from the Drupal page?
        2. What styling/layout elements might be incorrect?
        3. What specific improvements should be made?
        
        Return a JSON list of specific action items to fix this page.
        """
        
        messages = [{"role": "user", "content": analysis_prompt}]
        
        try:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=1024,
                messages=messages,
            )
            analysis_text = response.content[0].text.strip()
            
            # Try to parse as JSON
            import re
            json_match = re.search(r'\[[\s\S]*\]', analysis_text)
            if json_match:
                try:
                    missing_pieces = json.loads(json_match.group())
                except:
                    missing_pieces = [{"action": "analyze", "description": analysis_text[:500]}]
            else:
                missing_pieces = [{"action": "review", "description": analysis_text[:500]}]
                
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}")
            missing_pieces = [{"action": "manual_review", "error": str(e)}]
        
        # Store the analysis in memory for QA agent
        self.memory.set(f"missing_pieces_{page_path.replace('/', '_')}", {
            "page_path": page_path,
            "similarity": diff_result.get("similarity", 0),
            "missing_pieces": missing_pieces,
            "source_url": source_url,
        })
        
        await self.log(
            f"Missing piece analysis complete: {len(missing_pieces)} items identified",
            detail=f"First item: {missing_pieces[0].get('action', 'N/A') if missing_pieces else 'None'}"
        )
        
        return {
            "page_path": page_path,
            "similarity": diff_result.get("similarity", 0),
            "missing_pieces": missing_pieces,
        }

    # ── Extra tools ───────────────────────────────────────────

    def _tool_get_blueprint(self) -> str:
        bp = self.memory.get_blueprint()
        if not bp:
            return "No blueprint found. AnalyzerAgent must run first."
        # Return a condensed version to save tokens
        condensed = {
            "title": bp.get("title"),
            "pages": bp.get("pages", []),
            "navigation": bp.get("navigation", []),
            "sections": [
                {
                    "type": s["type"],
                    "heading": s.get("heading", ""),
                    "text_preview": s.get("text_preview", "")[:150],
                    "drupal_component": s.get("drupal_component", ""),
                }
                for s in bp.get("sections", [])
            ],
        }
        return json.dumps(condensed)

    def _tool_get_component_knowledge(self, content_type: str) -> str:
        doc = self.memory.get_component(content_type)
        if not doc:
            return f"No knowledge for '{content_type}'. Available: {self.memory.list_components()}"
        return json.dumps(doc)

    def _tool_get_mapping_manifest(self) -> str:
        """Get the mapping manifest from MappingAgent."""
        manifest = self.get_mapping_manifest()
        if manifest:
            return json.dumps(manifest)
        return "No mapping manifest found. Run MappingAgent first."

    def _tool_record_built_page(self, title: str, drupal_id: str, path: str, content_type: str) -> str:
        built = self.memory.get_or_default("built_pages", [])
        built.append({"title": title, "id": drupal_id, "path": path, "type": content_type})
        self.memory.set("built_pages", built)
        return f"Recorded: {title}"

    def _tool_get_built_pages(self) -> str:
        return json.dumps(self.memory.get_or_default("built_pages", []))

    def _tool_create_homepage(self, title: str, hero_html: str, sections_html: str = "") -> str:
        """Create the homepage with hero and main sections."""
        
        logger.info(f"[BUILD] Creating homepage: {title}")
        logger.info(f"[BUILD] Hero HTML length: {len(hero_html)} chars")
        logger.info(f"[BUILD] Sections HTML length: {len(sections_html)} chars")
        
        # Sanitize HTML before validation
        hero_html = self.sanitize_html(hero_html)
        sections_html = self.sanitize_html(sections_html)
        
        full_body = f"""
<div class="dm-hero">
  {hero_html}
</div>
<div class="dm-main-content">
  {sections_html}
</div>
"""
        # Validate payload
        payload = {
            "data": {
                "type": "node--page",
                "attributes": {
                    "title": title,
                    "body": {"value": full_body, "format": "full_html"},
                    "status": True,
                }
            }
        }
        is_valid, error = self.validate_payload(payload, "page")
        if not is_valid:
            logger.warning(f"[BUILD] Payload validation failed: {error}")
            # Try to fix by sanitizing
            full_body = self.sanitize_html(full_body)
            payload["data"]["attributes"]["body"]["value"] = full_body
            is_valid, _ = self.validate_payload(payload, "page")
            if not is_valid:
                return f"ERROR: Payload validation failed: {error}"
        
        try:
            logger.info(f"[BUILD] Saving homepage to Drupal...")
            node = self.drupal.create_node("page", {
                "title": title,
                "body": {"value": full_body, "format": "full_html"},
                "status": True,
                "path": {"alias": "/home"},
            })
            nid = node.get("attributes", {}).get("drupal_internal__nid", "")
            # Also store the UUID
            node_id = node.get("id", "")
            logger.info(f"[BUILD] Homepage saved successfully! Node ID: {node_id}, NID: {nid}")
            self._tool_record_built_page(title, node_id, "/", "page")
            return json.dumps({"success": True, "id": node_id, "nid": nid})
        except Exception as e:
            logger.error(f"[BUILD] Failed to save homepage: {e}")
            return f"ERROR: {e}"

    def _tool_delete_test_content(self) -> str:
        """Remove any test articles created during development."""
        try:
            nodes = self.drupal.get_nodes("article", limit=20)
            deleted = 0
            for n in nodes:
                title = n["attributes"].get("title", "")
                if "test" in title.lower() or "api test" in title.lower():
                    self.drupal.delete_node("article", n["id"])
                    deleted += 1
            return f"Deleted {deleted} test articles"
        except Exception as e:
            return f"ERROR: {e}"

    def _dispatch_tool(self, name: str, inputs: dict):
        extra = {
            "get_blueprint": self._tool_get_blueprint,
            "get_component_knowledge": self._tool_get_component_knowledge,
            "get_mapping_manifest": self._tool_get_mapping_manifest,
            "record_built_page": self._tool_record_built_page,
            "get_built_pages": self._tool_get_built_pages,
            "create_homepage": self._tool_create_homepage,
            "delete_test_content": self._tool_delete_test_content,
        }
        if name in extra:
            return extra[name](**inputs)
        return super()._dispatch_tool(name, inputs)

    # ── Entry point ───────────────────────────────────────────

    async def build_site(self) -> dict:
        """Build the full site from the blueprint."""
        logger.info("══════════════════════════════════════════════════════════════")
        logger.info("║ BUILD AGENT STARTING")
        logger.info("══════════════════════════════════════════════════════════════")
        
        # Log build start with detailed info
        await self.log_extended("build_start", {
            "blueprint_loaded": True,
        })
        
        blueprint = self.memory.get_blueprint()
        if not blueprint:
            await self.log_error("No blueprint found — run AnalyzerAgent first")
            await self.log_extended("build_error", {"error": "No blueprint"})
            return {"error": "No blueprint"}

        # Log blueprint details
        await self.log_data("blueprint_details", {
            "title": blueprint.get("title"),
            "source_url": blueprint.get("source_url"),
            "pages": [{"title": p.get("title"), "path": p.get("path")} for p in blueprint.get("pages", [])],
            "sections_count": len(blueprint.get("sections", [])),
            "content_types_needed": blueprint.get("content_types_needed", []),
        }, summary=f"Blueprint: {blueprint.get('title')} - {len(blueprint.get('pages', []))} pages")
        
        await self.log(
            f"Building '{blueprint.get('title', 'site')}' — "
            f"{len(blueprint.get('pages', []))} pages to build"
        )

        logger.info(f"Site title: {blueprint.get('title', 'site')}")
        logger.info(f"Pages to build: {len(blueprint.get('pages', []))}")
        logger.info(f"Blueprint sections: {len(blueprint.get('sections', []))}")
        
        # Get mapping manifest if available (with null safety)
        mapping_manifest = self.get_mapping_manifest() or {}
        if mapping_manifest:
            stats = mapping_manifest.get("statistics", {})
            logger.info(f"Mapping manifest available: {stats.get('total', 0)} elements")
            await self.log_data("mapping_manifest", {
                "total_mappings": stats.get("total", 0),
                "high_confidence": stats.get("high_confidence", 0),
                "low_confidence": stats.get("low_confidence", 0),
                "requires_review": mapping_manifest.get("requires_review", False),
            }, summary=f"Mapping: {stats.get('total', 0)} elements mapped")
        
        # Log build iteration configuration
        await self.log_extended("build_config", {
            "max_micro_iterations": self.MAX_MICRO_ITERATIONS,
            "max_meso_iterations": self.MAX_MESO_ITERATIONS,
            "similarity_threshold": self.SIMILARITY_THRESHOLD,
            "min_similarity_threshold": self.MIN_SIMILARITY_THRESHOLD,
        })
        
        result = await asyncio.to_thread(self._run_build_loop, blueprint)
        built = self.memory.get_or_default("built_pages", [])
        
        # Log built pages
        await self.log_data("built_pages", {
            "count": len(built),
            "pages": [{"title": p.get("title"), "path": p.get("path"), "content_type": p.get("content_type")} for p in built],
        }, summary=f"Built {len(built)} pages")
        
        # ── Meso-Loop: Page Refinement ───────────────────────────────
        # After building all pages, run visual diff on each
        if built and blueprint.get("source_url"):
            await self.log("Running visual diff on built pages (Meso-loop)...")
            await self.log_extended("meso_loop_start", {
                "pages_to_check": len(built),
                "source_url": blueprint.get("source_url"),
            })
            source_url = blueprint.get("source_url", "")
            
            meso_results = []
            total_meso_iterations = 0
            
            for page in built:
                page_path = page.get("path", "/")
                page_meso_iterations = 0
                best_similarity = 0
                
                logger.info(f"[MESO] Starting refinement for page: {page_path}")
                
                # Meso-loop: try up to MAX_MESO_ITERATIONS times per page
                while page_meso_iterations < self.MAX_MESO_ITERATIONS and total_meso_iterations < 10:
                    try:
                        logger.info(f"[MESO] Running visual diff for {page_path}...")
                        meso_result = await self.refine_page(page_path, source_url)
                        similarity = meso_result.get("similarity", 0)
                        page_meso_iterations += 1
                        total_meso_iterations += 1
                        
                        if similarity > best_similarity:
                            best_similarity = similarity
                        
                        await self.log(
                            f"Meso-loop {page_meso_iterations}/{self.MAX_MESO_ITERATIONS} for {page_path}: "
                            f"{similarity*100:.1f}% similarity"
                        )
                        
                        # Log detailed meso iteration
                        await self.log_data("meso_iteration", {
                            "page": page_path,
                            "iteration": page_meso_iterations,
                            "similarity": similarity,
                            "passed": similarity >= self.SIMILARITY_THRESHOLD,
                        }, summary=f"{page_path}: {similarity*100:.1f}%")
                        
                        # Check if we've reached threshold
                        if similarity >= self.SIMILARITY_THRESHOLD:
                            await self.log(f"✓ Page {page_path} reached {similarity*100:.1f}% - stopping refinement")
                            break
                        
                        # Check if similarity improved
                        if similarity < best_similarity - 0.1:
                            await self.log(f"⚠️ Similarity not improving - stopping early")
                            break
                        
                        # If similarity is very low, trigger missing piece detection
                        if similarity < self.MIN_SIMILARITY_THRESHOLD:
                            await self.log(
                                f"⚠️ LOW SIMILARITY ({similarity*100:.1f}%) for {page_path} - identifying missing pieces",
                                detail="Triggering gap analysis"
                            )
                            await self.log_warning("Low similarity detected", {
                                "page": page_path,
                                "similarity": similarity,
                                "threshold": self.MIN_SIMILARITY_THRESHOLD,
                            })
                            missing_analysis = await self._analyze_missing_pieces(
                                page_path, 
                                source_url, 
                                blueprint,
                                meso_result
                            )
                            meso_result["missing_analysis"] = missing_analysis
                            
                    except Exception as e:
                        logger.warning(f"Meso-loop failed for {page_path}: {e}")
                        break
                
                meso_results.append({
                    "page": page_path,
                    "iterations": page_meso_iterations,
                    "best_similarity": best_similarity,
                })
            
            # Log meso-loop summary
            passed_count = len([r for r in meso_results if r['best_similarity'] >= self.SIMILARITY_THRESHOLD])
            await self.log_extended("meso_loop_complete", {
                "total_iterations": total_meso_iterations,
                "pages_passed": passed_count,
                "pages_total": len(meso_results),
                "results": meso_results,
            })
            
            # Log summary
            await self.log(
                f"Meso-loop complete: {total_meso_iterations} total iterations, "
                f"{passed_count}/{len(meso_results)} pages passed"
            )
            
            # Store meso-loop results
            self.memory.set("meso_loop_results", meso_results)
        
        # Log final build result
        await self.log_extended("build_complete", {
            "pages_built": len(built),
            "meso_loop_run": bool(built and blueprint.get("source_url")),
        })
        
        await self.log_done(
            f"Build complete — {len(built)} pages created",
            detail=", ".join(p["title"] for p in built)
        )
        return result

    async def build_page(self, page_spec: dict) -> dict:
        """Build a single page."""
        title = page_spec.get('title', 'Untitled')
        path = page_spec.get('path', '/')
        content_type = page_spec.get('content_type', 'page')
        
        await self.log(f"Building page: {title}")
        
        # Log detailed page spec
        await self.log_data("page_spec", {
            "title": title,
            "path": path,
            "content_type": content_type,
            "description": page_spec.get("description", "")[:100],
            "has_hero": page_spec.get("has_hero", False),
            "sections_count": len(page_spec.get("sections", [])),
        }, summary=f"Building: {title} ({content_type})")
        
        result = await asyncio.to_thread(self._build_single_page, page_spec)
        
        # Log build result
        await self.log_data("page_built", {
            "title": title,
            "path": path,
            "result_type": type(result.get("result", "")).__name__,
        }, summary=f"Page built: {title}")
        
        await self.log_done(f"Page built: {title}")
        return result

    def _run_build_loop(self, blueprint: dict) -> dict:
        """Use LLM to drive the build process."""
        # Check if V5 content consolidation is enabled
        from config import V5_FEATURES
        
        if V5_FEATURES.get("ENABLE_CONTENT_CONSOLIDATION", False):
            # Use V5 build loop with content consolidation
            return self._run_build_loop_v5(blueprint)
        
        # Fall back to original LLM-based build
        tools = self.COMMON_TOOLS + [
            {
                "name": "get_blueprint",
                "description": "Get the site blueprint to understand what needs to be built.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_mapping_manifest",
                "description": "Get the mapping manifest with confidence scores.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_component_knowledge",
                "description": "Get documentation for a Drupal component/content type.",
                "input_schema": {
                    "type": "object",
                    "properties": {"content_type": {"type": "string"}},
                    "required": ["content_type"],
                },
            },
            {
                "name": "record_built_page",
                "description": "Record a successfully built page in memory.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "drupal_id": {"type": "string"},
                        "path": {"type": "string"},
                        "content_type": {"type": "string"},
                    },
                    "required": ["title", "drupal_id", "path", "content_type"],
                },
            },
            {
                "name": "get_built_pages",
                "description": "Get list of already-built pages.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "create_homepage",
                "description": "Create the homepage with hero section.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "hero_html": {"type": "string", "description": "HTML for the hero section"},
                        "sections_html": {"type": "string", "description": "HTML for remaining sections"},
                    },
                    "required": ["title", "hero_html"],
                },
            },
            {
                "name": "delete_test_content",
                "description": "Delete test content created during setup.",
                "input_schema": {"type": "object", "properties": {}},
            },
        ]

        messages = [
            {
                "role": "user",
                "content": (
                    f"Build the Drupal site. The blueprint title is: '{blueprint.get('title', 'My Site')}'.\n"
                    f"Pages to build: {json.dumps([p['title'] for p in blueprint.get('pages', [])])}\n\n"
                    "Steps:\n"
                    "1. Delete any test content first\n"
                    "2. Read the blueprint to understand the full site structure\n"
                    "3. Read the mapping manifest to understand component confidence scores\n"
                    "4. Build the homepage with proper hero HTML (include h1, tagline, CTA button)\n"
                    "5. Build each additional page with appropriate content\n"
                    "6. Create main menu items for each page\n"
                    "7. When done, summarize what was built\n\n"
                    "IMPORTANT: Always validate HTML content before sending to Drupal - remove any script tags, iframes, or event handlers.\n\n"
                    "Write real, meaningful HTML content based on what the blueprint describes."
                ),
            }
        ]

        logger.info("══════════════════════════════════════════════════════════════")
        logger.info("║ BUILD AGENT - LLM REQUEST")
        logger.info(f"║ System Prompt ({len(SYSTEM_PROMPT)} chars): {SYSTEM_PROMPT[:100]}...")
        logger.info(f"║ User Message: {messages[0]['content'][:150]}...")
        logger.info(f"║ Tools available: {len(tools)}")
        logger.info("══════════════════════════════════════════════════════════════")
        
        result = self.call_llm_with_tools(SYSTEM_PROMPT, messages, tools)
        return {"result": result, "built": self.memory.get_or_default("built_pages", [])}

    def _run_build_loop_v5(self, blueprint: dict) -> dict:
        """
        V5: Build all pages with proper content consolidation
        """
        from config import V5_FEATURES
        
        # Get mapping manifest with consolidated mappings
        mapping_manifest = self.get_mapping_manifest() or {}
        consolidated_mappings = [m for m in mapping_manifest.get("mappings", []) 
                           if m.get("element_type") == "consolidated_page"]
        
        built_pages = []
        errors = []
        
        logger.info(f"[BUILD] Building {len(consolidated_mappings)} consolidated pages")
        
        # If no consolidated mappings, fall back to building individual pages
        if not consolidated_mappings:
            logger.info("[BUILD] No consolidated mappings found, building individual pages")
            return self._build_individual_pages_v5(blueprint)
        
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
                    logger.error(f"[BUILD] ✗ Failed to build page: {mapping.get('title')}: {page_result.get('error')}")
                    
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
    
    def _build_individual_pages_v5(self, blueprint: dict) -> dict:
        """
        V5: Build pages individually when no consolidated mappings exist
        """
        from config import V5_FEATURES
        
        # Initialize content assembler
        assembler = ContentAssembler()
        
        built_pages = []
        errors = []
        pages = blueprint.get("pages", [])
        sections = blueprint.get("sections", [])
        
        logger.info(f"[BUILD] Building {len(pages)} pages individually")
        
        for page in pages:
            try:
                # Find sections for this page
                page_sections = [s for s in sections if s.get("index", -1) >= 0][:10]
                
                # Assemble content
                assembled_content = assembler.assemble_page_content(page_sections, page)
                
                # Create node in Drupal
                content_type = page.get("content_type", "page")
                
                node_data = {
                    "title": page.get("title"),
                    "body": {
                        "value": assembled_content.get("body_html", ""),
                        "format": "full_html"
                    },
                    "status": True
                }
                
                if page.get("path") and page.get("path") != "/":
                    node_data["path"] = {"alias": page.get("path")}
                
                # Validate payload
                is_valid, error = self.validate_payload({
                    "data": {
                        "type": f"node--{content_type}",
                        "attributes": node_data
                    }
                }, content_type)
                
                if not is_valid:
                    errors.append(f"Validation failed for {page.get('title')}: {error}")
                    continue
                
                # Create node
                node = self.drupal.create_node(content_type, node_data)
                
                built_pages.append({
                    "title": page.get("title"),
                    "id": node.get("id"),
                    "path": page.get("path"),
                    "content_type": content_type,
                    "sections_count": len(page_sections)
                })
                
                logger.info(f"[BUILD] ✓ Built page: {page.get('title')} with {len(page_sections)} sections")
                
            except Exception as e:
                logger.error(f"[BUILD] ✗ Error building page {page.get('title')}: {e}")
                errors.append(str(e))
        
        # Store built pages
        self.memory.set("built_pages", built_pages)
        
        return {
            "built_pages": len(built_pages),
            "errors": errors,
            "consolidation_successful": len(built_pages) > 0,
            "detail": f"Built {len(built_pages)} pages with content assembly"
        }
    
    def _build_consolidated_page(self, mapping: dict, blueprint: dict) -> dict:
        """
        V5: Build a single consolidated page from multiple sections
        """
        from config import V5_FEATURES
        
        # Initialize content assembler
        assembler = ContentAssembler()
        
        # Get sections for this page
        section_indices = mapping.get("sections_included", [])
        sections = blueprint.get("sections", [])
        page_sections = [sections[i] for i in section_indices if i < len(sections)]
        
        # If no specific sections, get all content sections
        if not page_sections:
            page_sections = [s for s in sections if s.get("type") not in ["navigation", "header", "footer"]]
        
        # Assemble content
        assembled_content = assembler.assemble_page_content(page_sections, mapping)
        
        # Get content type
        content_type = mapping.get("drupal_component", "page")
        
        # Build node data
        node_data = {
            "title": mapping.get("title"),
            "body": {
                "value": assembled_content.get("body_html", ""),
                "format": "full_html"
            },
            "status": True
        }
        
        if mapping.get("path") and mapping.get("path") != "/":
            node_data["path"] = {"alias": mapping.get("path")}
        
        # Validate content
        is_valid, error = self.validate_payload({
            "data": {
                "type": f"node--{content_type}",
                "attributes": node_data
            }
        }, content_type)
        
        if not is_valid:
            return {"success": False, "error": error}
        
        # Create the node
        try:
            node = self.drupal.create_node(content_type, node_data)
            
            return {
                "success": True,
                "node_id": node.get("id"),
                "sections_consolidated": len(page_sections)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _build_single_page(self, page_spec: dict) -> dict:
        """Build one page using LLM."""
        tools = self.COMMON_TOOLS + [
            {
                "name": "get_blueprint",
                "description": "Get the full site blueprint.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_mapping_manifest",
                "description": "Get the mapping manifest.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "record_built_page",
                "description": "Record a built page.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "drupal_id": {"type": "string"},
                        "path": {"type": "string"},
                        "content_type": {"type": "string"},
                    },
                    "required": ["title", "drupal_id", "path", "content_type"],
                },
            },
        ]

        messages = [
            {
                "role": "user",
                "content": (
                    f"Build this specific Drupal page:\n{json.dumps(page_spec)}\n\n"
                    "Use create_page or create_article as appropriate. "
                    "Write real HTML content matching the page type. "
                    "Validate and sanitize HTML before sending to Drupal. "
                    "Record it when done."
                ),
            }
        ]
        result = self.call_llm_with_tools(SYSTEM_PROMPT, messages, tools)
        return {"result": result}
