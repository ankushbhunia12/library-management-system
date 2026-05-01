import sqlite3
import json
from datetime import datetime
from flask import Flask, request, g

app = Flask(__name__)
DATABASE = 'library.db'

# ─── DB helpers ───────────────────────────────────────────────────────────────

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                title     TEXT NOT NULL,
                author    TEXT NOT NULL,
                isbn      TEXT,
                category  TEXT,
                copies    INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS issuances (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id     INTEGER NOT NULL REFERENCES books(id),
                member      TEXT NOT NULL,
                member_id   TEXT NOT NULL,
                issue_date  TEXT NOT NULL,
                due_date    TEXT NOT NULL,
                returned_at TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        # Seed data if empty
        count = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        if count == 0:
            db.executescript("""
                INSERT INTO books (title, author, isbn, category, copies) VALUES
                  ('The Great Gatsby',       'F. Scott Fitzgerald', '978-0743273565', 'Fiction',    4),
                  ('A Brief History of Time','Stephen Hawking',     '978-0553380163', 'Science',    3),
                  ('Sapiens',                'Yuval Noah Harari',   '978-0062316097', 'History',    5),
                  ('Clean Code',             'Robert C. Martin',    '978-0132350884', 'Technology', 2),
                  ('The Alchemist',          'Paulo Coelho',        '978-0062315007', 'Fiction',    6);

                INSERT INTO issuances (book_id, member, member_id, issue_date, due_date) VALUES
                  (1, 'Priya Sharma',  'LIB-001', '2026-04-10', '2026-04-25'),
                  (2, 'Rohan Mehta',   'LIB-002', '2026-04-15', '2026-04-29'),
                  (3, 'Anita Desai',   'LIB-003', '2026-04-20', '2026-05-04'),
                  (5, 'Vikram Nair',   'LIB-004', '2026-04-08', '2026-04-22');
            """)
        db.commit()

# ─── CORS (manual, no library needed) ────────────────────────────────────────

def cors(response, status=200):
    from flask import Response
    if not isinstance(response, Response):
        response = app.response_class(
            response=json.dumps(response),
            status=status,
            mimetype='application/json'
        )
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return response

def ok(data, status=200):
    return cors(data, status)

def err(msg, status=400):
    return cors({"error": msg}, status)

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return response

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def options(path):
    return ok({})

# ─── BOOKS ────────────────────────────────────────────────────────────────────

@app.route('/api/books', methods=['GET'])
def list_books():
    db = get_db()
    rows = db.execute("""
        SELECT b.*,
               COUNT(CASE WHEN i.returned_at IS NULL THEN 1 END) AS issued_count,
               b.copies - COUNT(CASE WHEN i.returned_at IS NULL THEN 1 END) AS available
        FROM books b
        LEFT JOIN issuances i ON i.book_id = b.id
        GROUP BY b.id
        ORDER BY b.title
    """).fetchall()
    return ok([dict(r) for r in rows])

@app.route('/api/books', methods=['POST'])
def add_book():
    data = request.get_json()
    if not data or not data.get('title') or not data.get('author'):
        return err("title and author are required")
    db = get_db()
    cur = db.execute(
        "INSERT INTO books (title, author, isbn, category, copies) VALUES (?,?,?,?,?)",
        (data['title'], data['author'], data.get('isbn',''), data.get('category','General'), int(data.get('copies',1)))
    )
    db.commit()
    book = db.execute("SELECT * FROM books WHERE id=?", (cur.lastrowid,)).fetchone()
    return ok({**dict(book), 'issued_count': 0, 'available': book['copies']}, 201)

@app.route('/api/books/<int:book_id>', methods=['PUT'])
def update_book(book_id):
    data = request.get_json()
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    if not book:
        return err("Book not found", 404)
    issued = db.execute("SELECT COUNT(*) FROM issuances WHERE book_id=? AND returned_at IS NULL", (book_id,)).fetchone()[0]
    new_copies = int(data.get('copies', book['copies']))
    if new_copies < issued:
        return err(f"Cannot set copies to {new_copies}, {issued} copies are currently issued")
    db.execute(
        "UPDATE books SET title=?, author=?, isbn=?, category=?, copies=? WHERE id=?",
        (data.get('title', book['title']), data.get('author', book['author']),
         data.get('isbn', book['isbn']), data.get('category', book['category']),
         new_copies, book_id)
    )
    db.commit()
    updated = db.execute("""
        SELECT b.*, COUNT(CASE WHEN i.returned_at IS NULL THEN 1 END) AS issued_count,
               b.copies - COUNT(CASE WHEN i.returned_at IS NULL THEN 1 END) AS available
        FROM books b LEFT JOIN issuances i ON i.book_id = b.id
        WHERE b.id=? GROUP BY b.id
    """, (book_id,)).fetchone()
    return ok(dict(updated))

@app.route('/api/books/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    db = get_db()
    issued = db.execute("SELECT COUNT(*) FROM issuances WHERE book_id=? AND returned_at IS NULL", (book_id,)).fetchone()[0]
    if issued > 0:
        return err("Cannot delete book with active issuances")
    db.execute("DELETE FROM books WHERE id=?", (book_id,))
    db.commit()
    return ok({"deleted": book_id})

# ─── ISSUANCES ────────────────────────────────────────────────────────────────

@app.route('/api/issuances', methods=['GET'])
def list_issuances():
    db = get_db()
    only_active = request.args.get('active', 'true').lower() == 'true'
    query = """
        SELECT i.*, b.title AS book_title, b.category
        FROM issuances i JOIN books b ON b.id = i.book_id
        WHERE i.returned_at IS NULL
        ORDER BY i.due_date
    """ if only_active else """
        SELECT i.*, b.title AS book_title, b.category
        FROM issuances i JOIN books b ON b.id = i.book_id
        ORDER BY i.created_at DESC
    """
    rows = db.execute(query).fetchall()
    return ok([dict(r) for r in rows])

@app.route('/api/issuances', methods=['POST'])
def issue_book():
    data = request.get_json()
    required = ['book_id', 'member', 'member_id', 'issue_date', 'due_date']
    if not data or not all(data.get(f) for f in required):
        return err("All fields are required: " + ", ".join(required))
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id=?", (data['book_id'],)).fetchone()
    if not book:
        return err("Book not found", 404)
    issued = db.execute("SELECT COUNT(*) FROM issuances WHERE book_id=? AND returned_at IS NULL", (data['book_id'],)).fetchone()[0]
    if issued >= book['copies']:
        return err("No copies available for this book")
    cur = db.execute(
        "INSERT INTO issuances (book_id, member, member_id, issue_date, due_date) VALUES (?,?,?,?,?)",
        (data['book_id'], data['member'], data['member_id'], data['issue_date'], data['due_date'])
    )
    db.commit()
    row = db.execute(
        "SELECT i.*, b.title AS book_title FROM issuances i JOIN books b ON b.id=i.book_id WHERE i.id=?",
        (cur.lastrowid,)
    ).fetchone()
    return ok(dict(row), 201)

@app.route('/api/issuances/<int:issuance_id>/return', methods=['POST'])
def return_book(issuance_id):
    db = get_db()
    row = db.execute("SELECT * FROM issuances WHERE id=?", (issuance_id,)).fetchone()
    if not row:
        return err("Issuance not found", 404)
    if row['returned_at']:
        return err("Book already returned")
    db.execute("UPDATE issuances SET returned_at=? WHERE id=?", (datetime.now().isoformat(), issuance_id))
    db.commit()
    return ok({"returned": issuance_id})

# ─── STATS ────────────────────────────────────────────────────────────────────

@app.route('/api/stats', methods=['GET'])
def stats():
    db = get_db()
    today = datetime.now().date().isoformat()
    total_books   = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    total_copies  = db.execute("SELECT SUM(copies) FROM books").fetchone()[0] or 0
    total_issued  = db.execute("SELECT COUNT(*) FROM issuances WHERE returned_at IS NULL").fetchone()[0]
    overdue_count = db.execute("SELECT COUNT(*) FROM issuances WHERE returned_at IS NULL AND due_date < ?", (today,)).fetchone()[0]
    return ok({
        "total_books": total_books,
        "total_copies": total_copies,
        "total_issued": total_issued,
        "available": total_copies - total_issued,
        "overdue": overdue_count
    })

# ─── HISTORY ─────────────────────────────────────────────────────────────────

@app.route('/api/history', methods=['GET'])
def history():
    db = get_db()
    rows = db.execute("""
        SELECT i.*, b.title AS book_title
        FROM issuances i JOIN books b ON b.id=i.book_id
        ORDER BY i.created_at DESC LIMIT 100
    """).fetchall()
    return ok([dict(r) for r in rows])

# ─── RUN ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print("\n Library Management API running at http://localhost:5000")
    print(" Endpoints:")
    print("   GET    /api/stats")
    print("   GET    /api/books")
    print("   POST   /api/books")
    print("   PUT    /api/books/:id")
    print("   DELETE /api/books/:id")
    print("   GET    /api/issuances")
    print("   POST   /api/issuances")
    print("   POST   /api/issuances/:id/return")
    print("   GET    /api/history\n")
    app.run(debug=True, port=5000)
