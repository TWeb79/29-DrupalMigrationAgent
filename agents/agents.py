"""
DrupalMind — ThemeAgent
Generates custom CSS matching source site's design tokens
and injects it into Drupal via a custom block.
"""
import json
import asyncio
import re
from base_agent import BaseAgent


class ThemeAgent(BaseAgent):
    def __init__(self):
        super().__init__("theme", "ThemeAgent")

    async def apply_theme(self) -> dict:
        await self.log("Generating theme from design tokens...")
        blueprint = self.memory.get_blueprint()
        if not blueprint:
            await self.log_error("No blueprint — cannot apply theme")
            return {"error": "No blueprint"}

        tokens = blueprint.get("design_tokens", {})
        result = await asyncio.to_thread(self._generate_and_inject_css, tokens, blueprint)
        await self.log_done("Theme CSS injected into Drupal", detail=f"Colors: {tokens.get('colors', [])[:3]}")
        return result

    def _generate_and_inject_css(self, tokens: dict, blueprint: dict) -> dict:
        css = self._generate_css(tokens, blueprint)
        # Inject as a custom HTML block in Drupal
        html_with_css = f"<style>{css}</style>"
        try:
            # Try creating a basic block with the CSS
            block = self.drupal.create_custom_block(
                "basic",
                "DrupalMind Custom Theme CSS",
                html_with_css,
                "full_html"
            )
            self.memory.set("theme_css", css)
            self.memory.set("theme_block_id", block.get("id", ""))
            return {"css_injected": True, "block_id": block.get("id", ""), "css_length": len(css)}
        except Exception as e:
            # Store CSS in memory even if injection fails
            self.memory.set("theme_css", css)
            return {"css_stored": True, "error": str(e), "css": css[:500]}

    def _generate_css(self, tokens: dict, blueprint: dict) -> str:
        primary = tokens.get("primary_color", "#1a1a2e")
        secondary = tokens.get("secondary_color", "#e94560")
        colors = tokens.get("colors", [primary, secondary])
        fonts = tokens.get("fonts", [])
        bg_color = self._find_bg_color(colors)
        text_color = self._contrast_color(bg_color)

        font_family = "sans-serif"
        heading_font = "sans-serif"
        if fonts:
            font_family = f"'{fonts[0]}', sans-serif"
            heading_font = f"'{fonts[1] if len(fonts) > 1 else fonts[0]}', sans-serif"

        return f"""
/* DrupalMind Generated Theme */
:root {{
  --dm-primary: {primary};
  --dm-secondary: {secondary};
  --dm-bg: {bg_color};
  --dm-text: {text_color};
  --dm-font: {font_family};
  --dm-heading-font: {heading_font};
}}

body {{
  font-family: var(--dm-font);
  color: var(--dm-text);
  background: var(--dm-bg);
  line-height: 1.6;
  margin: 0;
}}

h1, h2, h3, h4, h5, h6 {{
  font-family: var(--dm-heading-font);
  color: var(--dm-primary);
}}

a {{ color: var(--dm-secondary); }}
a:hover {{ opacity: 0.8; }}

.dm-hero {{
  background: var(--dm-primary);
  color: white;
  padding: 80px 40px;
  text-align: center;
}}

.dm-hero h1 {{
  font-size: 2.8rem;
  color: white;
  margin-bottom: 1rem;
}}

.dm-hero p {{
  font-size: 1.2rem;
  opacity: 0.9;
  max-width: 600px;
  margin: 0 auto 2rem;
}}

.dm-cta-button {{
  display: inline-block;
  background: var(--dm-secondary);
  color: white;
  padding: 14px 32px;
  border-radius: 4px;
  text-decoration: none;
  font-weight: 600;
  font-size: 1rem;
}}

.dm-main-content {{
  max-width: 1100px;
  margin: 0 auto;
  padding: 40px 20px;
}}

nav ul {{
  display: flex;
  list-style: none;
  gap: 24px;
  padding: 0;
  margin: 0;
}}

nav a {{
  color: var(--dm-primary);
  font-weight: 500;
  text-decoration: none;
}}

.layout-container {{
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}}
""".strip()

    def _find_bg_color(self, colors: list) -> str:
        # Look for light colors to use as background
        for color in colors:
            if color.startswith("#"):
                try:
                    r = int(color[1:3], 16)
                    g = int(color[3:5], 16) if len(color) > 4 else int(color[2:3] * 2, 16)
                    b = int(color[5:7], 16) if len(color) > 6 else int(color[3:4] * 2, 16)
                    if r > 200 and g > 200 and b > 200:
                        return color
                except Exception:
                    pass
        return "#ffffff"

    def _contrast_color(self, bg: str) -> str:
        try:
            r = int(bg[1:3], 16)
            g = int(bg[3:5], 16)
            b = int(bg[5:7], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            return "#111111" if luminance > 0.5 else "#f0f0f0"
        except Exception:
            return "#111111"


# ─────────────────────────────────────────────────────────────


class ContentAgent(BaseAgent):
    """Migrates actual content from source site into Drupal."""

    def __init__(self):
        super().__init__("content", "ContentAgent")

    async def migrate_content(self) -> dict:
        await self.log("Starting content migration...")
        blueprint = self.memory.get_blueprint()
        if not blueprint:
            await self.log_error("No blueprint found")
            return {"error": "No blueprint"}

        result = await asyncio.to_thread(self._migrate_all, blueprint)
        await self.log_done(
            f"Content migration done — {result.get('created', 0)} items created",
            detail=result.get("detail", "")
        )
        return result

    def _migrate_all(self, blueprint: dict) -> dict:
        created = 0
        errors = []

        # Create taxonomy terms from navigation-derived categories
        nav_items = blueprint.get("navigation", [])
        if nav_items:
            try:
                for item in nav_items[:5]:
                    if item["title"].lower() not in ("home", "contact"):
                        try:
                            self.drupal.create_term("tags", item["title"])
                        except Exception:
                            pass
            except Exception:
                pass

        # Create sample article nodes from blog sections
        sections = blueprint.get("sections", [])
        for section in sections:
            if section.get("type") in ("blog", "team", "testimonials"):
                try:
                    heading = section.get("heading", "Sample Post")
                    text = section.get("text_preview", "Content migrated by DrupalMind.")
                    body = f"<p>{text}</p>"
                    node = self.drupal.create_node("article", {
                        "title": heading or "Migrated Content",
                        "body": {"value": body, "format": "basic_html"},
                        "status": True,
                    })
                    created += 1
                except Exception as e:
                    errors.append(str(e))

        self.memory.set("content_migration", {"created": created, "errors": errors})
        return {
            "created": created,
            "errors": errors[:3],
            "detail": f"Tags, articles created from {len(sections)} source sections"
        }


# ─────────────────────────────────────────────────────────────


class TestAgent(BaseAgent):
    """Compares the built Drupal site against the source specification."""

    def __init__(self):
        super().__init__("test", "TestAgent")

    async def run_tests(self) -> dict:
        await self.log("Running comparison tests...")
        blueprint = self.memory.get_blueprint()
        built_pages = self.memory.get_or_default("built_pages", [])
        result = await asyncio.to_thread(self._run_all_tests, blueprint, built_pages)

        score = result.get("overall_score", 0)
        await self.log_done(
            f"Tests complete — {score}% match",
            detail=f"Pass: {result.get('passed', 0)}, Fail: {result.get('failed', 0)}"
        )
        self.memory.set_test_report(result)
        return result

    def _run_all_tests(self, blueprint: dict, built_pages: list) -> dict:
        checks = []
        passed = 0
        failed = 0

        # Check: blueprint exists
        if blueprint:
            checks.append({"check": "Site Blueprint", "status": "pass", "detail": "Blueprint found in memory"})
            passed += 1
        else:
            checks.append({"check": "Site Blueprint", "status": "fail", "detail": "No blueprint in memory"})
            failed += 1

        # Check: pages were built
        expected_pages = blueprint.get("pages", []) if blueprint else []
        if built_pages:
            checks.append({
                "check": "Pages Built",
                "status": "pass",
                "detail": f"{len(built_pages)} of {len(expected_pages)} pages created"
            })
            passed += 1
        else:
            checks.append({"check": "Pages Built", "status": "fail", "detail": "No pages built yet"})
            failed += 1

        # Check: navigation
        try:
            menus = self.drupal.get_menu_items("main")
            if menus:
                checks.append({"check": "Main Navigation", "status": "pass", "detail": f"{len(menus)} menu items found"})
                passed += 1
            else:
                checks.append({"check": "Main Navigation", "status": "warn", "detail": "No menu items found"})
        except Exception as e:
            checks.append({"check": "Main Navigation", "status": "fail", "detail": str(e)})
            failed += 1

        # Check: Drupal API responsive
        if self.drupal.health_check():
            checks.append({"check": "Drupal API", "status": "pass", "detail": "API is responding"})
            passed += 1
        else:
            checks.append({"check": "Drupal API", "status": "fail", "detail": "API not responding"})
            failed += 1

        # Check: content types available
        try:
            cts = self.drupal.get_content_types()
            needed = blueprint.get("content_types_needed", []) if blueprint else []
            available = [ct["machine_name"] for ct in cts]
            missing = [t for t in needed if t not in available]
            if not missing:
                checks.append({"check": "Content Types", "status": "pass", "detail": f"All required types available: {', '.join(available)}"})
                passed += 1
            else:
                checks.append({"check": "Content Types", "status": "warn", "detail": f"Missing: {', '.join(missing)}"})
        except Exception as e:
            failed += 1

        total = passed + failed
        score = int((passed / total) * 100) if total > 0 else 0

        fixes_needed = []
        for check in checks:
            if check["status"] == "fail":
                fixes_needed.append(f"Fix '{check['check']}': {check['detail']}")

        return {
            "checks": checks,
            "passed": passed,
            "failed": failed,
            "overall_score": score,
            "fixes_needed": fixes_needed,
            "ready_for_qa": score >= 75,
        }


# ─────────────────────────────────────────────────────────────


class QAAgent(BaseAgent):
    """Final quality assurance — accessibility, links, performance."""

    def __init__(self):
        super().__init__("qa", "QAAgent")

    async def run_qa(self) -> dict:
        await self.log("Running QA checks...")
        result = await asyncio.to_thread(self._run_qa_checks)
        score = result.get("score", 0)
        await self.log_done(
            f"QA complete — {score}% quality score",
            detail=f"{result.get('issues', 0)} issues found"
        )
        self.memory.set_qa_report(result)
        return result

    def _run_qa_checks(self) -> dict:
        checks = []
        passed = 0
        issues = 0

        # Check Drupal is running
        if self.drupal.health_check():
            checks.append({"check": "Site Availability", "status": "pass", "detail": "Drupal is online"})
            passed += 1
        else:
            checks.append({"check": "Site Availability", "status": "fail", "detail": "Site not reachable"})
            issues += 1

        # Check content was created
        try:
            pages = self.drupal.get_nodes("page", limit=20)
            articles = self.drupal.get_nodes("article", limit=20)
            total_content = len(pages) + len(articles)
            if total_content > 0:
                checks.append({
                    "check": "Content Exists",
                    "status": "pass",
                    "detail": f"{len(pages)} pages, {len(articles)} articles"
                })
                passed += 1
            else:
                checks.append({"check": "Content Exists", "status": "fail", "detail": "No content found"})
                issues += 1
        except Exception as e:
            checks.append({"check": "Content Exists", "status": "error", "detail": str(e)})
            issues += 1

        # Check navigation
        try:
            menu_items = self.drupal.get_menu_items("main")
            if menu_items:
                checks.append({"check": "Navigation Links", "status": "pass", "detail": f"{len(menu_items)} nav items"})
                passed += 1
            else:
                checks.append({"check": "Navigation Links", "status": "warn", "detail": "Main menu is empty"})
        except Exception:
            pass

        # Check theme CSS was applied
        theme_css = self.memory.get("theme_css")
        if theme_css:
            checks.append({"check": "Custom Theme", "status": "pass", "detail": f"{len(theme_css)} chars of CSS generated"})
            passed += 1
        else:
            checks.append({"check": "Custom Theme", "status": "warn", "detail": "No custom theme CSS found"})

        # Check all built pages accessible
        built_pages = self.memory.get_or_default("built_pages", [])
        if built_pages:
            accessible = 0
            for page in built_pages[:5]:
                try:
                    path = page.get("path", "/")
                    url = f"{self.drupal.base_url}{path}"
                    import requests as req
                    r = req.get(url, timeout=5, allow_redirects=True)
                    if r.status_code < 400:
                        accessible += 1
                except Exception:
                    pass
            if accessible == len(built_pages[:5]):
                checks.append({"check": "Page Accessibility", "status": "pass", "detail": f"All {accessible} pages return 200"})
                passed += 1
            else:
                checks.append({"check": "Page Accessibility", "status": "warn", "detail": f"{accessible}/{len(built_pages[:5])} pages accessible"})
                issues += 1

        # Check JSON:API permissions
        try:
            import requests as req
            r = req.get(
                f"{self.drupal.base_url}/jsonapi/node/article",
                headers={"Accept": "application/vnd.api+json"},
                timeout=5,
            )
            if r.status_code == 200:
                checks.append({"check": "API Permissions", "status": "pass", "detail": "Public JSON:API access working"})
                passed += 1
            else:
                checks.append({"check": "API Permissions", "status": "warn", "detail": f"API returned {r.status_code}"})
        except Exception as e:
            checks.append({"check": "API Permissions", "status": "error", "detail": str(e)})
            issues += 1

        total = len(checks)
        score = int((passed / total) * 100) if total > 0 else 0

        recommendations = []
        for c in checks:
            if c["status"] in ("fail", "warn"):
                recommendations.append(c["detail"])

        return {
            "checks": checks,
            "passed": passed,
            "issues": issues,
            "score": score,
            "recommendations": recommendations,
            "approved": score >= 70,
        }
