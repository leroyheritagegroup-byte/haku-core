from typing import Dict, Any
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.claude_service import ClaudeService
from services.gpt_service import GPTService
from services.gemini_service import GeminiService
from services.ollama_service import OllamaService

class TaskRouter:
    def __init__(self):
        self.claude = ClaudeService()
        self.gpt = GPTService()
        self.gemini = GeminiService()
        self.ollama = OllamaService()
    
    def analyze_task(self, message: str, mode: str) -> str:
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['ethics', 'governance', 'validate', 'truth', 'audit']):
            return 'claude'
        
        if any(word in message_lower for word in ['plan', 'strategy', 'roadmap', 'timeline']):
            return 'gpt'
        
        if any(word in message_lower for word in ['search', 'find', 'youtube', 'video', 'image']):
            return 'gemini'
        
        if mode == 'brainstorm':
            return 'gpt'
        elif mode == 'execute':
            return 'claude'
        elif mode == 'research':
            return 'gemini'
        
        return 'claude'
    
    async def route(self, message: str, mode: str, privacy_tier: int) -> Dict[str, Any]:
        if privacy_tier == 3:
            response = await self.ollama.process(message)
            return {
                'engine': 'ollama-mistral',
                'response': response,
                'privacy': 'local-only'
            }
        
        engine = self.analyze_task(message, mode)
        
        if engine == 'claude':
            response = await self.claude.process(message)
        elif engine == 'gpt':
            response = await self.gpt.process(message)
        elif engine == 'gemini':
            response = await self.gemini.process(message)
        else:
            response = await self.claude.process(message)
        
        return {
            'engine': engine,
            'response': response,
            'privacy': f'tier-{privacy_tier}'
        }
