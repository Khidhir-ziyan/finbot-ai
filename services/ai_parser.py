import json
import logging
from config import AI_API_KEY, AI_PROVIDER, CATEGORIES, JENIS_OPTIONS

logger = logging.getLogger(__name__)

PARSER_PROMPT = """Anda adalah asisten keuangan yang menganalisis transaksi bisnis.

Analisis teks berikut dan ekstrak data transaksi dalam format JSON:
{
    "jenis": "Pemasukan" atau "Pengeluaran",
    "kategori": "Fashion", "Makanan", "Minuman", "Operasional", "Dana Pribadi", "Kesehatan", "Transport", "Pendidikan", atau "Hiburan",
    "nominal": angka murni tanpa format (contoh: 150000),
    "keterangan": deskripsi singkat transaksi
}

Aturan:
1. "jenis" harus salah satu dari: Pemasukan, Pengeluaran
2. "kategori" harus salah satu dari: Fashion, Makanan, Minuman, Operasional
3. "nominal" harus berupa integer positif
4. Jika teks tidak mengandung informasi keuangan yang valid, kembalikan: {"error": "Tidak dapat memparse transaksi"}

Contoh:
- "Jual kaos hitam 3 pcs dapet 250rb" -> {"jenis": "Pemasukan", "kategori": "Fashion", "nominal": 250000, "keterangan": "Jual kaos hitam 3 pcs"}
- "Beli bahan baku bumbu dapur abis 75000" -> {"jenis": "Pengeluaran", "kategori": "Makanan", "nominal": 75000, "keterangan": "Beli bahan baku bumbu dapur"}
- "Bayar listrik bulanan 500rb" -> {"jenis": "Pengeluaran", "kategori": "Operasional", "nominal": 500000, "keterangan": "Bayar listrik bulanan"}
- "Transfer dana pribadi 200rb" -> {"jenis": "Pengeluaran", "kategori": "Dana Pribadi", "nominal": 200000, "keterangan": "Transfer dana pribadi"}
- "Bayar obat 50rb" -> {"jenis": "Pengeluaran", "kategori": "Kesehatan", "nominal": 50000, "keterangan": "Bayar obat"}
- "Grab ke kantor 25rb" -> {"jenis": "Pengeluaran", "kategori": "Transport", "nominal": 25000, "keterangan": "Grab ke kantor"}
- "Bayar kursus 500rb" -> {"jenis": "Pengeluaran", "kategori": "Pendidikan", "nominal": 500000, "keterangan": "Bayar kursus"}
- "Nonton bioskop 75rb" -> {"jenis": "Pengeluaran", "kategori": "Hiburan", "nominal": 75000, "keterangan": "Nonton bioskop"}

Teks: """

async def parse_with_gemini(text: str) -> dict:
    try:
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={AI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": PARSER_PROMPT + text}]}],
            "generationConfig": {"temperature": 0.3}
        }
        async with httpx.AsyncClient(trust_env=False, timeout=30) as client:
            response = await client.post(url, json=payload)
            data = response.json()
        
        logger.info(f"Gemini response: {data}")
        
        if "candidates" not in data:
            logger.error(f"Gemini error: {data}")
            return {"error": f"AI error: {data.get('error', {}).get('message', 'Unknown')}"}
        
        result_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:-3]
        elif result_text.startswith("```"):
            result_text = result_text[3:-3]
        
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return {"error": "Gagal memproses dengan AI"}

async def parse_with_openai(text: str) -> dict:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=AI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Anda adalah asisten keuangan yang menganalisis transaksi bisnis."},
                {"role": "user", "content": PARSER_PROMPT + text}
            ],
            temperature=0.3
        )
        
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:-3]
        elif result_text.startswith("```"):
            result_text = result_text[3:-3]
        
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return {"error": "Gagal memproses dengan AI"}

async def parse_with_mistral(text: str) -> dict:
    try:
        import httpx
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "mistral-small-latest",
            "messages": [
                {"role": "system", "content": "Anda adalah asisten keuangan yang menganalisis transaksi bisnis. Balas HANYA dengan JSON, tanpa teks lain."},
                {"role": "user", "content": PARSER_PROMPT + text}
            ],
            "temperature": 0.3
        }
        async with httpx.AsyncClient(trust_env=False, timeout=30) as client:
            response = await client.post(url, json=payload, headers=headers)
            data = response.json()
        
        logger.info(f"Mistral response: {data}")
        
        if "choices" not in data:
            logger.error(f"Mistral error: {data}")
            return {"error": f"AI error: {data.get('message', 'Unknown')}"}
        
        result_text = data["choices"][0]["message"]["content"].strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:-3]
        elif result_text.startswith("```"):
            result_text = result_text[3:-3]
        
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"Mistral API error: {e}")
        return {"error": "Gagal memproses dengan AI"}

async def parse_transaction(text: str) -> dict:
    if AI_PROVIDER == "gemini":
        result = await parse_with_gemini(text)
    elif AI_PROVIDER == "openai":
        result = await parse_with_openai(text)
    elif AI_PROVIDER == "mistral":
        result = await parse_with_mistral(text)
    else:
        return {"error": "AI provider tidak valid"}
    
    if "error" in result:
        return result
    
    if not all(key in result for key in ["jenis", "kategori", "nominal", "keterangan"]):
        return {"error": "Format response AI tidak valid"}
    
    if result["jenis"] not in JENIS_OPTIONS:
        return {"error": "Jenis transaksi tidak valid"}
    
    if result["kategori"] not in CATEGORIES:
        return {"error": "Kategori tidak valid"}
    
    try:
        result["nominal"] = int(result["nominal"])
    except (ValueError, TypeError):
        return {"error": "Nominal tidak valid"}
    
    return result