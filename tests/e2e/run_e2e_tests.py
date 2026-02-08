#!/usr/bin/env python3
"""
Comprehensive End-to-End Test Suite

Tests the full pipeline from user query to server response.
Logs all outputs to a file for manual analysis.

Usage:
    python tests/e2e/run_e2e_tests.py

Output:
    tests/e2e/test_results.txt
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Configuration
API_BASE = "http://localhost:8000"
OUTPUT_FILE = Path(__file__).parent / "test_results.txt"

# Test cases organized by category
TEST_CASES = [
    # ==========================================================================
    # SITUATION ANALYSIS - Testing yardline extraction
    # ==========================================================================
    {
        "category": "Situation Analysis - Yardline Parsing",
        "query": "Should I run or pass on 3rd and 5 at my 36",
        "expected_params": {"down": 3, "distance": 5, "yardline": 36},
        "notes": "User says 'at my 36' - should parse yardline as 36"
    },
    {
        "category": "Situation Analysis - Yardline Parsing",
        "query": "run or pass on 2nd and 8 at the 40 yard line",
        "expected_params": {"down": 2, "distance": 8, "yardline": 40},
        "notes": "Explicit 'at the 40 yard line'"
    },
    {
        "category": "Situation Analysis - Yardline Parsing",
        "query": "3rd and 7 from the 25",
        "expected_params": {"down": 3, "distance": 7, "yardline": 25},
        "notes": "'from the 25' format"
    },
    {
        "category": "Situation Analysis - Yardline Parsing",
        "query": "should I pass on 1st and 10 at midfield",
        "expected_params": {"down": 1, "distance": 10, "yardline": 50},
        "notes": "'midfield' should map to 50"
    },
    {
        "category": "Situation Analysis - Yardline Parsing",
        "query": "run or pass 3rd and 2 on their 15",
        "expected_params": {"down": 3, "distance": 2, "yardline": 15},
        "notes": "'on their 15' - opponent's territory"
    },
    {
        "category": "Situation Analysis - Yardline Parsing",
        "query": "2nd and goal from the 3",
        "expected_params": {"down": 2, "distance": 3, "yardline": 3},
        "notes": "Goal line situation"
    },
    {
        "category": "Situation Analysis - No Yardline",
        "query": "should I run or pass on 3rd and 5",
        "expected_params": {"down": 3, "distance": 5},
        "notes": "No yardline specified - should use default (50)"
    },
    
    # ==========================================================================
    # 4TH DOWN DECISIONS - Testing yardline extraction
    # ==========================================================================
    {
        "category": "4th Down - Yardline Parsing",
        "query": "should I go for it on 4th and 2 at the 35",
        "expected_params": {"down": 4, "distance": 2, "yardline": 35},
        "notes": "Standard 4th down query"
    },
    {
        "category": "4th Down - Yardline Parsing",
        "query": "4th and 1 at my own 28",
        "expected_params": {"down": 4, "distance": 1, "yardline": 72},
        "notes": "'my own 28' = 100-28 = 72 yards from opponent endzone"
    },
    {
        "category": "4th Down - Yardline Parsing",
        "query": "go for it on 4th and goal from the 1",
        "expected_params": {"down": 4, "distance": 1, "yardline": 1},
        "notes": "Goal line 4th down"
    },
    {
        "category": "4th Down - Yardline Parsing",
        "query": "4th and 5 at the opponent's 40",
        "expected_params": {"down": 4, "distance": 5, "yardline": 40},
        "notes": "Opponent's territory explicit"
    },
    
    # ==========================================================================
    # TEAM PROFILES
    # ==========================================================================
    {
        "category": "Team Profile",
        "query": "Tell me about the Chiefs",
        "expected_params": {"team": "KC"},
        "notes": "Full team name"
    },
    {
        "category": "Team Profile",
        "query": "team profile for KC",
        "expected_params": {"team": "KC"},
        "notes": "Abbreviation"
    },
    {
        "category": "Team Profile",
        "query": "How good are the 49ers",
        "expected_params": {"team": "SF"},
        "notes": "Nickname parsing"
    },
    {
        "category": "Team Profile",
        "query": "tell me about the niners",
        "expected_params": {"team": "SF"},
        "notes": "Alternate nickname"
    },
    {
        "category": "Team Profile",
        "query": "Ravens offense",
        "expected_params": {"team": "BAL"},
        "notes": "Partial query"
    },
    
    # ==========================================================================
    # TEAM COMPARISONS
    # ==========================================================================
    {
        "category": "Team Comparison",
        "query": "KC vs SF",
        "expected_params": {"team1": "KC", "team2": "SF"},
        "notes": "Simple vs format"
    },
    {
        "category": "Team Comparison",
        "query": "compare the Chiefs and Ravens",
        "expected_params": {"team1": "KC", "team2": "BAL"},
        "notes": "Full names with 'compare'"
    },
    {
        "category": "Team Comparison",
        "query": "Bills versus Dolphins matchup",
        "expected_params": {"team1": "BUF", "team2": "MIA"},
        "notes": "'versus' and 'matchup'"
    },
    {
        "category": "Team Comparison",
        "query": "How do the Eagles match up against Dallas",
        "expected_params": {"team1": "PHI", "team2": "DAL"},
        "notes": "Natural language comparison"
    },
    
    # ==========================================================================
    # TEAM TENDENCIES
    # ==========================================================================
    {
        "category": "Team Tendencies",
        "query": "How often do the Ravens pass",
        "expected_params": {"team": "BAL"},
        "notes": "Pass rate question"
    },
    {
        "category": "Team Tendencies",
        "query": "Chiefs tendencies on third down",
        "expected_params": {"team": "KC", "down": 3},
        "notes": "Situational tendencies"
    },
    {
        "category": "Team Tendencies",
        "query": "what is the KC offensive style",
        "expected_params": {"team": "KC"},
        "notes": "Style question"
    },
    
    # ==========================================================================
    # PLAYER RANKINGS
    # ==========================================================================
    {
        "category": "Player Rankings",
        "query": "top 10 running backs by EPA",
        "expected_params": {"position": "RB", "count": 10},
        "notes": "RB rankings"
    },
    {
        "category": "Player Rankings",
        "query": "best quarterbacks",
        "expected_params": {"position": "QB"},
        "notes": "QB without count"
    },
    {
        "category": "Player Rankings",
        "query": "top 5 wide receivers",
        "expected_params": {"position": "WR", "count": 5},
        "notes": "WR with count"
    },
    {
        "category": "Player Rankings",
        "query": "best TEs by yards",
        "expected_params": {"position": "TE", "metric": "yards"},
        "notes": "TE by yards metric"
    },
    
    # ==========================================================================
    # EDGE CASES & AMBIGUOUS QUERIES
    # ==========================================================================
    {
        "category": "Edge Case",
        "query": "KC",
        "expected_params": {"team": "KC"},
        "notes": "Just team abbreviation"
    },
    {
        "category": "Edge Case",
        "query": "run or pass",
        "expected_params": {},
        "notes": "Missing situation details"
    },
    {
        "category": "Edge Case",
        "query": "should I go for it",
        "expected_params": {},
        "notes": "Missing 4th down details"
    },
    {
        "category": "Edge Case",
        "query": "what's the weather like",
        "expected_params": {},
        "notes": "Unrelated query - should fallback"
    },
    {
        "category": "Edge Case",
        "query": "3rd and 5",
        "expected_params": {"down": 3, "distance": 5},
        "notes": "Just down and distance"
    },
    
    # ==========================================================================
    # CONTEXT-DEPENDENT QUERIES
    # ==========================================================================
    {
        "category": "Context",
        "query": "How do we match up against the Ravens",
        "context": {"favorite_team": "KC"},
        "expected_params": {"team1": "KC", "team2": "BAL"},
        "notes": "Uses favorite team from context"
    },
    {
        "category": "Context",
        "query": "tell me about my team",
        "context": {"favorite_team": "SF"},
        "expected_params": {"team": "SF"},
        "notes": "'my team' with context"
    },
    
    # ==========================================================================
    # DEFENSIVE FORMATION TESTS
    # ==========================================================================
    {
        "category": "Defensive Formation",
        "query": "run or pass on 2nd and 5 at the 30 with 8 in the box",
        "expected_params": {"down": 2, "distance": 5, "yardline": 30, "defenders_in_box": 8},
        "notes": "Stacked box should favor pass"
    },
    {
        "category": "Defensive Formation", 
        "query": "3rd and 2 at the 40 with a light box",
        "expected_params": {"down": 3, "distance": 2, "yardline": 40, "defenders_in_box": 6},
        "notes": "Light box should favor run"
    },
    {
        "category": "Defensive Formation",
        "query": "should I run with 6 men in the box on 1st and 10",
        "expected_params": {"down": 1, "distance": 10, "defenders_in_box": 6},
        "notes": "Light box run situation"
    },
    
    # ==========================================================================
    # NATURAL LANGUAGE VARIATIONS
    # ==========================================================================
    {
        "category": "Natural Language",
        "query": "KC stats",
        "expected_params": {"team": "KC"},
        "notes": "Short team stats query"
    },
    {
        "category": "Natural Language",
        "query": "How good are the Eagles?",
        "expected_params": {"team": "PHI"},
        "notes": "Conversational team query"
    },
    {
        "category": "Natural Language",
        "query": "Compare Chiefs and Bills",
        "expected_params": {"team1": "KC", "team2": "BUF"},
        "notes": "'Compare X and Y' pattern"
    },
    {
        "category": "Natural Language",
        "query": "Who's better Chiefs or 49ers?",
        "expected_params": {"team1": "KC", "team2": "SF"},
        "notes": "'Who's better X or Y' pattern"
    },
]


class TestRunner:
    def __init__(self, api_base: str = API_BASE):
        self.api_base = api_base
        self.results: List[Dict] = []
        self.log_lines: List[str] = []
        
    def log(self, message: str):
        """Add to log."""
        print(message)
        self.log_lines.append(message)
    
    def check_health(self) -> bool:
        """Check if API is running."""
        try:
            resp = requests.get(f"{self.api_base}/health", timeout=5)
            return resp.status_code == 200
        except:
            return False
    
    def send_chat(self, query: str, context: Optional[Dict] = None) -> Dict:
        """Send a chat message and return full response."""
        payload = {
            "message": query,
            "session_id": f"test-{datetime.now().timestamp()}",
            "use_llm": False,  # Use pipeline mode for consistent testing
        }
        
        if context:
            payload["context"] = context
        
        try:
            resp = requests.post(
                f"{self.api_base}/chat",
                json=payload,
                timeout=30
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    def run_test(self, test_case: Dict) -> Dict:
        """Run a single test case."""
        query = test_case["query"]
        context = test_case.get("context")
        expected = test_case.get("expected_params", {})
        
        # Send request
        response = self.send_chat(query, context)
        
        # Extract key info
        result = {
            "query": query,
            "category": test_case.get("category", "Unknown"),
            "notes": test_case.get("notes", ""),
            "context": context,
            "expected_params": expected,
            "response": response,
        }
        
        # Check for parameter extraction issues
        if "data" in response and response.get("data"):
            data = response["data"]
            
            # Check situation params
            if "situation" in data:
                sit = data["situation"]
                result["actual_params"] = {
                    "down": sit.get("down"),
                    "distance": sit.get("ydstogo") or sit.get("distance"),
                    "yardline": sit.get("yardline_100") or sit.get("yardline"),
                }
            
            # Check team params
            if "profile" in data:
                result["actual_params"] = {"team": data.get("team")}
            
            # Check comparison params
            if "comparison" in data:
                result["actual_params"] = {
                    "team1": data.get("team1"),
                    "team2": data.get("team2"),
                }
        
        return result
    
    def run_all(self):
        """Run all test cases."""
        self.log("=" * 80)
        self.log("FOOTBALL CHATBOT - END-TO-END TEST RESULTS")
        self.log(f"Timestamp: {datetime.now().isoformat()}")
        self.log(f"API Base: {self.api_base}")
        self.log("=" * 80)
        self.log("")
        
        # Health check
        self.log("Checking API health...")
        if not self.check_health():
            self.log("❌ API is not running! Start with: uvicorn api.main:app --reload")
            return
        
        health = requests.get(f"{self.api_base}/health").json()
        self.log(f"✅ API Status: {health.get('status')}")
        self.log(f"   LLM Available: {health.get('llm_available')}")
        self.log(f"   LLM Provider: {health.get('llm_provider', 'None')}")
        self.log(f"   LLM Model: {health.get('llm_model', 'None')}")
        self.log("")
        
        # Run tests by category
        current_category = None
        
        for i, test_case in enumerate(TEST_CASES, 1):
            category = test_case.get("category", "Unknown")
            
            # Print category header
            if category != current_category:
                self.log("")
                self.log("-" * 80)
                self.log(f"CATEGORY: {category}")
                self.log("-" * 80)
                current_category = category
            
            # Run test
            self.log("")
            self.log(f"TEST {i}: {test_case['query']}")
            if test_case.get("notes"):
                self.log(f"  Notes: {test_case['notes']}")
            if test_case.get("context"):
                self.log(f"  Context: {test_case['context']}")
            self.log(f"  Expected Params: {test_case.get('expected_params', {})}")
            
            result = self.run_test(test_case)
            self.results.append(result)
            
            # Log response
            response = result["response"]
            
            if "error" in response:
                self.log(f"  ❌ ERROR: {response['error']}")
            else:
                self.log(f"  Pipeline: {response.get('pipeline', 'unknown')}")
                self.log(f"  Confidence: {response.get('confidence', 0):.2f}")
                self.log(f"  Tier: {response.get('tier', '?')}")
                self.log(f"  Used LLM: {response.get('used_llm', False)}")
                
                # Log actual params if extracted
                if "actual_params" in result:
                    self.log(f"  Actual Params: {result['actual_params']}")
                    
                    # Check for mismatches
                    expected = test_case.get("expected_params", {})
                    actual = result["actual_params"]
                    mismatches = []
                    
                    for key, exp_val in expected.items():
                        act_val = actual.get(key)
                        if act_val != exp_val:
                            mismatches.append(f"{key}: expected {exp_val}, got {act_val}")
                    
                    if mismatches:
                        self.log(f"  ⚠️  MISMATCHES:")
                        for m in mismatches:
                            self.log(f"      - {m}")
                
                # Log response text (truncated)
                text = response.get("text", "")
                if len(text) > 200:
                    text = text[:200] + "..."
                self.log(f"  Response Text: {text}")
                
                # Log raw data structure
                if response.get("data"):
                    self.log(f"  Raw Data Keys: {list(response['data'].keys())}")
        
        # Summary
        self.log("")
        self.log("=" * 80)
        self.log("SUMMARY")
        self.log("=" * 80)
        self.log(f"Total Tests: {len(TEST_CASES)}")
        
        # Count issues
        issues = []
        for r in self.results:
            response = r.get("response", {})
            
            # Check for explicit error
            if "error" in response:
                issues.append(f"ERROR: {r['query']} - {response.get('error', 'Unknown error')}")
            
            # Check for success: false
            elif response.get("success") == False:
                error_text = response.get("text", "Unknown error")
                if "couldn't" in error_text.lower() or "not found" in error_text.lower():
                    issues.append(f"FAILED: {r['query']} - {error_text[:100]}")
            
            # Check param mismatches
            elif "actual_params" in r:
                expected = r.get("expected_params", {})
                actual = r["actual_params"]
                for key, exp_val in expected.items():
                    if actual.get(key) != exp_val:
                        issues.append(f"MISMATCH in '{r['query']}': {key} expected {exp_val}, got {actual.get(key)}")
        
        if issues:
            self.log(f"Issues Found: {len(issues)}")
            self.log("")
            for issue in issues:
                self.log(f"  ⚠️  {issue}")
        else:
            self.log("No issues found!")
        
        self.log("")
        self.log("=" * 80)
        self.log("RAW RESPONSE DATA")
        self.log("=" * 80)
        
        # Dump full response data for each test
        for i, result in enumerate(self.results, 1):
            self.log("")
            self.log(f"--- TEST {i}: {result['query']} ---")
            self.log(json.dumps(result["response"], indent=2, default=str))
    
    def save_results(self, filepath: Path = OUTPUT_FILE):
        """Save results to file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(self.log_lines))
        
        print(f"\nResults saved to: {filepath}")


def main():
    runner = TestRunner()
    runner.run_all()
    runner.save_results()


if __name__ == "__main__":
    main()
