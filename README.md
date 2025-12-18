# Haku - AI Orchestration Hub

AI orchestration with governance, multi-AI routing, and Heritage LLM integration.

## Features

- **Multi-AI Routing**: Routes to Claude, GPT, Gemini, or Ollama based on privacy tier and task type
- **Privacy Tiers**: 
  - Tier 3 (Secrets) → Local Ollama only
  - Tier 2 (Important) → Claude
  - Tier 1 (Planning) → GPT  
  - Tier 0 (Generic) → Task-based routing
- **Heritage LLM**: Query 63,085 encrypted paragraphs of knowledge
- **Session Auth**: Password unlocks encryption key, stays in memory until logout
- **Mobile Responsive**: Works on phone and desktop

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file (copy from `.env.example`):
```bash
cp .env.example .env
# Edit .env with your credentials
```

3. Run server:
```bash
python main.py
```

4. Open browser:
```
http://localhost:8000/index.html
```

## Railway Deployment

1. Push to GitHub (already connected to Railway)

2. Railway will auto-detect and deploy

3. Environment variables already set:
   - DATABASE_URL
   - ANTHROPIC_API_KEY
   - OPENAI_API_KEY
   - GOOGLE_API_KEY
   - ENCRYPTION_PASSWORD (add this one)

4. Access at your Railway URL

## API Endpoints

- `GET /` - Service info
- `POST /auth` - Authenticate and get session
- `POST /chat` - Send message (requires session_id)
- `POST /file-operation` - Preview file operations
- `GET /health` - Health check

## Architecture

```
User → Frontend (React) → FastAPI Backend → Multi-AI Router
                                         → Heritage LLM (PostgreSQL)
```

Privacy Tier determines AI routing:
- Tier 3: Ollama (local, secrets never leave)
- Tier 2: Claude (best reasoning)
- Tier 1: GPT (planning/strategy)
- Tier 0: Task-based (code→GPT, image→Gemini, default→Claude)

## Next Steps

1. **Add HGC-01 Validation**: Multi-AI cross-verification before returning response
2. **Auto-Apply Files**: Show what/why/trade-offs, user approves, Haku writes files
3. **Mobile App**: Convert to React Native
4. **Ollama Cloud**: Add as fallback for Tier 2 when needed

## File Structure

```
haku/
├── main.py              # FastAPI backend
├── index.html           # React frontend  
├── requirements.txt     # Python dependencies
├── Procfile            # Railway deployment
├── .env                # Local config (not committed)
└── .env.example        # Config template
```
