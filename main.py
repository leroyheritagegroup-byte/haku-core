# Temporarily simplified for deployment test
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "Haku is running", "version": "minimal-test"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
