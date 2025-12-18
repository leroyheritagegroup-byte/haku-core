#!/usr/bin/env python3
"""
Heritage LLM Knowledge Base Loader
Loads topic JSON files into encrypted PostgreSQL database
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from getpass import getpass
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC as PBKDF2
import base64

import psycopg2
from psycopg2.extras import execute_values

class EncryptedKnowledgeBase:
    """Manages encrypted knowledge base in PostgreSQL"""
    
    def __init__(self, database_url, encryption_password):
        """Initialize with database connection and encryption key"""
        self.conn = psycopg2.connect(database_url)
        self.cursor = self.conn.cursor()
        
        # Derive encryption key from password
        self.cipher = self._create_cipher(encryption_password)
        
        print("✓ Connected to database")
        print("✓ Encryption initialized")
    
    def _create_cipher(self, password):
        """Create Fernet cipher from password"""
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'heritage_llm_salt_v1',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
    
    def setup_schema(self):
        """Create database tables"""
        print("\nSetting up database schema...")
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id SERIAL PRIMARY KEY,
                topic_name VARCHAR(255) UNIQUE NOT NULL,
                source_file VARCHAR(255),
                paragraph_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS paragraphs (
                id SERIAL PRIMARY KEY,
                topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
                paragraph_index INTEGER,
                encrypted_content TEXT NOT NULL,
                source_conversation VARCHAR(255),
                source_message_id VARCHAR(255),
                author_role VARCHAR(50),
                create_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_paragraphs_topic ON paragraphs(topic_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_paragraphs_conversation ON paragraphs(source_conversation)")
        
        self.conn.commit()
        print("✓ Database schema ready")
    
    def encrypt_text(self, text):
        """Encrypt text content"""
        return self.cipher.encrypt(text.encode()).decode()
    
    def decrypt_text(self, encrypted_text):
        """Decrypt text content"""
        return self.cipher.decrypt(encrypted_text.encode()).decode()
    
    def load_topic_file(self, filepath):
        """Load a single topic JSON file"""
        filename = os.path.basename(filepath)
        topic_name = filename.replace('OPENAI_', '').replace('_FULL_CANONICAL_VERBATIM.json', '')
        topic_name = topic_name.replace('.json', '').replace('_', ' ')
        
        print(f"\n📄 Loading: {topic_name}")
        print(f"   File: {filename}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        paragraphs = data.get('paragraphs', [])
        if not paragraphs:
            print(f"   ⚠️  No paragraphs found in {filename}")
            return
        
        print(f"   Found {len(paragraphs)} paragraphs")
        
        self.cursor.execute("""
            INSERT INTO topics (topic_name, source_file, paragraph_count)
            VALUES (%s, %s, %s)
            ON CONFLICT (topic_name) 
            DO UPDATE SET 
                source_file = EXCLUDED.source_file,
                paragraph_count = EXCLUDED.paragraph_count,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, (topic_name, filename, len(paragraphs)))
        
        topic_id = self.cursor.fetchone()[0]
        self.cursor.execute("DELETE FROM paragraphs WHERE topic_id = %s", (topic_id,))
        
        paragraph_data = []
        for idx, para in enumerate(paragraphs):
            encrypted_content = self.encrypt_text(para.get('paragraph', ''))
            source = para.get('source', {})
            
            paragraph_data.append((
                topic_id, idx, encrypted_content,
                source.get('conversation_title', ''),
                source.get('message_id', ''),
                source.get('author_role', ''),
                datetime.fromtimestamp(source.get('create_time', 0)) if source.get('create_time') else None
            ))
        
        execute_values(
            self.cursor,
            "INSERT INTO paragraphs (topic_id, paragraph_index, encrypted_content, source_conversation, source_message_id, author_role, create_time) VALUES %s",
            paragraph_data
        )
        
        self.conn.commit()
        print(f"   ✓ Loaded {len(paragraphs)} encrypted paragraphs")
    
    def load_all_json_files(self, directory):
        """Load all JSON files from directory"""
        json_files = list(Path(directory).glob('OPENAI_*_FULL_CANONICAL_VERBATIM*.json'))
        
        print(f"\n{'='*60}")
        print(f"Found {len(json_files)} topic files to load")
        print(f"{'='*60}")
        
        for filepath in sorted(json_files):
            try:
                self.load_topic_file(filepath)
            except Exception as e:
                print(f"   ❌ Error loading {filepath.name}: {e}")
                continue
        
        self.conn.commit()
    
    def verify_loading(self):
        """Verify data was loaded correctly"""
        print(f"\n{'='*60}")
        print("VERIFICATION")
        print(f"{'='*60}\n")
        
        self.cursor.execute("SELECT COUNT(*) FROM topics")
        topic_count = self.cursor.fetchone()[0]
        print(f"✓ Topics loaded: {topic_count}")
        
        self.cursor.execute("SELECT COUNT(*) FROM paragraphs")
        para_count = self.cursor.fetchone()[0]
        print(f"✓ Paragraphs loaded: {para_count}")
        
        self.cursor.execute("SELECT topic_name, paragraph_count FROM topics ORDER BY topic_name")
        
        print(f"\n📚 Topics in knowledge base:")
        for topic_name, para_count in self.cursor.fetchall():
            print(f"   • {topic_name} ({para_count} paragraphs)")
    
    def test_encryption(self):
        """Test encryption/decryption works"""
        print(f"\n{'='*60}")
        print("TESTING ENCRYPTION")
        print(f"{'='*60}\n")
        
        self.cursor.execute("SELECT p.encrypted_content, t.topic_name FROM paragraphs p JOIN topics t ON p.topic_id = t.id LIMIT 1")
        
        result = self.cursor.fetchone()
        if result:
            encrypted_content, topic_name = result
            decrypted = self.decrypt_text(encrypted_content)
            print(f"✓ Sample from '{topic_name}':")
            print(f"  {decrypted[:200]}...")
            print(f"\n✓ Encryption/decryption working correctly")
    
    def close(self):
        """Close database connection"""
        self.cursor.close()
        self.conn.close()
        print("\n✓ Database connection closed")

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║         Heritage LLM Knowledge Base Loader               ║
║  Loads your 27 topic files into encrypted PostgreSQL    ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("\nEnter your Railway PostgreSQL connection string:")
        database_url = input("DATABASE_URL: ").strip()
    
    print("\nSet encryption password for your knowledge base:")
    password = getpass("Password: ")
    password_confirm = getpass("Confirm: ")
    
    if password != password_confirm:
        print("\nPasswords don't match!")
        sys.exit(1)
    
    if len(password) < 8:
        print("\nPassword must be at least 8 characters!")
        sys.exit(1)
    
    downloads_dir = os.path.expanduser("~/Downloads")
    print(f"\nLooking for JSON files in: {downloads_dir}")
    
    try:
        kb = EncryptedKnowledgeBase(database_url, password)
        kb.setup_schema()
        kb.load_all_json_files(downloads_dir)
        kb.verify_loading()
        kb.test_encryption()
        kb.close()
        
        print("\n" + "="*60)
        print("SUCCESS! Your knowledge base is ready.")
        print("="*60)
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
