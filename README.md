# TCG Trove - Quick Start

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
```powershell
python scripts\dev_server.py --reload
```
Open: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

### 🔑 Demo Accounts
| Role | Username | Password | Tabs to Check |
| --- | --- | --- | --- |
| **Admin** | `admin` | `admin` | Admin Dashboard |
| **Supervisor** | `supervisor` | `supervisor123` | Supervisor & Reports |
| **Seller** | `seller` | `seller123` | Seller Dashboard |
| **Buyer** | `buyer` | `buyer123` | Marketplace/Cart |

---

### 🧪 Testing
```powershell
python -m pytest
```
