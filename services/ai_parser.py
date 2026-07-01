import json
import logging
from config import AI_API_KEY, AI_PROVIDER, CATEGORIES, JENIS_OPTIONS

logger = logging.getLogger(__name__)

PARSER_PROMPT = """Anda adalah asisten keuangan yang menganalisis transaksi bisnis.

Analisis teks berikut dan ekstrak data transaksi dalam format JSON:
{
    "jenis": "Pemasukan" atau "Pengeluaran",
    "kategori": "Fashion", "Makanan", "Minuman", atau "Operasional",
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

Teks: """

async def parse_with_gemini(text: str) -> dict:
    try:
        import google.generativeai as genai
        genai.configure(api_key=AI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(PARSER_PROMPT + text)
        
        result_text = response.text.strip()
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

async def parse_transaction(text: str) -> dict:
    if AI_PROVIDER == "gemini":
        result = await parse_with_gemini(text)
    elif AI_PROVIDER == "openai":
        result = await parse_with_openai(text)
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