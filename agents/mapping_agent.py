"""
DrupalMind — MappingAgent
Maps each source element to the best available Drupal component using capability envelopes.
Assigns confidence scores and fidelity estimates.
Identifies compromises and flags low-confidence items for human review.
Produces the mapping manifest BuildAgent follows.
"""
import json
import asyncio
import logging
import time
from typing import Any, Optional
from base_agent import BaseAgent
from memory import memory as shared_memory

# Configure logging for MappingAgent
logger = logging.getLogger("drupalmind.mapping")


SYSTEM_PROMPT = """You are the MappingAgent for DrupalMind. Your job is to:
1. Read the site blueprint (source elements)
2. Read capability envelopes from ProbeAgent (what Drupal can do)
3. Read global knowledge base (past successful mappings)
4. Map each source element to the best available Drupal component
5. Assign confidence scores (0-1) and fidelity estimates
6. Flag low-confidence items for human review
7. Produce a mapping manifest for BuildAgent

For each source element, determine:
- Best matching Drupal component
- Confidence score (high: >0.8, medium: 0.5-0.8, low: <0.5)
- Any compromises needed (e.g., "no image carousel available, will use grid")
- Whether human review is needed

Store the mapping manifest in memory under key "mapping_manifest".
"""


# Default confidence thresholds
CONFIDENCE_THRESHOLD_HIGH = 0.8
CONFIDENCE_THRESHOLD_LOW = 0.5


class MappingAgent(BaseAgent):
    """Maps source elements to Drupal components with confidence scoring."""

    def __init__(self):
        super().__init__("mapping", "MappingAgent")

    async def create_mapping(self) -> dict:
        """
        Create mapping manifest from blueprint and capability envelopes.
        """
        await self.log("Creating mapping manifest...")
        
        # Log mapping start
        await self.log_extended("mapping_start", {
            "source": "blueprint",
        })
        
        blueprint = shared_memory.get_blueprint()
        if not blueprint:
            await self.log_error("No blueprint found - run AnalyzerAgent first")
            await self.log_extended("mapping_error", {"error": "No blueprint"})
            return {"error": "No blueprint"}

        # Get capability envelopes
        envelopes = self._get_all_envelopes()
        
        # Get global knowledge
        knowledge = shared_memory.get_global_knowledge()
        
        await self.log_data("mapping_inputs", {
            "blueprint_pages": len(blueprint.get("pages", [])),
            "blueprint_sections": len(blueprint.get("sections", [])),
            "available_envelopes": len(envelopes),
            "global_knowledge_mappings": len(knowledge.get("successful_mappings", [])),
        })
        
        result = await asyncio.to_thread(
            self._create_mapping_manifest, 
            blueprint, 
            envelopes,
            knowledge
        )
        
        # Store mapping manifest
        shared_memory.set_mapping_manifest(result)
        
        # Log detailed mapping for each element
        mappings = result.get("mappings", [])
        
        # Log all mappings in detail
        await self.log_extended("mapping_details", {
            "total_mappings": len(mappings),
        })
        
        # Log each mapping
        for i, mapping in enumerate(mappings[:20]):  # Log first 20 mappings in detail
            await self.log_data("mapping", {
                "index": i,
                "element_id": mapping.get("element_id"),
                "element_type": mapping.get("element_type"),
                "source_type": mapping.get("source_type"),
                "heading": mapping.get("heading", "")[:50],
                "title": mapping.get("title", "")[:50],
                "path": mapping.get("path", ""),
                "drupal_component": mapping.get("drupal_component"),
                "confidence": mapping.get("confidence"),
                "fidelity_estimate": mapping.get("fidelity_estimate"),
                "requires_review": mapping.get("requires_review"),
                "reasoning": mapping.get("reasoning", "")[:100],
                "compromises": [{
                    "type": c.get("type") if isinstance(c, dict) else str(c),
                    "description": (c.get("description", "")[:80] if isinstance(c, dict) else ""),
                } for c in mapping.get("compromises", [])],
            }, summary=f"{mapping.get('element_type')}: {mapping.get('source_type')} → {mapping.get('drupal_component')} ({mapping.get('confidence'):.0%})")
        
        if len(mappings) > 20:
            await self.log_data("mapping_remaining", {
                "count": len(mappings) - 20,
            }, summary=f"+ {len(mappings) - 20} more mappings")
        
        # Group mappings by Drupal component for overview
        component_counts = {}
        for m in mappings:
            comp = m.get("drupal_component", "unknown")
            component_counts[comp] = component_counts.get(comp, 0) + 1
        
        await self.log_data("mapping_by_component", {
            "components": component_counts,
        }, summary=f"Mappings by Drupal component")
        
        # Group mappings by source type
        source_type_counts = {}
        for m in mappings:
            st = m.get("source_type", "unknown")
            source_type_counts[st] = source_type_counts.get(st, 0) + 1
        
        await self.log_data("mapping_by_source_type", {
            "source_types": source_type_counts,
        }, summary=f"Mappings by source type")
        
        # Identify items needing review
        stats = result.get("statistics", {})
        low_confidence = result.get("review_items", [])
        
        # Log low confidence items specifically
        if low_confidence:
            await self.log_warning("Low confidence mappings detected", {
                "count": len(low_confidence),
                "items": [{
                    "element_id": lc.get("element_id"),
                    "source_type": lc.get("source_type"),
                    "drupal_component": lc.get("drupal_component"),
                    "confidence": lc.get("confidence"),
                } for lc in low_confidence[:10]],
            })
        
        # Log detailed mapping results
        await self.log_extended("mapping_complete", {
            "total_mappings": stats.get("total", 0),
            "high_confidence": stats.get("high_confidence", 0),
            "medium_confidence": stats.get("medium_confidence", 0),
            "low_confidence": stats.get("low_confidence", 0),
            "average_fidelity": stats.get("average_fidelity", 0),
            "requires_review": result.get("requires_review", False),
        })
        
        # Log metrics
        await self.log_metric("high_confidence_mappings", stats.get("high_confidence", 0), "", "mapping")
        await self.log_metric("low_confidence_mappings", stats.get("low_confidence", 0), "", "mapping")
        await self.log_metric("average_fidelity", stats.get("average_fidelity", 0) * 100, "%", "mapping")
        
        # Log check results
        if stats.get("low_confidence", 0) > 0:
            await self.log_check("Low confidence items", False, f"{stats.get('low_confidence', 0)} items need review", "warning")
        else:
            await self.log_check("All mappings confident", True, "No review needed", "success")
        
        await self.log_done(
            f"Mapping complete - {len(result.get('mappings', []))} elements mapped, "
            f"{len(low_confidence)} flagged for review"
        )
        
        return result

    def _get_all_envelopes(self) -> dict:
        """Get all capability envelopes from memory."""
        envelopes = {}
        envelope_keys = shared_memory.list_capability_envelopes()
        for key in envelope_keys:
            envelope = shared_memory.get_capability_envelope(key)
            if envelope:
                envelopes[key] = envelope
        return envelopes

    def _create_mapping_manifest(self, blueprint: dict, envelopes: dict, knowledge: dict) -> dict:
        """Create the full mapping manifest."""
        
        mappings = []
        sections = blueprint.get("sections", [])
        
        for section in sections:
            mapping = self._map_section(section, envelopes, knowledge)
            mappings.append(mapping)
        
        # Also map pages
        pages = blueprint.get("pages", [])
        for page in pages:
            mapping = self._map_page(page, envelopes, knowledge)
            mappings.append(mapping)
        
        # Calculate overall statistics
        high_conf = sum(1 for m in mappings if m.get("confidence", 0) >= CONFIDENCE_THRESHOLD_HIGH)
        medium_conf = sum(1 for m in mappings if CONFIDENCE_THRESHOLD_LOW <= m.get("confidence", 0) < CONFIDENCE_THRESHOLD_HIGH)
        low_conf = sum(1 for m in mappings if m.get("confidence", 0) < CONFIDENCE_THRESHOLD_LOW)
        
        avg_fidelity = 0
        if mappings:
            avg_fidelity = sum(m.get("fidelity_estimate", 0) for m in mappings) / len(mappings)
        
        return {
            "mappings": mappings,
            "statistics": {
                "total": len(mappings),
                "high_confidence": high_conf,
                "medium_confidence": medium_conf,
                "low_confidence": low_conf,
                "average_fidelity": avg_fidelity,
            },
            "requires_review": low_conf > 0,
            "review_items": [m for m in mappings if m.get("confidence", 1) < CONFIDENCE_THRESHOLD_LOW],
            "created_at": time.time(),
        }

    def _map_section(self, section: dict, envelopes: dict, knowledge: dict) -> dict:
        """Map a single section to a Drupal component."""
        
        section_type = section.get("type", "content")
        heading = section.get("heading", "")
        text_preview = section.get("text_preview", "")
        
        # Check global knowledge for successful mappings
        successful_mappings = knowledge.get("successful_mappings", [])
        learned_component = self._find_learned_mapping(section_type, successful_mappings)
        
        # Find best component from envelopes
        best_component = self._find_best_component(section_type, envelopes)
        
        # Calculate confidence
        confidence = 0.9  # Default high confidence
        if learned_component:
            confidence = 0.95  # Higher if we've done this before
        elif best_component:
            confidence = 0.8
        else:
            confidence = 0.5  # Lower if uncertain
        
        # Determine fidelity estimate
        fidelity_estimate = self._estimate_fidelity(section_type, best_component, envelopes)
        
        # Identify any compromises
        compromises = self._identify_compromises(section, best_component, envelopes)
        
        return {
            "element_id": f"section_{section.get('index', 0)}",
            "element_type": "section",
            "source_type": section_type,
            "heading": heading,
            "drupal_component": best_component or "basic_page",
            "confidence": confidence,
            "fidelity_estimate": fidelity_estimate,
            "compromises": compromises,
            "requires_review": confidence < CONFIDENCE_THRESHOLD_LOW,
            "reasoning": self._get_reasoning(section_type, best_component, learned_component),
        }

    def _map_page(self, page: dict, envelopes: dict, knowledge: dict) -> dict:
        """Map a page to a Drupal content type."""
        
        title = page.get("title", "")
        path = page.get("path", "/")
        content_type = page.get("content_type", "page")
        
        # Check global knowledge
        successful_mappings = knowledge.get("successful_mappings", [])
        
        # Determine content type
        drupal_type = "page"  # default
        confidence = 0.9
        
        if "article" in content_type.lower() or "blog" in content_type.lower() or "news" in content_type.lower():
            drupal_type = "article"
            confidence = 0.95
        elif "contact" in content_type.lower():
            drupal_type = "contact"  # if contact form content type exists
            confidence = 0.7
        
        return {
            "element_id": f"page_{path.replace('/', '_')}",
            "element_type": "page",
            "source_type": content_type,
            "title": title,
            "path": path,
            "drupal_component": drupal_type,
            "confidence": confidence,
            "fidelity_estimate": 0.9 if confidence > 0.8 else 0.6,
            "compromises": [],
            "requires_review": confidence < CONFIDENCE_THRESHOLD_LOW,
            "reasoning": f"Mapped to {drupal_type} based on URL path and content type",
        }

    def _find_learned_mapping(self, section_type: str, successful_mappings: list) -> Optional[str]:
        """Find a learned mapping from global knowledge base."""
        for mapping in reversed(successful_mappings):  # Most recent first
            if mapping.get("source_element") == section_type:
                return mapping.get("drupal_component")
        return None

    def _find_best_component(self, section_type: str, envelopes: dict) -> Optional[str]:
        """Find the best Drupal component for a section type."""
        
        # Mapping from source types to Drupal components
        type_to_component = {
            "hero": "page",
            "navigation": "menu_block",
            "features": "article",
            "about": "page",
            "blog": "article",
            "contact": "contact_form",
            "footer": "basic_block",
            "testimonials": "article",
            "team": "article",
            "pricing": "page",
            "content": "page",
            "header": "menu_block",
        }
        
        component = type_to_component.get(section_type)
        
        # Verify component exists in envelopes
        if component and component in envelopes:
            return component
        
        # Check for article (commonly available)
        if "article" in envelopes:
            return "article"
        
        # Fallback to page
        if "page" in envelopes:
            return "page"
        
        return None

    def _estimate_fidelity(self, section_type: str, component: Optional[str], envelopes: dict) -> float:
        """Estimate how well the component will match the source."""
        
        if not component or component not in envelopes:
            return 0.3  # Low fidelity if no matching component
        
        envelope = envelopes[component]
        
        # Check if component has necessary fields
        fields = envelope.get("fields", {})
        
        # High fidelity if all typical fields are available
        high_fidelity_fields = {
            "hero": ["body", "title"],
            "features": ["body", "title"],
            "blog": ["body", "title", "field_image"],
            "about": ["body", "title"],
        }
        
        required = high_fidelity_fields.get(section_type, ["title", "body"])
        available = list(fields.keys())
        
        has_required = all(f in available for f in required)
        
        if has_required:
            return 0.9
        elif "title" in available:
            return 0.7
        else:
            return 0.5

    def _identify_compromises(self, section: dict, component: Optional[str], envelopes: dict) -> list:
        """Identify what compromises will be needed."""
        
        compromises = []
        section_type = section.get("type", "")
        
        # Check for image handling
        if section.get("has_images") and component:
            envelope = envelopes.get(component, {})
            fields = envelope.get("fields", {})
            if "field_image" not in fields and "body" not in fields:
                compromises.append("No image field available - will include images in body HTML")
        
        # Check for complex layouts
        if section_type == "features":
            compromises.append("Complex feature grids simplified to basic list layout")
        
        if section_type == "hero":
            compromises.append("Hero section will use standard page with full-width body")
        
        return compromises

    def _get_reasoning(self, section_type: str, component: Optional[str], learned: Optional[str]) -> str:
        """Get human-readable reasoning for the mapping."""
        
        if learned:
            return f"Mapped to {component} based on past successful migration"
        elif component:
            return f"Mapped to {component} based on section type '{section_type}'"
        else:
            return f"No exact match found for '{section_type}', using default component"

    # ── Tools ─────────────────────────────────────────────────────

    def _tool_get_mapping_manifest(self) -> str:
        """Get the current mapping manifest."""
        manifest = shared_memory.get_mapping_manifest()
        if manifest:
            return json.dumps(manifest, indent=2)
        return "No mapping manifest found."

    def _tool_get_element_mapping(self, element_id: str) -> str:
        """Get mapping for a specific element."""
        mapping = shared_memory.get_mapping_for_element(element_id)
        if mapping:
            return json.dumps(mapping, indent=2)
        return f"No mapping found for element '{element_id}'"

    def _tool_list_review_items(self) -> str:
        """List all elements that need human review."""
        manifest = shared_memory.get_mapping_manifest()
        if not manifest:
            return "No mapping manifest found."
        
        review_items = manifest.get("review_items", [])
        return json.dumps(review_items, indent=2)
