# Library Management System — Backend

A full-stack Library Management System with a **Flask REST API** backend and **SQLite** database.

---

## Project Structure

```
library-backend/
├── app.py          ← Flask REST API server
├── index.html      ← Frontend (open in browser)
├── library.db      ← SQLite database (auto-created on first run)
└── README.md
```

---

## Requirements

- Python 3.8+
- Flask (install below)

---

## Setup & Run

### 1. Install Flask
```bash
pip install flask
```

### 2. Start the backend server
```bash
python app.py
```

You should see:
```
 Library Management API running at http://localhost:5000
```

### 3. Open the frontend
Open `index.html` in your browser (double-click the file or drag into Chrome/Firefox).

The green dot in the header confirms the API is connected.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | Dashboard statistics |
| GET | `/api/books` | List all books with availability |
| POST | `/api/books` | Add a new book |
| PUT | `/api/books/:id` | Update book details |
| DELETE | `/api/books/:id` | Delete a book |
| GET | `/api/issuances?active=true` | List active issuances |
| POST | `/api/issuances` | Issue a book to a member |
| POST | `/api/issuances/:id/return` | Return an issued book |
| GET | `/api/history` | Full issuance history |

---

## Example API Calls

### Add a book
```bash
curl -X POST http://localhost:5000/api/books \
  -H "Content-Type: application/json" \
  -d '{"title":"Wings of Fire","author":"A.P.J. Abdul Kalam","category":"Biography","copies":3}'
```

### Issue a book
```bash
curl -X POST http://localhost:5000/api/issuances \
  -H "Content-Type: application/json" \
  -d '{"book_id":1,"member":"Rahul Singh","member_id":"LIB-010","issue_date":"2026-05-01","due_date":"2026-05-15"}'
```

### Return a book
```bash
curl -X POST http://localhost:5000/api/issuances/1/return
```

---

## Features

- Full CRUD for books
- Issue books to members with due dates
- Track available vs issued copies per book
- Overdue detection and alerts
- Complete issuance history
- Data persists in SQLite across restarts
- Preloaded with sample data on first run
