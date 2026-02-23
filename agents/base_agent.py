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
import logging
from typing import Any, Callable, Optional
import anthropic
import openai

from memory import memory as shared_memory
from drupal_client import DrupalClient

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("drupalmind")


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
            from openai import OpenAI
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
        
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
        if self.provider == "anthropic":
            return "Anthropic Claude"
        elif self.provider == "openai":
            return "OpenAI GPT"
        elif self.provider == "ollama":
            return f"Ollama ({self.model})"
        return self.provider
    
    def call_with_tools(self, model: str, max_tokens: int, system: str, messages: list, tools: list = None) -> dict:
        """
        Call LLM with tools. Returns response with stop_reason and content.
        Unified interface for all providers.
        """
        logger.info(f"┌──────────────────────────────────────────────────────────────────────")
        logger.info(f"│ LLM REQUEST | Provider: {self.get_provider_name()} | Model: {model}")
        logger.info(f"│ System: {system[:100]}...")
        logger.info(f"│ Messages: {len(messages)} | Tools: {len(tools) if tools else 0}")
        logger.info(f"└──────────────────────────────────────────────────────────────────────")
        
        if self.provider == "anthropic":
            result = self._call_anthropic(model, max_tokens, system, messages, tools)
        elif self.provider == "openai":
            result = self._call_openai(model, max_tokens, system, messages, tools)
        elif self.provider == "ollama":
            result = self._call_ollama(model, max_tokens, system, messages, tools)
        else:
            result = {"content": "", "stop_reason": "error", "tool_calls": []}
        
        logger.info(f"┌──────────────────────────────────────────────────────────────────────")
        logger.info(f"│ LLM RESPONSE | Stop Reason: {result.get('stop_reason', 'unknown')}")
        content = result.get('content', '')
        logger.info(f"│ Content Length: {len(content)} chars")
        if content:
            logger.info(f"│ Content Preview: {content[:200]}...")
        tool_calls = result.get('tool_calls', [])
        if tool_calls:
            logger.info(f"│ Tool Calls: {len(tool_calls)}")
            for tc in tool_calls:
                logger.info(f"│   - {tc.get('name', 'unknown')}: {str(tc.get('input', {}))[:100]}...")
        logger.info(f"└──────────────────────────────────────────────────────────────────────")
        
        return result
    
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
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # Handle tool result messages - convert to OpenAI format
                if role == "tool":
                    # Tool results can be a list of results or a single result
                    if isinstance(content, list):
                        for tool_result in content:
                            openai_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_result.get("tool_call_id", ""),
                                "content": str(tool_result.get("content", "")),
                            })
                    else:
                        openai_messages.append({
                            "role": "tool",
                            "content": str(content),
                        })
                else:
                    # Regular message - convert content if needed
                    if isinstance(content, list):
                        # Handle content blocks
                        text_parts = []
                        for block in content:
                            if isinstance(block, dict):
                                if block.get("type") == "text":
                                    text_parts.append(str(block.get("text", "")))
                                elif block.get("type") == "tool_result":
                                    # Extract tool_result content
                                    text_parts.append(str(block.get("text", "")))
                            elif hasattr(block, "text"):
                                text_parts.append(str(block.text))
                        content = "\n".join(text_parts) if text_parts else ""
                    
                    openai_msg = {
                        "role": role,
                        "content": str(content) if content else "",
                    }
                    
                    # IMPORTANT: Preserve tool_calls field if present (for assistant messages with tool use)
                    if "tool_calls" in msg:
                        openai_msg["tool_calls"] = msg["tool_calls"]
                    
                    openai_messages.append(openai_msg)
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
        """Enhanced logging with debug information and extended event data."""
        import time
        import traceback
        
        # Build enhanced event with debug info
        event = {
            "type": "log",
            "agent": self.agent_key,
            "agent_label": self.label,
            "message": message,
            "status": status,
            "detail": detail,
            "timestamp": time.time(),
            "event_version": "2.0",
            "extended": {
                "memory_keys_count": 0,
                "memory_backend": "unknown",
                "session_id": None,
                "llm_provider": None,
                "stack_depth": len(traceback.extract_stack()),
            }
        }
        
        # Add memory info safely
        try:
            if hasattr(shared_memory, '_redis') and shared_memory._redis:
                event["extended"]["memory_keys_count"] = len(shared_memory._redis.keys("*"))
                event["extended"]["memory_backend"] = "redis"
            elif hasattr(shared_memory, '_local'):
                event["extended"]["memory_keys_count"] = len(shared_memory._local)
                event["extended"]["memory_backend"] = "local"
        except:
            pass
        
        if self._log_cb:
            await self._log_cb(event)
        else:
            print(f"[{self.label}] [{status.upper()}] {message}")
            if detail:
                print(f"       └─ {detail}")

    async def log_extended(self, event_type: str, data: dict, status: str = "active"):
        """Log an extended event with structured data for UI visualization."""
        import time
        
        event = {
            "type": event_type,
            "agent": self.agent_key,
            "agent_label": self.label,
            "timestamp": time.time(),
            "status": status,
            "event_version": "2.0",
            "data": data,
        }
        
        if self._log_cb:
            await self._log_cb(event)

    async def log_progress(self, current: int, total: int, label: str = ""):
        """Log progress with percentage for UI progress bar."""
        percentage = int((current / max(total, 1)) * 100)
        await self.log_extended(
            "progress",
            {
                "current": current,
                "total": total,
                "percentage": percentage,
                "label": label,
                "progress_bar": f"[{('█' * int(percentage/10)).ljust(10)}] {percentage}%"
            }
        )

    async def log_metric(self, name: str, value: float, unit: str = "", category: str = "general"):
        """Log a metric value for tracking."""
        await self.log_extended(
            "metric",
            {
                "name": name,
                "value": value,
                "unit": unit,
                "category": category,
                "formatted": f"{name}: {value}{unit}"
            }
        )

    async def log_check(self, check_name: str, passed: bool, message: str = "", severity: str = "info"):
        """Log a check result with pass/fail status."""
        await self.log_extended(
            "check",
            {
                "name": check_name,
                "passed": passed,
                "message": message,
                "severity": severity,
                "icon": "✓" if passed else "✗"
            }
        )

    async def log_data(self, data_type: str, data: dict, summary: str = ""):
        """Log structured data for UI to display."""
        await self.log_extended(
            "data",
            {
                "data_type": data_type,
                "data": data,
                "summary": summary,
                "keys": list(data.keys()) if isinstance(data, dict) else []
            }
        )

    async def log_warning(self, warning: str, context: dict = None):
        """Log a warning with context."""
        await self.log_extended(
            "warning",
            {
                "warning": warning,
                "context": context or {},
                "icon": "⚠️"
            }
        )

    async def log_image(self, image_url: str, label: str = "", width: int = 100):
        """
        Log an image for display in the UI.
        The image will be shown as a small preview (width px) in the expandable log.
        Clicking will open it in a new window.
        
        Supports:
        - HTTP URLs (displayed directly)
        - Base64 data URLs (data:image/png;base64,...)
        - Local file paths (not accessible from browser, logs a note)
        """
        # Check if it's a data URL (base64)
        if image_url and image_url.startswith('data:'):
            # It's a base64 data URL - send to UI for display
            await self.log_extended(
                "image",
                {
                    "image_url": image_url,
                    "label": label,
                    "preview_width": width,
                    "is_base64": True,
                }
            )
            return
        
        # Check if it's a local file path
        if image_url and not image_url.startswith('http'):
            # Log that screenshot was captured but can't be displayed in UI
            await self.log_extended(
                "screenshot_captured",
                {
                    "image_path": image_url,
                    "label": label,
                    "note": "Screenshot saved locally. Use VisualDiffAgent to view differences.",
                }
            )
            return
        
        # It's an HTTP URL
        await self.log_extended(
            "image",
            {
                "image_url": image_url,
                "label": label,
                "preview_width": width,
            }
        )

    async def log_done(self, message: str, detail: str = ""):
        await self.log(message, status="done", detail=detail)

    async def log_error(self, message: str, detail: str = ""):
        await self.log(message, status="error", detail=detail)

    # ── Enhanced Logging Methods (v4) ─────────────────────────────────

    async def log_step(self, step_number: int, total_steps: int, title: str, details: dict = None):
        """Log a numbered step in a multi-step process."""
        await self.log_extended("step", {
            "step": step_number,
            "total_steps": total_steps,
            "title": title,
            "details": details or {},
            "progress_percent": int((step_number / total_steps) * 100),
            "step_label": f"Step {step_number}/{total_steps}"
        }, summary=f"Step {step_number}/{total_steps}: {title}")

    async def log_item_processing(
        self,
        item_type: str,
        item_id: str,
        item_index: int,
        total_items: int,
        details: dict = None
    ):
        """Log processing of individual item in batch."""
        # Calculate progress
        pct = int((item_index / max(total_items, 1)) * 100)
        filled = int((item_index / max(total_items, 1)) * 20)
        progress_bar = f"[{'█' * filled}{' ' * (20 - filled)}] {pct}%"
        await self.log_extended("item_processing", {
            "item_type": item_type,
            "item_id": item_id,
            "index": item_index,
            "total": total_items,
            "progress_percent": pct,
            "progress_bar": progress_bar,
            "details": details or {},
        }, summary=f"{item_type} {item_index}/{total_items}: {item_id}")

    async def log_field_migration(
        self,
        field_name: str,
        field_type: str,
        value_preview: str,
        status: str = "success",
        error: str = None
    ):
        """Log migration of a single field."""
        icon = "✓" if status == "success" else "⚠️" if status == "warning" else "✕"
        await self.log_extended("field_migration", {
            "field_name": field_name,
            "field_type": field_type,
            "value_preview": value_preview[:100] if value_preview else "",
            "status": status,
            "error": error,
            "icon": icon,
        })

    async def log_batch_result(
        self,
        batch_name: str,
        total: int,
        successful: int,
        failed: int,
        warnings: int = 0
    ):
        """Log results of batch operation."""
        success_rate = (successful / max(total, 1)) * 100
        status = "success" if failed == 0 else "partial" if failed < total else "failed"
        await self.log_extended("batch_result", {
            "batch_name": batch_name,
            "total": total,
            "successful": successful,
            "failed": failed,
            "warnings": warnings,
            "success_rate": f"{success_rate:.1f}%",
            "status": status,
        }, summary=f"{batch_name}: {successful}/{total} successful ({success_rate:.0f}%)")

    async def log_validation_result(
        self,
        item_id: str,
        is_valid: bool,
        issues: list = None,
        warnings: list = None
    ):
        """Log validation results for an item."""
        await self.log_extended("validation_result", {
            "item_id": item_id,
            "is_valid": is_valid,
            "issues": issues or [],
            "warnings": warnings or [],
            "issue_count": len(issues or []),
            "warning_count": len(warnings or []),
            "status": "pass" if is_valid else "fail",
        })

    async def log_template_application(
        self,
        template_id: str,
        item_id: str,
        result: str,
        details: dict = None
    ):
        """Log application of a template."""
        icon = "✓" if result == "success" else "⚠️" if result == "partial" else "→"
        await self.log_extended("template_application", {
            "template_id": template_id,
            "item_id": item_id,
            "result": result,
            "details": details or {},
            "icon": icon,
        })

    async def log_media_item(
        self,
        url: str,
        status: str,
        details: dict = None
    ):
        """Log processing of a media item."""
        icon = "⬇️" if status == "downloaded" else "⬆️" if status == "uploaded" else "✕"
        await self.log_extended("media_item", {
            "url": url[:100] if url else "",
            "status": status,
            "details": details or {},
            "icon": icon,
        })

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
        logger.info(f"══════════════════════════════════════════════════════════════════")
        logger.info(f"║ AGENT START | {self.label} | System: {system[:50]}...")
        logger.info(f"║ Messages: {len(messages)} | Tools: {len(tools) if tools else 0}")
        logger.info(f"══════════════════════════════════════════════════════════════════")
        
        iterations = max_iterations or self.MAX_TOOL_ITERATIONS
        
        # Get model from provider
        model = self.llm.get_model()
        
        for i in range(iterations):
            logger.info(f"--- Iteration {i+1}/{iterations} ---")
            # Use unified LLM provider
            response = self.llm.call_with_tools(
                model=model,
                max_tokens=self.MAX_TOKENS,
                system=system,
                messages=messages,
                tools=tools if tools else None,
            )

            if response["stop_reason"] == "end_turn":
                logger.info(f"✓ Final response received ({len(response['content'])} chars)")
                logger.info(f"Preview: {response['content'][:200]}...")
                return response["content"]

            if response["stop_reason"] == "tool_use":
                # Convert unified tool calls back to message format
                # Include tool_calls in the assistant message for OpenAI compatibility
                assistant_msg = {
                    "role": "assistant",
                    "content": response["content"]
                }
                if response.get("tool_calls"):
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["input"])
                            }
                        }
                        for tc in response["tool_calls"]
                    ]
                messages.append(assistant_msg)
                
                tool_results = []
                
                logger.info(f"🔧 Tool calls: {len(response['tool_calls'])}")
                for tc in response["tool_calls"]:
                    tool_name = tc["name"]
                    tool_input = tc["input"]
                    logger.info(f"  → Executing: {tool_name}")
                    logger.debug(f"     Input: {json.dumps(tool_input)[:200]}...")
                    try:
                        result = self._dispatch_tool(tool_name, tool_input)
                        logger.info(f"  ✓ Result: {str(result)[:100]}...")
                    except Exception as e:
                        result = f"ERROR: {e}"
                        logger.error(f"  ✗ Error: {e}")
                    
                    # Store tool result with the tool_call_id for proper handling
                    tool_results.append({
                        "tool_call_id": tc["id"],
                        "content": str(result)[:8000],
                    })
                
                # Add tool results in the appropriate format for the LLM provider
                if self.llm.provider == "anthropic":
                    # Anthropic format: user message with tool_result content blocks
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": result["tool_call_id"],
                                "content": result["content"],
                            }
                            for result in tool_results
                        ]
                    })
                else:
                    # OpenAI format: tool message with tool_call_id and content
                    messages.append({"role": "tool", "content": tool_results})
            else:
                break
        logger.warning("⚠ Agent loop ended without final response (max iterations reached)")
        return "Agent loop ended without final response"

    def _dispatch_tool(self, name: str, inputs: dict) -> Any:
        """Route tool calls to methods. Override / extend in subclasses."""
        logger.info(f"╔══════════════════════════════════════════════════════════════")
        logger.info(f"║ TOOL DISPATCH | {name}")
        logger.info(f"║ Inputs: {json.dumps(inputs)[:200]}...")
        logger.info(f"╚══════════════════════════════════════════════════════════════")
        method = getattr(self, f"_tool_{name}", None)
        if method:
            return method(**inputs)
        logger.error(f"Unknown tool: {name}")
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