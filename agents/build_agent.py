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
