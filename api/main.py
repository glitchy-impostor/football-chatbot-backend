"""
Football Analytics Chatbot API (Standalone)

An intelligent NFL analytics API providing EPA-based insights.
All routes prefixed with /football/ for compatibility with merged API.

Usage:
    uvicorn api.main:app --reload
"""

import os
import sys
import logging
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

from pipelines.router import QueryRouter, PipelineType
from pipelines.executor import PipelineExecutor
from formatters.response_formatter import ResponseFormatter
from context.presets import ContextManager, UserContext, get_context_manager

# Try to import LLM handler
try:
    from llm.handler import LLMHandler, create_handler
    from llm.client import LLM_AVAILABLE, detect_provider, get_available_models
except ImportError:
    LLM_AVAILABLE = False
    LLMHandler = None
    create_handler = None
    detect_provider = None
    get_available_models = None


# =============================================================================
# Rate Limiter for LLM API Calls
# =============================================================================

class LLMRateLimiter:
    """Rate limiter for LLM API calls (100/day per user)."""
    
    def __init__(self, max_requests_per_day: int = 100):
        self.max_requests = max_requests_per_day
        self.usage: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0,
            'reset_date': self._get_today()
        })
        self._lock = Lock()
    
    def _get_today(self) -> str:
        return datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    def _get_reset_time(self) -> datetime:
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if tomorrow <= now:
            tomorrow += timedelta(days=1)
        return tomorrow
    
    def get_user_id(self, request: Request, session_id: Optional[str] = None) -> str:
        if session_id:
            return f"session:{session_id}"
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        client_ip = request.client.host if request.client else 'unknown'
        return f"ip:{client_ip}"
    
    def check_and_increment(self, user_id: str) -> tuple:
        with self._lock:
            today = self._get_today()
            user_data = self.usage[user_id]
            
            if user_data['reset_date'] != today:
                user_data['count'] = 0
                user_data['reset_date'] = today
            
            remaining = self.max_requests - user_data['count']
            reset_time = self._get_reset_time()
            
            if user_data['count'] >= self.max_requests:
                return False, 0, reset_time
            
            user_data['count'] += 1
            remaining = self.max_requests - user_data['count']
            
            return True, remaining, reset_time
    
    def get_usage(self, user_id: str) -> Dict:
        with self._lock:
            today = self._get_today()
            user_data = self.usage[user_id]
            
            if user_data['reset_date'] != today:
                return {
                    'used': 0,
                    'remaining': self.max_requests,
                    'limit': self.max_requests,
                    'reset_time': self._get_reset_time().isoformat()
                }
            
            return {
                'used': user_data['count'],
                'remaining': self.max_requests - user_data['count'],
                'limit': self.max_requests,
                'reset_time': self._get_reset_time().isoformat()
            }


# Initialize rate limiter
RATE_LIMIT_PER_DAY = int(os.getenv('FOOTBALL_RATE_LIMIT_PER_DAY', '100'))
llm_rate_limiter = LLMRateLimiter(max_requests_per_day=RATE_LIMIT_PER_DAY)


# =============================================================================
# Global Instances
# =============================================================================

router = QueryRouter()
executor = None
formatter = ResponseFormatter()
llm_handler = None


# =============================================================================
# Lifespan Management
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    global executor, llm_handler
    
    # Initialize executor (uses models from trained_models/)
    try:
        executor = PipelineExecutor()
        logger.info("Pipeline executor initialized")
    except Exception as e:
        logger.error(f"Failed to initialize executor: {e}")
        executor = None
    
    # Initialize LLM handler
    if LLM_AVAILABLE and create_handler:
        try:
            llm_handler = create_handler(use_llm=True)
            if executor:
                llm_handler.executor = executor  # Share executor
            logger.info("LLM handler initialized")
        except Exception as e:
            logger.warning(f"LLM initialization failed: {e}")
            llm_handler = None
    
    yield
    
    # Cleanup
    if executor and hasattr(executor, 'close'):
        executor.close()
    if llm_handler and hasattr(llm_handler, 'close'):
        llm_handler.close()


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Football Analytics Chatbot API",
    description="NFL analytics with EPA-based insights",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Request/Response Models
# =============================================================================

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None
    season: int = Field(2025, ge=2016, le=2030)
    use_llm: bool = True
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    text: str
    pipeline: str
    confidence: float
    success: bool
    data: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    used_llm: bool = False
    tier: int = 1
    session_id: Optional[str] = None


# =============================================================================
# API Endpoints - All prefixed with /football/
# =============================================================================

@app.get("/football/health")
async def health_check():
    """Check API health status."""
    provider = None
    model = None
    
    if llm_handler and llm_handler.client:
        try:
            info = llm_handler.client.get_info()
            provider = info.get("provider")
            model = info.get("model")
        except:
            pass
    
    return {
        "status": "healthy",
        "models_loaded": executor is not None,
        "llm_available": llm_handler is not None and llm_handler.client is not None,
        "llm_provider": provider,
        "llm_model": model,
        "rate_limit": {
            "llm_requests_per_day": RATE_LIMIT_PER_DAY
        }
    }


@app.post("/football/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):
    """Main chat endpoint for football analytics queries."""
    if executor is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    session_id = request.session_id or str(uuid.uuid4())
    
    cm = get_context_manager()
    user_ctx = cm.get_or_create(session_id)
    
    if request.context:
        if 'favorite_team' in request.context:
            user_ctx.favorite_team = request.context['favorite_team']
        if 'season' in request.context:
            user_ctx.season = request.context['season']
    
    context = request.context or {}
    if user_ctx:
        context['favorite_team'] = user_ctx.favorite_team
        context['season'] = user_ctx.season
        context['history'] = user_ctx.history.get_context_for_followup()
    
    # Execute pipeline
    route_result = router.route_with_suggestions(request.message, context)
    route = route_result['route']
    result = executor.execute(route)
    
    if not result.get('success', False):
        formatted = formatter.format(result)
        return ChatResponse(
            text=formatted['text'],
            pipeline=route.pipeline.value,
            confidence=route.confidence,
            success=False,
            data=result.get('data'),
            suggestions=route_result.get('suggestions'),
            used_llm=False,
            tier=route.tier,
            session_id=session_id
        )
    
    # Format response
    used_llm = False
    
    if request.use_llm and llm_handler is not None and llm_handler.client:
        user_id = llm_rate_limiter.get_user_id(http_request, session_id)
        allowed, remaining, reset_time = llm_rate_limiter.check_and_increment(user_id)
        
        if not allowed:
            logger.info(f"Rate limit exceeded for {user_id}")
            formatted = formatter.format(result)
            response_text = formatted['text']
            response_text += f"\n\n_Note: LLM rate limit reached ({RATE_LIMIT_PER_DAY}/day). Using structured response._"
        else:
            try:
                from llm.prompts import build_data_grounded_prompt
                
                prompt = build_data_grounded_prompt(
                    query=request.message,
                    pipeline=route.pipeline.value,
                    data=result.get('data', {}),
                    favorite_team=user_ctx.favorite_team if user_ctx else None
                )
                
                llm_response = llm_handler.client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500,
                    temperature=0.7
                )
                
                response_text = llm_response.get('content', '')
                
                if response_text:
                    used_llm = True
                else:
                    formatted = formatter.format(result)
                    response_text = formatted['text']
                    
            except Exception as e:
                logger.warning(f"LLM formatting failed: {e}")
                formatted = formatter.format(result)
                response_text = formatted['text']
    else:
        formatted = formatter.format(result)
        response_text = formatted['text']
    
    if user_ctx:
        user_ctx.history.add_turn(
            query=request.message,
            pipeline=route.pipeline.value,
            params=route.extracted_params
        )
    
    return ChatResponse(
        text=response_text,
        pipeline=route.pipeline.value,
        confidence=route.confidence,
        success=True,
        data=result.get('data'),
        suggestions=route_result.get('suggestions'),
        used_llm=used_llm,
        tier=route.tier,
        session_id=session_id
    )


@app.get("/football/rate-limit/status")
async def get_rate_limit_status(http_request: Request, session_id: Optional[str] = None):
    """Check current LLM rate limit status."""
    user_id = llm_rate_limiter.get_user_id(http_request, session_id)
    return llm_rate_limiter.get_usage(user_id)


@app.get("/football/teams/{team}/profile")
async def get_team_profile(team: str, season: int = 2025):
    """Get a team's full profile."""
    if executor is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    from pipelines.router import RouteResult
    
    route = RouteResult(
        pipeline=PipelineType.TEAM_PROFILE,
        confidence=1.0,
        extracted_params={'team': team.upper(), 'season': season},
        tier=1,
        reasoning="Direct API call"
    )
    
    result = executor.execute(route)
    
    if not result['success']:
        raise HTTPException(status_code=404, detail=result.get('error', 'Team not found'))
    
    return result['data']


@app.get("/football/teams/{team}/tendencies")
async def get_team_tendencies(
    team: str, 
    season: int = 2025, 
    down: Optional[int] = None, 
    distance: Optional[int] = None
):
    """Get a team's play-calling tendencies."""
    if executor is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    from pipelines.router import RouteResult
    
    params = {'team': team.upper(), 'season': season}
    if down:
        params['down'] = down
    if distance:
        params['distance'] = distance
    
    route = RouteResult(
        pipeline=PipelineType.TEAM_TENDENCIES,
        confidence=1.0,
        extracted_params=params,
        tier=1,
        reasoning="Direct API call"
    )
    
    result = executor.execute(route)
    
    if not result['success']:
        raise HTTPException(status_code=404, detail=result.get('error'))
    
    return result['data']


@app.get("/football/teams/compare")
async def compare_teams(team1: str, team2: str, season: int = 2025):
    """Compare two teams head-to-head."""
    if executor is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    from pipelines.router import RouteResult
    
    route = RouteResult(
        pipeline=PipelineType.TEAM_COMPARISON,
        confidence=1.0,
        extracted_params={
            'team1': team1.upper(), 
            'team2': team2.upper(), 
            'season': season
        },
        tier=1,
        reasoning="Direct API call"
    )
    
    result = executor.execute(route)
    
    if not result['success']:
        raise HTTPException(status_code=404, detail=result.get('error'))
    
    return result['data']


@app.get("/football/situation/analyze")
async def analyze_situation(
    down: int,
    distance: int,
    yardline: int = 50,
    score_diff: int = 0,
    quarter: int = 2,
    defenders_in_box: Optional[int] = None,
    season: int = 2025
):
    """Analyze a game situation and get play recommendations."""
    if executor is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    from pipelines.router import RouteResult
    
    params = {
        'down': down,
        'distance': distance,
        'yardline': yardline,
        'score_differential': score_diff,
        'quarter': quarter,
        'season': season
    }
    
    if defenders_in_box:
        params['defenders_in_box'] = defenders_in_box
    
    route = RouteResult(
        pipeline=PipelineType.SITUATION_ANALYSIS,
        confidence=1.0,
        extracted_params=params,
        tier=1,
        reasoning="Direct API call"
    )
    
    result = executor.execute(route)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result.get('error'))
    
    return result['data']


@app.get("/football/teams")
async def list_teams():
    """Get list of all NFL teams."""
    return {
        "teams": {
            "AFC": {
                "East": ["BUF", "MIA", "NE", "NYJ"],
                "North": ["BAL", "CIN", "CLE", "PIT"],
                "South": ["HOU", "IND", "JAX", "TEN"],
                "West": ["DEN", "KC", "LV", "LAC"]
            },
            "NFC": {
                "East": ["DAL", "NYG", "PHI", "WAS"],
                "North": ["CHI", "DET", "GB", "MIN"],
                "South": ["ATL", "CAR", "NO", "TB"],
                "West": ["ARI", "LAR", "SF", "SEA"]
            }
        }
    }


# =============================================================================
# Legacy routes (without /football/ prefix) for backwards compatibility
# =============================================================================

@app.get("/health")
async def health_check_legacy():
    """Legacy health check (redirects to /football/health)."""
    return await health_check()


@app.post("/chat", response_model=ChatResponse)
async def chat_legacy(request: ChatRequest, http_request: Request):
    """Legacy chat endpoint (same as /football/chat)."""
    return await chat(request, http_request)


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)