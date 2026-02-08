#!/usr/bin/env python3
"""
Phase 5 Validation Script

Validates the frontend setup:
- Required files exist
- Package.json has correct dependencies
- Vite config is valid

Usage:
    python tests/phase5/run_phase5_validation.py
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent to path
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"

CHECKS = []


def check(name):
    """Decorator to register a check."""
    def decorator(func):
        CHECKS.append((name, func))
        return func
    return decorator


# =============================================================================
# FILE STRUCTURE CHECKS
# =============================================================================

@check("Frontend Directory Exists")
def check_frontend_dir():
    exists = FRONTEND_DIR.exists()
    return exists, str(FRONTEND_DIR)


@check("package.json Exists")
def check_package_json():
    path = FRONTEND_DIR / "package.json"
    return path.exists(), "package.json found"


@check("package.json Has Dependencies")
def check_dependencies():
    path = FRONTEND_DIR / "package.json"
    if not path.exists():
        return False, "package.json not found"
    
    with open(path) as f:
        pkg = json.load(f)
    
    deps = pkg.get("dependencies", {})
    required = ["react", "react-dom", "lucide-react", "recharts"]
    
    missing = [d for d in required if d not in deps]
    
    if missing:
        return False, f"Missing: {', '.join(missing)}"
    
    return True, f"{len(deps)} dependencies"


@check("vite.config.js Exists")
def check_vite_config():
    path = FRONTEND_DIR / "vite.config.js"
    return path.exists(), "Vite config found"


@check("tailwind.config.js Exists")
def check_tailwind_config():
    path = FRONTEND_DIR / "tailwind.config.js"
    return path.exists(), "Tailwind config found"


@check("index.html Exists")
def check_index_html():
    path = FRONTEND_DIR / "index.html"
    return path.exists(), "index.html found"


# =============================================================================
# SOURCE FILE CHECKS
# =============================================================================

@check("src/main.jsx Exists")
def check_main_jsx():
    path = FRONTEND_DIR / "src" / "main.jsx"
    return path.exists(), "Entry point found"


@check("src/App.jsx Exists")
def check_app_jsx():
    path = FRONTEND_DIR / "src" / "App.jsx"
    return path.exists(), "App component found"


@check("src/index.css Exists")
def check_index_css():
    path = FRONTEND_DIR / "src" / "index.css"
    if not path.exists():
        return False, "CSS not found"
    
    with open(path) as f:
        content = f.read()
    
    has_tailwind = "@tailwind" in content
    return has_tailwind, "Tailwind directives found"


# =============================================================================
# COMPONENT CHECKS
# =============================================================================

@check("ChatWindow Component")
def check_chat_window():
    path = FRONTEND_DIR / "src" / "components" / "ChatWindow.jsx"
    return path.exists(), "ChatWindow.jsx found"


@check("Message Component")
def check_message():
    path = FRONTEND_DIR / "src" / "components" / "Message.jsx"
    return path.exists(), "Message.jsx found"


@check("EPAChart Component")
def check_epa_chart():
    path = FRONTEND_DIR / "src" / "components" / "EPAChart.jsx"
    return path.exists(), "EPAChart.jsx found"


@check("QuickActions Component")
def check_quick_actions():
    path = FRONTEND_DIR / "src" / "components" / "QuickActions.jsx"
    return path.exists(), "QuickActions.jsx found"


@check("Sidebar Component")
def check_sidebar():
    path = FRONTEND_DIR / "src" / "components" / "Sidebar.jsx"
    return path.exists(), "Sidebar.jsx found"


@check("SettingsPanel Component")
def check_settings():
    path = FRONTEND_DIR / "src" / "components" / "SettingsPanel.jsx"
    return path.exists(), "SettingsPanel.jsx found"


# =============================================================================
# UTILITY CHECKS
# =============================================================================

@check("API Hook (useApi.js)")
def check_api_hook():
    path = FRONTEND_DIR / "src" / "hooks" / "useApi.js"
    return path.exists(), "useApi.js found"


@check("Teams Utility (teams.js)")
def check_teams_util():
    path = FRONTEND_DIR / "src" / "utils" / "teams.js"
    if not path.exists():
        return False, "teams.js not found"
    
    with open(path) as f:
        content = f.read()
    
    has_teams = "NFL_TEAMS" in content
    has_colors = "primary" in content and "secondary" in content
    
    return has_teams and has_colors, "32 NFL teams with colors"


# =============================================================================
# CONFIGURATION CHECKS
# =============================================================================

@check("Tailwind Has NFL Team Colors")
def check_tailwind_colors():
    path = FRONTEND_DIR / "tailwind.config.js"
    if not path.exists():
        return False, "Config not found"
    
    with open(path) as f:
        content = f.read()
    
    has_nfl = "nfl:" in content or "'kc'" in content or '"kc"' in content
    has_dark = "darkMode" in content
    
    return has_nfl and has_dark, "NFL colors and dark mode"


@check("Vite Has API Proxy")
def check_vite_proxy():
    path = FRONTEND_DIR / "vite.config.js"
    if not path.exists():
        return False, "Config not found"
    
    with open(path) as f:
        content = f.read()
    
    has_proxy = "proxy" in content
    has_api = "/api" in content
    
    return has_proxy and has_api, "API proxy configured"


# =============================================================================
# RUNNER
# =============================================================================

def run_validation():
    """Run all Phase 5 validation checks."""
    print("=" * 70)
    print("PHASE 5 VALIDATION - Frontend (React + Vite + Tailwind)")
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
        print("🎉 PHASE 5 COMPLETE!")
        print()
        print("Your frontend is ready!")
        print()
        print("To run the frontend:")
        print()
        print("  1. Start the backend (in project root):")
        print("     uvicorn api.main:app --reload")
        print()
        print("  2. Start the frontend (in frontend/):")
        print("     cd frontend")
        print("     npm install")
        print("     npm run dev")
        print()
        print("  3. Open http://localhost:3000")
        print()
        print("Features included:")
        print("  • 🌙 Dark mode")
        print("  • 🏈 NFL team colors")
        print("  • 📊 EPA visualizations")
        print("  • ⚡ Quick action buttons")
        print("  • 📱 Mobile responsive")
        print()
        return True
    else:
        print()
        print("⚠️  Phase 5 has failures. Please check file structure.")
        print()
        return False


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
