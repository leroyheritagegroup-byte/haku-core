import os
from anthropic import Anthropic

class ClaudeService:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
    
    async def process(self, message: str, context: dict = None) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": message}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Claude error: {str(e)}"
