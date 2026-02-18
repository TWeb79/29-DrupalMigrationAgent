"""
DrupalMind — Base Agent
All agents inherit from this. Provides:
  - Multi-LLM support (Anthropic, OpenAI, Ollama)
  - Async logging with WebSocket push
  - Shared memory and Drupal client access
"""
import os
import json
import asyncio
from typing import Any, Callable, Optional
import anthropic
import openai

from memory import memory as shared_memory
from drupal_client import DrupalClient


# LLM Provider Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()  # anthropic, openai, ollama

# Anthropic Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")  # For custom endpoints

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")  # For custom endpoints
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Ollama Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")


class LLMProvider:
    """Unified LLM interface supporting Anthropic, OpenAI, and Ollama."""
    
    def __init__(self):
        self.provider = LLM_PROVIDER
        self._setup_client()
    
    def _setup_client(self):
        """Initialize the appropriate LLM client based on provider."""
        if self.provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable is required")
            base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
            if base_url != "https://api.anthropic.com":
                # Use custom endpoint (e.g., for proxy or self-hosted)
                self.client = anthropic.Anthropic(
                    api_key=api_key,
                    base_url=base_url
                )
            else:
                self.client = anthropic.Anthropic(api_key=api_key)
        
        elif self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")
            import openai as openai_module
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            openai_module.api_key = api_key
            openai_module.base_url = base_url
            self.client = openai_module
        
        elif self.provider == "ollama":
            self.base_url = OLLAMA_BASE_URL
            self.model = OLLAMA_MODEL
            # Ollama uses raw HTTP, we'll handle it differently
            self.client = None
        
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}. Use: anthropic, openai, or ollama")
    
    def get_model(self) -> str:
        """Get the model name based on provider."""
        if self.provider == "anthropic":
            return os.getenv("AGENT_MODEL", "claude-sonnet-4-20250514")
        elif self.provider == "openai":
            return os.getenv("OPENAI_MODEL", "gpt-4o")
        elif self.provider == "ollama":
            return self.model
        return "claude-sonnet-4-20250514"
    
    def get_provider_name(self) -> str:
        """Get human-readable provider name."""
        names = {
            "anthropic": "Anthropic Claude",
            "openai": "OpenAI GPT",
            "ollama": f"Ollama ({self.model})",
        }
        return names.get(self.provider, self.provider)
    
    def call_with_tools(self, model: str, max_tokens: int, system: str, messages: list, tools: list = None) -> dict:
        """
        Call LLM with tools. Returns response with stop_reason and content.
        Unified interface for all providers.
        """
        if self.provider == "anthropic":
            return self._call_anthropic(model, max_tokens, system, messages, tools)
        elif self.provider == "openai":
            return self._call_openai(model, max_tokens, system, messages, tools)
        elif self.provider == "ollama":
            return self._call_ollama(model, max_tokens, system, messages, tools)
    
    def _call_anthropic(self, model: str, max_tokens: int, system: str, messages: list, tools: list) -> dict:
        """Call Anthropic API."""
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        
        response = self.client.messages.create(**kwargs)
        
        # Convert Anthropic response to unified format
        content = ""
        stop_reason = "end_turn"
        tool_calls = []
        
        for block in response.content:
            if hasattr(block, "text"):
                content = block.text
            if block.type == "tool_use":
                stop_reason = "tool_use"
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        
        return {
            "content": content,
            "stop_reason": stop_reason,
            "tool_calls": tool_calls,
            "raw_response": response,
        }
    
    def _call_openai(self, model: str, max_tokens: int, system: str, messages: list, tools: list) -> dict:
        """Call OpenAI API."""
        # Convert messages to OpenAI format
        openai_messages = []
        if system:
            openai_messages.append({"role": "system", "content": system})
        
        for msg in messages:
            if isinstance(msg, dict):
                openai_messages.append(msg)
            elif hasattr(msg, "content"):
                openai_messages.append({
                    "role": msg.role,
                    "content": self._convert_content(msg.content),
                })
        
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": openai_messages,
        }
        
        if tools:
            # Convert tools to OpenAI format
            kwargs["tools"] = self._convert_tools(tools)
        
        response = self.client.chat.completions.create(**kwargs)
        
        # Convert OpenAI response to unified format
        content = ""
        stop_reason = "end_turn"
        tool_calls = []
        
        choice = response.choices[0]
        if choice.finish_reason == "tool_calls":
            stop_reason = "tool_use"
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments),
                })
        elif choice.finish_reason == "stop":
            content = choice.message.content or ""
        
        return {
            "content": content,
            "stop_reason": stop_reason,
            "tool_calls": tool_calls,
            "raw_response": response,
        }
    
    def _call_ollama(self, model: str, max_tokens: int, system: str, messages: list, tools: list) -> dict:
        """Call Ollama API (local LLM)."""
        import requests
        
        # Prepare messages for Ollama
        ollama_messages = []
        if system:
            ollama_messages.append({"role": "system", "content": system})
        
        for msg in messages:
            if isinstance(msg, dict):
                ollama_messages.append({
                    "role": msg.get("role", "user"),
                    "content": self._convert_content(msg.get("content", "")),
                })
            elif hasattr(msg, "content"):
                ollama_messages.append({
                    "role": msg.role,
                    "content": self._convert_content(msg.content),
                })
        
        # Ollama doesn't support tools natively in the same way
        # We'll use a simplified approach: if tools are provided,
        # include them in the system prompt and extract tool calls from response
        endpoint = f"{self.base_url}/api/chat"
        
        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            }
        }
        
        if tools:
            # Add tool descriptions to system prompt
            tool_descriptions = self._tools_to_ollama_prompt(tools)
            if ollama_messages and ollama_messages[0]["role"] == "system":
                ollama_messages[0]["content"] += "\n\n" + tool_descriptions
            else:
                ollama_messages.insert(0, {"role": "system", "content": tool_descriptions})
        
        response = requests.post(endpoint, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        
        content = result.get("message", {}).get("content", "")
        
        # Try to extract tool calls from response
        tool_calls = []
        stop_reason = "end_turn"
        
        # Check for tool call pattern in response
        if "tool_call" in content.lower() or "invoke" in content.lower():
            # Try to parse JSON tool calls from response
            import re
            json_matches = re.findall(r'\{[^{}]*"name"[^{}]*\}', content, re.DOTALL)
            for match in json_matches:
                try:
                    tc = json.loads(match)
                    if "name" in tc:
                        tool_calls.append({
                            "id": f"ollama_{len(tool_calls)}",
                            "name": tc["name"],
                            "input": tc.get("arguments", tc.get("input", {})),
                        })
                        stop_reason = "tool_use"
                except:
                    pass
        
        return {
            "content": content,
            "stop_reason": stop_reason,
            "tool_calls": tool_calls,
            "raw_response": result,
        }
    
    def _convert_content(self, content) -> str:
        """Convert content blocks to string."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                elif isinstance(block, dict):
                    parts.append(str(block.get("text", "")))
            return "\n".join(parts)
        return str(content)
    
    def _convert_tools(self, tools: list) -> list:
        """Convert Anthropic-style tools to OpenAI format."""
        openai_tools = []
        for tool in tools:
            if isinstance(tool, dict):
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    }
                })
        return openai_tools
    
    def _tools_to_ollama_prompt(self, tools: list) -> str:
        """Convert tools to Ollama system prompt."""
        prompt_parts = [
            "\nYou have access to the following tools:",
        ]
        for tool in tools:
            if isinstance(tool, dict):
                name = tool.get("name", "unknown")
                desc = tool.get("description", "")
                schema = tool.get("input_schema", {})
                prompt_parts.append(
                    f"\n- {name}: {desc}\n  Parameters: {json.dumps(schema)}"
                )
        prompt_parts.append("\n\nTo use a tool, respond with JSON in this format:")
        prompt_parts.append('{"name": "tool_name", "arguments": {"param1": "value1"}}')
        return "\n".join(prompt_parts)


# Global LLM provider instance
_llm_provider = None


def get_llm_provider() -> LLMProvider:
    """Get or create the global LLM provider instance."""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = LLMProvider()
    return _llm_provider


class BaseAgent:
    MODEL = os.getenv("AGENT_MODEL", "claude-sonnet-4-20250514")
    MAX_TOKENS = 4096
    MAX_TOOL_ITERATIONS = 20

    def __init__(self, agent_key: str, label: str):
        self.agent_key = agent_key      # short id used in log events e.g. "build"
        self.label = label              # display name e.g. "BuildAgent"
        
        # Use the unified LLM provider instead of direct Anthropic client
        self.llm = get_llm_provider()
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
        Uses unified LLM provider for Anthropic, OpenAI, or Ollama.
        """
        iterations = max_iterations or self.MAX_TOOL_ITERATIONS
        
        # Get model from provider
        model = self.llm.get_model()
        
        for _ in range(iterations):
            # Use unified LLM provider
            response = self.llm.call_with_tools(
                model=model,
                max_tokens=self.MAX_TOKENS,
                system=system,
                messages=messages,
                tools=tools if tools else None,
            )

            if response["stop_reason"] == "end_turn":
                return response["content"]

            if response["stop_reason"] == "tool_use":
                # Convert unified tool calls back to message format
                messages.append({"role": "assistant", "content": response["content"]})
                tool_results = []
                
                for tc in response["tool_calls"]:
                    try:
                        result = self._dispatch_tool(tc["name"], tc["input"])
                    except Exception as e:
                        result = f"ERROR: {e}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc["id"],
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
