import os
from pathlib import Path

# On Vercel the filesystem is read-only except for /tmp.
# VERCEL=1 is injected automatically by the Vercel runtime.
_IS_VERCEL = bool(os.environ.get("VERCEL"))
_BASE = Path("/tmp/campaign-analyzer") if _IS_VERCEL else Path(__file__).parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    UPLOAD_FOLDER = _BASE / "uploads"
    REPORT_FOLDER = _BASE / "reports"
    DATA_FOLDER = _BASE / "data"
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS = {"csv"}
