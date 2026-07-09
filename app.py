import sqlite3
from datetime import date, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-this-in-production"

DATABASE = "habits.db"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS habit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS habit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                UNIQUE(habit_id, date),
                FOREIGN KEY (habit_id) REFERENCES habit (id) ON DELETE CASCADE
            )
            """
        )
        db.commit()


# ---------- Auth helpers ----------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        db = get_db()
        g.user = db.execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()


# ---------- Auth routes ----------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not password:
            flash("Username and password are required.", "error")
            return redirect(url_for("signup"))
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("signup"))
        if password != confirm:
            flash("Passwords don't match.", "error")
            return redirect(url_for("signup"))

        db = get_db()
        existing = db.execute("SELECT id FROM user WHERE username = ?", (username,)).fetchone()
        if existing:
            flash("That username is already taken.", "error")
            return redirect(url_for("signup"))

        db.execute(
            "INSERT INTO user (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), date.today().isoformat()),
        )
        db.commit()
        flash("Account created! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM user WHERE username = ?", (username,)).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user["id"]
        flash(f"Welcome back, {user['username']}!", "success")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


# ---------- Habit logic ----------

def get_completed_dates(db, habit_id):
    rows = db.execute(
        "SELECT date FROM habit_log WHERE habit_id = ? ORDER BY date", (habit_id,)
    ).fetchall()
    return {r["date"] for r in rows}


def calculate_streaks(completed_dates):
    if not completed_dates:
        return 0, 0

    dates_as_dates = sorted(date.fromisoformat(d) for d in completed_dates)

    longest = 1
    run = 1
    for i in range(1, len(dates_as_dates)):
        if (dates_as_dates[i] - dates_as_dates[i - 1]).days == 1:
            run += 1
        else:
            run = 1
        longest = max(longest, run)

    today = date.today()
    current = 0
    cursor = today
    date_set = set(dates_as_dates)
    if today not in date_set:
        cursor = today - timedelta(days=1)
    while cursor in date_set:
        current += 1
        cursor -= timedelta(days=1)

    return current, longest


def get_owned_habit_or_404(db, habit_id):
    """Fetch a habit only if it belongs to the logged-in user."""
    habit = db.execute(
        "SELECT * FROM habit WHERE id = ? AND user_id = ?", (habit_id, g.user["id"])
    ).fetchone()
    return habit


# ---------- Habit routes (all scoped to the logged-in user) ----------

@app.route("/")
@login_required
def index():
    db = get_db()
    habits = db.execute(
        "SELECT * FROM habit WHERE user_id = ? ORDER BY created_at DESC", (g.user["id"],)
    ).fetchall()
    today_str = date.today().isoformat()

    habit_data = []
    for h in habits:
        completed_dates = get_completed_dates(db, h["id"])
        current, longest = calculate_streaks(completed_dates)
        habit_data.append(
            {
                "id": h["id"],
                "name": h["name"],
                "done_today": today_str in completed_dates,
                "current_streak": current,
                "longest_streak": longest,
                "total_completions": len(completed_dates),
            }
        )

    return render_template("index.html", habits=habit_data, today=today_str)


@app.route("/add", methods=["POST"])
@login_required
def add_habit():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Habit name can't be empty.", "error")
        return redirect(url_for("index"))

    db = get_db()
    db.execute(
        "INSERT INTO habit (user_id, name, created_at) VALUES (?, ?, ?)",
        (g.user["id"], name, date.today().isoformat()),
    )
    db.commit()
    flash(f'Added habit "{name}".', "success")
    return redirect(url_for("index"))


@app.route("/toggle/<int:habit_id>", methods=["POST"])
@login_required
def toggle_today(habit_id):
    db = get_db()
    habit = get_owned_habit_or_404(db, habit_id)
    if habit is None:
        flash("Habit not found.", "error")
        return redirect(url_for("index"))

    today_str = date.today().isoformat()
    existing = db.execute(
        "SELECT id FROM habit_log WHERE habit_id = ? AND date = ?", (habit_id, today_str)
    ).fetchone()

    if existing:
        db.execute("DELETE FROM habit_log WHERE id = ?", (existing["id"],))
    else:
        db.execute(
            "INSERT INTO habit_log (habit_id, date) VALUES (?, ?)", (habit_id, today_str)
        )
    db.commit()
    return redirect(request.referrer or url_for("index"))


@app.route("/delete/<int:habit_id>", methods=["POST"])
@login_required
def delete_habit(habit_id):
    db = get_db()
    habit = get_owned_habit_or_404(db, habit_id)
    if habit is None:
        flash("Habit not found.", "error")
        return redirect(url_for("index"))

    db.execute("DELETE FROM habit_log WHERE habit_id = ?", (habit_id,))
    db.execute("DELETE FROM habit WHERE id = ?", (habit_id,))
    db.commit()
    flash("Habit deleted.", "success")
    return redirect(url_for("index"))


@app.route("/habit/<int:habit_id>")
@login_required
def habit_detail(habit_id):
    db = get_db()
    habit = get_owned_habit_or_404(db, habit_id)
    if habit is None:
        flash("Habit not found.", "error")
        return redirect(url_for("index"))

    completed_dates = get_completed_dates(db, habit_id)
    current, longest = calculate_streaks(completed_dates)

    days = 90
    today = date.today()
    start = today - timedelta(days=days - 1)
    start -= timedelta(days=(start.weekday() + 1) % 7)

    weeks = []
    cursor = start
    current_week = []
    while cursor <= today:
        in_range = cursor >= (today - timedelta(days=days - 1))
        current_week.append(
            {
                "date": cursor.isoformat(),
                "completed": cursor.isoformat() in completed_dates,
                "in_range": in_range,
                "is_future": cursor > today,
            }
        )
        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []
        cursor += timedelta(days=1)
    if current_week:
        weeks.append(current_week)

    return render_template(
        "habit_detail.html",
        habit=habit,
        current_streak=current,
        longest_streak=longest,
        total_completions=len(completed_dates),
        weeks=weeks,
        today=today.isoformat(),
    )


@app.route("/api/habits")
@login_required
def api_habits():
    """JSON API endpoint -- returns only the logged-in user's habits."""
    db = get_db()
    habits = db.execute("SELECT * FROM habit WHERE user_id = ?", (g.user["id"],)).fetchall()
    result = []
    for h in habits:
        completed_dates = get_completed_dates(db, h["id"])
        current, longest = calculate_streaks(completed_dates)
        result.append(
            {
                "id": h["id"],
                "name": h["name"],
                "current_streak": current,
                "longest_streak": longest,
                "total_completions": len(completed_dates),
            }
        )
    return jsonify(result)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
