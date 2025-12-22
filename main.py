"""
Haku - AI Orchestration Hub with Governance
FastAPI backend with multi-AI routing, MOA organ system, Heritage LLM integration, and Librarian conversation management
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

# Governance layers
from tt01_validation import TT01Validator, ValidationStatus
from moa_routing import MOARouter, TaskClass

# Librarian conversation management
from librarian_schema import init_db, seed_initial_data, User, Topic, Conversation, Message
from librarian_agent import LibrarianAgent

# Database
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
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
GROK_API_KEY = os.getenv("GROK_API_KEY")  # Grok
ENCRYPTION_PASSWORD = os.getenv("ENCRYPTION_PASSWORD", "")

# Initialize AI clients
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
# Grok uses OpenAI-compatible API
grok_client = openai.OpenAI(
    api_key=GROK_API_KEY,
    base_url="https://api.x.ai/v1"
) if GROK_API_KEY else None

# Initialize governance layers
tt01_validator = TT01Validator()
moa_router = MOARouter()

# Initialize Librarian database (one-time setup, safe to run multiple times)
def initialize_librarian():
    """Initialize Librarian conversation management database"""
    try:
        print("Initializing Librarian database...")
        engine = init_db(DATABASE_URL)
        print("Tables created successfully")
        seed_initial_data(engine)
        print("✅ Librarian database ready")
        return engine
    except Exception as e:
        # If tables exist, that's fine - just return engine
        print(f"Librarian init info: {e}")
        return create_engine(DATABASE_URL)

# Create database engine and session maker
db_engine = initialize_librarian()
SessionLocal = sessionmaker(bind=db_engine)

# Dependency for database sessions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# SESSION STORAGE (enhanced with Librarian)
# ============================================================================

active_sessions: Dict[str, Dict[str, Any]] = {
    # session_id: {
    #     "encryption_key": bytes,
    #     "user_id": int,
    #     "username": str,
    #     "current_conversation_id": int,
    #     "created_at": datetime
    # }
}

# ============================================================================
# ENCRYPTION (Heritage LLM)
# ============================================================================

def get_encryption_key(password: str) -> bytes:
    """Derive encryption key from password"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'haku_heritage_salt',  # Use proper salt in production
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
        response = openai_client.chat.completions.create(
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
        # Convert messages to Gemini format
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        
        response = gemini_client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt
        )
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

async def execute_grok(messages: List[Dict]) -> str:
    """Execute using Grok (xAI)"""
    if not grok_client:
        # Fallback to GPT if Grok not configured
        return await execute_gpt(messages)
    
    try:
        response = grok_client.chat.completions.create(
            model="grok-beta",
            messages=messages,
            max_tokens=4000
        )
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Grok error: {str(e)}")

# ============================================================================
# MODELS
# ============================================================================

class AuthRequest(BaseModel):
    password: str
    username: str  # 'thom' or 'karen'

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
async def authenticate(request: AuthRequest, db: Session = Depends(get_db)):
    """Authenticate user and create session with Librarian"""
    try:
        # Verify password by attempting to decrypt
        key = get_encryption_key(request.password)
        
        # Test decryption with a known entry (optional)
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT encrypted_paragraph FROM heritage_paragraphs LIMIT 1")
                ).fetchone()
                
                if result:
                    decrypt_paragraph(result[0], key)
        except:
            pass  # Heritage LLM not loaded yet
        
        # Get or create user in Librarian
        user = db.query(User).filter_by(username=request.username).first()
        if not user:
            raise HTTPException(status_code=401, detail=f"User {request.username} not found")
        
        # Create session
        session_id = base64.urlsafe_b64encode(os.urandom(32)).decode()
        active_sessions[session_id] = {
            "encryption_key": key,
            "user_id": user.id,
            "username": user.username,
            "current_conversation_id": None,  # Will be set when first message sent
            "created_at": datetime.now()
        }
        
        return {
            "success": True,
            "session_id": session_id,
            "user": {
                "username": user.username,
                "display_name": user.display_name
            },
            "message": "Authentication successful"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid password")

@app.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Main chat endpoint with MOA routing, TT-01 validation, and Librarian storage"""
    
    # Verify session
    if request.session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    session = active_sessions[request.session_id]
    librarian = LibrarianAgent(db)
    
    # Get user
    user = db.query(User).filter_by(id=session["user_id"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    try:
        # Get or create conversation
        if session["current_conversation_id"]:
            conversation = db.query(Conversation).filter_by(
                id=session["current_conversation_id"]
            ).first()
        else:
            # Create new conversation with first message
            conversation = librarian.create_conversation(user, request.message)
            session["current_conversation_id"] = conversation.id
        
        # Get recent messages from conversation for context
        recent_messages = db.query(Message).filter_by(
            conversation_id=conversation.id
        ).order_by(Message.created_at.desc()).limit(10).all()
        recent_messages.reverse()  # Chronological order
        
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in recent_messages
        ]
        
        # Step 1: Query Heritage LLM for context (optional)
        heritage_context = []
        try:
            heritage_context = query_heritage_llm(
                request.message, 
                session["encryption_key"],
                max_results=3
            )
        except:
            pass  # Heritage LLM not loaded yet
        
        # Build context string
        context_str = ""
        if heritage_context:
            context_str = "\n\nRelevant context from Heritage LLM:\n"
            for ctx in heritage_context:
                context_str += f"- [{ctx['topic']}]: {ctx['content'][:200]}...\n"
        
        # Step 2: Classify privacy tier
        tier = classify_privacy_tier(request.message)
        
        # Step 3: Get MOA routing (organ-based + mode detection)
        routing = moa_router.get_routing(request.message, tier, context_str)
        
        # Step 4: Build messages array
        enhanced_message = request.message + context_str
        
        messages = [
            {"role": "system", "content": "You are Haku, an AI orchestration assistant with access to Heritage knowledge. Provide clear, evidence-based responses without shortcuts or assumptions."},
            *conversation_history,  # From database
            {"role": "user", "content": enhanced_message}
        ]
        
        # Step 5: Execute on primary AI (determined by MOA)
        ai_engine = routing['primary_ai']
        
        if ai_engine == 'claude':
            response = await execute_claude(messages)
        elif ai_engine == 'gpt':
            response = await execute_gpt(messages)
        elif ai_engine == 'gemini':
            response = await execute_gemini(messages)
        elif ai_engine == 'grok':
            response = await execute_grok(messages)
        else:  # ollama
            response = await execute_ollama(messages)
        
        # Step 6: TT-01 Validation (if required)
        validation_message = ""
        if routing['requires_conscience_check']:
            validation_result = tt01_validator.validate_response(
                response, 
                request.message,
                context_str
            )
            
            # Format validation feedback
            validation_message = tt01_validator.format_validation_message(validation_result)
            
            # Block if validation fails
            if validation_result.status == ValidationStatus.BLOCKED:
                return {
                    "response": "❌ TT-01 BLOCKED: Response failed validation checks.\n\n" + 
                               validation_message + 
                               "\n\nPlease rephrase your query or request clarification.",
                    "ai_engine": ai_engine,
                    "privacy_tier": tier,
                    "task_class": routing['task_class'],
                    "mode": routing['mode'],
                    "validation_status": "blocked",
                    "heritage_context_used": len(heritage_context) > 0
                }
        
        # Step 7: Save messages to database with Librarian
        # Save user message
        librarian.add_message(
            conversation=conversation,
            role="user",
            content=request.message
        )
        
        # Save assistant response
        librarian.add_message(
            conversation=conversation,
            role="assistant",
            content=response,
            ai_engine=ai_engine,
            privacy_tier=tier,
            task_class=routing['task_class'],
            mode=routing['mode']
        )
        
        # Step 8: Add validation message if present
        final_response = response
        if validation_message:
            final_response = response + "\n\n---\n" + validation_message
        
        return {
            "response": final_response,
            "ai_engine": ai_engine,
            "privacy_tier": tier,
            "task_class": routing['task_class'],
            "mode": routing['mode'],
            "validation_status": "approved" if not validation_message else "warnings",
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

@app.get("/conversations/recent")
async def get_recent_conversations(session_id: str, db: Session = Depends(get_db)):
    """Get user's recent conversations"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    session = active_sessions[session_id]
    user = db.query(User).filter_by(id=session["user_id"]).first()
    
    librarian = LibrarianAgent(db)
    conversations = librarian.get_recent_conversations(user, limit=20)
    
    return {"conversations": conversations}

@app.get("/conversations/by-topic/{topic_name}")
async def get_conversations_by_topic(
    topic_name: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get conversations for a specific topic"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    session = active_sessions[session_id]
    user = db.query(User).filter_by(id=session["user_id"]).first()
    
    librarian = LibrarianAgent(db)
    conversations = librarian.get_conversations_by_topic(topic_name, user, limit=20)
    
    return {
        "topic": topic_name,
        "conversations": [librarian.get_conversation_summary(c) for c in conversations]
    }

@app.get("/topics")
async def get_topics(session_id: str, db: Session = Depends(get_db)):
    """Get all topics (folders) with conversation counts"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    session = active_sessions[session_id]
    user = db.query(User).filter_by(id=session["user_id"]).first()
    
    librarian = LibrarianAgent(db)
    topics = librarian.get_all_topics(user)
    
    return {"topics": topics}

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
