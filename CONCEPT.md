# DrupalMind — Agentic AI Website Migration System
## Architecture & Agent Concept

---

## 1. System Overview

DrupalMind is a multi-agent AI system that takes a source website URL or natural language description and autonomously builds a matching Drupal site. A central Orchestration Agent coordinates a team of specialist agents, each with defined responsibilities, tools, memory access, and communication protocols.

The system operates in three phases:
- **Phase 0 — Discovery**: Analyze the source and understand what needs to be built
- **Phase 1 — Knowledge**: TrainAgent ensures the system knows what Drupal can do
- **Phase 2 — Build**: BuildAgent constructs the site iteratively
- **Phase 3 — Verify**: TestAgent and QA Agent validate the result

---

## 2. Agent Roster

### 🧠 OrchestratorAgent
**Role:** Central coordinator. The only agent that communicates with the user and directs all other agents.

**Responsibilities:**
- Receives user input (URL or description)
- Creates and manages the build plan (ordered task list)
- Assigns tasks to specialist agents
- Receives status reports and decides next actions
- Resolves conflicts between agents
- Decides when the build is complete
- Reports progress to the user via the UI

**Skills:**
- Task decomposition and prioritization
- Inter-agent communication protocol
- Build plan management
- Exception handling and retry logic
- User intent interpretation

**Tools:**
- `plan_manager` — create, update, read the current build plan
- `agent_dispatch(agent, task, context)` — send tasks to any agent
- `memory_read(key)` — read from shared memory
- `user_notify(message, status)` — push updates to the UI log
- `build_log_write(entry)` — append to the session build log

---

### 🔍 AnalyzerAgent *(new)*
**Role:** First agent to run. Deeply analyzes the source URL or description before any building starts.

**Responsibilities:**
- Scrape the source website (all pages if multi-page)
- Extract: layout structure, navigation, content types, color palette, fonts, images, forms, interactive elements
- Identify what Drupal content types, views, and blocks map to each section
- Produce a structured **Site Blueprint** document saved to shared memory
- Flag anything that may be impossible or difficult to replicate in Drupal

**Skills:**
- HTML/CSS structure parsing
- Visual layout analysis
- Content type mapping (blog, product, landing page, portfolio, etc.)
- Color and typography extraction
- Identification of dynamic vs. static content

**Tools:**
- `web_scraper(url, depth)` — crawl and extract full page HTML/CSS/content
- `screenshot_capture(url)` — capture visual screenshot for comparison later
- `color_extractor(html)` — extract dominant color palette
- `font_detector(html)` — identify font families in use
- `content_classifier(html)` — classify blocks as hero/nav/card/form/footer etc.
- `memory_write(key, value)` — write Site Blueprint to shared memory
- `llm_analyze(prompt, content)` — use LLM to interpret complex layouts

**Output:** `memory["site_blueprint"]` — structured JSON describing the full site

---

### 📚 TrainAgent
**Role:** The knowledge authority on Drupal. Maintains an up-to-date map of every available component, its configuration parameters, and how it renders.

**Responsibilities:**
- On first run: systematically test every Drupal core component (content types, blocks, views, paragraphs, layouts, menus, media, forms)
- For each component: create a test page, apply every known configuration combination, screenshot the result
- Maintain a **Component Knowledge Base** in Drupal itself (a special "training" section) and in shared memory
- When BuildAgent or OrchestratorAgent reports an unknown component: test it on demand and update the knowledge base
- Periodically re-validate knowledge when Drupal is updated or modules are added

**Skills:**
- Systematic component enumeration via JSON:API
- Parameter permutation testing
- Documentation generation
- Screenshot-to-description mapping

**Tools:**
- `drupal_api(method, endpoint, payload)` — full Drupal JSON:API access
- `drupal_get_content_types()` — list all available content types
- `drupal_get_blocks()` — list all available blocks
- `drupal_get_layouts()` — list all layout templates
- `drupal_get_fields(content_type)` — list fields on a content type
- `page_create(title, components)` — create a test page
- `screenshot_capture(url)` — capture test page result
- `memory_write("components/{name}", knowledge)` — store component knowledge
- `memory_read(key)` — read existing knowledge
- `knowledge_base_update(component, docs)` — update the Drupal knowledge wiki page

**Output:** `memory["components/*"]` — one entry per component with full parameter map and rendered examples

---

### 🏗️ BuildAgent
**Role:** The hands-on builder. Constructs pages in Drupal based on the Site Blueprint and Component Knowledge Base.

**Responsibilities:**
- Read the Site Blueprint from AnalyzerAgent
- For each page/section: look up the best matching component from TrainAgent's knowledge base
- Create pages, content types, blocks, menus, views, and media via the API
- If a required component has no knowledge entry: escalate to OrchestratorAgent to trigger TrainAgent
- Operate in iterative cycles — build a section, report to OrchestratorAgent, receive feedback from TestAgent, adjust
- Track what has been built vs. what remains in the build plan

**Skills:**
- Drupal JSON:API fluency
- Component-to-requirement mapping
- Iterative build and adjust loops
- Error interpretation and self-correction

**Tools:**
- `drupal_api(method, endpoint, payload)` — full API access
- `memory_read("site_blueprint")` — read the target
- `memory_read("components/{name}")` — read component knowledge
- `page_create(config)` — create a Drupal page
- `block_place(page, region, block_config)` — place a block on a page
- `menu_create(items)` — create navigation
- `media_upload(file_url)` — download source image and upload to Drupal
- `view_create(config)` — create a Drupal View
- `build_status_update(section, status)` — update build progress
- `escalate_unknown_component(component_description)` — trigger TrainAgent

---

### 🎨 ThemeAgent *(new)*
**Role:** Ensures the built site visually matches the source in terms of colors, typography, spacing, and overall aesthetic.

**Responsibilities:**
- Read color palette and font data from AnalyzerAgent output
- Generate a custom Drupal sub-theme with matching CSS variables
- Apply brand colors, heading fonts, body fonts
- Match spacing rhythm, border radius, shadow styles
- Generate a custom logo placeholder if none provided
- Ensure mobile responsiveness mirrors the source

**Skills:**
- CSS generation
- Drupal theming system (Olivero/Claro sub-theming)
- Design token extraction and application
- Responsive layout matching

**Tools:**
- `memory_read("site_blueprint")` — read color/font data
- `subtheme_create(base_theme, tokens)` — scaffold a Drupal sub-theme
- `css_generate(design_tokens)` — produce theme CSS
- `drupal_api("theme_enable", theme_name)` — activate the theme
- `screenshot_compare(source_url, drupal_url)` — visual diff
- `font_download(font_name)` — fetch web fonts

---

### 📝 ContentAgent *(new)*
**Role:** Migrates all actual content from the source site into the built Drupal structure.

**Responsibilities:**
- Extract all text content, headings, body copy from source pages
- Download all images and media files
- Map content to the correct Drupal content types and fields
- Handle content for each page individually
- Preserve SEO metadata (title, description, canonical URLs)
- Create taxonomy terms for tags/categories found on source site

**Skills:**
- Content extraction and cleaning
- HTML to Drupal body field formatting
- Image optimization and upload
- SEO metadata mapping
- Taxonomy management

**Tools:**
- `web_scraper(url)` — extract page content
- `html_to_drupal_body(html)` — clean and convert HTML
- `image_download_upload(src_url)` — fetch and push to Drupal media library
- `drupal_api(method, endpoint, payload)` — create nodes with content
- `metatag_set(node_id, meta)` — apply SEO metadata
- `taxonomy_create(vocab, terms)` — create tags/categories
- `pathauto_set(node_id, alias)` — set URL aliases

---

### 🧪 TestAgent
**Role:** Validates the built result against the original specification. The feedback engine.

**Responsibilities:**
- Compare built Drupal pages against the source URL or description
- Check: navigation structure, content sections, visual layout, links, images
- Produce a structured **Test Report** listing what matches and what needs fixing
- Score each section (pass / partial / fail)
- Send detailed actionable feedback to OrchestratorAgent
- Re-test after each BuildAgent adjustment cycle

**Skills:**
- Visual comparison (screenshot diffing)
- Structural HTML comparison
- Content completeness checking
- Navigation and link validation
- Requirement coverage analysis

**Tools:**
- `screenshot_capture(url)` — capture both source and Drupal pages
- `screenshot_diff(img_a, img_b)` — pixel-level visual comparison
- `content_compare(source_html, drupal_html)` — structural diff
- `link_validator(page_url)` — check all links resolve
- `nav_compare(source_nav, drupal_nav)` — compare navigation trees
- `memory_read("site_blueprint")` — read original requirements
- `test_report_write(report)` — store test results
- `llm_evaluate(source_screenshot, built_screenshot)` — AI visual judgment

**Output:** Structured test report with section-by-section pass/fail and specific fix instructions

---

### ✅ QAAgent
**Role:** Final quality gate. Runs after TestAgent approves. Checks code quality, accessibility, performance, and interactive functionality.

**Responsibilities:**
- Validate all HTML is well-formed
- Run accessibility checks (WCAG 2.1 AA)
- Check all buttons, links, forms are clickable and functional
- Validate Drupal-specific best practices (cache tags, config, permissions)
- Performance check (page weight, image sizes, render-blocking resources)
- Check mobile responsiveness
- Produce final QA report and sign-off or escalate

**Skills:**
- HTML/CSS validation
- Accessibility auditing
- Performance analysis
- Drupal security and config best practices
- Cross-device compatibility

**Tools:**
- `html_validator(url)` — W3C HTML validation
- `accessibility_audit(url)` — axe-core / WCAG checker
- `lighthouse_run(url)` — performance, SEO, accessibility scores
- `click_tester(url)` — headless browser interaction test (Playwright)
- `form_tester(url)` — submit all forms and verify responses
- `mobile_screenshot(url)` — capture on mobile viewport
- `drupal_config_audit()` — check Drupal security config
- `qa_report_write(report)` — store final QA report

---

### 🗄️ MemoryAgent *(new)*
**Role:** Manages the shared knowledge store. All agents read/write through this agent.

**Responsibilities:**
- Maintain the persistent memory store (Redis or Drupal nodes as key-value store)
- Version-control knowledge entries so they can be rolled back
- Index and search the Component Knowledge Base
- Provide a `search_components(description)` semantic search so agents can find the best component for a need without knowing its exact name
- Expose the knowledge base as a human-readable page in Drupal for debugging

**Skills:**
- Key-value storage management
- Semantic search / vector similarity
- Knowledge versioning
- Cache invalidation

**Tools:**
- `memory_read(key)` — retrieve a value
- `memory_write(key, value, version)` — store with versioning
- `memory_search(query)` — semantic search over knowledge base
- `memory_list(prefix)` — list all keys under a namespace
- `knowledge_page_sync()` — sync memory to human-readable Drupal page

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────┐
│                   USER INTERFACE                 │
│  URL/Description Input → Live Progress Log       │
│  Agent Status Board → Preview Panel              │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│              ORCHESTRATOR AGENT                  │
│  Build Plan │ Task Queue │ Agent Dispatcher      │
└──┬──────────┬───────────┬──────────┬────────────┘
   │          │           │          │
   ▼          ▼           ▼          ▼
Analyzer   Train       Build      Theme
Agent      Agent       Agent      Agent
   │          │           │          │
   └──────────┴─────┬─────┴──────────┘
                    │
              ┌─────▼──────┐
              │ MEMORY      │
              │ AGENT       │
              │ (shared     │
              │  knowledge) │
              └─────┬──────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    Content      Test         QA
    Agent        Agent        Agent
        │           │           │
        └───────────┼───────────┘
                    │
                    ▼
         ┌──────────────────┐
         │   DRUPAL API     │
         │ localhost:5500   │
         └──────────────────┘
```

---

## 4. Build Workflow (Step by Step)

```
1. USER submits URL or description
2. ORCHESTRATOR creates build plan, notifies UI
3. ORCHESTRATOR → ANALYZER: "Analyze this source"
4. ANALYZER scrapes, extracts, writes Site Blueprint to MEMORY
5. ORCHESTRATOR reads blueprint, checks MEMORY for component knowledge gaps
6. ORCHESTRATOR → TRAIN: "Test these unknown components"
7. TRAIN builds test pages, documents components, updates MEMORY
8. ORCHESTRATOR → BUILD + THEME + CONTENT (parallel):
   - BUILD creates page structure
   - THEME generates sub-theme with brand tokens
   - CONTENT migrates text + media
9. BUILD escalates unknown component → ORCHESTRATOR → TRAIN → MEMORY → BUILD resumes
10. ORCHESTRATOR → TEST: "Compare what's built against source"
11. TEST produces report with pass/fail per section
12. ORCHESTRATOR → BUILD: "Fix these sections" (loop back to step 8)
13. Repeat steps 8-12 until TEST passes all sections
14. ORCHESTRATOR → QA: "Final quality check"
15. QA runs accessibility, performance, interaction tests
16. If QA fails → ORCHESTRATOR → BUILD for targeted fixes
17. QA passes → ORCHESTRATOR notifies USER: "Build complete"
18. USER reviews in preview panel, requests tweaks if needed
```

---

## 5. Shared Memory Schema

```json
{
  "site_blueprint": {
    "source_url": "https://example.com",
    "pages": [...],
    "navigation": {...},
    "design_tokens": { "colors": [], "fonts": [] },
    "content_types_needed": [...],
    "sections": [...]
  },
  "components": {
    "node--article": { "fields": [...], "example_config": {}, "screenshot": "..." },
    "block--views": { ... },
    "paragraph--hero": { ... }
  },
  "build_plan": {
    "status": "in_progress",
    "tasks": [
      { "id": 1, "agent": "build", "task": "create homepage", "status": "done" },
      { "id": 2, "agent": "content", "task": "migrate hero text", "status": "in_progress" }
    ]
  },
  "test_reports": [...],
  "qa_report": { ... }
}
```

---

## 6. User Interface Concept

The UI has four panels:

**Left: Input Panel**
- URL input field or free-text description area
- Toggle: "Migrate existing site" vs "Build from description"
- Options: full migration / single page / structure only (no content)
- "Start Build" button

**Center-Top: Live Agent Log**
- Real-time stream of agent actions
- Each entry shows: timestamp, agent name (color-coded), action, status
- Collapsible detail for each log entry

**Center-Bottom: Build Plan**
- Visual kanban/checklist of all tasks
- Status per task: pending / in-progress / done / failed
- Click a task to see its detailed log

**Right: Preview Panel**
- Side-by-side: source screenshot (left) vs current Drupal build (right)
- Updates after each TestAgent run
- Link to open live Drupal page in new tab

---

## 7. Open Questions

Before implementation I need your input on:

1. **Agent Framework** — Which framework should power the agents? Options:
   - **n8n** (visual workflows, you may already have it)
   - **CrewAI** (Python, purpose-built for multi-agent teams)
   - **LangChain/LangGraph** (Python, highly flexible)
   - **AutoGen** (Microsoft, strong at agent-to-agent conversation)
   - **Custom** (direct API calls, full control)

2. **AI Model** — Which LLM should power the agents?
   - Claude (Anthropic API)
   - GPT-4o (OpenAI)
   - Local model (Ollama)?

3. **Migration Scope** — Single page or full multi-page site migrations?

4. **Source Site Access** — Should the system handle password-protected or JS-heavy SPAs (React/Vue sites), or only traditional HTML sites?

5. **Content Ownership** — Should ContentAgent copy images/media from the source directly, or just reference them? (Copyright implications for real migrations)

6. **Hosting** — Should this system run locally alongside your Docker Drupal stack, or in the cloud?

7. **Human-in-the-loop** — Should the user be able to intervene between agent cycles (approve each step) or should it run fully autonomously until done?
