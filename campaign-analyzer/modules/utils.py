import re
from datetime import datetime


def allowed_file(filename: str, allowed_extensions: set = None) -> bool:
    if allowed_extensions is None:
        allowed_extensions = {"csv"}
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in allowed_extensions
    )


def generate_unique_filename(client_name: str, original_filename: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_client = re.sub(r"[^a-zA-Z0-9]", "_", client_name).lower().strip("_")
    ext = original_filename.rsplit(".", 1)[1].lower() if "." in original_filename else "csv"
    return f"{timestamp}_{safe_client}.{ext}"


def safe_float(value, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = value.replace(",", ".").replace("R$", "").replace(" ", "").replace("%", "")
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default: int = 0) -> int:
    try:
        return int(safe_float(value, float(default)))
    except (ValueError, TypeError):
        return default


def platform_label(platform: str) -> str:
    return {"meta": "Meta Ads", "google": "Google Ads"}.get(platform, platform)
