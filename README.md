# TCG Trove

TCG Trove is a FastAPI web app for browsing, listing, and managing trading card
marketplace activity.

The final app only needs these files:

```text
app/                 FastAPI app, templates, static files, database models
requirements.txt     Python packages needed to run the website
tcg_trove.db         ready-to-use SQLite demo database
.env.example         example environment settings
README.md            this guide
```

### 1. Setup

**Windows:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

**Mac/Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Run

The app runs on port `8010` to avoid the more common `8000` port.

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

Open: [http://127.0.0.1:8010](http://127.0.0.1:8010)

---

### Demo Accounts

| Role | Username | Password | Tabs to Check |
| --- | --- | --- | --- |
| **Admin** | `admin` | `admin` | Admin Dashboard |
| **Supervisor** | `supervisor` | `supervisor123` | Supervisor & Reports |
| **Seller** | `seller` | `seller123` | Seller Dashboard |
| **Buyer** | `buyer` | `buyer123` | Marketplace/Cart |
