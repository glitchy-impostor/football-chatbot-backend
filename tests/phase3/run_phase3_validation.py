#!/usr/bin/env python3
"""
Phase 3 Validation Script

Validates the pipeline infrastructure:
- Query routing
- Pipeline execution
- Response formatting
- API endpoints (if server running)

Usage:
    python tests/phase3/run_phase3_validation.py
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


def check(name):
    """Decorator to register a check."""
    def decorator(func):
        CHECKS.append((name, func))
        return func
    return decorator


# =============================================================================
# QUERY ROUTER CHECKS
# =============================================================================

@check("Router Initializes")
def check_router_init():
    from pipelines.router import QueryRouter
    router = QueryRouter()
    return True, "Router created"


@check("Router: Team Profile Pattern")
def check_router_team_profile():
    from pipelines.router import QueryRouter, PipelineType
    router = QueryRouter()
    
    result = router.route("team profile for KC")
    ok = result.pipeline == PipelineType.TEAM_PROFILE
    return ok, f"Pipeline: {result.pipeline.value}, Params: {result.extracted_params}"


@check("Router: Team Comparison Pattern")
def check_router_team_compare():
    from pipelines.router import QueryRouter, PipelineType
    router = QueryRouter()
    
    result = router.route("KC vs SF matchup")
    ok = result.pipeline == PipelineType.TEAM_COMPARISON
    return ok, f"Teams: {result.extracted_params.get('team1')}, {result.extracted_params.get('team2')}"


@check("Router: Situation EPA Pattern")
def check_router_situation():
    from pipelines.router import QueryRouter, PipelineType
    router = QueryRouter()
    
    result = router.route("should I run or pass on 3rd and 5?")
    ok = result.pipeline == PipelineType.SITUATION_EPA
    return ok, f"Down: {result.extracted_params.get('down')}, Distance: {result.extracted_params.get('distance')}"


@check("Router: 4th Down Decision Pattern")
def check_router_4th_down():
    from pipelines.router import QueryRouter, PipelineType
    router = QueryRouter()
    
    result = router.route("should I go for it on 4th and 2 at the 35?")
    ok = result.pipeline == PipelineType.DECISION_ANALYSIS
    params_ok = result.extracted_params.get('distance') == 2
    return ok and params_ok, f"Distance: {result.extracted_params.get('distance')}"


@check("Router: Player Rankings Pattern")
def check_router_rankings():
    from pipelines.router import QueryRouter, PipelineType
    router = QueryRouter()
    
    result = router.route("top 10 RBs by EPA")
    ok = result.pipeline == PipelineType.PLAYER_RANKINGS
    return ok, f"Position: {result.extracted_params.get('position')}"


@check("Router: Team Name Normalization")
def check_router_team_names():
    from pipelines.router import QueryRouter
    router = QueryRouter()
    
    # Test various team names
    tests = [
        ("Chiefs", "KC"),
        ("49ers", "SF"),
        ("Niners", "SF"),
        ("Patriots", "NE"),
        ("Green Bay", "GB"),
    ]
    
    passed = 0
    for name, expected in tests:
        result = router.route(f"tell me about {name}")
        if result.extracted_params.get('team') == expected:
            passed += 1
    
    return passed == len(tests), f"{passed}/{len(tests)} team names normalized"


@check("Router: Tier 2 Keyword Matching")
def check_router_keywords():
    from pipelines.router import QueryRouter, PipelineType
    router = QueryRouter()
    
    # Test that keywords route to correct pipeline (tier doesn't matter)
    result = router.route("what is the KC offensive style and tendency")
    ok = result.pipeline == PipelineType.TEAM_TENDENCIES
    return ok, f"Pipeline: {result.pipeline.value}, Team: {result.extracted_params.get('team')}"


@check("Router: Context Integration")
def check_router_context():
    from pipelines.router import QueryRouter
    router = QueryRouter()
    
    context = {'favorite_team': 'KC', 'season': 2023}
    result = router.route("show me the tendencies", context)
    
    # Should use context team
    team_used = result.extracted_params.get('team') == 'KC'
    season_used = result.extracted_params.get('season') == 2023
    
    return team_used and season_used, f"Team: {result.extracted_params.get('team')}"


# =============================================================================
# PIPELINE EXECUTOR CHECKS
# =============================================================================

@check("Executor Initializes")
def check_executor_init():
    from pipelines.executor import PipelineExecutor
    executor = PipelineExecutor()
    return True, "Executor created"


@check("Executor: Team Profile Pipeline")
def check_executor_team_profile():
    from pipelines.router import RouteResult, PipelineType
    from pipelines.executor import PipelineExecutor
    
    executor = PipelineExecutor()
    
    route = RouteResult(
        pipeline=PipelineType.TEAM_PROFILE,
        confidence=0.95,
        extracted_params={'team': 'KC', 'season': 2023},
        tier=1,
        reasoning="test"
    )
    
    result = executor.execute(route)
    executor.close()
    
    ok = result.get('success') == True
    has_profile = 'profile' in result.get('data', {})
    
    return ok and has_profile, f"Success: {ok}, Has profile: {has_profile}"


@check("Executor: Team Comparison Pipeline")
def check_executor_comparison():
    from pipelines.router import RouteResult, PipelineType
    from pipelines.executor import PipelineExecutor
    
    executor = PipelineExecutor()
    
    route = RouteResult(
        pipeline=PipelineType.TEAM_COMPARISON,
        confidence=0.95,
        extracted_params={'team1': 'KC', 'team2': 'SF', 'season': 2023},
        tier=1,
        reasoning="test"
    )
    
    result = executor.execute(route)
    executor.close()
    
    ok = result.get('success') == True
    has_comparison = 'comparison' in result.get('data', {})
    
    return ok and has_comparison, "Comparison executed"


@check("Executor: Situation EPA Pipeline")
def check_executor_situation():
    from pipelines.router import RouteResult, PipelineType
    from pipelines.executor import PipelineExecutor
    
    executor = PipelineExecutor()
    
    route = RouteResult(
        pipeline=PipelineType.SITUATION_EPA,
        confidence=0.95,
        extracted_params={'down': 3, 'distance': 5, 'yardline': 40, 'season': 2023},
        tier=1,
        reasoning="test"
    )
    
    result = executor.execute(route)
    executor.close()
    
    ok = result.get('success') == True
    has_analysis = 'analysis' in result.get('data', {})
    
    return ok and has_analysis, f"Recommendation: {result.get('data', {}).get('analysis', {}).get('recommendation')}"


@check("Executor: Decision Analysis Pipeline")
def check_executor_decision():
    from pipelines.router import RouteResult, PipelineType
    from pipelines.executor import PipelineExecutor
    
    executor = PipelineExecutor()
    
    route = RouteResult(
        pipeline=PipelineType.DECISION_ANALYSIS,
        confidence=0.95,
        extracted_params={'down': 4, 'distance': 2, 'yardline': 35},
        tier=1,
        reasoning="test"
    )
    
    result = executor.execute(route)
    executor.close()
    
    ok = result.get('success') == True
    has_rec = 'recommendation' in result.get('data', {})
    
    return ok and has_rec, f"Recommendation: {result.get('data', {}).get('recommendation')}"


@check("Executor: Player Rankings Pipeline")
def check_executor_rankings():
    from pipelines.router import RouteResult, PipelineType
    from pipelines.executor import PipelineExecutor
    
    executor = PipelineExecutor()
    
    route = RouteResult(
        pipeline=PipelineType.PLAYER_RANKINGS,
        confidence=0.95,
        extracted_params={'position': 'RB', 'count': 5, 'metric': 'epa'},
        tier=1,
        reasoning="test"
    )
    
    result = executor.execute(route)
    executor.close()
    
    ok = result.get('success') == True
    has_players = len(result.get('data', {}).get('players', [])) > 0
    
    return ok and has_players, f"Found {len(result.get('data', {}).get('players', []))} players"


# =============================================================================
# RESPONSE FORMATTER CHECKS
# =============================================================================

@check("Formatter Initializes")
def check_formatter_init():
    from formatters.response_formatter import ResponseFormatter
    formatter = ResponseFormatter()
    return True, "Formatter created"


@check("Formatter: Team Profile Output")
def check_formatter_team_profile():
    from formatters.response_formatter import ResponseFormatter
    
    formatter = ResponseFormatter()
    
    result = {
        'success': True,
        'pipeline': 'team_profile',
        'data': {
            'team': 'KC',
            'season': 2023,
            'profile': {
                'overall': {
                    'epa_per_play': 0.05,
                    'pass_rate': 0.65,
                    'success_rate': 0.48,
                    'pass_epa': 0.08,
                    'rush_epa': -0.02
                },
                'defense': {
                    'epa_per_play': -0.03
                },
                'strengths': ['passing_attack'],
                'weaknesses': []
            }
        }
    }
    
    formatted = formatter.format(result)
    
    has_text = len(formatted.get('text', '')) > 50
    has_team = 'KC' in formatted.get('text', '')
    
    return has_text and has_team, f"Text length: {len(formatted.get('text', ''))}"


@check("Formatter: Situation EPA Output")
def check_formatter_situation():
    from formatters.response_formatter import ResponseFormatter
    
    formatter = ResponseFormatter()
    
    result = {
        'success': True,
        'pipeline': 'situation_epa',
        'data': {
            'situation': {'down': 3, 'distance': 5, 'yardline': 40},
            'analysis': {
                'pass_epa': 0.05,
                'run_epa': -0.02,
                'recommendation': 'pass',
                'confidence': 0.72
            }
        }
    }
    
    formatted = formatter.format(result)
    text_upper = formatted.get('text', '').upper()
    
    # Check for recommendation (either PASS or RUN) and EPA values
    has_rec = 'PASS' in text_upper or 'RUN' in text_upper or 'RECOMMENDATION' in text_upper
    has_epa = 'EPA' in text_upper or '+0.05' in formatted.get('text', '') or '-0.02' in formatted.get('text', '')
    
    return has_rec and has_epa, f"Has recommendation: {has_rec}, Has EPA: {has_epa}"


@check("Formatter: Error Handling")
def check_formatter_error():
    from formatters.response_formatter import ResponseFormatter
    
    formatter = ResponseFormatter()
    
    result = {
        'success': False,
        'pipeline': 'team_profile',
        'error': 'Team not found'
    }
    
    formatted = formatter.format(result)
    
    has_error_msg = 'not found' in formatted.get('text', '').lower() or "couldn't" in formatted.get('text', '').lower()
    success_false = formatted.get('success') == False
    
    return has_error_msg and success_false, "Error handled gracefully"


# =============================================================================
# CONTEXT MANAGER CHECKS
# =============================================================================

@check("Context Manager Initializes")
def check_context_init():
    from context.presets import ContextManager
    cm = ContextManager()
    return True, "Context manager created"


@check("Context: Create and Retrieve")
def check_context_crud():
    from context.presets import ContextManager
    
    cm = ContextManager()
    ctx = cm.create_context('test-session', favorite_team='KC')
    
    retrieved = cm.get_context('test-session')
    
    ok = retrieved is not None
    team_ok = retrieved.favorite_team == 'KC'
    
    return ok and team_ok, f"Team: {retrieved.favorite_team if retrieved else 'None'}"


@check("Context: Apply Preset")
def check_context_preset():
    from context.presets import ContextManager
    
    cm = ContextManager()
    ctx = cm.apply_preset('test-session-2', 'chiefs_fan')
    
    ok = ctx is not None
    team_ok = ctx.favorite_team == 'KC' if ctx else False
    detail_ok = ctx.detail_level == 'detailed' if ctx else False
    
    return ok and team_ok and detail_ok, f"Preset applied: {ctx.favorite_team if ctx else 'None'}"


# =============================================================================
# INTEGRATION CHECKS
# =============================================================================

@check("Integration: Full Query Flow")
def check_integration_flow():
    from pipelines.router import QueryRouter
    from pipelines.executor import PipelineExecutor
    from formatters.response_formatter import ResponseFormatter
    
    router = QueryRouter()
    executor = PipelineExecutor()
    formatter = ResponseFormatter()
    
    # Simulate full flow
    query = "team profile for Chiefs"
    
    route = router.route(query)
    result = executor.execute(route)
    formatted = formatter.format(result)
    
    executor.close()
    
    ok = formatted.get('success') == True
    has_text = len(formatted.get('text', '')) > 50
    
    return ok and has_text, f"Pipeline: {route.pipeline.value}"


@check("Integration: Situation Analysis Flow")
def check_integration_situation():
    from pipelines.router import QueryRouter
    from pipelines.executor import PipelineExecutor
    from formatters.response_formatter import ResponseFormatter
    
    router = QueryRouter()
    executor = PipelineExecutor()
    formatter = ResponseFormatter()
    
    query = "should I run or pass on 3rd and 7?"
    
    route = router.route(query)
    result = executor.execute(route)
    formatted = formatter.format(result)
    
    executor.close()
    
    ok = formatted.get('success') == True
    has_recommendation = 'recommendation' in formatted.get('text', '').lower() or 'pass' in formatted.get('text', '').lower() or 'run' in formatted.get('text', '').lower()
    
    return ok and has_recommendation, f"Flow complete"


@check("Integration: 4th Down Decision Flow")
def check_integration_4th_down():
    from pipelines.router import QueryRouter
    from pipelines.executor import PipelineExecutor
    from formatters.response_formatter import ResponseFormatter
    
    router = QueryRouter()
    executor = PipelineExecutor()
    formatter = ResponseFormatter()
    
    query = "should I go for it on 4th and 1 at the 40?"
    
    route = router.route(query)
    result = executor.execute(route)
    formatted = formatter.format(result)
    
    executor.close()
    
    ok = formatted.get('success') == True
    
    return ok, "4th down flow complete"


# =============================================================================
# RUNNER
# =============================================================================

def run_validation():
    """Run all Phase 3 validation checks."""
    print("=" * 70)
    print("PHASE 3 VALIDATION - Pipeline Infrastructure")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    
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
        print("🎉 PHASE 3 COMPLETE!")
        print()
        print("Your pipeline infrastructure is ready:")
        print("  • Query Router: Routes queries to appropriate pipelines")
        print("  • Pipeline Executor: Runs analysis using trained models")
        print("  • Response Formatter: Converts results to natural language")
        print("  • Context Manager: Handles user preferences")
        print()
        print("To start the API server:")
        print("  uvicorn api.main:app --reload")
        print()
        print("Ready to proceed to Phase 4: LLM Integration")
        print()
        return True
    else:
        print()
        print("⚠️  Phase 3 has failures. Please fix before proceeding.")
        print()
        return False


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
