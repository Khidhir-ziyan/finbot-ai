import logging
from datetime import datetime
import httpx
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

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
            "created_at": datetime.now().isoformat()
        }
        with httpx.Client(trust_env=False, timeout=10) as client:
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
        with httpx.Client(trust_env=False, timeout=10) as client:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/cash_flow",
                params=f"created_at=gte.{date}T00:00:00&created_at=lte.{date}T23:59:59&order=created_at.desc",
                headers=HEADERS
            )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

def get_transactions_by_week(start_date: str, end_date: str) -> list:
    try:
        with httpx.Client(trust_env=False, timeout=10) as client:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/cash_flow",
                params=f"created_at=gte.{start_date}T00:00:00&created_at=lte.{end_date}T23:59:59&order=created_at.desc",
                headers=HEADERS
            )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

def get_all_transactions() -> list:
    try:
        with httpx.Client(trust_env=False, timeout=10) as client:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/cash_flow",
                params="order=created_at.desc",
                headers=HEADERS
            )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []
