"""
DrupalMind — Drupal JSON:API Client
Wraps all interactions with the Drupal REST/JSON:API endpoints.
"""
import os
import json
import base64
import requests
from typing import Any, Optional
from requests.auth import HTTPBasicAuth


class DrupalClient:
    def __init__(self):
        self.base_url = os.getenv("DRUPAL_API_URL", "http://drupal").rstrip("/")
        self.user = os.getenv("DRUPAL_API_USER", "apiuser")
        self.password = os.getenv("DRUPAL_API_PASS", "apiuser")
        self.auth = HTTPBasicAuth(self.user, self.password)
        self.jsonapi_headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
        }
        self.session = requests.Session()
        self.session.auth = self.auth

    def _jsonapi_url(self, path: str) -> str:
        return f"{self.base_url}/jsonapi/{path.lstrip('/')}"

    def _rest_url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    # ── Discovery ────────────────────────────────────────────

    def get_api_index(self) -> dict:
        """Get all available JSON:API resource types."""
        r = self.session.get(self._jsonapi_url(""), headers=self.jsonapi_headers)
        r.raise_for_status()
        return r.json()

    def get_content_types(self) -> list[dict]:
        """Return all Drupal content type definitions."""
        r = self.session.get(
            self._jsonapi_url("node_type/node_type"),
            headers=self.jsonapi_headers
        )
        r.raise_for_status()
        data = r.json().get("data", [])
        return [
            {
                "id": ct["id"],
                "machine_name": ct["attributes"]["drupal_internal__type"],
                "label": ct["attributes"]["name"],
                "description": ct["attributes"].get("description", ""),
            }
            for ct in data
        ]

    def get_fields_for_type(self, content_type: str) -> list[dict]:
        """Return field definitions for a content type."""
        r = self.session.get(
            self._jsonapi_url(f"field_config/field_config"),
            params={"filter[entity_type]": "node", "filter[bundle]": content_type},
            headers=self.jsonapi_headers
        )
        if r.status_code != 200:
            return []
        data = r.json().get("data", [])
        return [
            {
                "field_name": f["attributes"].get("field_name", ""),
                "label": f["attributes"].get("label", ""),
                "field_type": f["attributes"].get("field_type", ""),
                "required": f["attributes"].get("required", False),
            }
            for f in data
        ]

    def get_block_types(self) -> list[dict]:
        """Return all block content types."""
        r = self.session.get(
            self._jsonapi_url("block_content_type/block_content_type"),
            headers=self.jsonapi_headers
        )
        if r.status_code != 200:
            return []
        return r.json().get("data", [])

    def get_views(self) -> list[dict]:
        """Return all Views."""
        r = self.session.get(
            self._jsonapi_url("view/view"),
            headers=self.jsonapi_headers
        )
        if r.status_code != 200:
            return []
        return [
            {
                "id": v["id"],
                "label": v["attributes"].get("label", ""),
                "machine_name": v["attributes"].get("drupal_internal__id", ""),
            }
            for v in r.json().get("data", [])
        ]

    def get_menus(self) -> list[dict]:
        """Return all menus."""
        r = self.session.get(
            self._jsonapi_url("menu/menu"),
            headers=self.jsonapi_headers
        )
        if r.status_code != 200:
            return []
        return [
            {
                "id": m["id"],
                "label": m["attributes"].get("label", ""),
                "machine_name": m["attributes"].get("drupal_internal__id", ""),
            }
            for m in r.json().get("data", [])
        ]

    # ── Nodes (Content) ──────────────────────────────────────

    def get_nodes(self, content_type: str, limit: int = 50) -> list[dict]:
        r = self.session.get(
            self._jsonapi_url(f"node/{content_type}"),
            params={"page[limit]": limit},
            headers=self.jsonapi_headers
        )
        if r.status_code != 200:
            return []
        return r.json().get("data", [])

    def create_node(self, content_type: str, attributes: dict, relationships: dict = None) -> dict:
        payload = {
            "data": {
                "type": f"node--{content_type}",
                "attributes": attributes,
            }
        }
        if relationships:
            payload["data"]["relationships"] = relationships

        r = self.session.post(
            self._jsonapi_url(f"node/{content_type}"),
            json=payload,
            headers=self.jsonapi_headers
        )
        if not r.ok:
            raise Exception(f"Failed to create node: {r.status_code} {r.text[:500]}")
        return r.json().get("data", {})

    def update_node(self, content_type: str, node_id: str, attributes: dict) -> dict:
        payload = {
            "data": {
                "type": f"node--{content_type}",
                "id": node_id,
                "attributes": attributes,
            }
        }
        r = self.session.patch(
            self._jsonapi_url(f"node/{content_type}/{node_id}"),
            json=payload,
            headers=self.jsonapi_headers
        )
        if not r.ok:
            raise Exception(f"Failed to update node: {r.status_code} {r.text[:500]}")
        return r.json().get("data", {})

    def delete_node(self, content_type: str, node_id: str) -> bool:
        r = self.session.delete(
            self._jsonapi_url(f"node/{content_type}/{node_id}"),
            headers=self.jsonapi_headers
        )
        return r.status_code == 204

    def get_node_by_id(self, content_type: str, node_id: str) -> Optional[dict]:
        r = self.session.get(
            self._jsonapi_url(f"node/{content_type}/{node_id}"),
            headers=self.jsonapi_headers
        )
        if r.status_code != 200:
            return None
        return r.json().get("data")

    # ── Menu Items ────────────────────────────────────────────

    def create_menu_item(self, menu_id: str, title: str, url: str, weight: int = 0) -> dict:
        payload = {
            "data": {
                "type": "menu_link_content--menu_link_content",
                "attributes": {
                    "title": title,
                    "link": {"uri": f"internal:{url}"},
                    "menu_name": menu_id,
                    "weight": weight,
                    "enabled": True,
                }
            }
        }
        r = self.session.post(
            self._jsonapi_url("menu_link_content/menu_link_content"),
            json=payload,
            headers=self.jsonapi_headers
        )
        if not r.ok:
            raise Exception(f"Failed to create menu item: {r.status_code} {r.text[:300]}")
        return r.json().get("data", {})

    def get_menu_items(self, menu_id: str) -> list[dict]:
        r = self.session.get(
            self._jsonapi_url("menu_link_content/menu_link_content"),
            params={"filter[menu_name]": menu_id},
            headers=self.jsonapi_headers
        )
        if r.status_code != 200:
            return []
        return r.json().get("data", [])

    # ── Media / Files ─────────────────────────────────────────

    def upload_file(self, filename: str, file_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[dict]:
        """Upload a binary file and return the file entity."""
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Disposition": f'file; filename="{filename}"',
            "Accept": "application/vnd.api+json",
        }
        r = self.session.post(
            self._jsonapi_url("media/image/field_media_image"),
            data=file_bytes,
            headers=headers
        )
        if not r.ok:
            return None
        return r.json().get("data")

    def create_media_image(self, name: str, file_id: str) -> Optional[dict]:
        payload = {
            "data": {
                "type": "media--image",
                "attributes": {"name": name},
                "relationships": {
                    "field_media_image": {
                        "data": {"type": "file--file", "id": file_id}
                    }
                }
            }
        }
        r = self.session.post(
            self._jsonapi_url("media/image"),
            json=payload,
            headers=self.jsonapi_headers
        )
        if not r.ok:
            return None
        return r.json().get("data")

    # ── Taxonomy ──────────────────────────────────────────────

    def create_term(self, vocabulary: str, name: str, description: str = "") -> dict:
        payload = {
            "data": {
                "type": f"taxonomy_term--{vocabulary}",
                "attributes": {
                    "name": name,
                    "description": {"value": description, "format": "plain_text"},
                }
            }
        }
        r = self.session.post(
            self._jsonapi_url(f"taxonomy_term/{vocabulary}"),
            json=payload,
            headers=self.jsonapi_headers
        )
        if not r.ok:
            raise Exception(f"Failed to create term: {r.status_code} {r.text[:300]}")
        return r.json().get("data", {})

    def get_terms(self, vocabulary: str) -> list[dict]:
        r = self.session.get(
            self._jsonapi_url(f"taxonomy_term/{vocabulary}"),
            headers=self.jsonapi_headers
        )
        if r.status_code != 200:
            return []
        return r.json().get("data", [])

    # ── Custom CSS Block ──────────────────────────────────────

    def create_custom_block(self, block_type: str, info: str, body: str, format: str = "full_html") -> dict:
        payload = {
            "data": {
                "type": f"block_content--{block_type}",
                "attributes": {
                    "info": info,
                    "body": {"value": body, "format": format},
                }
            }
        }
        r = self.session.post(
            self._jsonapi_url(f"block_content/{block_type}"),
            json=payload,
            headers=self.jsonapi_headers
        )
        if not r.ok:
            raise Exception(f"Failed to create block: {r.status_code} {r.text[:300]}")
        return r.json().get("data", {})

    # ── Utility ───────────────────────────────────────────────

    def health_check(self) -> bool:
        try:
            r = self.session.get(
                self._jsonapi_url(""),
                headers=self.jsonapi_headers,
                timeout=5
            )
            return r.status_code == 200
        except Exception:
            return False

    def get_site_url(self) -> str:
        """Return the public URL (from the host's perspective)."""
        return os.getenv("DRUPAL_PUBLIC_URL", "http://localhost:5500")
