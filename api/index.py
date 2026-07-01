import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

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

HELP_TEXT = """FinBot-AI - Asisten Keuangan

Cara menggunakan:
- Kirim pesan untuk mencatat transaksi
- Contoh: 'Jual kaos hitam 3 pcs dapet 250rb'
- Contoh: 'Beli bahan baku abis 75000'

Perintah:
/help - Tampilkan bantuan ini
/today - Ringkasan transaksi hari ini
/weekly - Ringkasan transaksi minggu ini
/summary - Ringkasan semua transaksi"""

async def send_message(chat_id: int, text: str):
    await bot.send_message(chat_id=chat_id, text=text)

async def process_message(chat_id: int, text: str):
    try:
        parsed = await parse_transaction(text)

        if "error" in parsed:
            await send_message(chat_id, f"Error: {parsed['error']}\n\nContoh:\n- 'Jual kaos hitam 3 pcs dapet 250rb'\n- 'Beli bahan baku abis 75000'")
            return

        result = save_transaction(
            jenis=parsed["jenis"],
            kategori=parsed["kategori"],
            nominal=parsed["nominal"],
            keterangan=parsed["keterangan"],
            raw_text=text
        )

        if result["success"]:
            confirmation = (
                f"Transaksi berhasil dicatat!\n\n"
                f"Jenis: {parsed['jenis']}\n"
                f"Kategori: {parsed['kategori']}\n"
                f"Nominal: Rp {parsed['nominal']:,.0f}\n"
                f"Keterangan: {parsed['keterangan']}"
            )
            await send_message(chat_id, confirmation)
        else:
            await send_message(chat_id, "Gagal menyimpan data. Coba lagi.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await send_message(chat_id, "Terjadi kesalahan. Coba lagi nanti.")

async def handle_today(chat_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    transactions = get_transactions_by_date(today)
    if not transactions:
        await send_message(chat_id, "Tidak ada transaksi hari ini.")
        return
    total_pemasukan = sum(t["nominal"] for t in transactions if t["jenis"] == "Pemasukan")
    total_pengeluaran = sum(t["nominal"] for t in transactions if t["jenis"] == "Pengeluaran")
    summary = f"Ringkasan {today}:\n\n"
    summary += f"Pemasukan: Rp {total_pemasukan:,.0f}\n"
    summary += f"Pengeluaran: Rp {total_pengeluaran:,.0f}\n"
    summary += f"Selisih: Rp {total_pemasukan - total_pengeluaran:,.0f}\n\n"
    for t in transactions:
        summary += f"- {t['keterangan']} (Rp {t['nominal']:,.0f})\n"
    await send_message(chat_id, summary)

async def handle_weekly(chat_id: int):
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    transactions = get_transactions_by_week(week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d"))
    if not transactions:
        await send_message(chat_id, "Tidak ada transaksi minggu ini.")
        return
    total_pemasukan = sum(t["nominal"] for t in transactions if t["jenis"] == "Pemasukan")
    total_pengeluaran = sum(t["nominal"] for t in transactions if t["jenis"] == "Pengeluaran")
    summary = f"Ringkasan Mingguan:\n\n"
    summary += f"Pemasukan: Rp {total_pemasukan:,.0f}\n"
    summary += f"Pengeluaran: Rp {total_pengeluaran:,.0f}\n"
    summary += f"Selisih: Rp {total_pemasukan - total_pengeluaran:,.0f}\n"
    summary += f"Jumlah: {len(transactions)} transaksi"
    await send_message(chat_id, summary)

async def handle_summary(chat_id: int):
    transactions = get_all_transactions()
    if not transactions:
        await send_message(chat_id, "Belum ada transaksi.")
        return
    total_pemasukan = sum(t["nominal"] for t in transactions if t["jenis"] == "Pemasukan")
    total_pengeluaran = sum(t["nominal"] for t in transactions if t["jenis"] == "Pengeluaran")
    summary = f"Ringkasan Semua:\n\n"
    summary += f"Pemasukan: Rp {total_pemasukan:,.0f}\n"
    summary += f"Pengeluaran: Rp {total_pengeluaran:,.0f}\n"
    summary += f"Selisih: Rp {total_pemasukan - total_pengeluaran:,.0f}\n"
    summary += f"Jumlah: {len(transactions)} transaksi"
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
                else:
                    await process_message(chat_id, text)

            return PlainTextResponse("ok")
        except Exception as e:
            logger.error(f"Error: {e}")
            return PlainTextResponse("ok")
