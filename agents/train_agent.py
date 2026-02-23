"""
DrupalMind — TrainAgent
Loads Drupal knowledge for other agents.
v2: Reads ready-made envelopes from ProbeAgent instead of self-discovering.
"""
import json
import asyncio
from base_agent import BaseAgent
from memory import memory as shared_memory


SYSTEM_PROMPT = """You are the TrainAgent for DrupalMind. Your job is to:
1. Read capability envelopes from ProbeAgent (key: "capability_envelopes/*")
2. Format this knowledge for downstream agents
3. Make the component knowledge easily accessible via tools

The capability envelopes contain verified information about what each component
can actually do - discovered through empirical testing by ProbeAgent.
"""


class TrainAgent(BaseAgent):
    """Loads Drupal knowledge from ProbeAgent envelopes."""
    
    def __init__(self):
        super().__init__("train", "TrainAgent")

    async def train(self, specific_component: str = None) -> dict:
        """
        Run training. Reads envelopes from ProbeAgent instead of self-discovery.
        """
        if specific_component:
            await self.log(f"Training on component: {specific_component}")
            result = await asyncio.to_thread(self._train_specific, specific_component)
        else:
            await self.log("Reading capability envelopes from ProbeAgent...")
            result = await asyncio.to_thread(self._load_from_probe)

        components = self.memory.list_components()
        await self.log_done(
            f"Training complete — {len(components)} components loaded from ProbeAgent",
            detail=f"Components: {', '.join(components[:8])}"
        )
        return result

    def _load_from_probe(self) -> dict:
        """
        Load component knowledge from ProbeAgent's capability envelopes.
        This is the v2 approach - use empirically tested envelopes.
        """
        knowledge = {}
        
        # Get all capability envelopes from ProbeAgent
        envelope_names = shared_memory.list_capability_envelopes()
        
        if not envelope_names:
            # No envelopes yet - fall back to direct discovery
            return self._fallback_discovery()
        
        # Transform envelopes into component knowledge
        for env_name in envelope_names:
            envelope = shared_memory.get_capability_envelope(env_name)
            if not envelope:
                continue
                
            # Convert envelope to component format for backward compatibility
            component_doc = self._envelope_to_component(envelope)
            
            # Store in both locations
            shared_memory.set_component(env_name, component_doc)
            knowledge[env_name] = component_doc
        
        # Also load menus and taxonomy from envelopes if available
        if "menus" in envelope_names:
            menus_envelope = shared_memory.get_capability_envelope("menus")
            if menus_envelope:
                shared_memory.set_component("menus", {
                    "type": "menus",
                    "description": "Drupal navigation menus",
                    "available": menus_envelope.get("available", []),
                    "usage": "Use menu_link_content API to add items",
                })
        
        # Store training summary
        summary = {
            "source": "probe_agent",
            "envelope_count": len(envelope_names),
            "content_types": [e for e in envelope_names if e not in ["menus", "blocks"]],
            "trained_at": "v2_from_envelopes",
        }
        self.memory.set("training_summary", summary)
        
        return knowledge

    def _envelope_to_component(self, envelope: dict) -> dict:
        """Convert a capability envelope to component knowledge format."""
        machine_name = envelope.get("machine_name", envelope.get("type", "unknown"))
        
        # Extract field information from envelope
        fields = envelope.get("fields", {})
        field_list = []
        for fname, fdata in fields.items():
            field_list.append({
                "field_name": fname,
                "field_type": fdata.get("field_type", "unknown"),
                "required": fdata.get("required", False),
                "stable": fdata.get("stable", True),
            })
        
        return {
            "type": envelope.get("type", "node"),
            "machine_name": machine_name,
            "label": envelope.get("label", machine_name),
            "description": envelope.get("description", ""),
            "fields": field_list,
            "stable": envelope.get("stable", True),
            "usage": self._generate_usage(machine_name, field_list),
            "api_create_endpoint": f"jsonapi/node/{machine_name}",
            "api_payload_example": self._build_example_payload(machine_name, field_list),
            "capability_envelope": envelope,  # Keep original envelope for reference
        }

    def _generate_usage(self, machine_name: str, fields: list) -> str:
        """Generate usage description from fields."""
        field_names = [f["field_name"] for f in fields]
        descriptions = {
            "article": "Use for blog posts, news items, team bios. Has title, body, image, tags fields.",
            "page": "Use for static pages like About, Services, Contact. Has title and body fields.",
        }
        desc = descriptions.get(machine_name, f"Content type '{machine_name}'.")
        if field_names:
            desc += f" Available fields: {', '.join(field_names[:8])}."
        return desc

    def _build_example_payload(self, machine_name: str, fields: list) -> dict:
        """Build example payload from field list."""
        attrs = {"title": f"Example {machine_name.title()}", "status": True}
        for field in fields:
            fname = field["field_name"]
            ftype = field.get("field_type", "")
            if fname == "body" or ftype == "text_with_summary":
                attrs["body"] = {"value": "<p>Example content</p>", "format": "basic_html"}
        return {
            "data": {
                "type": f"node--{machine_name}",
                "attributes": attrs,
            }
        }

    def _fallback_discovery(self) -> dict:
        """
        Fallback to direct discovery if no envelopes available.
        This is the original v1 behavior.
        """
        # Step 1: Get content types
        content_types = []
        try:
            content_types = self.drupal.get_content_types()
        except Exception as e:
            return {"error": str(e)}

        knowledge = {}
        for ct in content_types:
            machine_name = ct["machine_name"]
            doc = self._document_content_type(ct)
            self.memory.set_component(machine_name, doc)
            knowledge[machine_name] = doc

        # Document menus
        try:
            menus = self.drupal.get_menus()
            self.memory.set_component("menus", {
                "type": "menus",
                "description": "Drupal navigation menus",
                "available": menus,
            })
        except Exception:
            pass

        # Document taxonomy
        self.memory.set_component("taxonomy_tags", {
            "type": "taxonomy_term",
            "vocabulary": "tags",
            "description": "Tags vocabulary",
        })

        summary = {
            "content_types": [ct["machine_name"] for ct in content_types],
            "source": "fallback_discovery",
            "trained_at": "v1_fallback",
        }
        self.memory.set("training_summary", summary)
        return knowledge

    def _train_specific(self, component: str) -> dict:
        """Train on a specific component - check envelopes first, then fallback."""
        # Try envelopes first
        envelope = shared_memory.get_capability_envelope(component)
        if envelope:
            return self._envelope_to_component(envelope)
        
        # Fall back to direct discovery
        try:
            content_types = self.drupal.get_content_types()
            for ct in content_types:
                if ct["machine_name"] == component or ct["label"].lower() == component.lower():
                    doc = self._document_content_type(ct)
                    self.memory.set_component(ct["machine_name"], doc)
                    return doc
        except Exception:
            pass

        # Final fallback to LLM
        return self._document_via_llm(component)

    def _document_content_type(self, ct: dict) -> dict:
        """Document a content type (fallback method)."""
        machine_name = ct["machine_name"]
        
        # Get fields
        fields = []
        try:
            fields = self.drupal.get_fields_for_type(machine_name)
        except Exception:
            pass
        
        # Get existing nodes as examples
        examples = []
        try:
            nodes = self.drupal.get_nodes(machine_name, limit=2)
            for n in nodes:
                examples.append({
                    "id": n["id"],
                    "title": n["attributes"].get("title", ""),
                })
        except Exception:
            pass
        
        return {
            "type": "node",
            "machine_name": machine_name,
            "label": ct["label"],
            "description": ct.get("description", ""),
            "fields": fields,
            "examples": examples,
            "usage": self._describe_usage(machine_name, ct["label"], fields),
            "api_create_endpoint": f"jsonapi/node/{machine_name}",
            "api_payload_example": self._build_example_payload(machine_name, fields),
        }

    def _describe_usage(self, machine_name: str, label: str, fields: list) -> str:
        """Generate usage description."""
        field_names = [f["field_name"] for f in fields]
        descriptions = {
            "article": "Use for blog posts, news items, team bios. Has title, body, image, tags fields.",
            "page": "Use for static pages like About, Services, Contact. Has title and body fields.",
        }
        desc = descriptions.get(machine_name, f"Content type '{label}'.")
        if field_names:
            desc += f" Available fields: {', '.join(field_names[:8])}."
        return desc

    def _document_via_llm(self, component: str) -> dict:
        """Use LLM to document an unknown component."""
        messages = [
            {
                "role": "user",
                "content": (
                    f"Document the Drupal component '{component}' for use with JSON:API. "
                    "Return a JSON object with: type, machine_name, label, description, usage, "
                    "api_create_endpoint, api_payload_example. Return ONLY valid JSON."
                ),
            }
        ]
        try:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=1024,
                messages=messages,
            )
            text = response.content[0].text.strip()
            import re
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"```\s*$", "", text)
            doc = json.loads(text)
            self.memory.set_component(component, doc)
            return doc
        except Exception as e:
            doc = {
                "type": "unknown",
                "machine_name": component,
                "label": component,
                "description": f"Component documented via LLM fallback. Error: {e}",
                "usage": "Manually verify this component in Drupal admin.",
            }
            self.memory.set_component(component, doc)
            return doc
