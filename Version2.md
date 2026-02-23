# DrupalMind v2 — Summary of Changes

---

## New Features (7 Sprints)

| Sprint | Feature | What it does |
|---|---|---|
| 1 | **Visual Feedback Signal** | Playwright renders source and Drupal output side by side. Perceptual hash diff produces a 0–1 similarity score and diff image after every migration. |
| 2 | **Payload Validator** | Every JSON:API payload is checked before it leaves the agent layer. Any raw HTML, inline styles, or unknown component types are rejected and corrected before hitting Drupal. |
| 3 | **Empirical Component Discovery** | A new ProbeAgent tests every Drupal component and parameter by making real API calls and observing what renders. Builds a verified capability envelope stored in Redis — persists across migrations, re-probed when Drupal changes. |
| 4 | **Confidence-Scored Mapping** | A new MappingAgent explicitly maps each source element to the best available component, with a confidence score and fidelity estimate. Low-confidence decisions are flagged for human review before anything is built. |
| 5 | **Refinement Loops** | BuildAgent now refines each component placement using visual diff feedback (micro-loop, up to 5 iterations per component). After a full page is built, weak sections are re-mapped and rebuilt automatically (meso-loop). |
| 6 | **Gap Report & Human Review Gate** | Before anything publishes, a structured Gap Report lists every compromise made during migration with before/after screenshots. A human must approve or decide on each flagged item. Publish is blocked until all decisions are made. |
| 7 | **Cross-Migration Learning** | After each approved migration, QAAgent writes what worked — successful mappings, component tips, failure patterns — to a permanent global knowledge base. Every subsequent migration starts with this accumulated experience. |

---

## Agents

### Existing agents (unchanged role, some internal changes)

| Agent | Role | Changes in v2 |
|---|---|---|
| **OrchestratorAgent** | Coordinates the pipeline, streams progress to UI | Gains pause/resume around the human review gate; calls two new agents |
| **AnalyzerAgent** | Scrapes source site, extracts structure and content | Adds structured style token extraction; captures reference screenshots |
| **TrainAgent** | Loads Drupal knowledge for other agents | Simplified — reads ready-made envelopes from ProbeAgent instead of self-discovering |
| **BuildAgent** | Creates pages and components via JSON:API | Gains payload validator, reads mapping manifest, drives micro-loop |
| **ThemeAgent** | Applies visual design to Drupal theme | Consumes structured style tokens from AnalyzerAgent |
| **ContentAgent** | Migrates text and media into Drupal fields | Reads capability envelopes to apply field-level constraints proactively |
| **TestAgent** | Compares result to source | Unchanged; feeds into the Gap Report |
| **QAAgent** | Final quality check | Gains Gap Report output structure; gains macro-loop writer after publish |

### New agents

| Agent | Role | When it runs |
|---|---|---|
| **ProbeAgent** | Tests every Drupal component empirically. Discovers what each parameter accepts, what it rejects, how failures present, and which component combinations are stable. Writes capability envelopes to Redis. | Before TrainAgent. Background re-probe every 24h. |
| **MappingAgent** | Maps each source element to the best available component using the capability envelopes. Scores confidence and fidelity, identifies compromises, flags items for human review. Produces the mapping manifest BuildAgent follows. | Between TrainAgent and BuildAgent. |
| **VisualDiffAgent** | Renders source and Drupal output using Playwright. Computes perceptual hash similarity, breaks diff down by region, and returns actionable refinement instructions to BuildAgent. | After each component placement (micro-loop), after each full page (meso-loop), and at end of run. |

---

## Updated Process

```
┌─────────────────────────────────────────────────────────────────┐
│  BACKGROUND (continuous, decoupled from migrations)             │
│  ProbeAgent — probes all components, updates capability         │
│  envelopes in Redis every 24h or after Drupal updates           │
└─────────────────────────┬───────────────────────────────────────┘
                          │ envelopes ready before migration starts
                          ▼
User submits URL
          │
          ▼
OrchestratorAgent creates session
          │
          ├─► AnalyzerAgent
          │     scrapes source, extracts semantic element map,
          │     style tokens, content inventory, reference screenshots
          │
          ├─► TrainAgent
          │     reads ProbeAgent envelopes, formats Drupal
          │     knowledge for downstream agents
          │
          ├─► MappingAgent                               ← NEW
          │     maps each source element to best component
          │     with confidence score + fidelity estimate
          │     flags low-confidence items for human review
          │     produces mapping manifest + gap report draft
          │
          ├─► BuildAgent  ◄──────────────────────────────────────┐
          │     follows mapping manifest                          │
          │     for each component:                               │
          │       place component via JSON:API                    │ meso-loop
          │       [payload validator blocks raw HTML]             │ re-maps and
          │       VisualDiffAgent scores placement ──► refine ─┐  │ rebuilds weak
          │       micro-loop (up to 5 iterations)   ◄──────────┘  │ regions
          │     full page complete                                 │
          │     VisualDiffAgent scores full page ─────────────────┘
          │     (repeat until threshold met or alternatives exhausted)
          │
          ├─► ThemeAgent
          │     applies style tokens to Drupal theme
          │
          ├─► ContentAgent
          │     migrates content with field-level constraints
          │     from capability envelopes applied proactively
          │
          ├─► TestAgent
          │     link integrity, asset loading, WCAG 2.1 AA,
          │     no-raw-HTML check, JSON:API schema compliance
          │
          ├─► QAAgent
          │     compiles final Gap Report:
          │       every element · component used · fidelity score
          │       compromises made · before/after screenshots
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│  HUMAN REVIEW GATE  ← pipeline pauses here                      │
│  Reviewer sees Gap Report with screenshot pairs                 │
│  Per-item decision: Accept / Request alternative /              │
│                     Exclude / Manual build                      │
│  Publish button activates only when all items decided           │
└─────────────────────────┬───────────────────────────────────────┘
                          │ approved
                          ▼
                    Drupal publishes
                          │
                          ▼
                    QAAgent writes macro learnings      ← NEW
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  GLOBAL KNOWLEDGE BASE (Redis, permanent)                       │
│  Successful mapping patterns · Component configuration tips     │
│  Failure patterns · Fidelity benchmarks per element type        │
│  Consumed by MappingAgent on every future migration             │
└─────────────────────────────────────────────────────────────────┘
```

---

## What v1 built in one pass, v2 refines in three loops

| Loop | Scope | Trigger | Termination |
|---|---|---|---|
| **Micro** | Single component | After each placement | Score ≥ threshold or max iterations |
| **Meso** | Full page | After all components placed | Page score ≥ threshold or alternatives exhausted |
| **Macro** | All future migrations | After each approved publish | Permanent — accumulates indefinitely |