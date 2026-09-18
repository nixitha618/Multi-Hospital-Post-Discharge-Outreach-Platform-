import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    APP_NAME: str = "Multi-Hospital Outreach Platform"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./outreach_platform.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secure-dev-secret-key-38472918")
    
    # Concurrency and worker defaults
    DEFAULT_MAX_CONCURRENT_CALLS: int = 5
    WORKER_HEARTBEAT_TIMEOUT_SECONDS: int = 90
    DEFAULT_MAX_RETRIES: int = 3
    
    # Prioritization weights
    WEIGHT_RISK: float = 0.35
    WEIGHT_DEADLINE: float = 0.30
    WEIGHT_DISCHARGE_AGE: float = 0.15
    WEIGHT_CAMPAIGN: float = 0.10
    WEIGHT_STARVATION: float = 0.10
    
    # LLM Settings
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "deterministic") # "deterministic" or "gemini" or "openai"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

settings = Settings()
