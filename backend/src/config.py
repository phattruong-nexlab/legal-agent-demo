import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
PROJECT_ROOT = BASE_DIR.parent                      # repo root

# .env may live at the repo root (local dev) or under backend/.
# Load the first one found. In containers/Cloud Run env vars are injected
# directly, so a missing file is fine (load_dotenv never overrides real env).
for _env_file in (PROJECT_ROOT / ".env", BASE_DIR / ".env"):
    if _env_file.exists():
        load_dotenv(_env_file)
        break


class Settings:
    def __init__(self) -> None:

        # Server (local dev only; in containers uvicorn binds $PORT via the CLI)
        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        self.PORT: int = int(os.getenv("PORT", "8000"))
        self.DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")

        # GEMINI
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        # Accept GEMINI_MODEL too (alias used in some .env / CI configs).
        self.GEMINI_MODEL_NAME: str = (
            os.getenv("GEMINI_MODEL_NAME") or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
        )
        self.GEMINI_REGION: str = os.getenv("GEMINI_REGION", "asia-southeast1")

        self.GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "a3-internal-tools")
        self.GCP_REGION = os.getenv("GCP_REGION", "asia-southeast1")

        self.AUTH_METHOD: str = os.getenv("AUTH_METHOD", "service_account")

        self.LEGAL_BUCKET: str = os.getenv("LEGAL_BUCKET", "legal_docs_storage_testing_01")

        self.NEO4J_URI: str = os.getenv("NEO4J_URI", "")
        self.NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "")
        self.NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
        self.NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "")
        self.AURA_INSTANCEID: str = os.getenv("AURA_INSTANCEID", "")    
        self.AURA_INSTANCENAME: str = os.getenv("AURA_INSTANCENAME", "")
        self.AURA_INSTANCEID: str = os.getenv("AURA_INSTANCEID", "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
