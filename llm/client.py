"""
Unified LLM Client

Supports both Anthropic (Claude) and OpenAI (GPT) APIs with automatic
detection and configurable models via environment variables.

Environment Variables:
    LLM_PROVIDER: 'anthropic' or 'openai' (auto-detected if not set)
    LLM_MODEL: Model name to use (provider-specific defaults if not set)
    ANTHROPIC_API_KEY: Anthropic API key
    OPENAI_API_KEY: OpenAI API key
"""

import os
import logging
import json
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


# =============================================================================
# MODEL CONFIGURATIONS
# =============================================================================

ANTHROPIC_MODELS = {
    # Claude 4 family (latest - 2025)
    "claude-sonnet-4-20250514": {
        "name": "Claude Sonnet 4",
        "description": "Best balance of intelligence and speed (recommended)",
        "max_tokens": 8192,
        "supports_tools": True,
    },
    "claude-opus-4-20250514": {
        "name": "Claude Opus 4",
        "description": "Most capable, best for complex reasoning",
        "max_tokens": 8192,
        "supports_tools": True,
    },
    # Claude 3.5 family
    "claude-3-5-sonnet-20241022": {
        "name": "Claude 3.5 Sonnet",
        "description": "Previous generation, still excellent",
        "max_tokens": 8192,
        "supports_tools": True,
    },
    "claude-3-5-haiku-20241022": {
        "name": "Claude 3.5 Haiku",
        "description": "Fastest and most cost-effective",
        "max_tokens": 8192,
        "supports_tools": True,
    },
}

OPENAI_MODELS = {
    # GPT-4o family (2024)
    "gpt-4o": {
        "name": "GPT-4o",
        "description": "Most capable GPT-4 model, multimodal (recommended)",
        "max_tokens": 4096,
        "supports_tools": True,
    },
    "gpt-4o-mini": {
        "name": "GPT-4o Mini",
        "description": "Faster and cheaper, good for most tasks",
        "max_tokens": 4096,
        "supports_tools": True,
    },
    # GPT-4 Turbo
    "gpt-4-turbo": {
        "name": "GPT-4 Turbo",
        "description": "GPT-4 Turbo with vision",
        "max_tokens": 4096,
        "supports_tools": True,
    },
    # GPT-3.5
    "gpt-3.5-turbo": {
        "name": "GPT-3.5 Turbo",
        "description": "Fast and economical",
        "max_tokens": 4096,
        "supports_tools": True,
    },
}

# Default models (can be overridden via LLM_MODEL env var)
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_OPENAI_MODEL = "gpt-4o"


# =============================================================================
# CHECK AVAILABLE PACKAGES
# =============================================================================

try:
    from anthropic import Anthropic
    ANTHROPIC_SDK_AVAILABLE = True
except ImportError:
    ANTHROPIC_SDK_AVAILABLE = False
    Anthropic = None

try:
    from openai import OpenAI
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False
    OpenAI = None


# =============================================================================
# BASE CLIENT INTERFACE
# =============================================================================

class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    provider: LLMProvider
    model: str
    
    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        tools: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Send a chat message."""
        pass
    
    @abstractmethod
    def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        system: Optional[str] = None,
        max_tokens: int = 1024,
        tool_executor: Optional[callable] = None,
        max_iterations: int = 5,
    ) -> Dict[str, Any]:
        """Chat with automatic tool execution."""
        pass
    
    def simple_query(
        self,
        query: str,
        system: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """Simple single-turn query."""
        response = self.chat(
            messages=[{"role": "user", "content": query}],
            system=system,
            max_tokens=max_tokens,
        )
        return response["content"]
    
    def get_info(self) -> Dict[str, str]:
        """Get client info."""
        return {
            "provider": self.provider.value,
            "model": self.model,
        }


# =============================================================================
# ANTHROPIC CLIENT
# =============================================================================

class AnthropicClient(BaseLLMClient):
    """Client for Anthropic's Claude API."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        if not ANTHROPIC_SDK_AVAILABLE:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
        
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("No Anthropic API key. Set ANTHROPIC_API_KEY environment variable.")
        
        # Model priority: explicit param > LLM_MODEL env > default
        self.model = model or os.getenv("LLM_MODEL") or DEFAULT_ANTHROPIC_MODEL
        self.client = Anthropic(api_key=self.api_key)
        self.provider = LLMProvider.ANTHROPIC
        
        logger.info(f"Anthropic client initialized with model: {self.model}")
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        tools: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        
        if system:
            kwargs["system"] = system
        
        if tools:
            kwargs["tools"] = tools
        
        response = self.client.messages.create(**kwargs)
        
        return {
            "content": self._extract_content(response),
            "role": response.role,
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "tool_calls": self._extract_tool_calls(response),
            "raw_response": response,
            "provider": "anthropic",
            "model": self.model,
        }
    
    def _extract_content(self, response) -> str:
        text_parts = []
        for block in response.content:
            if hasattr(block, 'text'):
                text_parts.append(block.text)
        return '\n'.join(text_parts)
    
    def _extract_tool_calls(self, response) -> List[Dict]:
        tool_calls = []
        for block in response.content:
            if hasattr(block, 'type') and block.type == 'tool_use':
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        return tool_calls
    
    def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        system: Optional[str] = None,
        max_tokens: int = 1024,
        tool_executor: Optional[callable] = None,
        max_iterations: int = 5,
    ) -> Dict[str, Any]:
        current_messages = messages.copy()
        
        for iteration in range(max_iterations):
            response = self.chat(
                messages=current_messages,
                system=system,
                max_tokens=max_tokens,
                tools=tools,
            )
            
            if not response["tool_calls"]:
                return response
            
            if not tool_executor:
                return response
            
            # Add assistant's response
            assistant_content = []
            for block in response["raw_response"].content:
                if hasattr(block, 'text'):
                    assistant_content.append({"type": "text", "text": block.text})
                elif hasattr(block, 'type') and block.type == 'tool_use':
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })
            
            current_messages.append({"role": "assistant", "content": assistant_content})
            
            # Execute tools
            tool_results = []
            for tool_call in response["tool_calls"]:
                try:
                    result = tool_executor(tool_call["name"], tool_call["input"])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call["id"],
                        "content": json.dumps(result) if isinstance(result, dict) else str(result)
                    })
                except Exception as e:
                    logger.error(f"Tool execution error: {e}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call["id"],
                        "content": f"Error: {str(e)}",
                        "is_error": True
                    })
            
            current_messages.append({"role": "user", "content": tool_results})
        
        return response


# =============================================================================
# OPENAI CLIENT
# =============================================================================

class OpenAIClient(BaseLLMClient):
    """Client for OpenAI's GPT API."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        if not OPENAI_SDK_AVAILABLE:
            raise ImportError("openai package not installed. Run: pip install openai")
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("No OpenAI API key. Set OPENAI_API_KEY environment variable.")
        
        # Model priority: explicit param > LLM_MODEL env > default
        self.model = model or os.getenv("LLM_MODEL") or DEFAULT_OPENAI_MODEL
        self.client = OpenAI(api_key=self.api_key)
        self.provider = LLMProvider.OPENAI
        
        logger.info(f"OpenAI client initialized with model: {self.model}")
    
    def _convert_tools_to_openai(self, tools: List[Dict]) -> List[Dict]:
        """Convert Anthropic tool format to OpenAI function format."""
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"]
                }
            })
        return openai_tools
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        tools: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        # Build messages with system prompt
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)
        
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": full_messages,
            "temperature": temperature,
        }
        
        if tools:
            kwargs["tools"] = self._convert_tools_to_openai(tools)
        
        response = self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        
        return {
            "content": message.content or "",
            "role": message.role,
            "stop_reason": response.choices[0].finish_reason,
            "usage": {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
            "tool_calls": self._extract_tool_calls(message),
            "raw_response": response,
            "provider": "openai",
            "model": self.model,
        }
    
    def _extract_tool_calls(self, message) -> List[Dict]:
        if not message.tool_calls:
            return []
        
        tool_calls = []
        for tc in message.tool_calls:
            tool_calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "input": json.loads(tc.function.arguments),
            })
        return tool_calls
    
    def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        system: Optional[str] = None,
        max_tokens: int = 1024,
        tool_executor: Optional[callable] = None,
        max_iterations: int = 5,
    ) -> Dict[str, Any]:
        current_messages = messages.copy()
        
        for iteration in range(max_iterations):
            response = self.chat(
                messages=current_messages,
                system=system,
                max_tokens=max_tokens,
                tools=tools,
            )
            
            if not response["tool_calls"]:
                return response
            
            if not tool_executor:
                return response
            
            # Add assistant message with tool calls
            raw_message = response["raw_response"].choices[0].message
            current_messages.append({
                "role": "assistant",
                "content": raw_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in raw_message.tool_calls
                ] if raw_message.tool_calls else None
            })
            
            # Execute tools and add results
            for tool_call in response["tool_calls"]:
                try:
                    result = tool_executor(tool_call["name"], tool_call["input"])
                    content = json.dumps(result) if isinstance(result, dict) else str(result)
                except Exception as e:
                    logger.error(f"Tool execution error: {e}")
                    content = f"Error: {str(e)}"
                
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": content
                })
        
        return response


# =============================================================================
# UNIFIED CLIENT FACTORY
# =============================================================================

def detect_provider() -> Optional[LLMProvider]:
    """
    Auto-detect which LLM provider to use.
    
    Priority:
    1. LLM_PROVIDER environment variable
    2. ANTHROPIC_API_KEY (if set)
    3. OPENAI_API_KEY (if set)
    """
    # Check explicit preference first
    provider_env = os.getenv("LLM_PROVIDER", "").lower()
    if provider_env == "anthropic":
        return LLMProvider.ANTHROPIC
    elif provider_env == "openai":
        return LLMProvider.OPENAI
    
    # Auto-detect based on available keys
    if os.getenv("ANTHROPIC_API_KEY"):
        return LLMProvider.ANTHROPIC
    elif os.getenv("OPENAI_API_KEY"):
        return LLMProvider.OPENAI
    
    return None


def create_client(
    provider: Optional[LLMProvider] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> BaseLLMClient:
    """
    Create an LLM client.
    
    Args:
        provider: LLM provider (auto-detected if not specified)
        model: Model name (uses default for provider if not specified)
        api_key: API key (uses environment variable if not specified)
    
    Returns:
        Configured LLM client
    
    Raises:
        ValueError: If no provider available
    """
    if provider is None:
        provider = detect_provider()
    
    if provider is None:
        raise ValueError(
            "No LLM provider available. Set one of:\n"
            "  - ANTHROPIC_API_KEY for Claude\n"
            "  - OPENAI_API_KEY for GPT\n"
            "  - LLM_PROVIDER to force 'anthropic' or 'openai'"
        )
    
    if provider == LLMProvider.ANTHROPIC:
        if not ANTHROPIC_SDK_AVAILABLE:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
        return AnthropicClient(api_key=api_key, model=model)
    
    elif provider == LLMProvider.OPENAI:
        if not OPENAI_SDK_AVAILABLE:
            raise ImportError("openai package not installed. Run: pip install openai")
        return OpenAIClient(api_key=api_key, model=model)
    
    raise ValueError(f"Unknown provider: {provider}")


# =============================================================================
# GLOBAL CLIENT SINGLETON
# =============================================================================

_client: Optional[BaseLLMClient] = None


def get_llm_client() -> BaseLLMClient:
    """Get or create the global LLM client."""
    global _client
    if _client is None:
        _client = create_client()
    return _client


def reset_client():
    """Reset the global client (useful for testing)."""
    global _client
    _client = None


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_available_models() -> Dict[str, Dict]:
    """Get all available models organized by provider."""
    return {
        "anthropic": ANTHROPIC_MODELS,
        "openai": OPENAI_MODELS,
    }


def get_model_info(provider: str, model: str) -> Optional[Dict]:
    """Get info about a specific model."""
    models = ANTHROPIC_MODELS if provider == "anthropic" else OPENAI_MODELS
    return models.get(model)


def list_models_table() -> str:
    """Get a formatted table of all available models."""
    lines = [
        "=" * 80,
        "AVAILABLE MODELS",
        "=" * 80,
        "",
        "ANTHROPIC (Claude):",
        "-" * 40,
    ]
    
    for model_id, info in ANTHROPIC_MODELS.items():
        rec = " (default)" if model_id == DEFAULT_ANTHROPIC_MODEL else ""
        lines.append(f"  {model_id}{rec}")
        lines.append(f"    {info['description']}")
    
    lines.extend([
        "",
        "OPENAI (GPT):",
        "-" * 40,
    ])
    
    for model_id, info in OPENAI_MODELS.items():
        rec = " (default)" if model_id == DEFAULT_OPENAI_MODEL else ""
        lines.append(f"  {model_id}{rec}")
        lines.append(f"    {info['description']}")
    
    lines.extend([
        "",
        "CONFIGURATION:",
        "-" * 40,
        "  LLM_PROVIDER=anthropic|openai  (auto-detected from API key if not set)",
        "  LLM_MODEL=<model-id>           (uses default for provider if not set)",
        "  ANTHROPIC_API_KEY=sk-ant-...   (for Claude models)",
        "  OPENAI_API_KEY=sk-...          (for GPT models)",
        "=" * 80,
    ])
    
    return "\n".join(lines)


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

# Alias for backward compatibility with Phase 4 code
ClaudeClient = AnthropicClient

# Check availability flags
ANTHROPIC_AVAILABLE = ANTHROPIC_SDK_AVAILABLE and bool(os.getenv("ANTHROPIC_API_KEY"))
OPENAI_AVAILABLE = OPENAI_SDK_AVAILABLE and bool(os.getenv("OPENAI_API_KEY"))
LLM_AVAILABLE = ANTHROPIC_AVAILABLE or OPENAI_AVAILABLE


def get_claude_client() -> AnthropicClient:
    """Get Anthropic client (backward compatibility)."""
    return AnthropicClient()
