# AutoApply

Automated job application system — MVP.

## Tech Stack

- **Backend:** Python + FastAPI + SQLAlchemy + SQLite
- **Frontend:** React + Vite + TypeScript + react-bootstrap
- **AI:** Google Gemini

## Setup

### Backend

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate   # Windows
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```
