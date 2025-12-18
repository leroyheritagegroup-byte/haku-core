import json
import requests
import os
from datetime import datetime
from collections import defaultdict

class PlanExtractor:
    def __init__(self, json_path: str, output_dir: str = "extracted-plans"):
        self.json_path = json_path
        self.output_dir = output_dir
        self.ollama_url = "http://localhost:11434/api/generate"
        os.makedirs(output_dir, exist_ok=True)
        
    def load_conversations(self):
        with open(self.json_path, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, list) else [data]
    
    def extract_full_conversation(self, conversation: dict) -> str:
        messages = []
        mapping = conversation.get('mapping', {})
        for node_id, node_data in mapping.items():
            message = node_data.get('message')
            if message and message.get('content'):
                content = message['content']
                if content.get('content_type') == 'text':
                    parts = content.get('parts', [])
                    for part in parts:
                        if isinstance(part, str) and len(part) > 20:
                            messages.append(part)
        return "\n\n".join(messages)
    
    def identify_topics(self, conv_text: str) -> list:
        prompt = f"""Analyze this conversation and identify the MAJOR plan topics discussed.

Look for distinct projects, systems, strategies, or initiatives like:
- ForgeOS, HeritageOS
- Hearthline, Heritage Hub
- ArtOps, MakerOps
- Patent strategies
- Exit strategies

List ONLY the major topic names, one per line.

CONVERSATION SAMPLE:
{conv_text[:8000]}

MAJOR TOPICS:"""
        try:
            response = requests.post(
                self.ollama_url,
                json={"model": "mistral", "prompt": prompt, "stream": False},
                timeout=180
            )
            if response.status_code == 200:
                topics_text = response.json()["response"]
                topics = [line.strip() for line in topics_text.split('\n') if line.strip() and len(line.strip()) > 5]
                return topics[:10]
        except Exception as e:
            print(f"Error identifying topics: {e}")
        return []
    
    def extract_topic_content(self, conv_text: str, topic: str) -> str:
        topic_keywords = topic.lower().split()
        paragraphs = conv_text.split('\n\n')
        relevant_text = []
        for para in paragraphs:
            para_lower = para.lower()
            if any(keyword in para_lower for keyword in topic_keywords):
                relevant_text.append(para)
        if not relevant_text:
            return ""
        combined = '\n\n'.join(relevant_text[:50])
        prompt = f"""Extract and organize ALL content about "{topic}" from these sections.

# {topic}

**Status:** [approved/locked/current/proposed]

**Summary:** 
[2-3 sentences]

**Details:**
[Organize into clear sections]
[Include ALL numbers, dates, technical details]

CONTENT:
{combined[:12000]}

EXTRACTION:"""
        try:
            response = requests.post(
                self.ollama_url,
                json={"model": "mistral", "prompt": prompt, "stream": False},
                timeout=600
            )
            if response.status_code == 200:
                return response.json()["response"]
        except Exception as e:
            return f"Error: {str(e)}"
        return ""
    
    def process_conversation(self, conv: dict) -> dict:
        title = conv.get('title', 'Untitled')
        conv_id = conv.get('id')
        updated = datetime.fromtimestamp(conv.get('update_time', 0)).strftime('%Y-%m-%d')
        print(f"\nProcessing: {title}")
        conv_text = self.extract_full_conversation(conv)
        if len(conv_text) < 100:
            return None
        print("  Identifying topics...")
        topics = self.identify_topics(conv_text)
        if not topics:
            return None
        print(f"  Found {len(topics)} topics")
        extractions = {}
        for topic in topics:
            print(f"  Extracting: {topic}")
            content = self.extract_topic_content(conv_text, topic)
            if content and len(content) > 50:
                extractions[topic] = {
                    'content': content,
                    'source_conversation': title,
                    'conversation_id': conv_id,
                    'last_updated': updated
                }
        return extractions
    
    def consolidate_and_save(self, all_extractions: dict):
        by_topic = defaultdict(list)
        for conv_data in all_extractions.values():
            if conv_data:
                for topic, details in conv_data.items():
                    by_topic[topic].append(details)
        index = {'generated': datetime.now().isoformat(), 'topics': {}}
        for topic, entries in by_topic.items():
            filename = topic.replace(' ', '-').replace('/', '-') + '.md'
            filepath = os.path.join(self.output_dir, filename)
            consolidated = f"# {topic}\n\n*From {len(entries)} conversation(s)*\n\n---\n\n"
            for entry in entries:
                consolidated += entry['content'] + "\n\n"
                consolidated += f"*Source: {entry['source_conversation']} ({entry['last_updated']})*\n\n---\n\n"
            with open(filepath, 'w') as f:
                f.write(consolidated)
            index['topics'][topic] = {
                'filename': filename,
                'filepath': filepath,
                'source_count': len(entries),
                'sources': [e['source_conversation'] for e in entries]
            }
            print(f"Saved: {filename}")
        index_path = os.path.join(self.output_dir, 'master-index.json')
        with open(index_path, 'w') as f:
            json.dump(index, f, indent=2)
        print(f"\nIndex: {index_path}")
        return index
    
    def test_on_heritage_master(self):
        conversations = self.load_conversations()
        target = None
        for conv in conversations:
            if 'heritage master' in conv.get('title', '').lower():
                target = conv
                break
        if not target:
            return {"error": "Not found"}
        print("TESTING ON HERITAGE MASTER 6")
        extractions = {target['id']: self.process_conversation(target)}
        index = self.consolidate_and_save(extractions)
        return {
            'status': 'complete',
            'output_directory': self.output_dir,
            'topics_extracted': len(index['topics']),
            'index': index
        }
    
    def process_all_conversations(self, limit: int = None):
        conversations = self.load_conversations()
        if limit:
            conversations = conversations[:limit]
        print(f"PROCESSING {len(conversations)} CONVERSATIONS")
        all_extractions = {}
        for i, conv in enumerate(conversations, 1):
            print(f"\n[{i}/{len(conversations)}]")
            result = self.process_conversation(conv)
            if result:
                all_extractions[conv['id']] = result
        index = self.consolidate_and_save(all_extractions)
        return {
            'status': 'complete',
            'conversations_processed': len(conversations),
            'output_directory': self.output_dir,
            'topics_extracted': len(index['topics']),
            'index': index
        }
