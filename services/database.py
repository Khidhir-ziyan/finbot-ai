import logging
import httpx
from datetime import datetime
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

logger.info(f"SUPABASE_URL: {SUPABASE_URL[:30] if SUPABASE_URL else 'NONE'}...")
logger.info(f"SUPABASE_KEY set: {bool(SUPABASE_KEY)}")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def save_transaction(jenis: str, kategori: str, nominal: int, keterangan: str, raw_text: str) -> dict:
    try:
        data = {
            "jenis": jenis,
            "kategori": kategori,
            "nominal": nominal,
            "keterangan": keterangan,
            "raw_text": raw_text,
        }
        with httpx.Client(trust_env=False, timeout=10, follow_redirects=True) as client:
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/cash_flow",
                json=data,
                headers=HEADERS
            )
        response.raise_for_status()
        logger.info(f"Transaction saved: {response.json()}")
        return {"success": True, "data": response.json()}
    except Exception as e:
        logger.error(f"Database error: {e}")
        return {"success": False, "error": str(e)}

def get_transactions_by_date(date: str) -> list:
    try:
        with httpx.Client(trust_env=False, timeout=10, follow_redirects=True) as client:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/cash_flow",
                headers=HEADERS,
                params={"created_at": f"gte.{date}T00:00:00", "order": "created_at.desc"}
            )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

def get_transactions_by_week(start_date: str, end_date: str) -> list:
    try:
        with httpx.Client(trust_env=False, timeout=10, follow_redirects=True) as client:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/cash_flow",
                headers=HEADERS,
                params={"created_at": f"gte.{start_date}T00:00:00", "order": "created_at.desc"}
            )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

def get_all_transactions() -> list:
    try:
        with httpx.Client(trust_env=False, timeout=10, follow_redirects=True) as client:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/cash_flow",
                headers=HEADERS,
                params={"order": "created_at.desc"}
            )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []
