import requests

class OllamaService:
    def __init__(self):
        self.base_url = "http://localhost:11434"
        self.mistral_model = "mistral"
        self.llama_model = "llama3.2:3b"
    
    async def process(self, message: str, model: str = "mistral", context: dict = None) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model if model in ["mistral", "llama3.2:3b"] else self.mistral_model,
                    "prompt": message,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                return response.json()["response"]
            else:
                return f"Ollama error: {response.status_code}"
        except Exception as e:
            return f"Ollama connection error: {str(e)}"
