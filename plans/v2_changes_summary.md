# DrupalMind v2 - Analyse der erforderlichen Änderungen

## Zusammenfassung der Version 2 Anforderungen

Basierend auf der Analyse von `Version2.md` und dem bestehenden Code in `agents/`, sind folgende Änderungen erforderlich:

---

## 1. Fehlende Agenten (3 neue Agenten erstellen)

### 1.1 ProbeAgent
- **Rolle**: Testet empirisch jede Drupal-Komponente durch echte API-Aufrufe
- **Funktion**: Entdeckt was jeder Parameter akzeptiert, was abgelehnt wird, wie Fehler präsentiert werden, welche Komponentenkombinationen stabil sind
- **Ausgabe**: Capability Envelopes in Redis speichern
- **Zeitpunkt**: Vor TrainAgent, Hintergrund-Re-Probe alle 24h

### 1.2 MappingAgent
- **Rolle**: Ordnet jedes Quellelement der besten verfügbaren Komponente zu
- **Funktion**: Vergibt Confidence-Scores und Fidelity-Schätzungen, identifiziert Kompromisse, markiert Items für menschliche Prüfung
- **Ausgabe**: Mapping Manifest für BuildAgent, Gap Report Entwurf
- **Zeitpunkt**: Zwischen TrainAgent und BuildAgent

### 1.3 VisualDiffAgent
- **Rolle**: Rendert Quelle und Drupal-Ausgabe mit Playwright
- **Funktion**: Berechnet Perceptual Hash Ähnlichkeit, teilt Diff nach Regionen auf, gibt umsetzbare Verfeinerungsanweisungen zurück
- **Zeitpunkt**: Nach jeder Komponentenplatzierung (Micro-Loop), nach jeder vollen Seite (Meso-Loop), am Ende des Laufs

---

## 2. Änderungen an bestehenden Agenten

### 2.1 OrchestratorAgent
**Datei**: `agents/orchestrator.py`

| Änderung | Beschreibung |
|----------|--------------|
| **BUILD_PHASES erweitern** | 3 neue Phasen einfügen: Probe, Mapping, Human Review |
| **Neue Agenten instanziieren** | ProbeAgent, MappingAgent, VisualDiffAgent hinzufügen |
| **Pipeline erweitern** | Vor TrainAgent: ProbeAgent aufrufen |
| **Pipeline erweitern** | Nach TrainAgent: MappingAgent aufrufen |
| **Human Review Gate** | Pause/Resume Funktionalität einbauen |
| **VisualDiff integrieren** | Nach BuildAgent aufrufen |

**Neue BUILD_PHASES:**
```python
BUILD_PHASES = [
    {"id": 1, "section": "Probe",       "task": "Test Drupal components empirically", "agent": "probe"},
    {"id": 2, "section": "Discovery",  "task": "Scrape & analyze source site",       "agent": "analyzer"},
    {"id": 3, "section": "Knowledge",  "task": "Discover Drupal components",        "agent": "train"},
    {"id": 4, "section": "Mapping",    "task": "Map source to components",         "agent": "mapping"},
    {"id": 5, "section": "Build",      "task": "Build site with refinement loops",  "agent": "build"},
    {"id": 6, "section": "Theme",      "task": "Apply design tokens & custom CSS", "agent": "theme"},
    {"id": 7, "section": "Content",    "task": "Migrate text & media content",     "agent": "content"},
    {"id": 8, "section": "Verify",     "task": "Compare built site to source",      "agent": "test"},
    {"id": 9, "section": "QA",         "task": "Final quality checks + Gap Report","agent": "qa"},
    {"id": 10, "section": "Review",    "task": "Human review gate",                "agent": "orchestrator"},
    {"id": 11, "section": "Publish",   "task": "Publish + write learnings",         "agent": "orchestrator"},
]
```

### 2.2 AnalyzerAgent
**Datei**: `agents/analyzer.py`

| Änderung | Beschreibung |
|----------|--------------|
| **Strukturierte Style Token Extraktion** | Design-Tokens müssen strukturiert ausgegeben werden |
| **Referenz-Screenshots** | Screenshots der Quellseite für späteren Vergleich erstellen |

### 2.3 TrainAgent
**Datei**: `agents/train_agent.py`

| Änderung | Beschreibung |
|----------|--------------|
| **Vereinfachung** | Liest statt Selbst-Discovery die Envelopes von ProbeAgent |
| **Keine API-Discovery mehr** | Entferne `_train_all()` Logik |
| **Neu**: Envelope-Reader | Liest `capability_envelopes` aus Redis |

### 2.4 BuildAgent
**Datei**: `agents/build_agent.py`

| Änderung | Beschreibung |
|----------|--------------|
| **Payload Validator** | Prüft JSON:API Payload vor dem Senden - lehnt raw HTML, inline styles, unbekannte Komponenten ab |
| **Mapping Manifest lesen** | Liest Mapping von MappingAgent |
| **Micro-Loop** | Verfeinerung mit bis zu 5 Iterationen pro Komponente |
| **Meso-Loop** | Nach Seitenbau: schwache Bereiche neu mappen und rebuilden |
| **VisualDiff Integration** | Ruft VisualDiffAgent nach jeder Platzierung auf |

### 2.5 ThemeAgent
**Datei**: `agents/agents.py` (ThemeAgent)

| Änderung | Beschreibung |
|----------|--------------|
| **Strukturierte Style Tokens konsumieren** | Liest strukturierte Tokens von AnalyzerAgent |

### 2.6 ContentAgent
**Datei**: `agents/agents.py` (ContentAgent)

| Änderung | Beschreibung |
|----------|--------------|
| **Capability Envelope Nutzung** | Liest Envelopes von ProbeAgent für Feld-Level-Constraints |

### 2.7 TestAgent
**Datei**: `agents/agents.py` (TestAgent)

| Änderung | Beschreibung |
|----------|--------------|
| **Unverändert** | Feed-in für Gap Report bleibt |

### 2.8 QAAgent
**Datei**: `agents/agents.py` (QAAgent)

| Änderung | Beschreibung |
|----------|--------------|
| **Gap Report Struktur** | Gap Report mit allen Elementen, verwendeter Komponente, Fidelity-Score |
| **Before/After Screenshots** | Screenshot-Paare in Report |
| **Macro-Loop Writer** | Nach Freigabe: schreibt Learnings in Global Knowledge Base |

---

## 3. Neue Features (7 Sprints)

| Sprint | Feature | Implementierungsort |
|--------|---------|---------------------|
| 1 | **Visual Feedback Signal** | VisualDiffAgent + BuildAgent Micro-Loop |
| 2 | **Payload Validator** | BuildAgent - neue Validierungsmethode |
| 3 | **Empirical Component Discovery** | ProbeAgent - neuer Agent |
| 4 | **Confidence-Scored Mapping** | MappingAgent - neuer Agent |
| 5 | **Refinement Loops** | BuildAgent - Micro/Meso-Loop implementierung |
| 6 | **Gap Report & Human Review Gate** | QAAgent + Orchestrator |
| 7 | **Cross-Migration Learning** | QAAgent + Memory Store Erweiterung |

---

## 4. Memory Store Erweiterungen

**Datei**: `agents/memory.py`

Neue Keys hinzufügen:
- `capability_envelopes/*` - ProbeAgent Envelopes
- `mapping_manifest` - MappingAgent Ausgabe
- `gap_report` - QAAgent Gap Report
- `global_knowledge_base` - Cross-Migration Learnings
- `visual_diff_results` - VisualDiffAgent Ergebnisse

---

## 5. Prozess-Änderungen (Drei-Schleifen-System)

### Micro-Loop
- **Scope**: Einzelne Komponente
- **Trigger**: Nach jeder Platzierung
- **Termination**: Score ≥ Threshold oder max 5 Iterationen

### Meso-Loop
- **Scope**: Volle Seite
- **Trigger**: Nach allen Komponenten platziert
- **Termination**: Page Score ≥ Threshold oder Alternativen erschöpft

### Macro-Loop
- **Scope**: Alle zukünftigen Migrationen
- **Trigger**: Nach jeder genehmigten Veröffentlichung
- **Termination**: Permanent - sammelt unbegrenzt

---

## 6. Abhängigkeiten (requirements.txt)

Neue Dependencies hinzufügen:
- `playwright` - Für VisualDiffAgent
- `imagehash` - Für Perceptual Hash Berechnung
- `Pillow` - Bildverarbeitung

---

## 7. Priorisierung der Implementierung

### Phase 1: Foundation
1. Memory Store erweitern
2. ProbeAgent erstellen
3. Orchestrator: Phase 1 (Probe) einfügen

### Phase 2: Mapping
4. MappingAgent erstellen
5. Orchestrator: Phase 4 (Mapping) einfügen

### Phase 3: Visual Feedback
6. VisualDiffAgent erstellen
7. BuildAgent: Payload Validator
8. BuildAgent: Micro-Loop

### Phase 4: Refinement
9. BuildAgent: Meso-Loop
10. AnalyzerAgent: Style Tokens + Screenshots

### Phase 5: Quality
11. QAAgent: Gap Report
12. Orchestrator: Human Review Gate
13. QAAgent: Macro-Loop Writer

---

## 8. Datei-Übersicht der Änderungen

| Datei | Aktion | Änderung |
|-------|--------|----------|
| `agents/probe_agent.py` | **NEU** | ProbeAgent erstellen |
| `agents/mapping_agent.py` | **NEU** | MappingAgent erstellen |
| `agents/visual_diff_agent.py` | **NEU** | VisualDiffAgent erstellen |
| `agents/orchestrator.py` | MODIFY | Phasen erweitern, neue Agents einbinden |
| `agents/analyzer.py` | MODIFY | Style Token Struktur + Screenshots |
| `agents/train_agent.py` | MODIFY |vereinfachen, Envelope-Reader |
| `agents/build_agent.py` | MODIFY | Payload Validator + Loops |
| `agents/agents.py` | MODIFY | QAAgent erweitern |
| `agents/memory.py` | MODIFY | Neue Keys |
| `agents/requirements.txt` | MODIFY | Neue Dependencies |
