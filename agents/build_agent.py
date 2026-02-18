"""
DrupalMind — BuildAgent
Constructs Drupal pages based on the Site Blueprint and Component Knowledge Base.
Uses the LLM tool-use loop to reason about what to build and how.
"""
import json
import asyncio
import logging
from base_agent import BaseAgent

# Configure logging for BuildAgent
logger = logging.getLogger("drupalmind.build")


SYSTEM_PROMPT = """You are the BuildAgent for DrupalMind, an AI system that builds Drupal websites.

Your job is to build a Drupal site based on the Site Blueprint in shared memory.

PROCESS:
1. Read the site blueprint from memory (key: "site_blueprint")
2. Read available component knowledge (key: "components/*")
3. For each page in the blueprint, create it in Drupal using the appropriate API calls
4. Create navigation menu items for the main menu
5. Report what you've built

RULES:
- Create ONE page per task. Don't try to do everything at once.
- Use "basic_html" format for body fields unless you have full_html available
- For hero sections, include a prominent heading in the body HTML
- For navigation, use the "main" menu
- Always set status: true to publish content
- Store a record of what you built in memory under key "built_pages"

AVAILABLE CONTENT TYPES: article (for blog/news), page (for static pages)

When creating page body content, write clean HTML including headings, paragraphs, and structure.
Make the content match what would be on the source page.
"""


class BuildAgent(BaseAgent):
    def __init__(self):
        super().__init__("build", "BuildAgent")

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

    def _tool_record_built_page(self, title: str, drupal_id: str, path: str, content_type: str) -> str:
        built = self.memory.get_or_default("built_pages", [])
        built.append({"title": title, "id": drupal_id, "path": path, "type": content_type})
        self.memory.set("built_pages", built)
        return f"Recorded: {title}"

    def _tool_get_built_pages(self) -> str:
        return json.dumps(self.memory.get_or_default("built_pages", []))

    def _tool_create_homepage(self, title: str, hero_html: str, sections_html: str = "") -> str:
        """Create the homepage with hero and main sections."""
        full_body = f"""
<div class="dm-hero">
  {hero_html}
</div>
<div class="dm-main-content">
  {sections_html}
</div>
"""
        try:
            node = self.drupal.create_node("page", {
                "title": title,
                "body": {"value": full_body, "format": "full_html"},
                "status": True,
                "path": {"alias": "/home"},
            })
            nid = node.get("attributes", {}).get("drupal_internal__nid", "")
            # Also store the UUID
            node_id = node.get("id", "")
            self._tool_record_built_page(title, node_id, "/", "page")
            return json.dumps({"success": True, "id": node_id, "nid": nid})
        except Exception as e:
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
        
        blueprint = self.memory.get_blueprint()
        if not blueprint:
            await self.log_error("No blueprint found — run AnalyzerAgent first")
            return {"error": "No blueprint"}

        await self.log(
            f"Building '{blueprint.get('title', 'site')}' — "
            f"{len(blueprint.get('pages', []))} pages to build"
        )

        logger.info(f"Site title: {blueprint.get('title', 'site')}")
        logger.info(f"Pages to build: {len(blueprint.get('pages', []))}")
        logger.info(f"Blueprint sections: {len(blueprint.get('sections', []))}")
        
        result = await asyncio.to_thread(self._run_build_loop, blueprint)
        built = self.memory.get_or_default("built_pages", [])
        await self.log_done(
            f"Build complete — {len(built)} pages created",
            detail=", ".join(p["title"] for p in built)
        )
        return result

    async def build_page(self, page_spec: dict) -> dict:
        """Build a single page."""
        await self.log(f"Building page: {page_spec.get('title', '?')}")
        result = await asyncio.to_thread(self._build_single_page, page_spec)
        await self.log_done(f"Page built: {page_spec.get('title')}")
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
                    "3. Build the homepage with proper hero HTML (include h1, tagline, CTA button)\n"
                    "4. Build each additional page with appropriate content\n"
                    "5. Create main menu items for each page\n"
                    "6. When done, summarize what was built\n\n"
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
                    "Record it when done."
                ),
            }
        ]
        result = self.call_llm_with_tools(SYSTEM_PROMPT, messages, tools)
        return {"result": result}
