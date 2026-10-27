from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, json
from functools import wraps
from flask import session, redirect, url_for, flash
from pathlib import Path
from functools import wraps
from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "salon.db"
OLD_JSON = BASE_DIR / "appointments.json"

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "admin123"

SERVICES = [
    ("Hair Cut", 350, "Professional haircut and styling"),
    ("Hair Color", 1200, "Hair coloring service"),
    ("Rebond", 1499, "Smooth and straight hair rebonding"),
    ("Manicure", 299, "Classic manicure and nail care"),
    ("Spa", 799, "Relaxing salon spa treatment"),
]

STAFF = [
    ("Maria Santos","Hair Stylist","09123456789"),
    ("Anna Cruz","Nail Technician","09234567890"),
    ("Jessica Garcia","Hair Colorist","09345678901"),
    ("Sofia Reyes","Beauty Specialist","09456789012"),
    ("Angela Flores","Hair Stylist","09567890123"),
    ("Patricia Ramos","Nail Technician","09678901234"),
    ("Catherine Lopez","Hair Colorist","09789012345"),
    ("Isabella Torres","Beauty Specialist","09890123456"),
    ("Michelle Aquino","Hair Stylist","09901234567"),
    ("Rachel Mendoza","Nail Technician","09012345678"),
]

PROMOS = [
    ("Rebond","₱1,299","Hair rebonding promo"),
    ("Manicure","₱200","Classic manicure promo"),
    ("Spa","₱699","Relaxing spa promo"),
]

def get_db():
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row
    return db


    

def init_db():
    db = get_db()

    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        price REAL NOT NULL,
        description TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        position TEXT NOT NULL,
        contact TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer TEXT NOT NULL,
        contact TEXT,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        service TEXT NOT NULL,
        staff TEXT NOT NULL,
        price REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Booked',
        created TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Add user_email if using an older database
    columns = [
        row[1]
        for row in db.execute(
            "PRAGMA table_info(appointments)"
        ).fetchall()
    ]

    if "user_email" not in columns:
        db.execute(
            "ALTER TABLE appointments ADD COLUMN user_email TEXT"
        )

    # Add default services
    for row in SERVICES:
        db.execute(
            "INSERT OR IGNORE INTO services(name, price, description) VALUES(?,?,?)",
            row
        )

    # Add staff only if the table is empty
    if db.execute("SELECT COUNT(*) FROM staff").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO staff(name, position, contact) VALUES(?,?,?)",
            STAFF
        )

    # Preserve existing appointments.json
    if (
        db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 0
        and OLD_JSON.exists()
    ):
        try:
            data = json.loads(
                OLD_JSON.read_text(encoding="utf-8")
            )
            prices = {x[0]: x[1] for x in SERVICES}

            for x in data if isinstance(data, list) else []:
                if isinstance(x, dict):
                    service = x.get("service", "Hair Cut")

                    db.execute("""
                    INSERT INTO appointments
                    (customer, contact, date, time, service, staff, price, status, user_email)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                     customer,
                     contact,
                     date,
                     time,
                     service,
                     staff,
                     price,
                     status,
                      session.get("user_email") if session.get("role") == "user" else None
                     ))

        except Exception as e:
            print("Appointments JSON import skipped:", e)

    db.commit()
    db.close()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper
def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))

        if session.get("role") != "admin":
            flash("Admin access only.", "error")
            return redirect(url_for("dashboard"))

        return fn(*args, **kwargs)

    return wrapper

@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # ADMIN LOGIN
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session.clear()
            session["logged_in"] = True
            session["role"] = "admin"
            session["user_name"] = "Admin"
            session["user_email"] = email

            return redirect(url_for("dashboard"))

        # REGISTERED USER LOGIN
        db = get_db()

        try:
            user = db.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()
        finally:
            db.close()

        if user and check_password_hash(
            user["password_hash"], password
        ):
            session.clear()
            session["logged_in"] = True
            session["role"] = "user"
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]

            return redirect(url_for("dashboard"))

        flash("Incorrect email or password.", "error")

    return render_template("login.html")

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.get("/dashboard")
@login_required
def dashboard():
    db = get_db()

    try:
        services = db.execute(
            "SELECT * FROM services ORDER BY id"
        ).fetchall()

        # USER DASHBOARD
        if session.get("role") == "user":
            appointments = db.execute(
                """
                SELECT * FROM appointments
                WHERE user_email = ?
                ORDER BY id DESC
                LIMIT 10
                """,
                (session.get("user_email"),)
            ).fetchall()

            return render_template(
                "user_dashboard.html",
                services=services,
                appointments=appointments,
                promos=PROMOS
            )

        # ADMIN DASHBOARD
        counts = {
            "appointments": db.execute(
                "SELECT COUNT(*) FROM appointments"
            ).fetchone()[0],
            "staff": db.execute(
                "SELECT COUNT(*) FROM staff"
            ).fetchone()[0],
            "services": db.execute(
                "SELECT COUNT(*) FROM services"
            ).fetchone()[0]
        }

        recent = db.execute(
            "SELECT * FROM appointments ORDER BY id DESC LIMIT 5"
        ).fetchall()

        return render_template(
            "dashboard.html",
            counts=counts,
            recent=recent,
            services=services,
            promos=PROMOS
        )

    finally:
        db.close()

@app.route("/appointments", methods=["GET", "POST"])
@login_required
def appointments():
    db = get_db()

    try:
        if request.method == "POST":
            customer = request.form.get("customer", "").strip()
            contact = request.form.get("contact", "").strip()
            date_value = request.form.get("date", "").strip()
            time_value = request.form.get("time", "").strip()
            service_name = request.form.get("service", "").strip()
            staff_name = request.form.get("staff", "").strip()

            # Para sa User, gamitin ang pangalan mula sa account
            if session.get("role") == "user":
                customer = session.get("user_name", "")

            if not all([
                customer, date_value, time_value,
                service_name, staff_name
            ]):
                flash("Please complete all required fields.", "error")
            else:
                try:
                    booking_date = date.fromisoformat(date_value)
                    datetime.strptime(time_value, "%H:%M")
                    valid_datetime = True
                except ValueError:
                    valid_datetime = False

                if not valid_datetime:
                    flash("Invalid date or time.", "error")
                elif booking_date < date.today():
                    flash("Please choose today or a future date.", "error")
                else:
                    service = db.execute(
                        "SELECT name, price FROM services WHERE name = ?",
                        (service_name,)
                    ).fetchone()

                    staff_member = db.execute(
                        "SELECT name FROM staff WHERE name = ?",
                        (staff_name,)
                    ).fetchone()

                    if not service or not staff_member:
                        flash(
                            "Please select a valid service and staff member.",
                            "error"
                        )
                    else:
                        conflict = db.execute("""
                            SELECT id FROM appointments
                            WHERE date = ? AND time = ? AND staff = ?
                            AND status NOT IN ('Cancelled', 'Completed')
                        """, (
                            date_value, time_value, staff_name
                        )).fetchone()

                        if conflict:
                            flash(
                                "This staff member already has an appointment at that time.",
                                "error"
                            )
                        else:
                            db.execute("""
                                INSERT INTO appointments
                                (
                                    customer, contact, date, time,
                                    service, staff, price, status,
                                    user_email
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, 'Booked', ?)
                            """, (
                                customer,
                                contact,
                                date_value,
                                time_value,
                                service["name"],
                                staff_member["name"],
                                service["price"],
                                (
                                    session.get("user_email")
                                    if session.get("role") == "user"
                                    else None
                                )
                            ))

                            db.commit()
                            flash(
                                "Appointment saved successfully.",
                                "success"
                            )
                            return redirect(url_for("appointments"))

        services = db.execute(
            "SELECT * FROM services ORDER BY id"
        ).fetchall()

        staff = db.execute(
            "SELECT * FROM staff ORDER BY id"
        ).fetchall()

        # Admin sees all appointments; User sees only their own
        if session.get("role") == "admin":
            rows = db.execute(
                "SELECT * FROM appointments ORDER BY id DESC"
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT * FROM appointments
                WHERE user_email = ?
                ORDER BY id DESC
                """,
                (session.get("user_email"),)
            ).fetchall()

        return render_template(
            "appointments.html",
            appointments=rows,
            services=services,
            staff=staff
        )

    finally:
        db.close()
@app.get("/staff")
@login_required
@admin_required
def staff_page():
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM staff ORDER BY id"
        ).fetchall()

        return render_template("staff.html", staff=rows)
    finally:
        db.close()
@app.get("/services")
@login_required
def services_page():
    db=get_db(); rows=db.execute("SELECT * FROM services ORDER BY id").fetchall(); db.close()
    return render_template("services.html", services=rows, promos=PROMOS)

@app.get("/history")
@login_required
@admin_required
def history():
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM appointments ORDER BY id DESC"
        ).fetchall()

        return render_template(
            "history.html",
            appointments=rows
        )
    finally:
        db.close()

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("Please complete all required fields.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            db = get_db()
            try:
                db.execute(
                    """INSERT INTO users (name, email, password_hash)
                       VALUES (?, ?, ?)""",
                    (name, email, generate_password_hash(password))
                )
                db.commit()
                flash("Account created! You can now log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Email is already registered.", "error")
            finally:
                db.close()

    return render_template("signup.html")

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)