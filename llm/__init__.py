"""
LLM Integration Module

Provides multi-provider LLM support (Anthropic Claude / OpenAI GPT)
with tool use for the football analytics chatbot.
"""

from .client import (
    # Client classes
    AnthropicClient,
    OpenAIClient,
    BaseLLMClient,
    LLMProvider,
    
    # Factory functions
    create_client,
    get_llm_client,
    reset_client,
    detect_provider,
    
    # Model info
    ANTHROPIC_MODELS,
    OPENAI_MODELS,
    get_available_models,
    get_model_info,
    list_models_table,
    
    # Availability flags
    LLM_AVAILABLE,
    ANTHROPIC_AVAILABLE,
    OPENAI_AVAILABLE,
    ANTHROPIC_SDK_AVAILABLE,
    OPENAI_SDK_AVAILABLE,
    
    # Backward compatibility
    ClaudeClient,
    get_claude_client,
)

from .handler import LLMHandler, SimpleLLMHandler, create_handler
from .tools import PIPELINE_TOOLS, get_all_tools, get_tool_names
from .prompts import build_system_prompt

__all__ = [
    # Clients
    'AnthropicClient',
    'OpenAIClient', 
    'BaseLLMClient',
    'LLMProvider',
    'ClaudeClient',
    
    # Factory
    'create_client',
    'get_llm_client',
    'reset_client',
    'detect_provider',
    'get_claude_client',
    
    # Models
    'ANTHROPIC_MODELS',
    'OPENAI_MODELS',
    'get_available_models',
    'get_model_info',
    'list_models_table',
    
    # Availability
    'LLM_AVAILABLE',
    'ANTHROPIC_AVAILABLE',
    'OPENAI_AVAILABLE',
    'ANTHROPIC_SDK_AVAILABLE',
    'OPENAI_SDK_AVAILABLE',
    
    # Handler
    'LLMHandler',
    'SimpleLLMHandler',
    'create_handler',
    
    # Tools
    'PIPELINE_TOOLS',
    'get_all_tools',
    'get_tool_names',
    'build_system_prompt',
]
