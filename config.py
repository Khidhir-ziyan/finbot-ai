import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
AI_API_KEY = os.getenv("AI_API_KEY")
AUTHORIZED_SENDER_ID = int(os.getenv("AUTHORIZED_SENDER_ID", "0"))
AI_PROVIDER = os.getenv("AI_PROVIDER", "mistral")

CATEGORIES = ["Fashion", "Makanan", "Minuman", "Operasional"]
JENIS_OPTIONS = ["Pemasukan", "Pengeluaran"]