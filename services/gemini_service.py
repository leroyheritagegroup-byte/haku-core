import os
import google.generativeai as genai

class GeminiService:
    def __init__(self):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    async def process(self, message: str, context: dict = None) -> str:
        try:
            response = self.model.generate_content(message)
            return response.text
        except Exception as e:
            return f"Gemini error: {str(e)}"
