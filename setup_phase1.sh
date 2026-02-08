#!/bin/bash
# Phase 1 Quick Setup Script
# Run: chmod +x setup_phase1.sh && ./setup_phase1.sh

set -e

echo "=========================================="
echo "Football Analytics Chatbot - Phase 1 Setup"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.9+"
    exit 1
fi
echo "✅ Python found: $(python3 --version)"

# Create directory structure
echo ""
echo "Creating directory structure..."
mkdir -p data/raw data/processed
mkdir -p database
mkdir -p scripts
mkdir -p tests/phase1
mkdir -p config

echo "✅ Directories created"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate and install dependencies
echo ""
echo "Installing dependencies..."
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "✅ Dependencies installed"

# Check for DATABASE_URL
echo ""
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️  DATABASE_URL not set"
    echo ""
    echo "Please set your database URL:"
    echo "  export DATABASE_URL='postgresql://user:pass@localhost:5432/football_analytics'"
    echo ""
    echo "Or create a .env file with:"
    echo "  DATABASE_URL=postgresql://user:pass@localhost:5432/football_analytics"
    echo ""
    
    # Create .env template
    if [ ! -f ".env" ]; then
        echo "# Database Configuration" > .env
        echo "DATABASE_URL=postgresql://localhost:5432/football_analytics" >> .env
        echo "Created .env template - please update with your credentials"
    fi
else
    echo "✅ DATABASE_URL is set"
fi

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Ensure PostgreSQL is running"
echo "  2. Create database: createdb football_analytics"
echo "  3. Set DATABASE_URL environment variable"
echo "  4. Run: psql \$DATABASE_URL -f database/schema.sql"
echo "  5. Run: psql \$DATABASE_URL -f database/indexes.sql"
echo "  6. Run: python scripts/ingest_pbp.py"
echo "  7. Run: python scripts/build_derived_tables.py"
echo "  8. Run: python tests/phase1/run_phase1_validation.py"
echo ""
