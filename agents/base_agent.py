"""
DrupalMind — Base Agent
All agents inherit from this. Provides:
 - Anthropic tool-use loop
 - Async logging with WebSocket push
 - Shared memory and Drupal client access
"""
import os
import json
import asyncio
from typing import Any, Callable, Optional
import anthropic

from memory import memory as shared_memory
from drupal_client import DrupalClient


class BaseAgent:
    MODEL = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
    MAX_TOKENS = 4096
    MAX_TOOL_ITERATIONS = 20

    def __init__(self, agent_key: str, label: str):
        self.agent_key = agent_key      # short id used in log events e.g. "build"
        self.label = label              # display name e.g. "BuildAgent"
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.drupal = DrupalClient()
        self.memory = shared_memory
        self._log_cb: Optional[Callable] = None  # async callback → WebSocket

    # ── Logging ───────────────────────────────────────────────

    def set_log_callback(self, cb: Callable):
        self._log_cb = cb

    async def log(self, message: str, status: str = "active", detail: str = ""):
        if self._log_cb:
            await self._log_cb({
                "type": "log",
                "agent": self.agent_key,
                "message": message,
                "status": status,
                "detail": detail,
            })
        else:
            print(f"[{self.label}] {message}")

    async def log_done(self, message: str, detail: str = ""):
        await self.log(message, status="done", detail=detail)

    async def log_error(self, message: str, detail: str = ""):
        await self.log(message, status="error", detail=detail)

    # ── Tool-use loop ─────────────────────────────────────────

    def call_llm_with_tools(
        self,
        system: str,
        messages: list,
        tools: list,
        max_iterations: int = None,
    ) -> str:
        """
        Synchronous tool-use loop.
        Call from async code via asyncio.to_thread().
        """
        iterations = max_iterations or self.MAX_TOOL_ITERATIONS
        for _ in range(iterations):
            kwargs = dict(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=system,
                messages=messages,
            )
            if tools:
                kwargs["tools"] = tools

            response = self.client.messages.create(**kwargs)

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        try:
                            result = self._dispatch_tool(block.name, block.input)
                        except Exception as e:
                            result = f"ERROR: {e}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result)[:8000],
                        })
                messages.append({"role": "user", "content": tool_results})
            else:
                break
        return "Agent loop ended without final response"

    def _dispatch_tool(self, name: str, inputs: dict) -> Any:
        """Route tool calls to methods. Override / extend in subclasses."""
        method = getattr(self, f"_tool_{name}", None)
        if method:
            return method(**inputs)
        return f"Unknown tool: {name}"

    # ── Common tools available to all agents ─────────────────

    def _tool_memory_read(self, key: str) -> Any:
        val = self.memory.get(key)
        return json.dumps(val) if val is not None else "null"

    def _tool_memory_write(self, key: str, value: Any) -> str:
        self.memory.set(key, value)
        return f"Written: {key}"

    def _tool_memory_list(self, prefix: str = "") -> str:
        return json.dumps(self.memory.list_keys(prefix))

    def _tool_drupal_health(self) -> str:
        ok = self.drupal.health_check()
        return "Drupal API is reachable" if ok else "Drupal API is NOT reachable"

    def _tool_get_content_types(self) -> str:
        try:
            cts = self.drupal.get_content_types()
            return json.dumps(cts)
        except Exception as e:
            return f"ERROR: {e}"

    def _tool_get_nodes(self, content_type: str, limit: int = 10) -> str:
        try:
            nodes = self.drupal.get_nodes(content_type, limit)
            simplified = [
                {
                    "id": n["id"],
                    "title": n["attributes"].get("title", ""),
                    "status": n["attributes"].get("status", False),
                    "path": n["attributes"].get("path", {}).get("alias", ""),
                }
                for n in nodes
            ]
            return json.dumps(simplified)
        except Exception as e:
            return f"ERROR: {e}"

    def _tool_create_article(self, title: str, body: str, summary: str = "") -> str:
        try:
            node = self.drupal.create_node("article", {
                "title": title,
                "body": {"value": body, "format": "basic_html", "summary": summary},
                "status": True,
                "promote": True,
            })
            return json.dumps({"id": node["id"], "title": title})
        except Exception as e:
            return f"ERROR: {e}"

    def _tool_create_page(self, title: str, body: str, path_alias: str = "") -> str:
        try:
            attrs: dict = {
                "title": title,
                "body": {"value": body, "format": "full_html"},
                "status": True,
            }
            if path_alias:
                attrs["path"] = {"alias": path_alias}
            node = self.drupal.create_node("page", attrs)
            return json.dumps({"id": node["id"], "title": title, "path": path_alias})
        except Exception as e:
            return f"ERROR: {e}"

    def _tool_create_menu_item(self, menu_id: str, title: str, url: str, weight: int = 0) -> str:
        try:
            item = self.drupal.create_menu_item(menu_id, title, url, weight)
            return json.dumps({"id": item["id"], "title": title})
        except Exception as e:
            return f"ERROR: {e}"

    def _tool_get_menus(self) -> str:
        try:
            return json.dumps(self.drupal.get_menus())
        except Exception as e:
            return f"ERROR: {e}"

    # ── Common tool schemas ───────────────────────────────────

    COMMON_TOOLS = [
        {
            "name": "memory_read",
            "description": "Read a value from shared agent memory by key.",
            "input_schema": {
                "type": "object",
                "properties": {"key": {"type": "string", "description": "Memory key to read"}},
                "required": ["key"],
            },
        },
        {
            "name": "memory_write",
            "description": "Write a value to shared agent memory.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"description": "Value to store (any JSON)"},
                },
                "required": ["key", "value"],
            },
        },
        {
            "name": "memory_list",
            "description": "List memory keys, optionally filtered by prefix.",
            "input_schema": {
                "type": "object",
                "properties": {"prefix": {"type": "string", "default": ""}},
            },
        },
        {
            "name": "drupal_health",
            "description": "Check if the Drupal API is reachable.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "get_content_types",
            "description": "Get all Drupal content types.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "get_nodes",
            "description": "Get nodes of a content type.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "content_type": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["content_type"],
            },
        },
        {
            "name": "create_article",
            "description": "Create a Drupal article node.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string", "description": "HTML body content"},
                    "summary": {"type": "string"},
                },
                "required": ["title", "body"],
            },
        },
        {
            "name": "create_page",
            "description": "Create a Drupal basic page node.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string", "description": "HTML body content"},
                    "path_alias": {"type": "string", "description": "URL alias e.g. /about"},
                },
                "required": ["title", "body"],
            },
        },
        {
            "name": "create_menu_item",
            "description": "Add an item to a Drupal navigation menu.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "menu_id": {"type": "string", "description": "Menu machine name e.g. main"},
                    "title": {"type": "string"},
                    "url": {"type": "string", "description": "Internal path e.g. /about"},
                    "weight": {"type": "integer", "default": 0},
                },
                "required": ["menu_id", "title", "url"],
            },
        },
        {
            "name": "get_menus",
            "description": "Get all available Drupal menus.",
            "input_schema": {"type": "object", "properties": {}},
        },
    ]
