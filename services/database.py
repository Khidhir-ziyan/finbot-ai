import logging
import json
from datetime import datetime
import urllib.request
import urllib.parse
import os
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def _request(method: str, url: str, data: dict = None, params: str = "") -> dict:
    if params:
        url = f"{url}?{params}"
    
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    
    # Disable proxy from env
    https_handler = urllib.request.HTTPSHandler()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    
    with opener.open(req, timeout=10) as resp:
        return json.loads(resp.read().decode())

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
        result = _request("POST", f"{SUPABASE_URL}/rest/v1/cash_flow", data)
        logger.info(f"Transaction saved: {result}")
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Database error: {e}")
        return {"success": False, "error": str(e)}

def get_transactions_by_date(date: str) -> list:
    try:
        params = f"created_at=gte.{date}T00:00:00&created_at=lte.{date}T23:59:59&order=created_at.desc"
        return _request("GET", f"{SUPABASE_URL}/rest/v1/cash_flow", params=params)
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

def get_transactions_by_week(start_date: str, end_date: str) -> list:
    try:
        params = f"created_at=gte.{start_date}T00:00:00&created_at=lte.{end_date}T23:59:59&order=created_at.desc"
        return _request("GET", f"{SUPABASE_URL}/rest/v1/cash_flow", params=params)
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

def get_all_transactions() -> list:
    try:
        return _request("GET", f"{SUPABASE_URL}/rest/v1/cash_flow", params="order=created_at.desc")
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []
