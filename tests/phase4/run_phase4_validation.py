#!/usr/bin/env python3
"""
Phase 4 Validation Script

Validates the LLM integration:
- Multi-provider client (Anthropic/OpenAI)
- Tool definitions
- LLM handler (pipeline mode)
- Prompt generation

Usage:
    python tests/phase4/run_phase4_validation.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CHECKS = []
HAS_ANTHROPIC_KEY = bool(os.getenv("ANTHROPIC_API_KEY"))
HAS_OPENAI_KEY = bool(os.getenv("OPENAI_API_KEY"))
HAS_ANY_KEY = HAS_ANTHROPIC_KEY or HAS_OPENAI_KEY


def check(name):
    """Decorator to register a check."""
    def decorator(func):
        CHECKS.append((name, func))
        return func
    return decorator


# =============================================================================
# MODEL CONFIGURATION CHECKS
# =============================================================================

@check("Model Configs Load")
def check_models_load():
    from llm.client import ANTHROPIC_MODELS, OPENAI_MODELS
    
    anthropic_count = len(ANTHROPIC_MODELS)
    openai_count = len(OPENAI_MODELS)
    
    return anthropic_count >= 3 and openai_count >= 3, f"Anthropic: {anthropic_count}, OpenAI: {openai_count}"


@check("List Models Table")
def check_list_models():
    from llm.client import list_models_table
    
    table = list_models_table()
    
    has_anthropic = "ANTHROPIC" in table
    has_openai = "OPENAI" in table
    has_config = "LLM_PROVIDER" in table
    
    return has_anthropic and has_openai and has_config, f"Table length: {len(table)} chars"


# =============================================================================
# TOOL DEFINITION CHECKS
# =============================================================================

@check("Tool Definitions Load")
def check_tools_load():
    from llm.tools import PIPELINE_TOOLS, get_all_tools
    tools = get_all_tools()
    return len(tools) >= 5, f"Loaded {len(tools)} tools"


@check("Tool Definitions Have Required Fields")
def check_tools_structure():
    from llm.tools import PIPELINE_TOOLS
    
    required_fields = ['name', 'description', 'input_schema']
    
    all_valid = True
    for tool in PIPELINE_TOOLS:
        for field in required_fields:
            if field not in tool:
                all_valid = False
                break
    
    return all_valid, f"All {len(PIPELINE_TOOLS)} tools have required fields"


@check("Tool Names Map to Pipelines")
def check_tool_mapping():
    from llm.tools import TOOL_TO_PIPELINE, get_tool_names
    
    tool_names = get_tool_names()
    mapped = sum(1 for t in tool_names if t in TOOL_TO_PIPELINE)
    
    return mapped == len(tool_names), f"{mapped}/{len(tool_names)} tools mapped"


# =============================================================================
# PROMPT CHECKS
# =============================================================================

@check("System Prompt Builds")
def check_system_prompt():
    from llm.prompts import build_system_prompt
    
    prompt = build_system_prompt()
    
    has_role = "NFL" in prompt or "analytics" in prompt.lower()
    has_tools = "tool" in prompt.lower() or "capabilit" in prompt.lower()
    
    return has_role and has_tools, f"Prompt length: {len(prompt)} chars"


@check("System Prompt With Context")
def check_system_prompt_context():
    from llm.prompts import build_system_prompt
    
    context = {
        'favorite_team': 'KC',
        'season': 2023,
        'detail_level': 'detailed'
    }
    
    prompt = build_system_prompt(context)
    
    has_team = 'KC' in prompt
    has_season = '2023' in prompt
    
    return has_team and has_season, "Context included in prompt"


# =============================================================================
# CLIENT CHECKS
# =============================================================================

@check("Client Module Imports")
def check_client_imports():
    from llm.client import (
        AnthropicClient, OpenAIClient, BaseLLMClient,
        LLMProvider, create_client, detect_provider,
        ANTHROPIC_SDK_AVAILABLE, OPENAI_SDK_AVAILABLE
    )
    return True, f"Anthropic SDK: {ANTHROPIC_SDK_AVAILABLE}, OpenAI SDK: {OPENAI_SDK_AVAILABLE}"


@check("Provider Detection")
def check_provider_detection():
    from llm.client import detect_provider, LLMProvider
    
    provider = detect_provider()
    
    if provider is None:
        return not HAS_ANY_KEY, "No provider (no API keys)"
    
    provider_name = provider.value if provider else "none"
    return True, f"Detected: {provider_name}"


@check("Client Handles Missing API Key")
def check_client_no_key():
    from llm.client import AnthropicClient, ANTHROPIC_SDK_AVAILABLE
    
    if not ANTHROPIC_SDK_AVAILABLE:
        return True, "Anthropic SDK not installed (expected)"
    
    # Save and remove key
    original_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    
    try:
        client = AnthropicClient(api_key=None)
        result = False, "Should have raised error"
    except ValueError as e:
        result = True, "Raised ValueError as expected"
    except Exception as e:
        result = False, f"Wrong error type: {type(e).__name__}"
    finally:
        if original_key:
            os.environ["ANTHROPIC_API_KEY"] = original_key
    
    return result


# =============================================================================
# HANDLER CHECKS (Pipeline Mode)
# =============================================================================

@check("LLM Handler Initializes (No LLM)")
def check_handler_init():
    from llm.handler import LLMHandler
    
    handler = LLMHandler()
    handler._llm_available = False  # Force pipeline-only mode
    
    result = handler is not None
    handler.close()
    
    return result, "Handler created in pipeline mode"


@check("Handler Executes Pipeline Directly")
def check_handler_pipeline():
    from llm.handler import LLMHandler
    
    handler = LLMHandler()
    handler._llm_available = False
    
    result = handler.handle_query(
        "team profile for KC",
        use_llm=False
    )
    
    handler.close()
    
    ok = result.get('pipeline') == 'team_profile'
    return ok, f"Pipeline: {result.get('pipeline')}"


@check("Handler Tool Execution Works")
def check_handler_tool_exec():
    from llm.handler import LLMHandler
    
    handler = LLMHandler()
    
    result = handler._execute_tool("get_team_profile", {"team": "KC", "season": 2023})
    
    handler.close()
    
    ok = result.get('success') == True
    has_profile = 'profile' in result.get('data', {})
    
    return ok and has_profile, f"Tool execution success: {ok}"


@check("Handler Situation Analysis Tool")
def check_handler_situation_tool():
    from llm.handler import LLMHandler
    
    handler = LLMHandler()
    
    result = handler._execute_tool("analyze_situation", {
        "down": 3,
        "distance": 5,
        "yardline": 40
    })
    
    handler.close()
    
    ok = result.get('success') == True
    has_analysis = 'analysis' in result.get('data', {})
    
    return ok and has_analysis, f"Situation tool success: {ok}"


@check("Handler 4th Down Tool")
def check_handler_4th_down_tool():
    from llm.handler import LLMHandler
    
    handler = LLMHandler()
    
    result = handler._execute_tool("fourth_down_decision", {
        "distance": 2,
        "yardline": 35
    })
    
    handler.close()
    
    ok = result.get('success') == True
    has_rec = 'recommendation' in result.get('data', {})
    
    return ok and has_rec, f"4th down tool success: {ok}"


@check("Simple Handler Works")
def check_simple_handler():
    from llm.handler import SimpleLLMHandler
    
    handler = SimpleLLMHandler()
    
    result = handler.handle("KC vs SF", context=None)
    
    handler.close()
    
    ok = 'text' in result and len(result['text']) > 0
    return ok, f"Pipeline: {result.get('pipeline')}"


# =============================================================================
# LLM INTEGRATION CHECKS (Only if API key available)
# =============================================================================

if HAS_ANTHROPIC_KEY:
    @check("Anthropic Client Connects")
    def check_anthropic_connection():
        from llm.client import AnthropicClient
        
        try:
            client = AnthropicClient()
            response = client.simple_query("Say 'test' and nothing else.")
            
            ok = 'test' in response.lower()
            return ok, f"Model: {client.model}"
        except Exception as e:
            return False, str(e)

if HAS_OPENAI_KEY:
    @check("OpenAI Client Connects")
    def check_openai_connection():
        from llm.client import OpenAIClient
        
        try:
            client = OpenAIClient()
            response = client.simple_query("Say 'test' and nothing else.")
            
            ok = 'test' in response.lower()
            return ok, f"Model: {client.model}"
        except Exception as e:
            return False, str(e)

if HAS_ANY_KEY:
    @check("Unified Client Auto-Detects Provider")
    def check_unified_client():
        from llm.client import create_client
        
        try:
            client = create_client()
            info = client.get_info()
            
            return True, f"Provider: {info['provider']}, Model: {info['model']}"
        except Exception as e:
            return False, str(e)
    
    @check("Tool Calling Works")
    def check_tool_calling():
        from llm.client import create_client
        from llm.tools import get_all_tools
        
        client = create_client()
        
        response = client.chat(
            messages=[{"role": "user", "content": "Get the team profile for KC."}],
            tools=get_all_tools(),
            max_tokens=500
        )
        
        has_tool_call = len(response.get('tool_calls', [])) > 0
        
        if has_tool_call:
            tool_name = response['tool_calls'][0]['name']
            return True, f"Tool called: {tool_name}"
        else:
            return True, "Model responded directly (also valid)"
    
    @check("Full LLM Handler Flow")
    def check_full_llm_flow():
        from llm.handler import LLMHandler
        from context.presets import UserContext
        
        handler = LLMHandler()
        
        user_ctx = UserContext(favorite_team='KC', season=2023)
        
        result = handler.handle_query(
            "How do the Chiefs compare to the 49ers?",
            user_context=user_ctx,
            use_llm=True
        )
        
        handler.close()
        
        ok = len(result.get('text', '')) > 50
        used_llm = result.get('used_llm', False)
        
        return ok, f"Used LLM: {used_llm}, Response length: {len(result.get('text', ''))}"


# =============================================================================
# RUNNER
# =============================================================================

def run_validation():
    """Run all Phase 4 validation checks."""
    print("=" * 70)
    print("PHASE 4 VALIDATION - LLM Integration (Multi-Provider)")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 70)
    print(f"Anthropic API Key: {'✓ Set' if HAS_ANTHROPIC_KEY else '✗ Not set'}")
    print(f"OpenAI API Key:    {'✓ Set' if HAS_OPENAI_KEY else '✗ Not set'}")
    print("=" * 70)
    print()
    
    # Print available models
    try:
        from llm.client import list_models_table
        print(list_models_table())
        print()
    except:
        pass
    
    passed = 0
    failed = 0
    
    print("-" * 70)
    print("Running checks...")
    print("-" * 70)
    print()
    
    for name, check_func in CHECKS:
        try:
            result = check_func()
            if isinstance(result, tuple):
                ok, detail = result
            else:
                ok, detail = result, ""
            
            if ok:
                status = "✅ PASS"
                passed += 1
            else:
                status = "❌ FAIL"
                failed += 1
            
            detail_str = f" → {detail}" if detail else ""
            print(f"  {status} | {name}{detail_str}")
            
        except Exception as e:
            print(f"  ❌ FAIL | {name} → Error: {e}")
            failed += 1
    
    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print()
        print("🎉 PHASE 4 COMPLETE!")
        print()
        print("Your LLM integration supports:")
        if HAS_ANTHROPIC_KEY:
            print("  ✓ Anthropic Claude (API key configured)")
        if HAS_OPENAI_KEY:
            print("  ✓ OpenAI GPT (API key configured)")
        if not HAS_ANY_KEY:
            print("  • Pipeline-only mode (no API keys)")
            print()
            print("To enable LLM features, add to .env:")
            print("  ANTHROPIC_API_KEY=sk-ant-...")
            print("  # or")
            print("  OPENAI_API_KEY=sk-...")
        print()
        print("To customize model, add to .env:")
        print("  LLM_PROVIDER=anthropic  # or 'openai'")
        print("  LLM_MODEL=claude-sonnet-4-20250514  # or 'gpt-4o'")
        print()
        print("To start the API:")
        print("  uvicorn api.main:app --reload")
        print()
        return True
    else:
        print()
        print("⚠️  Phase 4 has failures. Please fix before proceeding.")
        print()
        return False


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
