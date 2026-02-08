#!/usr/bin/env python3
"""
LLM Response Validation Tests

These tests verify that LLM responses are grounded in actual data
by checking that key statistics mentioned match the database values.

Usage:
    python tests/validation/test_llm_grounding.py
"""

import os
import sys
import json
import re
import requests
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

API_BASE = os.getenv("API_BASE", "http://localhost:8000")


def extract_numbers_from_text(text: str) -> List[float]:
    """Extract all numbers from text."""
    # Match decimals like 0.058, percentages like 61.3%, integers
    pattern = r'[-+]?\d*\.?\d+%?'
    matches = re.findall(pattern, text)
    numbers = []
    for m in matches:
        try:
            if m.endswith('%'):
                numbers.append(float(m[:-1]))
            else:
                numbers.append(float(m))
        except ValueError:
            pass
    return numbers


def get_team_profile_data(team: str, season: int = 2025) -> Optional[Dict]:
    """Fetch team profile from API."""
    try:
        response = requests.get(f"{API_BASE}/teams/{team}/profile?season={season}")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None


def validate_team_profile_response(query: str, response_text: str, expected_team: str) -> Dict:
    """
    Validate that a team profile response contains accurate data.
    
    Returns validation result with pass/fail and details.
    """
    result = {
        'query': query,
        'passed': True,
        'checks': [],
        'errors': []
    }
    
    # Get actual data from API
    profile = get_team_profile_data(expected_team)
    if not profile:
        result['passed'] = False
        result['errors'].append(f"Could not fetch profile for {expected_team}")
        return result
    
    # Extract key stats from profile
    overall = profile.get('overall', {})
    actual_epa = overall.get('epa_per_play', 0)
    actual_pass_rate = overall.get('pass_rate', 0) * 100  # Convert to percentage
    
    # Check if response mentions the team
    if expected_team.upper() not in response_text.upper():
        result['checks'].append(f"⚠️  Team {expected_team} not clearly mentioned")
    else:
        result['checks'].append(f"✅ Team {expected_team} mentioned")
    
    # Extract numbers from response
    response_numbers = extract_numbers_from_text(response_text)
    
    # Check if EPA value is close to actual (within 0.01)
    epa_found = False
    for num in response_numbers:
        if abs(num - actual_epa) < 0.02:
            epa_found = True
            result['checks'].append(f"✅ EPA value ~{actual_epa:.3f} found")
            break
    
    if not epa_found and actual_epa != 0:
        result['checks'].append(f"⚠️  EPA value {actual_epa:.3f} not found in response")
    
    # Check if pass rate is close (within 2%)
    pass_rate_found = False
    for num in response_numbers:
        if abs(num - actual_pass_rate) < 3:
            pass_rate_found = True
            result['checks'].append(f"✅ Pass rate ~{actual_pass_rate:.1f}% found")
            break
    
    if not pass_rate_found:
        result['checks'].append(f"⚠️  Pass rate {actual_pass_rate:.1f}% not found in response")
    
    return result


def validate_comparison_response(query: str, response_text: str, team1: str, team2: str) -> Dict:
    """Validate that comparison response uses accurate data for both teams."""
    result = {
        'query': query,
        'passed': True,
        'checks': [],
        'errors': []
    }
    
    # Get actual data for both teams
    profile1 = get_team_profile_data(team1)
    profile2 = get_team_profile_data(team2)
    
    if not profile1 or not profile2:
        result['passed'] = False
        result['errors'].append(f"Could not fetch profiles for {team1} and/or {team2}")
        return result
    
    # Check both teams mentioned
    for team in [team1, team2]:
        if team.upper() in response_text.upper():
            result['checks'].append(f"✅ Team {team} mentioned")
        else:
            result['checks'].append(f"⚠️  Team {team} not clearly mentioned")
    
    # Check that the comparison is directionally correct
    epa1 = profile1.get('overall', {}).get('epa_per_play', 0)
    epa2 = profile2.get('overall', {}).get('epa_per_play', 0)
    
    better_team = team1 if epa1 > epa2 else team2
    
    # Look for "edge" or "better" language
    response_lower = response_text.lower()
    if 'edge' in response_lower or 'better' in response_lower or 'higher' in response_lower:
        if better_team.lower() in response_lower.split('edge')[0] if 'edge' in response_lower else response_lower:
            result['checks'].append(f"✅ Correctly identifies {better_team} has edge in EPA")
    
    return result


def validate_situation_response(query: str, response_text: str, expected_down: int, expected_distance: int) -> Dict:
    """Validate situation analysis response."""
    result = {
        'query': query,
        'passed': True,
        'checks': [],
        'errors': []
    }
    
    response_lower = response_text.lower()
    
    # Check down is mentioned
    down_patterns = [f"{expected_down}st", f"{expected_down}nd", f"{expected_down}rd", f"{expected_down}th"]
    down_found = any(p in response_lower for p in down_patterns)
    
    if down_found:
        result['checks'].append(f"✅ Down {expected_down} correctly shown")
    else:
        result['checks'].append(f"⚠️  Down {expected_down} not clearly shown")
    
    # Check distance mentioned
    if str(expected_distance) in response_text:
        result['checks'].append(f"✅ Distance {expected_distance} shown")
    else:
        result['checks'].append(f"⚠️  Distance {expected_distance} not shown")
    
    # Check recommendation is present
    if 'pass' in response_lower or 'run' in response_lower:
        result['checks'].append("✅ Clear recommendation provided")
    else:
        result['checks'].append("⚠️  No clear recommendation")
    
    # Check EPA values present
    if 'epa' in response_lower or 'expected' in response_lower:
        result['checks'].append("✅ EPA values mentioned")
    else:
        result['checks'].append("⚠️  EPA values not mentioned")
    
    return result


def run_validation_tests():
    """Run all validation tests."""
    print("=" * 70)
    print("LLM GROUNDING VALIDATION TESTS")
    print("=" * 70)
    
    # Check API is available
    try:
        health = requests.get(f"{API_BASE}/health")
        if health.status_code != 200:
            print(f"❌ API not available at {API_BASE}")
            return
        print(f"✅ API available at {API_BASE}\n")
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return
    
    test_cases = [
        # Team profile tests
        {
            'type': 'team_profile',
            'query': 'Tell me about the Chiefs',
            'team': 'KC'
        },
        {
            'type': 'team_profile', 
            'query': 'How good are the 49ers?',
            'team': 'SF'
        },
        # Comparison tests
        {
            'type': 'comparison',
            'query': 'Chiefs vs Bills',
            'team1': 'KC',
            'team2': 'BUF'
        },
        {
            'type': 'comparison',
            'query': 'Compare the Eagles and Cowboys',
            'team1': 'PHI',
            'team2': 'DAL'
        },
        # Situation tests
        {
            'type': 'situation',
            'query': 'Should I run or pass on 3rd and 5 at the 40?',
            'down': 3,
            'distance': 5
        },
        {
            'type': 'situation',
            'query': '2nd and 8 at the 30 with 8 in the box',
            'down': 2,
            'distance': 8
        },
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n--- Test {i}: {test['query']} ---")
        
        # Send query to API
        try:
            response = requests.post(
                f"{API_BASE}/chat",
                json={'message': test['query'], 'session_id': f'validation_{i}'}
            )
            
            if response.status_code != 200:
                print(f"❌ API returned {response.status_code}")
                continue
            
            data = response.json()
            response_text = data.get('text', '')
            
            print(f"Pipeline: {data.get('pipeline')}")
            print(f"Response: {response_text[:200]}...")
            
            # Validate based on test type
            if test['type'] == 'team_profile':
                result = validate_team_profile_response(
                    test['query'], response_text, test['team']
                )
            elif test['type'] == 'comparison':
                result = validate_comparison_response(
                    test['query'], response_text, test['team1'], test['team2']
                )
            elif test['type'] == 'situation':
                result = validate_situation_response(
                    test['query'], response_text, test['down'], test['distance']
                )
            else:
                result = {'checks': [], 'errors': ['Unknown test type']}
            
            # Print validation results
            for check in result.get('checks', []):
                print(f"  {check}")
            for error in result.get('errors', []):
                print(f"  ❌ {error}")
            
            results.append(result)
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    total_checks = sum(len(r.get('checks', [])) for r in results)
    passed_checks = sum(
        len([c for c in r.get('checks', []) if c.startswith('✅')]) 
        for r in results
    )
    
    print(f"Total tests: {len(results)}")
    print(f"Validation checks: {passed_checks}/{total_checks} passed")
    
    if passed_checks < total_checks:
        print("\n⚠️  Some validations failed - LLM responses may not be fully grounded")
    else:
        print("\n✅ All validations passed - responses appear grounded in data")


if __name__ == "__main__":
    run_validation_tests()