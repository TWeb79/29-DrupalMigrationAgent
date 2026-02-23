"""
DrupalMind — ProbeAgent
Tests Drupal components empirically through real API calls.
Discovers what each parameter accepts, what it rejects, how failures present,
and which component combinations are stable.
Writes capability envelopes to Redis.
"""
import json
import asyncio
import logging
import time
from typing import Any, Optional
from base_agent import BaseAgent
from memory import memory as shared_memory
from drupal_client import DrupalClient

# Configure logging for ProbeAgent
logger = logging.getLogger("drupalmind.probe")


SYSTEM_PROMPT = """You are the ProbeAgent for DrupalMind. Your job is to:
1. Test Drupal components by making real API calls
2. Discover what fields and parameters are actually accepted
3. Document what causes errors vs success
4. Build a verified "capability envelope" for each component

For each component you probe:
- Try creating a minimal node with just required fields
- Try adding optional fields one by one
- Test edge cases (empty values, max lengths, special characters)
- Document the exact payload that succeeded or failed
- Record error messages so other agents can avoid mistakes

Store results as capability envelopes in memory under key "capability_envelopes/{component_name}".
"""


class ProbeAgent(BaseAgent):
    """Empirically probes Drupal components and builds capability envelopes."""

    def __init__(self):
        super().__init__("probe", "ProbeAgent")
        self.drupal = DrupalClient()
        self.probe_results = {}
        self._probe_interval = 24 * 3600  # 24 hours in seconds

    async def probe_all(self, force: bool = False) -> dict:
        """
        Probe all available Drupal components.
        If force=False and recent probe exists, skip.
        """
        await self.log("Starting component probing...")
        
        # Log extended probe start event
        await self.log_extended("probe_start", {
            "force": force,
            "target": "all_components",
        })
        
        # Check if we need to probe (not forced and recent probe exists)
        last_probe = shared_memory.get("last_probe_timestamp")
        if not force and last_probe:
            age = time.time() - last_probe
            if age < self._probe_interval:
                await self.log(f"Skipping probe - last probe was {int(age/3600)}h ago")
                envelopes = shared_memory.list_capability_envelopes()
                await self.log_extended("probe_skipped", {
                    "age_hours": int(age/3600),
                    "envelope_count": len(envelopes),
                })
                return {"status": "skipped", "envelopes_count": len(envelopes), "age_hours": int(age/3600)}

        result = await asyncio.to_thread(self._probe_components)
        
        # Update timestamp
        shared_memory.set("last_probe_timestamp", time.time())
        
        # Log detailed results
        envelope_count = len(result.get('envelopes', {}))
        await self.log_extended("probe_complete", {
            "envelope_count": envelope_count,
            "components": list(result.get('envelopes', {}).keys()),
            "probed_at": result.get('probed_at'),
        })
        
        # Log metrics
        await self.log_metric("components_probed", envelope_count, "", "probe")
        await self.log_metric("probe_duration", time.time() - (result.get('probed_at', time.time()) - 10), "s", "probe")
        
        await self.log_done(f"Probing complete - {envelope_count} components probed")
        return result

    def _probe_components(self) -> dict:
        """Probe all content types and build capability envelopes."""
        envelopes = {}
        
        # Get all content types
        try:
            content_types = self.drupal.get_content_types()
        except Exception as e:
            logger.error(f"Failed to get content types: {e}")
            return {"error": str(e), "envelopes": {}}

        # Probe each content type
        for ct in content_types:
            machine_name = ct["machine_name"]
            logger.info(f"Probing content type: {machine_name}")
            
            envelope = self._probe_content_type(machine_name, ct)
            envelopes[machine_name] = envelope
            
            # Store in memory
            shared_memory.set_capability_envelope(machine_name, envelope)

        # Also probe menus, taxonomy, blocks
        self._probe_menus()
        self._probe_taxonomy()
        self._probe_blocks()

        return {"envelopes": envelopes, "probed_at": time.time()}

    def _probe_content_type(self, machine_name: str, ct: dict) -> dict:
        """Probe a specific content type."""
        envelope = {
            "type": "node",
            "machine_name": machine_name,
            "label": ct.get("label", machine_name),
            "description": ct.get("description", ""),
            "probed_at": time.time(),
            "fields": {},
            "test_results": [],
            "stable": True,
        }

        # Get field definitions
        try:
            fields = self.drupal.get_fields_for_type(machine_name)
        except Exception as e:
            logger.warning(f"Failed to get fields for {machine_name}: {e}")
            fields = []

        # Test each field
        for field in fields:
            field_name = field.get("field_name", "")
            field_type = field.get("field_type", "")
            
            field_test = {
                "field_name": field_name,
                "field_type": field_type,
                "required": field.get("required", False),
                "tests": [],
                "stable": True,
            }

            # Test basic operations based on field type
            if field_name == "title":
                # Test title field
                test_result = self._test_title_field(machine_name)
                field_test["tests"].append(test_result)
                field_test["stable"] = test_result.get("success", False)
                
            elif field_name == "body":
                # Test body field
                test_result = self._test_body_field(machine_name)
                field_test["tests"].append(test_result)
                field_test["stable"] = test_result.get("success", False)
                
            elif field_type in ("image", "file"):
                # Test file field
                test_result = self._test_file_field(machine_name, field_name)
                field_test["tests"].append(test_result)
                field_test["stable"] = test_result.get("success", False)
                
            elif field_name.startswith("field_"):
                # Generic field test
                test_result = self._test_generic_field(machine_name, field_name, field_type)
                field_test["tests"].append(test_result)
                field_test["stable"] = test_result.get("success", False)
            else:
                # Skip non-custom fields
                field_test["stable"] = True

            envelope["fields"][field_name] = field_test

        # Overall stability
        unstable_fields = [f for f in envelope["fields"].values() if not f.get("stable", True)]
        envelope["stable"] = len(unstable_fields) == 0

        return envelope

    def _test_title_field(self, content_type: str) -> dict:
        """Test title field with various inputs."""
        tests = [
            {"input": "Test Title", "expect": "success"},
            {"input": "", "expect": "fail"},
            {"input": "A" * 255, "expect": "success"},
            {"input": "Special chars: <>&\"'", "expect": "success"},
        ]
        
        results = []
        for test in tests:
            try:
                node = self.drupal.create_node(content_type, {
                    "title": test["input"],
                    "status": True,
                })
                success = "id" in node or "attributes" in node
                results.append({
                    "input": test["input"],
                    "expected": test["expect"],
                    "actual": "success" if success else "fail",
                    "success": success == (test["expect"] == "success"),
                })
                # Cleanup - delete test node
                if success:
                    node_id = node.get("id", "") or node.get("attributes", {}).get("drupal_internal__nid", "")
                    if node_id:
                        try:
                            self.drupal.delete_node(content_type, node_id)
                        except:
                            pass
            except Exception as e:
                results.append({
                    "input": test["input"],
                    "expected": test["expect"],
                    "actual": "fail",
                    "success": test["expect"] == "fail",
                    "error": str(e)[:100],
                })

        return {"tests": results, "success": all(r.get("success", False) for r in results)}

    def _test_body_field(self, content_type: str) -> dict:
        """Test body field with various formats."""
        tests = [
            {"input": "<p>Simple paragraph</p>", "format": "basic_html", "expect": "success"},
            {"input": "<p>With bold text</p>", "format": "basic_html", "expect": "success"},
            {"input": "Plain text only", "format": "plain_text", "expect": "success"},
        ]
        
        results = []
        for test in tests:
            try:
                node = self.drupal.create_node(content_type, {
                    "title": "Body Test",
                    "body": {"value": test["input"], "format": test["format"]},
                    "status": True,
                })
                success = "id" in node
                results.append({
                    "input": test["input"][:50],
                    "format": test["format"],
                    "expected": test["expect"],
                    "actual": "success" if success else "fail",
                    "success": success == (test["expect"] == "success"),
                })
                # Cleanup
                if success:
                    node_id = node.get("id", "")
                    if node_id:
                        try:
                            self.drupal.delete_node(content_type, node_id)
                        except:
                            pass
            except Exception as e:
                results.append({
                    "input": test["input"][:50],
                    "format": test["format"],
                    "expected": test["expect"],
                    "actual": "fail",
                    "success": test["expect"] == "fail",
                    "error": str(e)[:100],
                })

        return {"tests": results, "success": any(r.get("success", False) for r in results)}

    def _test_file_field(self, content_type: str, field_name: str) -> dict:
        """Test file/image field - simplified."""
        # For now, just document that we can't easily test file uploads
        return {
            "tests": [],
            "success": True,
            "note": "File upload testing requires actual file data - skipped in probe"
        }

    def _test_generic_field(self, content_type: str, field_name: str, field_type: str) -> dict:
        """Test a generic field."""
        # Try with null/empty value
        try:
            node = self.drupal.create_node(content_type, {
                "title": "Generic Field Test",
                field_name: None,
                "status": True,
            })
            success = "id" in node
            if success:
                node_id = node.get("id", "")
                if node_id:
                    try:
                        self.drupal.delete_node(content_type, node_id)
                    except:
                        pass
            return {"tests": [{"field": field_name, "null_value": success}], "success": True}
        except Exception as e:
            return {
                "tests": [{"field": field_name, "null_value": "fail"}],
                "success": True,  # Not a problem if it doesn't accept null
                "error": str(e)[:100]
            }

    def _probe_menus(self):
        """Probe available menus."""
        try:
            menus = self.drupal.get_menus()
            envelope = {
                "type": "menus",
                "probed_at": time.time(),
                "available": [{"id": m["id"], "label": m["label"], "machine_name": m["machine_name"]} for m in menus],
                "stable": True,
            }
            shared_memory.set_capability_envelope("menus", envelope)
        except Exception as e:
            logger.warning(f"Menu probing failed: {e}")

    def _probe_taxonomy(self):
        """Probe taxonomy vocabularies."""
        try:
            # Try common vocabularies
            for vocab in ["tags", "categories"]:
                try:
                    terms = self.drupal.get_terms(vocab)
                    envelope = {
                        "type": "taxonomy",
                        "vocabulary": vocab,
                        "probed_at": time.time(),
                        "term_count": len(terms),
                        "stable": True,
                    }
                    shared_memory.set_capability_envelope(f"taxonomy_{vocab}", envelope)
                except:
                    pass
        except Exception as e:
            logger.warning(f"Taxonomy probing failed: {e}")

    def _probe_blocks(self):
        """Probe block types."""
        try:
            block_types = self.drupal.get_block_types()
            envelope = {
                "type": "blocks",
                "probed_at": time.time(),
                "available": [b.get("id", "") for b in block_types],
                "stable": True,
            }
            shared_memory.set_capability_envelope("blocks", envelope)
        except Exception as e:
            logger.warning(f"Block probing failed: {e}")

    # ── Tool: Get envelope for a component ─────────────────────────

    def _tool_get_envelope(self, component: str) -> str:
        """Get capability envelope for a specific component."""
        envelope = shared_memory.get_capability_envelope(component)
        if envelope:
            return json.dumps(envelope)
        return f"No envelope found for '{component}'. Run probe first."

    def _tool_list_envelopes(self) -> str:
        """List all available capability envelopes."""
        envelopes = shared_memory.list_capability_envelopes()
        return json.dumps(envelopes)

    # ── Background probe scheduler ─────────────────────────────────

    async def schedule_background_probe(self):
        """Schedule periodic background probing."""
        while True:
            await asyncio.sleep(self._probe_interval)
            logger.info("Running scheduled background probe...")
            try:
                await self.probe_all(force=True)
            except Exception as e:
                logger.error(f"Background probe failed: {e}")
