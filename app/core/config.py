import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Nexus AI Full Stack RAG"
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    CHROMA_DB_DIR: str = "./data/chroma_db"
    UPLOADS_DIR: str = "./data/uploads"

settings = Settings()
