"""
DrupalMind — TrainAgent
Discovers all available Drupal components, tests their parameters,
and maintains the Component Knowledge Base in shared memory.
"""
import json
import asyncio
from base_agent import BaseAgent


SYSTEM_PROMPT = """You are the TrainAgent for DrupalMind. Your job is to:
1. Discover all available Drupal content types, fields, and components via the API
2. Document each component with its capabilities, fields, and example usage
3. Store this knowledge in shared memory for other agents to use

Be systematic. For each content type, document:
- Machine name
- Available fields and their types
- What kind of content it's good for
- Example API payload to create a node

Use the available tools to explore the Drupal API and build comprehensive documentation.
Store results under memory key "components/{content_type_name}".
"""


class TrainAgent(BaseAgent):
    def __init__(self):
        super().__init__("train", "TrainAgent")

    async def train(self, specific_component: str = None) -> dict:
        """
        Run training. If specific_component is given, only train that one.
        Otherwise do a full discovery pass.
        """
        if specific_component:
            await self.log(f"Training on component: {specific_component}")
            result = await asyncio.to_thread(self._train_specific, specific_component)
        else:
            await self.log("Starting full component discovery...")
            result = await asyncio.to_thread(self._train_all)

        components = self.memory.list_components()
        await self.log_done(
            f"Training complete — {len(components)} components documented",
            detail=f"Components: {', '.join(components[:8])}"
        )
        return result

    def _train_all(self) -> dict:
        """Discover all Drupal components and document them."""
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

        # Step 2: Document menus
        try:
            menus = self.drupal.get_menus()
            self.memory.set_component("menus", {
                "type": "menus",
                "description": "Drupal navigation menus",
                "available": menus,
                "usage": "Use menu_link_content API to add items. Menu machine names: " + ", ".join(m["machine_name"] for m in menus),
                "api_example": {
                    "endpoint": "jsonapi/menu_link_content/menu_link_content",
                    "payload": {
                        "data": {
                            "type": "menu_link_content--menu_link_content",
                            "attributes": {
                                "title": "My Page",
                                "link": {"uri": "internal:/my-page"},
                                "menu_name": "main",
                                "weight": 0,
                                "enabled": True,
                            }
                        }
                    }
                }
            })
        except Exception:
            pass

        # Step 3: Document taxonomy
        self.memory.set_component("taxonomy_tags", {
            "type": "taxonomy_term",
            "vocabulary": "tags",
            "description": "Tags vocabulary for categorizing articles",
            "usage": "Create terms then reference them in article nodes via field_tags relationship",
            "api_example": {
                "endpoint": "jsonapi/taxonomy_term/tags",
                "payload": {
                    "data": {
                        "type": "taxonomy_term--tags",
                        "attributes": {"name": "My Tag"}
                    }
                }
            }
        })

        # Step 4: Store capability summary
        summary = {
            "content_types": [ct["machine_name"] for ct in content_types],
            "menus": True,
            "taxonomy": True,
            "media": True,
            "blocks": True,
            "trained_at": "initial",
        }
        self.memory.set("training_summary", summary)
        return knowledge

    def _train_specific(self, component: str) -> dict:
        """Document a specific component."""
        try:
            # Try to find it as a content type
            content_types = self.drupal.get_content_types()
            for ct in content_types:
                if ct["machine_name"] == component or ct["label"].lower() == component.lower():
                    doc = self._document_content_type(ct)
                    self.memory.set_component(ct["machine_name"], doc)
                    return doc
        except Exception:
            pass

        # Fall back to LLM-based documentation
        return self._document_via_llm(component)

    def _document_content_type(self, ct: dict) -> dict:
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

        # Build documentation
        doc = {
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
        return doc

    def _describe_usage(self, machine_name: str, label: str, fields: list) -> str:
        field_names = [f["field_name"] for f in fields]
        descriptions = {
            "article": "Use for blog posts, news items, team bios. Has title, body, image, tags fields.",
            "page": "Use for static pages like About, Services, Contact. Has title and body fields.",
        }
        desc = descriptions.get(machine_name, f"Content type '{label}'.")
        if field_names:
            desc += f" Available fields: {', '.join(field_names[:8])}."
        return desc

    def _build_example_payload(self, machine_name: str, fields: list) -> dict:
        attrs: dict = {"title": f"Example {machine_name.title()}", "status": True}
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
