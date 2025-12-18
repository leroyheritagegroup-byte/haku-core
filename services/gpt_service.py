import os
from openai import OpenAI

class GPTService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o"
    
    async def process(self, message: str, context: dict = None) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": message}],
                max_tokens=1024
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"GPT error: {str(e)}"
