import logging
import httpx
from datetime import datetime
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

async def save_transaction(jenis: str, kategori: str, nominal: int, keterangan: str, raw_text: str) -> dict:
    try:
        data = {
            "jenis": jenis,
            "kategori": kategori,
            "nominal": nominal,
            "keterangan": keterangan,
            "raw_text": raw_text,
        }
        async with httpx.AsyncClient(trust_env=False, timeout=10, follow_redirects=True) as client:
            response = await client.post(
                f"{SUPABASE_URL}/rest/v1/cash_flow",
                json=data,
                headers=HEADERS
            )
        logger.info(f"Transaction saved: {response.json()}")
        return {"success": True, "data": response.json()}
    except Exception as e:
        logger.error(f"Database error: {e}")
        return {"success": False, "error": str(e)}

async def get_transactions_by_date(date: str) -> list:
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=10, follow_redirects=True) as client:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/cash_flow",
                headers=HEADERS,
                params={"created_at": f"gte.{date}T00:00:00", "order": "created_at.desc"}
            )
        return response.json()
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

async def get_transactions_by_week(start_date: str, end_date: str) -> list:
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=10, follow_redirects=True) as client:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/cash_flow",
                headers=HEADERS,
                params={"created_at": f"gte.{start_date}T00:00:00", "order": "created_at.desc"}
            )
        return response.json()
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

async def get_all_transactions() -> list:
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=10, follow_redirects=True) as client:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/cash_flow",
                headers=HEADERS,
                params={"order": "created_at.desc"}
            )
        return response.json()
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []
