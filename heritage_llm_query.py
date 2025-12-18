#!/usr/bin/env python3
import os
import sys
from getpass import getpass
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import psycopg2
from psycopg2.extras import RealDictCursor

class HeritageQuery:
    def __init__(self, database_url, encryption_password):
        self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        self.cursor = self.conn.cursor()
        self.cipher = self._create_cipher(encryption_password)
        print("✓ Connected\n")
    
    def _create_cipher(self, password):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'heritage_llm_salt_v1',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
    
    def decrypt_text(self, encrypted_text):
        try:
            return self.cipher.decrypt(encrypted_text.encode()).decode()
        except:
            return "[Decrypt failed]"
    
    def list_topics(self):
        self.cursor.execute("SELECT topic_name, paragraph_count FROM topics ORDER BY topic_name")
        print("📚 Topics:\n")
        for row in self.cursor.fetchall():
            print(f"   • {row['topic_name']} ({row['paragraph_count']} paragraphs)")
        print()
    
    def search_all(self, query_text, limit=10):
        print(f"🔍 Searching: '{query_text}'\n")
        self.cursor.execute("""
            SELECT p.encrypted_content, t.topic_name, p.source_conversation
            FROM paragraphs p
            JOIN topics t ON p.topic_id = t.id
            LIMIT 10000
        """)
        
        results = []
        for row in self.cursor.fetchall():
            decrypted = self.decrypt_text(row['encrypted_content'])
            if query_text.lower() in decrypted.lower():
                results.append({
                    'topic': row['topic_name'],
                    'content': decrypted,
                    'source': row['source_conversation']
                })
                if len(results) >= limit:
                    break
        return results
    
    def display_results(self, results):
        if not results:
            print("❌ No results\n")
            return
        
        print(f"✓ Found {len(results)} results:\n")
        for i, r in enumerate(results, 1):
            print(f"[{i}] {r['topic']}")
            print(f"    {r['content'][:1000]}...\n")
    
    def interactive_mode(self):
        print("Heritage LLM - 33 topics, 63,085 paragraphs ready\n")
        
        while True:
            print("Commands: list | search <query> | quit")
            cmd = input("\n> ").strip()
            
            if cmd == "quit":
                print("Goodbye!")
                break
            elif cmd == "list":
                self.list_topics()
            elif cmd.startswith("search "):
                query = cmd[7:].strip()
                results = self.search_all(query)
                self.display_results(results)
            else:
                print("Unknown command")
    
    def close(self):
        self.cursor.close()
        self.conn.close()

def main():
    database_url = os.getenv('DATABASE_URL') or input("DATABASE_URL: ").strip()
    password = getpass("Password: ")
    
    try:
        hq = HeritageQuery(database_url, password)
        hq.interactive_mode()
        hq.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
