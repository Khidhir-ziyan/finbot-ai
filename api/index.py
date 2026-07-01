import os
import sys
import logging
import re
import httpx
from pathlib import Path
from datetime import datetime, timedelta

for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"]:
    os.environ.pop(var, None)

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from telegram import Update, Bot

from config import TELEGRAM_TOKEN, AUTHORIZED_SENDER_ID, CATEGORIES, SUPABASE_URL, SUPABASE_KEY
from services.ai_parser import parse_transaction
from services.database import (
    save_transaction, get_transactions_by_date, get_transactions_by_week,
    get_all_transactions, set_budget, get_all_budgets, get_budget_by_kategori
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
bot = Bot(token=TELEGRAM_TOKEN)

HELP_TEXT = """*FinBot-AI* - Asisten Keuangan Pintar

*Cara mencatat transaksi:*
Kirim pesan natural, contoh:
- *Jual kaos hitam 3 pcs dapet 250rb*
- *Beli bahan kopi 60000*
- *Bayar listrik 350rb*

*Perintah:*
/help - Bantuan
/today - Ringkasan hari ini
/weekly - Ringkasan minggu ini
/summary - Semua transaksi
/budget - Lihat semua budget
/analisis - Analisis keuangan & rekomendasi

*Query natural:*
- *berapa total* - Total semua transaksi
- *total hari ini* - Total hari ini
- *pengeluaran minggu ini* - Total pengeluaran minggu ini
- *liat semua* - Semua transaksi

*Budget:*
- *set budget makanan 500rb* - Set budget kategori
- *budget makanan* - Cek sisa budget
- *hapus budget makanan* - Hapus budget

*Analisis:*
- *analisis* - Analisis keuangan & rekomendasi
- *tips* - Tips keuangan"""

def format_rp(nominal):
    return f"Rp {nominal:,.0f}".replace(",", ".")

def parse_rp(text):
    text = text.lower().replace("rp", "").replace(".", "").replace(",", "").strip()
    multipliers = {"rb": 1000, "jt": 1000000, "k": 1000, "m": 1000000, "juta": 1000000, "ribu": 1000, "ibu": 1000}
    for suffix, mult in multipliers.items():
        if text.endswith(suffix):
            text = text[:-len(suffix)].strip()
            try:
                return int(float(text) * mult)
            except ValueError:
                return None
    try:
        return int(float(text))
    except ValueError:
        return None

def is_query(text):
    keywords = ["berapa", "total", "ringkasan", "rekap", "laporan", "sisa", "selisih", "keuntungan", "lab", "rugi", "lihat", "liat", "cek", "show", "semua", "semuanya", "tampilkan", "kasih tau", "info", "status", "posisi"]
    return any(k in text.lower() for k in keywords)

def is_budget_set(text):
    text = text.lower()
    patterns = [
        r"set\s+budget\s+",
        r"budget\s+.*\d+",
        r"anggaran\s+",
        r"alokasi\s+",
    ]
    has_amount = bool(re.search(r"\d+", text))
    has_kategori = any(k in text for k in ["set budget", "anggaran", "alokasi", "budget"])
    return has_kategori and has_amount

def is_budget_check(text):
    text = text.lower()
    if "set" in text or "hapus" in text:
        return False
    patterns = [
        r"^budget\s+\w+$",
        r"sisa\s+budget",
        r"cek\s+budget",
        r"berapa\s+budget",
        r"budget\s+(saya|ku|gw)",
    ]
    return any(re.search(p, text) for p in patterns)

def is_budget_delete(text):
    return any(k in text.lower() for k in ["hapus budget", "hapus anggaran", "remove budget", "delete budget"])

def is_analisis(text):
    return any(k in text.lower() for k in ["analisis", "analisa", "rekomendasi", "saran", "tips", "strategy", "strategi"])

async def send_message(chat_id: int, text: str):
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception:
        await bot.send_message(chat_id=chat_id, text=text)

async def handle_budget_set(chat_id: int, text: str):
    text_lower = text.lower()
    nominal = None
    kategori = None

    # Extract nominal
    amount_match = re.search(r"(\d+[\d\.]*)\s*(rb|k|jt|m|juta|ribu|ibu)?", text_lower)
    if amount_match:
        nominal = parse_rp(amount_match.group(0))

    # Extract kategori
    for cat in CATEGORIES:
        if cat.lower() in text_lower:
            kategori = cat
            break

    if not kategori:
        # Try to find any word that looks like a category
        words = text_lower.split()
        for word in words:
            if word not in ["set", "budget", "anggaran", "alokasi", "untuk", "dari", "ke"] and not re.match(r"\d", word):
                kategori = word.capitalize()
                break

    if not nominal:
        await send_message(chat_id, "Contoh:\n- *set budget makanan 500rb*\n- *budget olahraga 300k*\n- *anggaran transport 200ribu*")
        return

    if not kategori:
        kategori = "Lainnya"

    result = await set_budget(kategori, nominal)
    if result["success"]:
        await send_message(chat_id, f"✅ *Budget {kategori} berhasil diset!*\n\nBudget bulanan: {format_rp(nominal)}\n\nKetik *budget {kategori.lower()}* untuk cek sisa budget.")
    else:
        await send_message(chat_id, "Gagal set budget. Coba lagi.")

async def handle_budget_check(chat_id: int, text: str):
    text_lower = text.lower()
    kategori = None

    # Extract kategori
    for cat in CATEGORIES:
        if cat.lower() in text_lower:
            kategori = cat
            break

    if not kategori:
        # Try to find any word that looks like a category
        words = text_lower.split()
        for word in words:
            if word not in ["budget", "sisa", "cek", "berapa", "saya", "ku", "gw", "untuk", "dari", "ke"] and not re.match(r"\d", word):
                kategori = word.capitalize()
                break

    if not kategori:
        await send_message(chat_id, "Contoh:\n- *budget makanan*\n- *sisa budget transport*\n- *berapa budget hiburan*")
        return

    budget = await get_budget_by_kategori(kategori)

    if not budget:
        await send_message(chat_id, f"Belum ada budget untuk *{kategori}*.\n\nSet dengan: *set budget {kategori.lower()} 500rb*")
        return

    now = datetime.now()
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    all_t = await get_all_transactions()
    spent = sum(t["nominal"] for t in all_t if t.get("kategori") == kategori and t.get("jenis") == "Pengeluaran" and t.get("created_at", "")[:10] >= month_start)

    budget_nominal = budget["nominal"]
    sisa = budget_nominal - spent
    persen = (spent / budget_nominal * 100) if budget_nominal > 0 else 0

    bar_len = 10
    filled = int(persen / 100 * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)

    status = "✅ Aman" if persen < 80 else "⚠️ Hati-hati" if persen < 100 else "🚨 Overbudget!"

    summary = f"*Budget {kategori} - {now.strftime('%B %Y')}*\n\n"
    summary += f"*Budget:* {format_rp(budget_nominal)}\n"
    summary += f"*Terpakai:* {format_rp(spent)} ({persen:.0f}%)\n"
    summary += f"*Sisa:* {format_rp(sisa)}\n"
    summary += f"*Status:* {status}\n"
    summary += f"[{bar}]"

    await send_message(chat_id, summary)

async def handle_budget_delete(chat_id: int, text: str):
    match = re.search(r"hapus budget (\w+)", text.lower())
    if not match:
        await send_message(chat_id, "Format: *hapus budget makanan*")
        return
    kategori = match.group(1).capitalize()
    try:
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        async with httpx.AsyncClient(trust_env=False, timeout=10, follow_redirects=True) as client:
            await client.delete(
                f"{SUPABASE_URL}/rest/v1/budgets",
                headers=headers,
                params={"kategori": f"eq.{kategori}"}
            )
        await send_message(chat_id, f"✅ Budget *{kategori}* berhasil dihapus.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await send_message(chat_id, "Gagal hapus budget.")

async def handle_budget_list(chat_id: int):
    budgets = await get_all_budgets()
    if not budgets:
        await send_message(chat_id, "Belum ada budget.\n\nSet dengan: *set budget makanan 500rb*")
        return

    now = datetime.now()
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    all_t = await get_all_transactions()

    summary = f"*Budget Bulanan - {now.strftime('%B %Y')}*\n{'='*25}\n\n"
    for b in budgets:
        kategori = b["kategori"]
        budget_nominal = b["nominal"]
        spent = sum(t["nominal"] for t in all_t if t.get("kategori") == kategori and t.get("jenis") == "Pengeluaran" and t.get("created_at", "")[:10] >= month_start)
        sisa = budget_nominal - spent
        persen = (spent / budget_nominal * 100) if budget_nominal > 0 else 0

        bar_len = 10
        filled = int(persen / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        status_icon = "✅" if persen < 80 else "⚠️" if persen < 100 else "🚨"
        summary += f"*{kategori}* {status_icon}\n"
        summary += f"  {format_rp(spent)} / {format_rp(budget_nominal)}\n"
        summary += f"  [{bar}] {persen:.0f}%\n"
        summary += f"  Sisa: {format_rp(sisa)}\n\n"

    await send_message(chat_id, summary)

async def handle_analisis(chat_id: int):
    now = datetime.now()
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    all_t = await get_all_transactions()
    month_t = [t for t in all_t if t.get("created_at", "")[:10] >= month_start]

    if not month_t:
        await send_message(chat_id, "Belum ada data untuk dianalisis.")
        return

    total_pemasukan = sum(t["nominal"] for t in month_t if t.get("jenis") == "Pemasukan")
    total_pengeluaran = sum(t["nominal"] for t in month_t if t.get("jenis") == "Pengeluaran")
    selisih = total_pemasukan - total_pengeluaran
    persen_tabungan = (selisih / total_pemasukan * 100) if total_pemasukan > 0 else 0

    # Top pengeluaran
    pengeluaran = [t for t in month_t if t.get("jenis") == "Pengeluaran"]
    by_kategori = {}
    for t in pengeluaran:
        k = t.get("kategori", "Lainnya")
        by_kategori[k] = by_kategori.get(k, 0) + t.get("nominal", 0)

    sorted_kategori = sorted(by_kategori.items(), key=lambda x: x[1], reverse=True)

    # Rekomendasi
    rekomendasi = []
    if persen_tabungan < 20:
        rekomendasi.append("💡 Tabungan kurang dari 20%. Coba kurangi pengeluaran non-esensial.")
    if by_kategori.get("Hiburan", 0) > total_pemasukan * 0.2:
        rekomendasi.append("🎮 Pengeluaran hiburan cukup besar. Pertimbangkan untuk mengurangi.")
    if not any(b["kategori"] == "Dana Pribadi" for b in await get_all_budgets()):
        rekomendasi.append("💰 Belum ada budget dana pribadi. Pertimbangkan untuk set.")
    if persen_tabungan >= 30:
        rekomendasi.append("🌟 Hebat! Tabungan lebih dari 30%. Pertimbangkan investasi.")

    summary = f"*Analisis Keuangan - {now.strftime('%B %Y')}*\n{'='*25}\n\n"
    summary += f"*Pemasukan:* {format_rp(total_pemasukan)}\n"
    summary += f"*Pengeluaran:* {format_rp(total_pengeluaran)}\n"
    summary += f"*Selisih:* {format_rp(selisih)}\n"
    summary += f"*Persentase Tabungan:* {persen_tabungan:.1f}%\n\n"

    if sorted_kategori:
        summary += f"*Top Pengeluaran:*\n"
        for k, v in sorted_kategori[:5]:
            summary += f"- {k}: {format_rp(v)}\n"

    if rekomendasi:
        summary += f"\n*Rekomendasi:*\n"
        for r in rekomendasi:
            summary += f"{r}\n"

    await send_message(chat_id, summary)

async def handle_query(chat_id: int, text: str):
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    month_start = today.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    text_lower = text.lower()

    if "hari ini" in text_lower or "today" in text_lower:
        transactions = await get_transactions_by_date(today_str)
        label = "Hari Ini"
    elif "minggu" in text_lower or "week" in text_lower:
        transactions = await get_transactions_by_week(week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d"))
        label = "Minggu Ini"
    elif "bulan" in text_lower or "month" in text_lower:
        all_t = await get_all_transactions()
        transactions = [t for t in all_t if month_start.strftime("%Y-%m-%d") <= (t.get("created_at", "")[:10]) <= month_end.strftime("%Y-%m-%d")]
        label = "Bulan Ini"
    else:
        transactions = await get_all_transactions()
        label = "Semua"

    if not transactions:
        await send_message(chat_id, f"Tidak ada transaksi *{label.lower()}*.")
        return

    total_pemasukan = sum(t["nominal"] for t in transactions if t.get("jenis") == "Pemasukan")
    total_pengeluaran = sum(t["nominal"] for t in transactions if t.get("jenis") == "Pengeluaran")
    selisih = total_pemasukan - total_pengeluaran

    kategori_stats = {}
    for t in transactions:
        k = t.get("kategori", "Lainnya")
        if k not in kategori_stats:
            kategori_stats[k] = {"Pemasukan": 0, "Pengeluaran": 0}
        kategori_stats[k][t.get("jenis", "")] += t.get("nominal", 0)

    summary = f"*Rekap Keuangan - {label}*\n{'='*25}\n\n"
    summary += f"*Pemasukan:* {format_rp(total_pemasukan)}\n"
    summary += f"*Pengeluaran:* {format_rp(total_pengeluaran)}\n"
    summary += f"*Selisih:* {format_rp(selisih)}\n"
    summary += f"*Jumlah Transaksi:* {len(transactions)}\n"

    if kategori_stats:
        summary += f"\n*Per Kategori:*\n"
        for k, v in kategori_stats.items():
            total = v["Pemasukan"] - v["Pengeluaran"]
            summary += f"- {k}: {format_rp(abs(total))} {'+' if total >= 0 else '-'}\n"

    await send_message(chat_id, summary)

async def process_message(chat_id: int, text: str):
    try:
        parsed = await parse_transaction(text)
        if "error" in parsed:
            await send_message(chat_id, f"⚠️ *Error:* {parsed['error']}\n\nContoh:\n- *Jual kaos hitam 3 pcs dapet 250rb*\n- *Beli bahan baku abis 75000*")
            return
        result = await save_transaction(jenis=parsed["jenis"], kategori=parsed["kategori"], nominal=parsed["nominal"], keterangan=parsed["keterangan"], raw_text=text)
        if result["success"]:
            emoji = "📈" if parsed["jenis"] == "Pemasukan" else "📉"
            confirmation = f"{emoji} *Transaksi Tercatat!*\n\n*Jenis:* {parsed['jenis']}\n*Kategori:* {parsed['kategori']}\n*Nominal:* {format_rp(parsed['nominal'])}\n*Keterangan:* {parsed['keterangan']}"
            await send_message(chat_id, confirmation)
        else:
            await send_message(chat_id, "Gagal menyimpan data. Coba lagi.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await send_message(chat_id, "Terjadi kesalahan. Coba lagi nanti.")

async def handle_today(chat_id: int):
    today_str = datetime.now().strftime("%Y-%m-%d")
    transactions = await get_transactions_by_date(today_str)
    if not transactions:
        await send_message(chat_id, "Tidak ada transaksi hari ini.")
        return
    total_pemasukan = sum(t["nominal"] for t in transactions if t.get("jenis") == "Pemasukan")
    total_pengeluaran = sum(t["nominal"] for t in transactions if t.get("jenis") == "Pengeluaran")
    summary = f"*Ringkasan {today_str}*\n\n*Pemasukan:* {format_rp(total_pemasukan)}\n*Pengeluaran:* {format_rp(total_pengeluaran)}\n*Selisih:* {format_rp(total_pemasukan - total_pengeluaran)}\n\n"
    for t in transactions:
        emoji = "+" if t.get("jenis") == "Pemasukan" else "-"
        summary += f"- {t.get('keterangan', '')} ({format_rp(t.get('nominal', 0))}) {emoji}\n"
    await send_message(chat_id, summary)

async def handle_weekly(chat_id: int):
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    transactions = await get_transactions_by_week(week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d"))
    if not transactions:
        await send_message(chat_id, "Tidak ada transaksi minggu ini.")
        return
    total_pemasukan = sum(t["nominal"] for t in transactions if t.get("jenis") == "Pemasukan")
    total_pengeluaran = sum(t["nominal"] for t in transactions if t.get("jenis") == "Pengeluaran")
    summary = f"*Ringkasan Mingguan*\n{week_start.strftime('%d %b')} - {week_end.strftime('%d %b %Y')}\n\n*Pemasukan:* {format_rp(total_pemasukan)}\n*Pengeluaran:* {format_rp(total_pengeluaran)}\n*Selisih:* {format_rp(total_pemasukan - total_pengeluaran)}\n*Transaksi:* {len(transactions)}"
    await send_message(chat_id, summary)

async def handle_summary(chat_id: int):
    transactions = await get_all_transactions()
    if not transactions:
        await send_message(chat_id, "Belum ada transaksi.")
        return
    total_pemasukan = sum(t["nominal"] for t in transactions if t.get("jenis") == "Pemasukan")
    total_pengeluaran = sum(t["nominal"] for t in transactions if t.get("jenis") == "Pengeluaran")
    summary = f"*Ringkasan Semua Transaksi*\n\n*Pemasukan:* {format_rp(total_pemasukan)}\n*Pengeluaran:* {format_rp(total_pengeluaran)}\n*Selisih:* {format_rp(total_pemasukan - total_pengeluaran)}\n*Total Transaksi:* {len(transactions)}"
    await send_message(chat_id, summary)

@app.api_route("/{path:path}", methods=["GET", "POST"])
async def handler(request: Request, path: str = ""):
    if request.method == "GET":
        if path == "health":
            return JSONResponse({"status": "healthy"})
        return JSONResponse({"message": "FinBot-AI is running"})

    if request.method == "POST":
        try:
            data = await request.json()
            update = Update.de_json(data, bot)
            if update.message:
                sender_id = update.message.from_user.id
                if sender_id != AUTHORIZED_SENDER_ID:
                    await send_message(update.message.chat_id, "Akses ditolak.")
                    return PlainTextResponse("ok")
                text = update.message.text or ""
                chat_id = update.message.chat_id

                if text == "/help":
                    await send_message(chat_id, HELP_TEXT)
                elif text == "/today":
                    await handle_today(chat_id)
                elif text == "/weekly":
                    await handle_weekly(chat_id)
                elif text == "/summary":
                    await handle_summary(chat_id)
                elif text == "/budget":
                    await handle_budget_list(chat_id)
                elif text == "/analisis":
                    await handle_analisis(chat_id)
                elif is_budget_set(text):
                    await handle_budget_set(chat_id, text)
                elif is_budget_delete(text):
                    await handle_budget_delete(chat_id, text)
                elif is_budget_check(text):
                    await handle_budget_check(chat_id, text)
                elif is_analisis(text):
                    await handle_analisis(chat_id)
                elif is_query(text):
                    await handle_query(chat_id, text)
                else:
                    await process_message(chat_id, text)

            return PlainTextResponse("ok")
        except Exception as e:
            logger.error(f"Error: {e}")
            return PlainTextResponse("ok")
