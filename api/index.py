import os
import sys
import logging
import re
from pathlib import Path
from datetime import datetime, timedelta

for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"]:
    os.environ.pop(var, None)

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from telegram import Update, Bot

from config import TELEGRAM_TOKEN, AUTHORIZED_SENDER_ID
from services.ai_parser import parse_transaction
from services.database import save_transaction, get_transactions_by_date, get_transactions_by_week, get_all_transactions

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
- *Utang client 500rb*

*Perintah:*
/help - Bantuan
/today - Ringkasan hari ini
/weekly - Ringkasan minggu ini
/summary - Semua transaksi

*Query natural:*
- *berapa total* - Total semua transaksi
- *total hari ini* - Total hari ini
- *pengeluaran minggu ini* - Total pengeluaran minggu ini
- *pemasukan bulan ini* - Total pemasukan bulan ini"""

def format_rp(nominal):
    return f"Rp {nominal:,.0f}".replace(",", ".")

def is_query(text):
    keywords = ["berapa", "total", "ringkasan", "rekap", "laporan", "sisa", "selisih", "keuntungan", "lab", "rugi"]
    return any(k in text.lower() for k in keywords)

async def send_message(chat_id: int, text: str):
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

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
    status = "Untung" if selisih >= 0 else "Rugi"

    # Count by category
    kategori_stats = {}
    for t in transactions:
        k = t.get("kategori", "Lainnya")
        if k not in kategori_stats:
            kategori_stats[k] = {"Pemasukan": 0, "Pengeluaran": 0}
        kategori_stats[k][t.get("jenis", "")] += t.get("nominal", 0)

    summary = f"*Rekap Keuangan - {label}*\n"
    summary += f"{'='*25}\n\n"
    summary += f"*Pemasukan:* {format_rp(total_pemasukan)}\n"
    summary += f"*Pengeluaran:* {format_rp(total_pengeluaran)}\n"
    summary += f"*{status}:* {format_rp(abs(selisih))}\n"
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

        result = await save_transaction(
            jenis=parsed["jenis"],
            kategori=parsed["kategori"],
            nominal=parsed["nominal"],
            keterangan=parsed["keterangan"],
            raw_text=text
        )

        if result["success"]:
            emoji = "📈" if parsed["jenis"] == "Pemasukan" else "📉"
            confirmation = (
                f"{emoji} *Transaksi Tercatat!*\n\n"
                f"*Jenis:* {parsed['jenis']}\n"
                f"*Kategori:* {parsed['kategori']}\n"
                f"*Nominal:* {format_rp(parsed['nominal'])}\n"
                f"*Keterangan:* {parsed['keterangan']}"
            )
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
    summary = f"*Ringkasan {today_str}*\n\n"
    summary += f"*Pemasukan:* {format_rp(total_pemasukan)}\n"
    summary += f"*Pengeluaran:* {format_rp(total_pengeluaran)}\n"
    summary += f"*Selisih:* {format_rp(total_pemasukan - total_pengeluaran)}\n\n"
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
    summary = f"*Ringkasan Mingguan*\n{week_start.strftime('%d %b')} - {week_end.strftime('%d %b %Y')}\n\n"
    summary += f"*Pemasukan:* {format_rp(total_pemasukan)}\n"
    summary += f"*Pengeluaran:* {format_rp(total_pengeluaran)}\n"
    summary += f"*Selisih:* {format_rp(total_pemasukan - total_pengeluaran)}\n"
    summary += f"*Transaksi:* {len(transactions)}"
    await send_message(chat_id, summary)

async def handle_summary(chat_id: int):
    transactions = await get_all_transactions()
    if not transactions:
        await send_message(chat_id, "Belum ada transaksi.")
        return
    total_pemasukan = sum(t["nominal"] for t in transactions if t.get("jenis") == "Pemasukan")
    total_pengeluaran = sum(t["nominal"] for t in transactions if t.get("jenis") == "Pengeluaran")
    summary = f"*Ringkasan Semua Transaksi*\n\n"
    summary += f"*Pemasukan:* {format_rp(total_pemasukan)}\n"
    summary += f"*Pengeluaran:* {format_rp(total_pengeluaran)}\n"
    summary += f"*Selisih:* {format_rp(total_pemasukan - total_pengeluaran)}\n"
    summary += f"*Total Transaksi:* {len(transactions)}"
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
                elif is_query(text):
                    await handle_query(chat_id, text)
                else:
                    await process_message(chat_id, text)

            return PlainTextResponse("ok")
        except Exception as e:
            logger.error(f"Error: {e}")
            return PlainTextResponse("ok")
