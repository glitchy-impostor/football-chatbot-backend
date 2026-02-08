"""
LLM Handler

Main handler for LLM-powered queries. Orchestrates tool calling,
response generation, and conversation flow.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.client import (
    create_client, get_llm_client, reset_client,
    LLM_AVAILABLE, LLMProvider, BaseLLMClient,
    ANTHROPIC_SDK_AVAILABLE, OPENAI_SDK_AVAILABLE,
    detect_provider
)
from llm.prompts import build_system_prompt, build_response_prompt
from llm.tools import PIPELINE_TOOLS, TOOL_TO_PIPELINE, get_all_tools
from pipelines.router import QueryRouter, PipelineType, RouteResult
from pipelines.executor import PipelineExecutor
from formatters.response_formatter import ResponseFormatter
from context.presets import UserContext

logger = logging.getLogger(__name__)


class LLMHandler:
    """
    Handles LLM-powered queries with tool use.
    """
    
    def __init__(
        self,
        executor: Optional[PipelineExecutor] = None,
        client: Optional[BaseLLMClient] = None,
    ):
        """
        Initialize the LLM handler.
        
        Args:
            executor: Pipeline executor (created if not provided)
            client: LLM client (created if not provided)
        """
        self.executor = executor or PipelineExecutor()
        self.formatter = ResponseFormatter(include_data=False)
        
        # Only initialize LLM client if available
        self._client = client
        self._llm_available = LLM_AVAILABLE
        
        # Conversation history for multi-turn
        self.conversation_history: List[Dict] = []
    
    @property
    def client(self) -> Optional[BaseLLMClient]:
        """Lazy load LLM client."""
        if self._client is None and self._llm_available:
            try:
                self._client = get_llm_client()
            except Exception as e:
                logger.warning(f"Could not initialize LLM client: {e}")
                self._llm_available = False
        return self._client
    
    def _execute_tool(self, tool_name: str, tool_input: Dict) -> Dict:
        """
        Execute a tool call by routing to the appropriate pipeline.
        
        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            
        Returns:
            Tool execution result
        """
        logger.info(f"Executing tool: {tool_name} with input: {tool_input}")
        
        # Map tool input to pipeline parameters
        params = self._map_tool_to_params(tool_name, tool_input)
        
        # Get pipeline type
        pipeline_type_str = TOOL_TO_PIPELINE.get(tool_name)
        if not pipeline_type_str:
            return {"error": f"Unknown tool: {tool_name}"}
        
        try:
            pipeline_type = PipelineType(pipeline_type_str)
        except ValueError:
            return {"error": f"Invalid pipeline: {pipeline_type_str}"}
        
        # Create route result
        route = RouteResult(
            pipeline=pipeline_type,
            confidence=1.0,
            extracted_params=params,
            tier=1,
            reasoning=f"LLM tool call: {tool_name}"
        )
        
        # Execute pipeline
        result = self.executor.execute(route)
        
        return result
    
    def _map_tool_to_params(self, tool_name: str, tool_input: Dict) -> Dict:
        """Map tool input to pipeline parameters."""
        params = tool_input.copy()
        
        # Ensure season default
        if 'season' not in params:
            params['season'] = 2025
        
        # Handle specific mappings
        if tool_name == "analyze_situation":
            # Map 'distance' to both 'distance' and 'ydstogo' for compatibility
            if 'distance' in params:
                params['ydstogo'] = params['distance']
        
        if tool_name == "fourth_down_decision":
            params['down'] = 4
            if 'distance' in params:
                params['ydstogo'] = params['distance']
        
        if tool_name == "simulate_drive":
            params['n_simulations'] = 5000
        
        return params
    
    def handle_query(
        self,
        query: str,
        user_context: Optional[UserContext] = None,
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        """
        Handle a user query with optional LLM enhancement.
        
        Args:
            query: User's query
            user_context: User context and preferences
            use_llm: Whether to use LLM for complex queries
            
        Returns:
            Response dict with 'text', 'data', 'pipeline', etc.
        """
        context_dict = {}
        if user_context:
            context_dict = {
                'favorite_team': user_context.favorite_team,
                'season': user_context.season,
            }
        
        # First, try direct routing
        router = QueryRouter()
        route_result = router.route_with_suggestions(query, context_dict)
        route = route_result['route']
        
        # If high confidence match (Tier 1 or strong Tier 2), use pipeline directly
        if route.confidence >= 0.8 and route.pipeline != PipelineType.GENERAL_QUERY:
            logger.info(f"Direct pipeline routing: {route.pipeline.value}")
            
            result = self.executor.execute(route)
            formatted = self.formatter.format(result)
            
            return {
                'text': formatted['text'],
                'pipeline': route.pipeline.value,
                'confidence': route.confidence,
                'tier': route.tier,
                'data': result.get('data'),
                'used_llm': False,
                'suggestions': route_result.get('suggestions', [])
            }
        
        # For lower confidence or general queries, use LLM if available
        if use_llm and self._llm_available and self.client:
            return self._handle_with_llm(query, user_context, route_result)
        
        # Fallback: try to execute anyway
        if route.pipeline != PipelineType.UNKNOWN:
            result = self.executor.execute(route)
            formatted = self.formatter.format(result)
            
            return {
                'text': formatted['text'],
                'pipeline': route.pipeline.value,
                'confidence': route.confidence,
                'tier': route.tier,
                'data': result.get('data'),
                'used_llm': False,
                'suggestions': route_result.get('suggestions', [])
            }
        
        # Can't handle without LLM
        return {
            'text': "I'm not sure how to help with that. Could you try asking about a specific team, game situation, or player ranking?",
            'pipeline': 'unknown',
            'confidence': 0.0,
            'tier': 3,
            'used_llm': False,
            'suggestions': [
                "Try: 'Tell me about the Chiefs'",
                "Try: 'Should I run or pass on 3rd and 5?'",
                "Try: 'Compare KC vs SF'"
            ]
        }
    
    def _handle_with_llm(
        self,
        query: str,
        user_context: Optional[UserContext],
        route_result: Dict
    ) -> Dict[str, Any]:
        """Handle query using Claude with tool calling."""
        
        # Build system prompt
        context_dict = None
        if user_context:
            context_dict = {
                'favorite_team': user_context.favorite_team,
                'season': user_context.season,
                'detail_level': user_context.detail_level,
            }
        
        system_prompt = build_system_prompt(context_dict)
        
        # Build messages
        messages = [{"role": "user", "content": query}]
        
        # Add conversation history if multi-turn
        if self.conversation_history:
            messages = self.conversation_history + messages
        
        try:
            # Call Claude with tools
            response = self.client.chat_with_tools(
                messages=messages,
                tools=get_all_tools(),
                system=system_prompt,
                max_tokens=1024,
                tool_executor=self._execute_tool,
                max_iterations=3,
            )
            
            # Extract response
            text = response["content"]
            tool_calls = response.get("tool_calls", [])
            
            # Update conversation history
            self.conversation_history.append({"role": "user", "content": query})
            self.conversation_history.append({"role": "assistant", "content": text})
            
            # Keep history manageable
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
            
            # Determine which pipeline was used (if any)
            pipeline_used = "llm_direct"
            if tool_calls:
                pipeline_used = TOOL_TO_PIPELINE.get(tool_calls[0]["name"], "llm_tool")
            
            return {
                'text': text,
                'pipeline': pipeline_used,
                'confidence': 0.9,
                'tier': 3,
                'used_llm': True,
                'tool_calls': tool_calls,
                'usage': response.get('usage', {}),
            }
            
        except Exception as e:
            logger.error(f"LLM handling error: {e}")
            
            # Fallback to route result
            route = route_result['route']
            if route.pipeline != PipelineType.UNKNOWN:
                result = self.executor.execute(route)
                formatted = self.formatter.format(result)
                
                return {
                    'text': formatted['text'],
                    'pipeline': route.pipeline.value,
                    'confidence': route.confidence,
                    'tier': route.tier,
                    'used_llm': False,
                    'error': str(e)
                }
            
            return {
                'text': f"I encountered an error processing your request. Please try again.",
                'pipeline': 'error',
                'confidence': 0.0,
                'used_llm': False,
                'error': str(e)
            }
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
    
    def close(self):
        """Clean up resources."""
        if self.executor:
            self.executor.close()


class SimpleLLMHandler:
    """
    Simplified handler that works without LLM (pipeline-only mode).
    """
    
    def __init__(self):
        self.executor = PipelineExecutor()
        self.router = QueryRouter()
        self.formatter = ResponseFormatter()
    
    def handle(self, query: str, context: Optional[Dict] = None) -> Dict:
        """Handle a query using pipelines only."""
        route = self.router.route(query, context)
        result = self.executor.execute(route)
        formatted = self.formatter.format(result)
        
        return {
            'text': formatted['text'],
            'pipeline': route.pipeline.value,
            'confidence': route.confidence,
            'tier': route.tier,
            'data': result.get('data'),
        }
    
    def close(self):
        self.executor.close()


def create_handler(use_llm: bool = True) -> LLMHandler:
    """
    Factory function to create appropriate handler.
    
    Args:
        use_llm: Whether to enable LLM features
        
    Returns:
        LLMHandler instance
    """
    handler = LLMHandler()
    
    if not use_llm:
        handler._llm_available = False
    
    return handler
