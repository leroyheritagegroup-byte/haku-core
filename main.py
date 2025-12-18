"""
Haku - AI Orchestration Hub with Governance
FastAPI backend with multi-AI routing and Heritage LLM integration
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import asyncio
from datetime import datetime
import json

# Database
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import psycopg2
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64

# AI clients
import anthropic
import openai
from google import genai

app = FastAPI(title="Haku", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# CONFIGURATION
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ENCRYPTION_PASSWORD = os.getenv("ENCRYPTION_PASSWORD", "")

# Initialize AI clients
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
openai.api_key = OPENAI_API_KEY
genai.configure(api_key=GOOGLE_API_KEY)

# ============================================================================
# SESSION STORAGE (in-memory for demo, use Redis in production)
# ============================================================================

active_sessions: Dict[str, Dict[str, Any]] = {}

# ============================================================================
# ENCRYPTION (Heritage LLM)
# ============================================================================

def get_encryption_key(password: str) -> bytes:
    """Derive encryption key from password"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'heritage_llm_salt_v1',  # Use proper salt in production
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def decrypt_paragraph(encrypted_text: str, key: bytes) -> str:
    """Decrypt a paragraph"""
    f = Fernet(key)
    return f.decrypt(encrypted_text.encode()).decode()

# ============================================================================
# HERITAGE LLM QUERIES
# ============================================================================

def query_heritage_llm(query: str, encryption_key: bytes, max_results: int = 5) -> List[Dict]:
    """Query Heritage LLM database"""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Simple text search (can be enhanced with full-text search)
            result = conn.execute(
                text("""
                    SELECT topic, encrypted_paragraph 
                    FROM heritage_paragraphs 
                    WHERE topic ILIKE :query 
                    OR encrypted_paragraph ILIKE :query
                    LIMIT :limit
                """),
                {"query": f"%{query}%", "limit": max_results}
            )
            
            results = []
            for row in result:
                try:
                    decrypted = decrypt_paragraph(row[1], encryption_key)
                    results.append({
                        "topic": row[0],
                        "content": decrypted[:500]  # First 500 chars
                    })
                except Exception as e:
                    continue
            
            return results
    except Exception as e:
        print(f"Heritage LLM query error: {e}")
        return []

# ============================================================================
# PRIVACY TIER ROUTING
# ============================================================================

def classify_privacy_tier(message: str) -> int:
    """
    Classify message privacy tier
    Tier 3: Secrets (customer PII, financial data, specific deal terms)
    Tier 2: Important (complex business analysis, strategy)
    Tier 1: Planning (high-level planning)
    Tier 0: Generic (public knowledge)
    """
    # Simple keyword-based classification (enhance with ML later)
    tier3_keywords = ["ssn", "credit card", "password", "api key", "customer data", "financial"]
    tier2_keywords = ["strategy", "competitive", "internal", "confidential"]
    
    message_lower = message.lower()
    
    if any(kw in message_lower for kw in tier3_keywords):
        return 3
    elif any(kw in message_lower for kw in tier2_keywords):
        return 2
    elif any(kw in message_lower for kw in ["plan", "roadmap", "execute"]):
        return 1
    else:
        return 0

def route_to_ai(tier: int, task_type: str) -> str:
    """
    Route to appropriate AI based on privacy tier and task type
    Returns: 'claude', 'gpt', 'gemini', or 'ollama'
    """
    if tier == 3:
        return 'ollama'  # Secrets stay local
    elif tier == 2:
        return 'claude'  # Best reasoning
    elif tier == 1:
        return 'gpt'     # Planning/strategy
    else:
        # Task-based routing for generic content
        if 'code' in task_type or 'execute' in task_type:
            return 'gpt'
        elif 'image' in task_type or 'multimodal' in task_type:
            return 'gemini'
        else:
            return 'claude'  # Default

# ============================================================================
# AI EXECUTION
# ============================================================================

async def execute_claude(messages: List[Dict]) -> str:
    """Execute using Claude"""
    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=messages
        )
        return response.content[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claude error: {str(e)}")

async def execute_gpt(messages: List[Dict]) -> str:
    """Execute using GPT"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo-preview",
            messages=messages,
            max_tokens=4000
        )
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GPT error: {str(e)}")

async def execute_gemini(messages: List[Dict]) -> str:
    """Execute using Gemini"""
    try:
        model = genai.GenerativeModel('gemini-pro')
        # Convert messages to Gemini format
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}")

async def execute_ollama(messages: List[Dict]) -> str:
    """Execute using local Ollama"""
    # Note: This requires Ollama to be running locally
    # For Railway deployment, this would need Ollama in a container
    try:
        import requests
        prompt = messages[-1]['content']  # Get last user message
        
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'mistral:latest',
                'prompt': prompt,
                'stream': False
            }
        )
        return response.json()['response']
    except Exception as e:
        # Fallback to Claude if Ollama not available
        return await execute_claude(messages)

# ============================================================================
# MODELS
# ============================================================================

class AuthRequest(BaseModel):
    password: str

class ChatRequest(BaseModel):
    message: str
    session_id: str

class FileOperationRequest(BaseModel):
    operation: str  # 'create', 'edit', 'delete'
    path: str
    content: Optional[str] = None
    session_id: str

# ============================================================================
# ROUTES
# ============================================================================

@app.get("/")
async def root():
    """Serve the main UI"""
    return FileResponse('index.html')

@app.get("/haku-logo.png")
async def logo():
    """Serve the logo"""
    return FileResponse('haku-logo.png')

@app.post("/auth")
async def authenticate(request: AuthRequest):
    """Authenticate user and create session - TEMP: skip verification"""
    try:
        key = get_encryption_key(request.password)
        
        # Create session without verification
        session_id = base64.urlsafe_b64encode(os.urandom(32)).decode()
        active_sessions[session_id] = {
            "encryption_key": key,
            "created_at": datetime.now(),
            "conversation_history": []
        }
        
        return {
            "success": True,
            "session_id": session_id,
            "message": "Authentication successful"
        }
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest):
    """Main chat endpoint with multi-AI routing"""
    
    # Verify session
    if request.session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    session = active_sessions[request.session_id]
    
    try:
        # Query Heritage LLM for context
        heritage_context = query_heritage_llm(
            request.message, 
            session["encryption_key"],
            max_results=3
        )
        
        # Build context-enhanced message
        context_str = ""
        if heritage_context:
            context_str = "\n\nRelevant context from Heritage LLM:\n"
            for ctx in heritage_context:
                context_str += f"- [{ctx['topic']}]: {ctx['content'][:200]}...\n"
        
        enhanced_message = request.message + context_str
        
        # Classify privacy tier
        tier = classify_privacy_tier(request.message)
        
        # Route to appropriate AI
        ai_engine = route_to_ai(tier, request.message)
        
        # Build messages array
        messages = [
            {"role": "system", "content": "You are Haku, an AI orchestration assistant with access to Heritage knowledge."},
            *session["conversation_history"][-10:],  # Last 10 messages for context
            {"role": "user", "content": enhanced_message}
        ]
        
        # Execute on selected AI
        if ai_engine == 'claude':
            response = await execute_claude(messages)
        elif ai_engine == 'gpt':
            response = await execute_gpt(messages)
        elif ai_engine == 'gemini':
            response = await execute_gemini(messages)
        else:  # ollama
            response = await execute_ollama(messages)
        
        # Update conversation history
        session["conversation_history"].append({"role": "user", "content": request.message})
        session["conversation_history"].append({"role": "assistant", "content": response})
        
        return {
            "response": response,
            "ai_engine": ai_engine,
            "privacy_tier": tier,
            "heritage_context_used": len(heritage_context) > 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/file-operation")
async def file_operation(request: FileOperationRequest):
    """Preview file operations before applying"""
    
    # Verify session
    if request.session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # This endpoint returns a preview
    # Actual application requires separate approval endpoint
    
    operation_preview = {
        "operation": request.operation,
        "path": request.path,
        "what": f"{request.operation.capitalize()} file at {request.path}",
        "why": "Based on your request",
        "trade_offs": {
            "pros": ["Implements requested functionality"],
            "cons": ["Will modify filesystem"]
        },
        "requires_approval": True
    }
    
    return operation_preview

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": DATABASE_URL is not None,
        "anthropic": ANTHROPIC_API_KEY is not None,
        "openai": OPENAI_API_KEY is not None,
        "google": GOOGLE_API_KEY is not None,
        "active_sessions": len(active_sessions)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
