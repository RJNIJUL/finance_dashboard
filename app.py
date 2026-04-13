from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# -------------------- DATABASE --------------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

# -------------------- INIT DB --------------------
def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        image TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        amount REAL,
        category TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY,
        budget REAL
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT,
        user_id INTEGER,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    if not conn.execute("SELECT * FROM settings WHERE id=1").fetchone():
        conn.execute("INSERT INTO settings (id, budget) VALUES (1, 0)")

    conn.commit()
    conn.close()

# -------------------- REGISTER --------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if not username or not password or not confirm:
            error = "Fill all fields"
        elif password != confirm:
            error = "Passwords do not match"
        else:
            conn = get_db()
            if conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone():
                error = "Username already exists"
            else:
                hashed = generate_password_hash(password)
                conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
                conn.commit()
                conn.close()
                return redirect('/login')
            conn.close()

    return render_template("register.html", error=error)

# -------------------- LOGIN --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect('/')
        else:
            error = "Invalid credentials"

    return render_template("login.html", error=error)

# -------------------- LOGOUT --------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# -------------------- DASHBOARD --------------------
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session['user_id'],)
    ).fetchone()

    month = request.args.get('month')

    if month:
        data = conn.execute("""
            SELECT * FROM transactions 
            WHERE user_id=? AND strftime('%m', date)=?
        """, (session['user_id'], month)).fetchall()
    else:
        data = conn.execute(
            "SELECT * FROM transactions WHERE user_id=?",
            (session['user_id'],)
        ).fetchall()

    income = sum(r['amount'] for r in data if r['type'] == 'income')
    expense = sum(r['amount'] for r in data if r['type'] == 'expense')
    balance = income - expense

    budget = conn.execute("SELECT budget FROM settings WHERE id=1").fetchone()['budget']
    warning = "⚠️ Budget Exceeded!" if budget and expense > budget else None

    categories = {}
    for r in data:
        if r['type'] == 'expense':
            categories[r['category']] = categories.get(r['category'], 0) + r['amount']

    labels = list(categories.keys())
    values = list(categories.values())

    # Activity
    activity = conn.execute("""
        SELECT * FROM activity 
        WHERE user_id=? 
        ORDER BY date DESC LIMIT 5
    """, (session['user_id'],)).fetchall()

    conn.close()

    return render_template("index.html",
                           data=data,
                           income=income,
                           expense=expense,
                           balance=balance,
                           budget=budget,
                           warning=warning,
                           labels=labels,
                           values=values,
                           activity=activity,
                           user=user)

# -------------------- ADD --------------------
@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        type_ = request.form['type']
        amount = request.form['amount']
        category = request.form['category']

        conn = get_db()
        conn.execute("""
            INSERT INTO transactions (type, amount, category, user_id)
            VALUES (?, ?, ?, ?)
        """, (type_, float(amount), category, session['user_id']))

        conn.execute(
            "INSERT INTO activity (message, user_id) VALUES (?, ?)",
            (f"Added ₹{amount} for {category}", session['user_id'])
        )

        conn.commit()
        conn.close()
        return redirect('/')

    return render_template("add.html")

# -------------------- DELETE --------------------
@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db()

    conn.execute("DELETE FROM transactions WHERE id=? AND user_id=?",
                 (id, session['user_id']))

    conn.execute(
        "INSERT INTO activity (message, user_id) VALUES (?, ?)",
        ("Deleted a transaction", session['user_id'])
    )

    conn.commit()
    conn.close()
    return redirect('/')

# -------------------- EDIT --------------------
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    conn = get_db()

    if request.method == 'POST':
        type_ = request.form['type']
        amount = request.form['amount']
        category = request.form['category']

        conn.execute("""
            UPDATE transactions 
            SET type=?, amount=?, category=? 
            WHERE id=? AND user_id=?
        """, (type_, float(amount), category, id, session['user_id']))

        conn.commit()
        conn.close()
        return redirect('/')

    t = conn.execute(
        "SELECT * FROM transactions WHERE id=? AND user_id=?",
        (id, session['user_id'])
    ).fetchone()

    conn.close()
    return render_template("edit.html", t=t)

# -------------------- PROFILE --------------------
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()

    user = conn.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    data = conn.execute("SELECT * FROM transactions WHERE user_id=?", (session['user_id'],)).fetchall()

    income = sum(r['amount'] for r in data if r['type'] == 'income')
    expense = sum(r['amount'] for r in data if r['type'] == 'expense')
    balance = income - expense

    conn.close()

    return render_template("profile.html",
                           user=user,
                           income=income,
                           expense=expense,
                           balance=balance)

# -------------------- UPLOAD IMAGE --------------------
@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        return redirect('/login')

    file = request.files.get('image')

    if not file or file.filename == '':
        return redirect('/profile')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    conn = get_db()
    conn.execute("UPDATE users SET image=? WHERE id=?", (file.filename, session['user_id']))
    conn.commit()
    conn.close()

    return redirect('/profile')

# -------------------- CHANGE PASSWORD --------------------
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect('/login')

    error = None

    if request.method == 'POST':
        old = request.form['old_password']
        new = request.form['new_password']

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()

        if not check_password_hash(user['password'], old):
            error = "Wrong old password"
        else:
            new_hash = generate_password_hash(new)
            conn.execute("UPDATE users SET password=? WHERE id=?", (new_hash, session['user_id']))
            conn.commit()
            conn.close()
            return redirect('/profile')

    return render_template("change_password.html", error=error)

# -------------------- SET BUDGET --------------------
@app.route('/set_budget', methods=['POST'])
def set_budget():
    budget_input = request.form.get('budget')

    if not budget_input:
        return redirect('/')

    try:
        budget = float(budget_input)
    except:
        return redirect('/')

    conn = get_db()
    conn.execute("UPDATE settings SET budget=? WHERE id=1", (budget,))
    conn.commit()
    conn.close()

    return redirect('/')

# -------------------- MAIN --------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)