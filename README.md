# Football Analytics Chatbot - Backend

An intelligent NFL analytics API that provides data-driven insights using Expected Points Added (EPA), play-by-play analysis, and natural language processing.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- 🏈 **Natural Language Queries**: Ask questions like "Should I run or pass on 3rd and 5?"
- 📊 **EPA-Based Analysis**: All recommendations grounded in Expected Points Added metrics
- 🏟️ **Team Profiles**: Comprehensive statistics for all 32 NFL teams
- ⚔️ **Team Comparisons**: Head-to-head statistical comparisons
- 🎯 **Situational Analysis**: Down, distance, field position, and score-aware recommendations
- 🛡️ **Defensive Formation Support**: Factor in defenders in the box
- 💬 **Conversation History**: Context-aware follow-up questions
- 🤖 **Hybrid LLM Responses**: Accurate data with natural language formatting

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- OpenAI API key (optional, for natural language responses)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/football-chatbot-backend.git
cd football-chatbot-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database URL and API keys
```

### Database Setup

```bash
# Create database
createdb football_analytics

# Run schema
psql -d football_analytics -f database/schema.sql

# Ingest data
python scripts/ingest_pbp.py --seasons 2025

# Build derived tables
python scripts/build_derived_tables.py

# Train models
python training/train_all_models.py
```

### Run the Server

```bash
uvicorn api.main:app --reload
```

API available at `http://localhost:8000`

## API Endpoints

All endpoints are prefixed with `/football/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/football/health` | Health check |
| POST | `/football/chat` | Main chat endpoint |
| GET | `/football/rate-limit/status` | Check rate limit |
| GET | `/football/teams/{team}/profile` | Team profile |
| GET | `/football/teams/{team}/tendencies` | Team tendencies |
| GET | `/football/teams/compare` | Compare two teams |
| GET | `/football/situation/analyze` | Analyze game situation |
| GET | `/football/teams` | List all teams |

### Example: Chat Request

```bash
curl -X POST "http://localhost:8000/football/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me about the Chiefs",
    "season": 2025,
    "use_llm": true
  }'
```

### Example: Situation Analysis

```bash
curl "http://localhost:8000/football/situation/analyze?down=3&distance=5&yardline=40&defenders_in_box=8"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `OPENAI_API_KEY` | OpenAI API key | Optional |
| `LLM_PROVIDER` | `openai` or `anthropic` | `openai` |
| `FOOTBALL_RATE_LIMIT_PER_DAY` | Max LLM requests/user/day | `100` |
| `ALLOWED_ORIGINS` | CORS allowed origins | `*` |

## Rate Limiting

- **Default**: 100 LLM requests per user per day
- **Identification**: Session ID or IP address
- **Bypass**: Set `use_llm: false` for unlimited structured responses

Check your limit:
```bash
curl "http://localhost:8000/football/rate-limit/status?session_id=your-session"
```

## Project Structure

```
football-chatbot-backend/
├── api/
│   └── main.py              # FastAPI application
├── pipelines/
│   ├── router.py            # Query routing
│   └── executor.py          # Pipeline execution
├── models/
│   ├── epa_model.py         # EPA predictions
│   └── drive_simulator.py   # Drive simulation
├── llm/
│   ├── client.py            # LLM wrapper
│   ├── handler.py           # Request handling
│   └── prompts.py           # System prompts
├── formatters/
│   └── response_formatter.py
├── database/
│   └── schema.sql
├── scripts/
│   ├── ingest_pbp.py
│   └── build_derived_tables.py
└── training/
    └── train_all_models.py
```

## Deployment

### Railway / Render

1. Connect GitHub repository
2. Set environment variables
3. Deploy with: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`

### Docker

```bash
docker build -t football-chatbot-backend .
docker run -p 8000:8000 --env-file .env football-chatbot-backend
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [nflfastR](https://github.com/nflverse/nflverse-data) for play-by-play data
- [nflverse](https://nflverse.com/) community
