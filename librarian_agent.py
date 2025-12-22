"""
Librarian Agent - Conversation Organization & Retrieval
Auto-detects topics, organizes conversations, prevents duplication
"""

from typing import List, Dict, Optional, Set
from sqlalchemy.orm import Session
from librarian_schema import User, Topic, Conversation, Message, KnowledgeLink
from datetime import datetime
import re

class LibrarianAgent:
    """
    Organizes conversations, auto-creates topic folders, links related content
    """
    
    def __init__(self, db_session: Session):
        self.session = db_session
        
        # Topic detection patterns
        self.topic_patterns = {
            'Patents': [
                r'\bpatent\b', r'\bprovisional\b', r'\busto\b', r'\bip strategy\b',
                r'\bprior art\b', r'\bclaims\b', r'\bfiling\b'
            ],
            'ForgedOS': [
                r'\bforgeos\b', r'\bplatform\b', r'\bexit\b', r'\bvaluation\b',
                r'\bbuyer\b', r'\bearnout\b'
            ],
            'Haku': [
                r'\bhaku\b', r'\borchestration\b', r'\bmulti-ai\b', r'\brouting\b'
            ],
            'MOA': [
                r'\bmoa\b', r'\bmodel.organism\b', r'\borgan\b', r'\bsenses\b',
                r'\bbrain\b', r'\bconscience\b', r'\bhands\b'
            ],
            'Governance': [
                r'\btt-?01\b', r'\bhgc-?01\b', r'\brao\b', r'\betg\b', r'\bcbg\b',
                r'\bgovernance\b', r'\bcompliance\b'
            ],
            'TT-01': [
                r'\btt-?01\b', r'\btruth team\b', r'\bvalidation\b', r'\bshortcut\b'
            ],
            'HGC-01': [
                r'\bhgc-?01\b', r'\bheritage governance\b', r'\bmission\b'
            ],
            'Valuation': [
                r'\bvaluation\b', r'\b\$\d+m\b', r'\bexit\b', r'\bapril 2026\b'
            ],
            'Heritage': [
                r'\bheritage llm\b', r'\bencrypted\b', r'\bknowledge base\b',
                r'\blibrarian\b'
            ],
            'Mobile': [
                r'\bmobile\b', r'\bphone\b', r'\bresponsive\b', r'\bui\b'
            ],
            'API': [
                r'\bapi\b', r'\banthropic\b', r'\bopenai\b', r'\bgoogle\b',
                r'\bgrok\b', r'\bcost\b', r'\btokens\b'
            ]
        }
    
    def detect_topics(self, message: str) -> Set[str]:
        """
        Detect which topics are mentioned in a message
        Returns set of topic names
        """
        message_lower = message.lower()
        detected = set()
        
        for topic, patterns in self.topic_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    detected.add(topic)
                    break
        
        # Always include General if no topics detected
        if not detected:
            detected.add('General')
        
        return detected
    
    def get_or_create_topic(self, topic_name: str, auto_created: bool = True) -> Topic:
        """Get existing topic or create new one"""
        topic = self.session.query(Topic).filter_by(name=topic_name).first()
        
        if not topic:
            topic = Topic(
                name=topic_name,
                description=f"Auto-detected topic: {topic_name}",
                auto_created=auto_created
            )
            self.session.add(topic)
            self.session.commit()
        
        return topic
    
    def create_conversation(
        self, 
        user: User,
        first_message: str,
        initial_topics: Optional[Set[str]] = None
    ) -> Conversation:
        """
        Create a new conversation with auto-detected topics
        """
        # Detect topics from first message
        if initial_topics is None:
            initial_topics = self.detect_topics(first_message)
        
        # Generate title from first message (first 50 chars)
        title = first_message[:50].strip()
        if len(first_message) > 50:
            title += "..."
        
        # Create conversation
        conversation = Conversation(
            user_id=user.id,
            title=title
        )
        
        # Link topics
        for topic_name in initial_topics:
            topic = self.get_or_create_topic(topic_name)
            conversation.topics.append(topic)
        
        self.session.add(conversation)
        self.session.commit()
        
        return conversation
    
    def add_message(
        self,
        conversation: Conversation,
        role: str,
        content: str,
        ai_engine: Optional[str] = None,
        privacy_tier: Optional[int] = None,
        task_class: Optional[str] = None,
        mode: Optional[str] = None
    ) -> Message:
        """
        Add message to conversation and update topics if new ones detected
        """
        # Create message
        message = Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            ai_engine=ai_engine,
            privacy_tier=privacy_tier,
            task_class=task_class,
            mode=mode
        )
        
        self.session.add(message)
        
        # Detect topics in new message
        if role == 'user':  # Only detect from user messages
            new_topics = self.detect_topics(content)
            
            # Get current topic names
            current_topic_names = {t.name for t in conversation.topics}
            
            # Add any new topics
            for topic_name in new_topics:
                if topic_name not in current_topic_names:
                    topic = self.get_or_create_topic(topic_name)
                    conversation.topics.append(topic)
        
        # Update conversation timestamp
        conversation.updated_at = datetime.utcnow()
        
        self.session.commit()
        
        return message
    
    def get_conversations_by_topic(
        self,
        topic_name: str,
        user: Optional[User] = None,
        limit: int = 20
    ) -> List[Conversation]:
        """
        Get all conversations tagged with a topic
        """
        query = self.session.query(Conversation).join(
            Conversation.topics
        ).filter(
            Topic.name == topic_name,
            Conversation.archived == False
        )
        
        if user:
            query = query.filter(Conversation.user_id == user.id)
        
        return query.order_by(
            Conversation.updated_at.desc()
        ).limit(limit).all()
    
    def search_conversations(
        self,
        query: str,
        user: Optional[User] = None,
        limit: int = 20
    ) -> List[Conversation]:
        """
        Search conversations by content
        """
        search = f"%{query}%"
        
        query_obj = self.session.query(Conversation).join(
            Conversation.messages
        ).filter(
            Message.content.ilike(search),
            Conversation.archived == False
        )
        
        if user:
            query_obj = query_obj.filter(Conversation.user_id == user.id)
        
        return query_obj.order_by(
            Conversation.updated_at.desc()
        ).limit(limit).all()
    
    def get_conversation_summary(self, conversation: Conversation) -> Dict:
        """
        Get summary of conversation for display
        """
        messages = sorted(conversation.messages, key=lambda m: m.created_at)
        
        return {
            'id': conversation.id,
            'title': conversation.title,
            'topics': [t.name for t in conversation.topics],
            'message_count': len(messages),
            'created_at': conversation.created_at.isoformat(),
            'updated_at': conversation.updated_at.isoformat(),
            'last_message': messages[-1].content[:100] if messages else None,
            'user': conversation.user.display_name
        }
    
    def get_recent_conversations(
        self,
        user: User,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get user's recent conversations with summaries
        """
        conversations = self.session.query(Conversation).filter(
            Conversation.user_id == user.id,
            Conversation.archived == False
        ).order_by(
            Conversation.updated_at.desc()
        ).limit(limit).all()
        
        return [self.get_conversation_summary(c) for c in conversations]
    
    def get_all_topics(self, user: Optional[User] = None) -> List[Dict]:
        """
        Get all topics with conversation counts
        """
        query = self.session.query(
            Topic,
            self.session.query(Conversation).join(
                Conversation.topics
            ).filter(
                Topic.id == conversation_topics.c.topic_id
            ).count().label('conversation_count')
        )
        
        if user:
            query = query.join(Conversation.topics).filter(
                Conversation.user_id == user.id
            )
        
        topics = query.all()
        
        return [
            {
                'name': t.Topic.name,
                'description': t.Topic.description,
                'conversation_count': t.conversation_count,
                'auto_created': t.Topic.auto_created
            }
            for t in topics
        ]


# Quick test
if __name__ == '__main__':
    # Test topic detection
    agent = LibrarianAgent(None)
    
    test_messages = [
        "Let's work on the TT-01 patent application",
        "How should we improve Haku's mobile UI?",
        "What's our exit valuation strategy?",
        "Can you help me with this Python script?"
    ]
    
    for msg in test_messages:
        topics = agent.detect_topics(msg)
        print(f"\nMessage: {msg}")
        print(f"Topics: {topics}")
