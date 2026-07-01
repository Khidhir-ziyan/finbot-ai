# FinBot-AI

AI-powered Telegram bot for business financial recording.

## Features

- Record transactions via natural language messages
- Auto-categorize transactions (Fashion, Makanan, Minuman, Operasional)
- Generate daily, weekly, and total summaries
- Secure access with sender_id validation

## Setup

### 1. Clone and Install

```bash
git clone <repository-url>
cd FinanceAI
pip install -r requirements.txt
```

### 2. Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
TELEGRAM_TOKEN=your_telegram_bot_token
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
AI_API_KEY=your_ai_api_key
AUTHORIZED_SENDER_ID=your_telegram_user_id
AI_PROVIDER=gemini
```

### 3. Database Setup

Create `cash_flow` table in Supabase:

```sql
CREATE TABLE cash_flow (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    jenis VARCHAR(20) NOT NULL,
    kategori VARCHAR(50) NOT NULL,
    nominal NUMERIC NOT NULL,
    keterangan TEXT,
    raw_text TEXT
);
```

### 4. Run Locally

```bash
python main.py
```

### 5. Deploy to Render

1. Push to GitHub
2. Create Web Service on Render
3. Set environment variables
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `python main.py`
6. Set webhook URL: `https://your-app.onrender.com/webhook`

## Bot Commands

- `/help` - Show help
- `/today` - Today's summary
- `/weekly` - Weekly summary
- `/summary` - All transactions summary

## Example Usage

```
Jual kaos hitam 3 pcs dapet 250rb
Beli bahan baku abis 75000
Bayar listrik bulanan 500rb
```

## Architecture

```
User → Telegram Bot API → FastAPI Webhook → AI Parser → Supabase
```