Development commands on Windows PowerShell:

```powershell
cd C:\Users\dimit\Desktop\computer_science\pythonprojects\tcgtrove
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts/dev_server.py --reload
```

Verification:

```powershell
python -m compileall app
python -m pytest -q
```

Direct server alternative:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Local app URL: http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs.