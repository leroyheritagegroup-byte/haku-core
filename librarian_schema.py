"""
Librarian Agent - Database Schema
Auto-organizing conversation management with topic detection
"""

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Table, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import os

Base = declarative_base()

# Junction table for many-to-many relationship between conversations and topics
conversation_topics = Table(
    'conversation_topics',
    Base.metadata,
    Column('conversation_id', Integer, ForeignKey('conversations.id'), primary_key=True),
    Column('topic_id', Integer, ForeignKey('topics.id'), primary_key=True)
)

class User(Base):
    """User accounts (Thom, Karen)"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)  # 'thom' or 'karen'
    display_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversations = relationship('Conversation', back_populates='user')

class Topic(Base):
    """Auto-detected conversation topics (folders)"""
    __tablename__ = 'topics'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)  # "Patents", "ForgedOS", "Haku", etc.
    description = Column(Text)
    auto_created = Column(Boolean, default=True)  # True if Librarian created it
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversations = relationship('Conversation', secondary=conversation_topics, back_populates='topics')

class Conversation(Base):
    """Conversation threads"""
    __tablename__ = 'conversations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    title = Column(String(200))  # Auto-generated from first message
    summary = Column(Text)  # AI-generated summary
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    archived = Column(Boolean, default=False)
    
    user = relationship('User', back_populates='conversations')
    messages = relationship('Message', back_populates='conversation', cascade='all, delete-orphan')
    topics = relationship('Topic', secondary=conversation_topics, back_populates='conversations')

class Message(Base):
    """Individual messages in conversations"""
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    
    # Metadata
    ai_engine = Column(String(20))  # 'claude', 'gpt', 'gemini', 'grok'
    privacy_tier = Column(Integer)  # 0-3
    task_class = Column(String(50))  # 'strategy', 'execution', etc.
    mode = Column(String(50))  # 'ideating', 'executing', etc.
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversation = relationship('Conversation', back_populates='messages')

class KnowledgeLink(Base):
    """Links between conversations and Heritage LLM paragraphs"""
    __tablename__ = 'knowledge_links'
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    heritage_topic = Column(String(200))  # Topic from Heritage LLM
    relevance_score = Column(Integer)  # 1-10, how relevant
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
def init_db(database_url):
    """Initialize database with schema"""
    engine = create_engine(database_url)
    
    # Explicitly create tables in order (dependencies first)
    # This ensures junction tables are created after their referenced tables
    User.__table__.create(engine, checkfirst=True)
    Topic.__table__.create(engine, checkfirst=True)
    Conversation.__table__.create(engine, checkfirst=True)
    conversation_topics.create(engine, checkfirst=True)
    Message.__table__.create(engine, checkfirst=True)
    KnowledgeLink.__table__.create(engine, checkfirst=True)
    
    return engine

# Seed initial data
def seed_initial_data(engine):
    """Create initial users and core topics"""
    from sqlalchemy.orm import Session
    
    session = Session(engine)
    
    try:
        # Create users if they don't exist
        if not session.query(User).filter_by(username='thom').first():
            thom = User(username='thom', display_name='Thom')
            session.add(thom)
        
        if not session.query(User).filter_by(username='karen').first():
            karen = User(username='karen', display_name='Karen')
            session.add(karen)
        
        # Commit users first
        session.commit()
        
        # Create core topics
        core_topics = [
            ('Patents', 'Patent applications and IP strategy'),
            ('ForgedOS', 'ForgedOS platform development and architecture'),
            ('Haku', 'Haku AI orchestration system'),
            ('Heritage', 'Heritage LLM and knowledge management'),
            ('MOA', 'Model-Organism Architecture'),
            ('Governance', 'AI governance frameworks (HGC-01, TT-01, etc.)'),
            ('Valuation', 'Exit strategy and valuation planning'),
            ('General', 'Miscellaneous conversations')
        ]
        
        for name, desc in core_topics:
            if not session.query(Topic).filter_by(name=name).first():
                topic = Topic(name=name, description=desc, auto_created=False)
                session.add(topic)
        
        session.commit()
        print("Seeded users and topics successfully")
    except Exception as e:
        session.rollback()
        print(f"Seed error (may be okay if already seeded): {e}")
    finally:
        session.close()

if __name__ == '__main__':
    # For testing
    db_url = os.getenv('DATABASE_URL', 'postgresql://localhost/haku')
    engine = init_db(db_url)
    seed_initial_data(engine)
    print("Database initialized!")
