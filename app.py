from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, Blueprint
import cv2
import os
import numpy as np
import base64
import MySQLdb
import MySQLdb.cursors
from functools import wraps
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import yagmail
from io import BytesIO
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from email.message import EmailMessage
import smtplib
import io
from apscheduler.schedulers.background import BackgroundScheduler

from urllib.parse import urlparse


app = Flask(__name__)

# ==============================
# SECURE EMAIL (WITH FALLBACK)
# ==============================
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_PASS")

# ==============================
# SECRET KEY
# ==============================
app.secret_key = os.getenv("SECRET_KEY") 

# ==============================
# MYSQL CONNECTION (RENDER / RAILWAY READY)
# ==============================
import os
import MySQLdb
from urllib.parse import urlparse

def get_db_connection():
    database_url = os.getenv("DATABASE_URL")

    # =========================
    # LOCAL (XAMPP fallback)
    # =========================
    if not database_url:
        return MySQLdb.connect(
            host="localhost",
            user="root",
            passwd="",
            db="appliance_loan_db",
            charset="utf8mb4"
        )

    # =========================
    # CLOUD (Render/Railway)
    # =========================
    url = urlparse(database_url)

    return MySQLdb.connect(
        host=url.hostname,
        user=url.username,
        passwd=url.password,
        db=url.path.lstrip("/"),
        port=url.port or 3306,
        charset="utf8mb4"
    )

# ==============================
# TEST ROUTE (FIXED)
# ==============================
@app.route("/test-db")
def test_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT DATABASE()")
    db = cur.fetchone()
    cur.close()
    conn.close()
    return {"database": db}




@app.route("/admin/appliances")
def admin_appliances():

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # ================= FILTERS =================
    category = request.args.get("category", "")
    appliance_name = request.args.get("appliance_name", "")

    query = """
        SELECT 
            a.*,

            IFNULL((
                SELECT SUM(quantity) 
                FROM stock_movements 
                WHERE appliance_id = a.id AND movement_type = 'stock_in'
            ), 0) AS items_added,

            IFNULL((
                SELECT SUM(quantity) 
                FROM stock_movements 
                WHERE appliance_id = a.id AND movement_type = 'stock_out'
            ), 0) AS items_sold

        FROM appliances a
        WHERE 1=1
    """

    params = []

    # ================= CATEGORY FILTER =================
    if category:
        query += " AND a.category LIKE %s"
        params.append(f"%{category}%")

    # ================= APPLIANCE FILTER =================
    if appliance_name:
        query += " AND a.appliance_name LIKE %s"
        params.append(f"%{appliance_name}%")

    query += " ORDER BY a.appliance_name"

    cur.execute(query, params)
    appliances = cur.fetchall()

    # ================= GET CATEGORY LIST =================
    cur.execute("SELECT DISTINCT category FROM appliances ORDER BY category")
    categories = cur.fetchall()

    # ================= GET APPLIANCE LIST =================
    appliance_query = "SELECT DISTINCT appliance_name FROM appliances WHERE 1=1"
    appliance_params = []

    if category:
        appliance_query += " AND category LIKE %s"
        appliance_params.append(f"%{category}%")

    appliance_query += " ORDER BY appliance_name"

    cur.execute(appliance_query, appliance_params)
    appliance_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "admin_appliances.html",
        appliances=appliances,
        categories=categories,
        appliance_list=appliance_list,
        selected_category=category,
        selected_appliance=appliance_name
    )

    
@app.route("/")
@app.route("/index1")
def index1():
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT * FROM appliances")
    appliances = cur.fetchall()

    cur.close()
    conn.close()

    cart = session.get("cart", {})
    cart_count = sum(cart.values())  # total quantity

    return render_template(
        "index1.html",
        appliance=appliances,
        cart_count=cart_count
    )

@app.route("/admin/edit_customer/<int:user_id>", methods=["GET", "POST"])
def edit_customer(user_id):
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        contact_number = request.form["contact_number"]
        address = request.form["address"]

        cur.execute("""
            UPDATE users
            SET full_name=%s, email=%s, contact_number=%s, address=%s
            WHERE id=%s
        """, (name, email, contact_number, address, user_id))

        conn.commit()
        cur.close()
        conn.close()

        flash("Customer updated successfully!", "success")
        return redirect(url_for("admin_customers"))

    cur.execute("""
        SELECT id, full_name, email, contact_number, address
        FROM users
        WHERE id=%s
    """, (user_id,))

    customer = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("edit_customer.html", customer=customer)

    
@app.route("/admin/delete_customer/<int:user_id>")
def delete_customer(user_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()

    cur.close()
    conn.close()

    flash("Customer deleted successfully!", "success")
    return redirect(url_for("admin_customers"))


@app.route("/admin/customers")
def admin_customers():
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT id, full_name, email, contact_number, address FROM users ORDER BY full_name ASC")
    customers = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin_customers.html", customers=customers)


@app.route("/admin/add_customer", methods=["POST"])
def add_customer():
    name = request.form["name"]
    email = request.form["email"]
    contact_number = request.form["contact_number"]
    address = request.form["address"]
    password = request.form["password"]

    hashed_password = generate_password_hash(password)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (full_name, email, contact_number, address, password, role)
        VALUES (%s, %s, %s, %s, %s, 'customer')
    """, (name, email, contact_number, address, hashed_password))

    conn.commit()

    cur.close()
    conn.close()

    flash("Customer added successfully!", "success")
    return redirect(url_for("admin_customers"))

#BLOCK CUSTOMERS 
# ---------------- Block User ----------------
@app.route("/admin/block/<int:user_id>")
def block_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET status='blocked' WHERE id=%s", (user_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return redirect("/admin/customers")


# ---------------- Unblock User ----------------
@app.route("/admin/unblock/<int:user_id>")
def unblock_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET status='active' WHERE id=%s", (user_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return redirect("/admin/customers")


# ---------------- Admin Dashboard ----------------
@app.route("/admin")
def admin_dashboard():
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # Appliances
    cur.execute("SELECT * FROM appliances")
    appliances = cur.fetchall()

    # Customers
    cur.execute("SELECT * FROM users")
    customers = cur.fetchall()

    # Loans
    cur.execute("SELECT * FROM loans")
    loans = cur.fetchall()

    # Payments
    cur.execute("SELECT * FROM payments")
    payments = cur.fetchall()

    # Orders
    cur.execute("SELECT * FROM orders")
    orders = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "admin.html",
        appliances=appliances,
        customers=customers,
        loans=loans,
        payments=payments,
        order=orders
    )


# ---------------- Upload Config ----------------
UPLOAD_FOLDER = "static/uploads/appliances"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/admin/add_appliance", methods=["GET", "POST"])
def admin_add_appliance():
    if request.method == "POST":
        name = request.form["appliance_name"]
        category = request.form["category"]
        price = request.form["price"]
        stock = int(request.form["stock"])
        image = request.files["image"]

        image_path_db = None

        # ---------------- SAVE IMAGE ----------------
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(image_path)

            image_path_db = f"uploads/appliances/{filename}"

        # ---------------- DB CONNECTION ----------------
        conn = get_db_connection()
        cur = conn.cursor()

        # 1️⃣ Insert appliance
        cur.execute("""
            INSERT INTO appliances (appliance_name, category, price, stock, image)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, category, price, stock, image_path_db))

        appliance_id = cur.lastrowid

        # 2️⃣ Insert stock movement
        cur.execute("""
            INSERT INTO stock_movements (appliance_id, movement_type, quantity, reference_note)
            VALUES (%s, %s, %s, %s)
        """, (appliance_id, 'stock_in', stock, 'Initial stock added'))

        conn.commit()
        cur.close()
        conn.close()

        flash("Appliance added successfully with stock recorded.", "success")
        return redirect(url_for("admin_appliances"))

    return render_template("admin_appliances.html")





# ---------------- DELETE APPLIANCE ----------------
@app.route("/admin/appliances/delete/<int:appliance_id>")
def delete_appliance(appliance_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM appliances WHERE id = %s", (appliance_id,))

    conn.commit()
    cur.close()
    conn.close()

    flash("Appliance deleted successfully!", "success")
    return redirect(url_for("admin_appliances"))


# ---------------- LOGIN REQUIRED ----------------
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrap


# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        contact_number = request.form.get("contact_number")
        address = request.form.get("address")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Validation
        if not full_name or not email or not password or not confirm_password or not contact_number or not address:
            return "All fields are required"

        if password != confirm_password:
            return "Passwords do not match"

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO users (full_name, email, contact_number, address, password)
                VALUES (%s, %s, %s, %s, %s)
            """, (full_name, email, contact_number, address, hashed_password))

            conn.commit()
            cur.close()
            conn.close()

            return redirect(url_for("login"))

        except Exception as e:
            return f"Signup error: {e}"

    return render_template("signup.html")

from werkzeug.security import generate_password_hash

hashed = generate_password_hash("admin123")
print(hashed)




from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db_connection()
        cur = conn.cursor(MySQLdb.cursors.DictCursor)

        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()

        cur.close()
        conn.close()

        if user is None:
            flash("Email not found", "danger")
            return render_template("login.html")

        db_password = user["password"]

        if check_password_hash(db_password, password):
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            elif user["role"] == "customer":
                return redirect(url_for("customer_dashboard"))
            else:
                flash("Your account role is not recognized.", "warning")
                return redirect(url_for("login"))
        else:
            flash("Incorrect password", "danger")
            return render_template("login.html")

    return render_template("login.html")


# ---------------- SESSION CHECK ----------------
@app.route('/check-session')
def check_session():
    return str(session.get('user_id'))


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index1"))


# ---------------- HOME ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FACE_CASCADE = cv2.CascadeClassifier(os.path.join(BASE_DIR, "haarcascades", "haarcascade_frontalface_default.xml"))
EYE_CASCADE = cv2.CascadeClassifier(os.path.join(BASE_DIR, "haarcascades", "haarcascade_eye.xml"))

UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

blink_detected = False


@app.route("/")
def home():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM appliances")
    appliances = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("index1.html", appliance=appliances)

# -------- Upload ID (no redirect) --------
@app.route("/train", methods=["POST"])
def train():
    file = request.files.get("id_photo")

    if not file or file.filename == "":
        return jsonify({"success": False, "message": "No ID uploaded."})

    try:
        id_path = os.path.join(UPLOADS_DIR, "id.jpg")
        file.save(id_path)

        return jsonify({"success": True, "message": "ID uploaded successfully."})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


# -------- Blink check --------
@app.route("/blink_check", methods=["POST"])
def blink_check():
    global blink_detected

    try:
        data = request.json["image"].split(",")[1]
        img_bytes = base64.b64decode(data)

        np_img = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = FACE_CASCADE.detectMultiScale(gray, 1.3, 5)

        blink_detected = False

        for (x, y, w, h) in faces:
            face_roi = gray[y:y+h, x:x+w]
            eyes = EYE_CASCADE.detectMultiScale(face_roi, 1.3, 5)

            if len(eyes) == 0:
                blink_detected = True
                break

        return jsonify({"blinked": blink_detected})

    except Exception as e:
        return jsonify({"blinked": False, "error": str(e)})


# -------- Verify selfie vs ID --------
UPLOADS_DIR = "static/uploads"


@app.route("/verify", methods=["POST"])
def verify():
    global blink_detected

    if not blink_detected:
        return jsonify({"success": False, "message": "Blink not detected yet."})

    try:
        # ---------------- SELFIE ----------------
        image_data = request.form.get("image_data").split(",")[1]
        img_bytes = base64.b64decode(image_data)

        np_img = np.frombuffer(img_bytes, np.uint8)
        selfie = cv2.imdecode(np_img, cv2.IMREAD_GRAYSCALE)

        # ---------------- ID IMAGE ----------------
        id_path_temp = os.path.join(UPLOADS_DIR, "id.jpg")

        if not os.path.exists(id_path_temp):
            return jsonify({"success": False, "message": "ID not uploaded."})

        id_img = cv2.imread(id_path_temp, cv2.IMREAD_GRAYSCALE)

        id_img = cv2.resize(id_img, (selfie.shape[1], selfie.shape[0]))

        # ---------------- FACE MATCH ----------------
        diff = cv2.absdiff(selfie, id_img)
        score = np.sum(diff)

        max_diff = selfie.shape[0] * selfie.shape[1] * 255
        similarity = 100 - (score / max_diff * 100)

        # ---------------- SUCCESS ----------------
        if similarity >= 70:
            loan = session.get("loan_data")

            if loan is None:
                return jsonify({"success": False, "message": "Loan data missing. Please apply again."})

            conn = get_db_connection()
            cur = conn.cursor()

            # 1️⃣ INSERT LOAN
            cur.execute("""
                INSERT INTO loans 
                (user_id, appliance_id, appliance_name, category, full_name, email, mobile, occupation, salary, months, amount, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session["user_id"],
                loan["appliance_id"],
                loan["appliance_name"],
                loan["category"],
                loan["full_name"],
                loan["email"],
                loan["mobile"],
                loan["occupation"],
                loan["salary"],
                loan["months"],
                loan["amount"],
                "pending"
            ))

            conn.commit()
            loan_id = cur.lastrowid

            # 2️⃣ SAVE IMAGES
            id_path = os.path.join(
                "static", "uploads",
                f"id_{session['user_id']}_{loan['appliance_id']}.jpg"
            ).replace("\\", "/")

            selfie_path = os.path.join(
                "static", "uploads",
                f"selfie_{session['user_id']}_{loan['appliance_id']}.jpg"
            ).replace("\\", "/")

            os.rename(id_path_temp, id_path)
            cv2.imwrite(selfie_path, selfie)

            # 3️⃣ UPDATE LOAN PATHS
            cur.execute("""
                UPDATE loans
                SET id_photo_path=%s, selfie_path=%s
                WHERE id=%s
            """, (id_path, selfie_path, loan_id))

            conn.commit()

            # 4️⃣ ADMIN NOTIFICATION
            message = f"{loan['full_name']} applied for a loan on {loan['appliance_name']}"

            cur.execute("""
                INSERT INTO admin_notifications
                (user_id, payment_id, message, is_read, created_at, link, loan_id)
                VALUES (%s,%s,%s,%s,NOW(),%s,%s)
            """, (
                42,
                None,
                message,
                0,
                f"/admin/loan/{loan_id}",
                loan_id
            ))

            conn.commit()
            cur.close()
            conn.close()

            session.pop("loan_data", None)

            return jsonify({
                "success": True,
                "message": "✅ Face matched! Loan submitted successfully."
            })

        else:
            return jsonify({
                "success": False,
                "message": f"❌ Face mismatch! Similarity: {similarity:.1f}%"
            })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


# ---------------- LOAN DETAILS ----------------
@app.route("/admin/loan_details/<int:loan_id>")
def loan_details(loan_id):
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT *, id_photo_path, selfie_path
        FROM loans
        WHERE id=%s
    """, (loan_id,))

    loan = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("admin_loan_details.html", loan=loan)



def auto_send_reminders():
    print("🔔 Auto reminder check running...")

    try:
        with app.app_context():

            conn = get_db_connection()
            cur = conn.cursor(MySQLdb.cursors.DictCursor)

            # ---------------- GET PAYMENTS ----------------
            cur.execute("""
                SELECT 
                    p.id AS payment_id,
                    p.amount_due,
                    p.due_date,
                    u.full_name,
                    u.email,
                    a.appliance_name
                FROM payments p
                JOIN loans l ON p.loan_id = l.id
                JOIN users u ON l.user_id = u.id
                JOIN appliances a ON l.appliance_id = a.id
                WHERE p.status = 'not_paid'
                AND DATEDIFF(p.due_date, NOW()) BETWEEN 0 AND 7
                AND (
                    p.reminder_sent_date IS NULL
                    OR DATE(p.reminder_sent_date) < CURDATE()
                )
            """)

            payments = cur.fetchall()

            if not payments:
                print("No reminders needed today.")
                cur.close()
                conn.close()
                return

            # ---------------- EMAIL SETUP ----------------
            yag = yagmail.SMTP(user=EMAIL_USER, password=EMAIL_APP_PASSWORD)

            for p in payments:

                # Safe date handling
                due_date = p['due_date']
                if isinstance(due_date, str):
                    due_date = datetime.strptime(due_date, "%Y-%m-%d")

                days_left = (due_date - datetime.now()).days
                long_due_date = due_date.strftime("%B %d, %Y")

                subject = f"Reminder: {days_left} day(s) before due date"

                body = f"""
Hello {p['full_name']},

This is a reminder that your payment for
"{p['appliance_name']}" is due on {long_due_date}.

Days remaining: {days_left}
Amount Due: ₱{p['amount_due']:.2f}

Please settle your payment before the due date.

Thank you,
Greater RJ Appliance and Trading Corporation
                """

                # Send email
                yag.send(
                    to=p['email'],
                    subject=subject,
                    contents=body,
                    headers={"From": f"Greater RJ Appliance and Trading Corporation <{EMAIL_USER}>"}
                )

                # ---------------- UPDATE REMINDER ----------------
                cur.execute("""
                    UPDATE payments
                    SET reminder_sent_date = NOW()
                    WHERE id = %s
                """, (p['payment_id'],))

                conn.commit()

            cur.close()
            conn.close()

            print(f"Sent {len(payments)} reminder(s).")

    except Exception as e:
        print("Reminder Error:", e)
@app.route("/admin/payments")
def admin_payments():
    loan_id = request.args.get('loan_id', type=int)

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # ---------------- IF VIEWING SPECIFIC LOAN ----------------
    if loan_id:
        cur.execute("""
            SELECT 
                p.*, l.appliance_id, a.appliance_name,
                u.id as user_id, u.full_name
            FROM payments p
            JOIN loans l ON p.loan_id = l.id
            JOIN users u ON l.user_id = u.id
            JOIN appliances a ON l.appliance_id = a.id
            WHERE l.id = %s
            ORDER BY p.month_no ASC
        """, (loan_id,))

        payments = cur.fetchall()

        cur.close()
        conn.close()

        return render_template("payments.html", loans=[{
            'appliance_name': payments[0]['appliance_name'] if payments else '',
            'status': 'ongoing',
            'amount': 0,
            'paid_amount_sum': 0,
            'balance': 0,
            'payments': payments or []
        }])

    # ---------------- ELSE: SHOW ALL CUSTOMERS ----------------
    cur.execute("""
        SELECT 
            u.id, 
            u.full_name, 
            u.email,
            CASE 
                WHEN EXISTS (
                    SELECT 1 FROM loans l
                    JOIN payments p ON l.id = p.loan_id
                    WHERE l.user_id = u.id
                ) THEN 1
                ELSE 0
            END AS has_payments
        FROM users u
        ORDER BY u.full_name ASC
    """)

    customers = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin_payments.html", customers=customers)






@app.route("/admin/payments/<int:user_id>/view")
def view_customer_payments(user_id):
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # Get customer info
    cur.execute("""
        SELECT id, full_name, email
        FROM users
        WHERE id = %s
    """, (user_id,))
    customer = cur.fetchone()

    # Get payments
    cur.execute("""
        SELECT 
            p.id,
            p.loan_id,
            p.amount_due,
            p.paid_amount,
            p.arrears,
            p.status,
            p.due_date,
            p.payment_proof,
            a.appliance_name
        FROM payments p
        JOIN loans l ON p.loan_id = l.id
        JOIN appliances a ON l.appliance_id = a.id
        WHERE l.user_id = %s
        ORDER BY a.appliance_name ASC, p.month_no ASC
    """, (user_id,))

    payments = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "admin_customer_payments.html",
        customer=customer,
        payments=payments
    )


@app.route("/mark_payment_paid/<int:payment_id>", methods=["POST"])
def mark_payment_paid(payment_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(MySQLdb.cursors.DictCursor)

        # ---------------- FETCH PAYMENT ----------------
        cur.execute("""
            SELECT p.*, u.full_name, u.email, a.appliance_name
            FROM payments p
            JOIN loans l ON p.loan_id = l.id
            JOIN users u ON l.user_id = u.id
            JOIN appliances a ON l.appliance_id = a.id
            WHERE p.id = %s
        """, (payment_id,))

        payment = cur.fetchone()

        if not payment:
            cur.close()
            conn.close()
            flash("Payment not found ❌", "danger")
            return redirect(request.referrer)

        # ---------------- UPDATE PAYMENT ----------------
        cur.execute("""
            UPDATE payments 
            SET status = 'paid', paid_at = NOW()
            WHERE id = %s
        """, (payment_id,))

        conn.commit()

        # ---------------- CREATE PDF ----------------
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=(300, 350))

        c.setFont("Helvetica-Bold", 12)
        c.drawString(20, 220, "Greater RJ Appliance and Trading Corporation")

        c.setFont("Helvetica", 10)
        c.drawString(20, 200, f"Customer: {payment['full_name']}")
        c.drawString(20, 185, f"Appliance: {payment['appliance_name']}")
        c.drawString(20, 170, f"Amount Paid: ₱{payment['amount_due']:.2f}")
        c.drawString(20, 155, f"Payment Date: {datetime.now().strftime('%B %d, %Y')}")
        c.drawString(20, 140, f"Receipt #: {payment_id}")
        c.drawString(20, 120, "Thank you for your payment!")

        c.save()
        pdf_buffer.seek(0)

        # ---------------- EMAIL ----------------
        yag = yagmail.SMTP(EMAIL_USER, EMAIL_APP_PASSWORD)

        subject = f"Payment Receipt – {payment['appliance_name']}"

        body = f"""
Hello {payment['full_name']},

Your payment of ₱{payment['amount_due']:.2f} has been received.

Attached is your official receipt.

Thank you,
Greater RJ Appliance and Trading Corporation
        """

        yag.send(
            to=payment['email'],
            subject=subject,
            contents=body,
            attachments=[pdf_buffer]
        )

        cur.close()
        conn.close()

        flash(f"Payment marked as paid ✅ and receipt sent to {payment['full_name']}.", "success")
        return redirect(request.referrer)

    except Exception as e:
        flash(f"Error marking payment as paid ❌: {str(e)}", "danger")
        return redirect(request.referrer)




from datetime import date

@app.route("/admin/loans")
def admin_loans():
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    try:
        # =========================
        # 1. Auto-update overdue payments
        # =========================
        cur.execute("""
            UPDATE payments
            SET status = 'overdue'
            WHERE status = 'pending'
            AND due_date < %s
        """, (date.today(),))

        conn.commit()

        # =========================
        # 2. Get overdue payments
        # =========================
        cur.execute("""
            SELECT p.id, l.user_id, p.amount_due, p.due_date
            FROM payments p
            JOIN loans l ON p.loan_id = l.id
            WHERE p.status = 'overdue' AND p.notified = 0
        """)
        overdues = cur.fetchall()

        # =========================
        # 3. Insert notifications
        # =========================
        for o in overdues:
            msg = f"Your payment of ₱{float(o['amount_due'] or 0):.2f} due on {o['due_date']} is OVERDUE."

            cur.execute("""
                INSERT INTO notifications (user_id, message)
                VALUES (%s, %s)
            """, (o['user_id'], msg))

            cur.execute("""
                UPDATE payments
                SET notified = 1
                WHERE id = %s
            """, (o['id'],))

        conn.commit()

        # =========================
        # 4. FILTER LOGIC
        # =========================
        status_filter = request.args.get("status")

        base_query = """
            SELECT loans.id, loans.status, loans.amount, loans.months, 
                   users.full_name, appliances.appliance_name
            FROM loans
            JOIN users ON loans.user_id = users.id
            JOIN appliances ON loans.appliance_id = appliances.id
        """

        params = []

        if status_filter:
            base_query += " WHERE loans.status = %s"
            params.append(status_filter)

        base_query += " ORDER BY loans.id DESC"

        cur.execute(base_query, params)
        loans = cur.fetchall()

        return render_template("admin_loans.html", loans=loans)

    finally:
        cur.close()
        conn.close()


@app.route("/customer_loans")
def customer_loans():
    if "user_id" not in session:
        flash("Please log in first", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # =========================
    # Get all loans for this user
    # =========================
    cur.execute("""
        SELECT loans.id, a.appliance_name, loans.amount, loans.months, loans.status
        FROM loans 
        JOIN appliances a ON loans.appliance_id = a.id
        WHERE loans.user_id = %s
        ORDER BY loans.id DESC
    """, (user_id,))

    loans = cur.fetchall()

    # =========================
    # Get payment schedule per loan
    # =========================
    for loan in loans:
        cur.execute("""
            SELECT month_no, amount_due, due_date, status
            FROM payments
            WHERE loan_id = %s
            ORDER BY month_no
        """, (loan['id'],))

        loan['payments'] = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("customer_loans.html", loans=loans)



from flask import flash

@app.route("/add_to_cart/<int:appliance_id>", methods=["POST"])
def add_to_cart(appliance_id):

    print("ADD TO CART TRIGGERED")

    if "user_id" not in session:
        flash("Please log in first", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT * FROM cart
        WHERE user_id = %s AND appliance_id = %s
    """, (user_id, appliance_id))

    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE cart
            SET quantity = quantity + 1
            WHERE user_id = %s AND appliance_id = %s
        """, (user_id, appliance_id))
    else:
        cur.execute("""
            INSERT INTO cart (user_id, appliance_id, quantity, date_added)
            VALUES (%s, %s, 1, NOW())
        """, (user_id, appliance_id))

    conn.commit()
    cur.close()
    conn.close()

    flash("Added to cart 🛒", "success")
    return redirect(url_for("index1"))



@app.route("/cart")
def cart():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT c.appliance_id, c.quantity,
               a.appliance_name, a.price, a.image
        FROM cart c
        JOIN appliances a ON c.appliance_id = a.id
        WHERE c.user_id = %s
    """, (user_id,))

    items = cur.fetchall()

    cur.close()
    conn.close()

    cart_items = []
    total = 0

    for item in items:
        subtotal = float(item["price"]) * int(item["quantity"])
        total += subtotal

        cart_items.append({
            "appliance_id": item["appliance_id"],
            "appliance_name": item["appliance_name"],
            "price": float(item["price"]),
            "quantity": int(item["quantity"]),
            "subtotal": subtotal,
            "image": item["image"]
        })

    return render_template(
        "cart_modal.html",
        cart_items=cart_items,
        total=total
    )
def cart():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT c.appliance_id, c.quantity,
               a.appliance_name, a.price, a.image
        FROM cart c
        JOIN appliances a ON c.appliance_id = a.id
        WHERE c.user_id = %s
    """, (user_id,))

    items = cur.fetchall()

    cur.close()
    conn.close()

    cart_items = []
    total = 0

    for item in items:
        subtotal = float(item["price"]) * int(item["quantity"])
        total += subtotal

        cart_items.append({
            "appliance_id": item["appliance_id"],
            "appliance_name": item["appliance_name"],
            "price": float(item["price"]),
            "quantity": int(item["quantity"]),
            "subtotal": subtotal,
            "image": item["image"]
        })

    return render_template("cart_modal.html",
                           cart_items=cart_items,
                           total=total)





@app.route("/update_cart/<int:appliance_id>", methods=["POST"])
def update_cart(appliance_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    action = request.form.get("action")
    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    if action == "increase":
        cur.execute("""
            UPDATE cart
            SET quantity = quantity + 1
            WHERE user_id = %s AND appliance_id = %s
        """, (user_id, appliance_id))

    elif action == "decrease":
        cur.execute("""
            UPDATE cart
            SET quantity = quantity - 1
            WHERE user_id = %s AND appliance_id = %s
        """, (user_id, appliance_id))

        cur.execute("""
            DELETE FROM cart
            WHERE user_id = %s AND appliance_id = %s AND quantity <= 0
        """, (user_id, appliance_id))

    elif action == "remove":
        cur.execute("""
            DELETE FROM cart
            WHERE user_id = %s AND appliance_id = %s
        """, (user_id, appliance_id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("cart"))

@app.route("/checkout", methods=["POST"])
def checkout():

    if "user_id" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # ---------------- 1. GET CART FROM DB ----------------
    cur.execute("""
        SELECT c.appliance_id, c.quantity,
               a.appliance_name, a.price
        FROM cart c
        JOIN appliances a ON c.appliance_id = a.id
        WHERE c.user_id = %s
    """, (user_id,))

    cart_items = cur.fetchall()

    if not cart_items:
        flash("Your cart is empty", "warning")
        cur.close()
        conn.close()
        return redirect(url_for("index1"))

    # ---------------- 2. COMPUTE TOTAL ----------------
    total_amount = 0

    for item in cart_items:
        total_amount += float(item["price"]) * int(item["quantity"])

    # ---------------- 3. INSERT ORDER ----------------
    cur.execute("""
        INSERT INTO orders (user_id, full_name, email, total_amount, status)
        VALUES (%s, %s, %s, %s, 'pending')
    """, (
        user_id,
        session.get("user_name"),
        session.get("email"),
        total_amount
    ))

    order_id = cur.lastrowid

    # ---------------- 4. INSERT ORDER ITEMS ----------------
    for item in cart_items:
        cur.execute("""
            INSERT INTO order_items
            (order_id, appliance_id, appliance_name, price, quantity)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            order_id,
            item["appliance_id"],
            item["appliance_name"],
            item["price"],
            item["quantity"]
        ))

        # Reduce stock safely
        cur.execute("""
            UPDATE appliances
            SET stock = stock - %s
            WHERE id = %s
        """, (item["quantity"], item["appliance_id"]))

    conn.commit()

    # ---------------- 5. CLEAR CART ----------------
    cur.execute("DELETE FROM cart WHERE user_id = %s", (user_id,))
    conn.commit()

    cur.close()
    conn.close()

    flash("✅ Order placed successfully!", "success")
    return redirect(url_for("index1"))




# ==============================
# ADMIN ORDERS
# ==============================
@app.route("/admin/orders")
def admin_orders():

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # Fetch all orders with customer info
    cur.execute("""
        SELECT o.*, u.full_name AS customer_name, u.email AS customer_email
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.created_at DESC
    """)

    orders = cur.fetchall()

    # Fetch items per order
    for order in orders:

        order_id = order.get("id")  # FIXED: safe key

        cur.execute("""
            SELECT 
                a.appliance_name,
                a.category,
                oi.price,
                oi.quantity
            FROM order_items oi
            JOIN appliances a ON oi.appliance_id = a.id
            WHERE oi.order_id = %s
        """, (order_id,))

        items = cur.fetchall()

        total = 0
        for item in items:
            item["subtotal"] = float(item["price"]) * int(item["quantity"])
            total += item["subtotal"]

        order["items"] = items
        order["total_amount"] = total

    cur.close()
    conn.close()

    return render_template("admin_orders.html", orders=orders)


# ==============================
# ADMIN DASHBOARD
# ==============================
@app.route("/dashboard")
def dashboard():

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT COUNT(*) AS total_customers FROM users")
    total_customers = cur.fetchone()["total_customers"]

    cur.execute("SELECT COUNT(*) AS total_loans FROM loans")
    total_loans = cur.fetchone()["total_loans"]

    cur.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_customers=total_customers,
        total_loans=total_loans
    )


# ==============================
# CUSTOMER DASHBOARD
# ==============================
@app.route('/customer/dashboard')
def customer_dashboard():
    return render_template('customer_dashboard.html')


# ==============================
# CUSTOMER PAGE
# ==============================
@app.route('/customer')
def customer():
    return render_template('customer.html')



 



# ==============================
# PAYMENT SCHEDULE (ADMIN)
# ==============================
@app.route('/admin/payment_schedule/<int:loan_id>')
def admin_payment_schedule(loan_id):

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT * FROM payment_schedule
        WHERE loan_id = %s
        ORDER BY due_date
    """, (loan_id,))

    schedule = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('admin_payment_schedule.html', schedule=schedule)


# ==============================
# START FACE VERIFICATION
# ==============================
@app.route('/proceed_face_verification', methods=['POST'])
def proceed_face_verification():
    session['loan_data'] = dict(request.form)
    return redirect(url_for('index'))


# ==============================
# FINAL LOAN SUBMISSION AFTER FACE VERIFICATION
# ==============================
@app.route('/face_verified')
def face_verified():

    data = session.get('loan_data')

    if not data:
        flash("Loan data missing. Please try again.", "danger")
        return redirect(url_for('customer_dashboard'))

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        INSERT INTO loans (user_id, appliance_id, amount, status)
        VALUES (%s, %s, %s, 'Pending')
    """, (
        session['user_id'],
        data['appliance_id'],
        data['price']
    ))

    conn.commit()
    cur.close()
    conn.close()

    session.pop('loan_data', None)

    flash("Loan application submitted successfully!", "success")
    return redirect(url_for('customer_dashboard'))


# ==============================
# FACE VERIFICATION PAGE
# ==============================
@app.route("/verify")
def index():
    return render_template("verify.html")


# ==============================
# APPLY LOAN PAGE
# ==============================
@app.route("/apply-loan/<int:appliance_id>", methods=["GET"])
def apply_loan(appliance_id):

    if "user_id" not in session:
        flash("Please log in first", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT * FROM appliances WHERE id = %s
    """, (appliance_id,))

    appliance = cur.fetchone()

    cur.close()
    conn.close()

    if not appliance:
        flash("Appliance not found.", "danger")
        return redirect(url_for("index"))

    return render_template("loan_modal.html", appliance=appliance)


@app.route("/submit_loan", methods=["POST"])
def submit_loan():

    if "user_id" not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # ---------------- GET FORM DATA ----------------
    appliance_id = int(request.form["appliance_id"])
    months = int(request.form["months"])
    amount = float(request.form["amount"])
    full_name = request.form["full_name"]
    email = request.form["email"]
    mobile = request.form["mobile"]
    occupation = request.form["occupation"]
    salary = float(request.form["salary"])

    # ---------------- DB CONNECTION ----------------
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # ---------------- FETCH APPLIANCE ----------------
    cur.execute("""
        SELECT appliance_name, category 
        FROM appliances 
        WHERE id = %s
    """, (appliance_id,))

    appliance = cur.fetchone()

    cur.close()
    conn.close()

    if not appliance:
        flash("Appliance not found.", "danger")
        return redirect(url_for("customer_dashboard"))

    # ---------------- STORE IN SESSION ----------------
    session["loan_data"] = {
        "user_id": user_id,
        "appliance_id": appliance_id,
        "appliance_name": appliance["appliance_name"],
        "category": appliance["category"],
        "months": months,
        "amount": amount,
        "full_name": full_name,
        "email": email,
        "mobile": mobile,
        "occupation": occupation,
        "salary": salary,
        "status": "Pending"
    }

    flash("Please complete facial verification to submit your loan.", "info")
    return redirect(url_for("verify"))


# ==============================
# FINAL LOAN INSERT AFTER FACE SUCCESS
# ==============================
@app.route("/loan-face-success")
def loan_face_success():

    if "loan_data" not in session:
        flash("Loan session expired", "danger")
        return redirect(url_for("index1"))

    data = session.pop("loan_data")
    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # ---------------- INSERT LOAN ----------------
    cur.execute("""
        INSERT INTO loans 
        (user_id, appliance_id, amount, months, status)
        VALUES (%s, %s, %s, %s, 'Pending')
    """, (
        user_id,
        data["appliance_id"],
        data["amount"],
        data["months"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    flash("Loan application submitted successfully!", "success")
    return redirect(url_for("index1"))






@app.route("/approve_loan/<int:loan_id>", methods=["POST"])
def approve_loan(loan_id):

    try:
        conn = get_db_connection()
        cur = conn.cursor(MySQLdb.cursors.DictCursor)

        # ---------------- 1. GET LOAN ----------------
        cur.execute("""
            SELECT l.*, u.full_name, u.email, a.appliance_name
            FROM loans l
            JOIN users u ON l.user_id = u.id
            JOIN appliances a ON l.appliance_id = a.id
            WHERE l.id = %s
        """, (loan_id,))

        loan = cur.fetchone()

        if not loan:
            cur.close()
            conn.close()
            flash("Loan not found.", "danger")
            return redirect(url_for("admin_loans"))

        if loan['status'] == 'Approved':
            cur.close()
            conn.close()
            flash("Loan is already approved.", "info")
            return redirect(url_for("admin_loans"))

        # ---------------- 2. CHECK STOCK ----------------
        cur.execute("""
            SELECT stock FROM appliances WHERE id=%s
        """, (loan['appliance_id'],))

        appliance = cur.fetchone()

        if not appliance:
            cur.close()
            conn.close()
            flash("Appliance not found.", "danger")
            return redirect(url_for("admin_loans"))

        if appliance['stock'] <= 0:
            cur.close()
            conn.close()
            flash("Insufficient stock to approve this loan.", "danger")
            return redirect(url_for("admin_loans"))

        # ---------------- 3. UPDATE LOAN ----------------
        cur.execute("""
            UPDATE loans SET status='Approved'
            WHERE id=%s
        """, (loan_id,))

        # ---------------- 4. UPDATE STOCK ----------------
        quantity = 1

        # get current stock again (safe practice)
        cur.execute("""
            SELECT stock FROM appliances WHERE id=%s
        """, (loan['appliance_id'],))

        current = cur.fetchone()
        current_stock = current['stock']

        new_stock = current_stock - quantity

        if new_stock < 0:
            cur.close()
            conn.close()
            flash("Stock cannot go below zero.", "danger")
            return redirect(url_for("admin_loans"))

        cur.execute("""
            UPDATE appliances
            SET stock = %s
            WHERE id = %s
        """, (new_stock, loan['appliance_id']))

        # ---------------- 5. STOCK MOVEMENT ----------------
        # ---------------- 5. STOCK MOVEMENT ----------------
        cur.execute("""
            INSERT INTO stock_movements
            (appliance_id, movement_type, quantity, reference_note, movement_date)
            VALUES (%s, %s, %s, %s, NOW())
        """, (
            loan['appliance_id'],
            'stock_out',   # ✅ FIXED
            quantity,
            f"Loan Approved (Loan ID: {loan_id})"
        ))

        # ---------------- 6. DELETE OLD PAYMENTS ----------------
        cur.execute("""
            DELETE FROM payments WHERE loan_id=%s
        """, (loan_id,))

        # ---------------- 7. GENERATE SCHEDULE ----------------
        amount = float(loan['amount'])
        months = int(loan['months'])

        if months <= 0:
            months = 1  # safety fix

        monthly_payment = round(amount / months, 2)
        start_date = date.today()

        for i in range(1, months + 1):
            due_date = start_date + relativedelta(months=i)

            cur.execute("""
                INSERT INTO payments 
                (loan_id, month_no, amount_due, due_date, status)
                VALUES (%s, %s, %s, %s, 'not_paid')
            """, (loan_id, i, monthly_payment, due_date))

        conn.commit()

        # ---------------- 8. EMAIL NOTIFICATION ----------------
        yag = yagmail.SMTP(EMAIL_USER, EMAIL_APP_PASSWORD)

        subject = "Loan Application Approved 🎉"

        body = f"""
Hello {loan['full_name']},

Good news! 🎉

Your loan for:
Appliance: {loan['appliance_name']}

Has been APPROVED.

Amount: ₱{loan['amount']:.2f}
Months: {loan['months']}

Your payment schedule is now available in your dashboard.

Thank you,
Greater RJ Appliance and Trading Corporation
        """

        yag.send(
            to=loan['email'],
            subject=subject,
            contents=body,
            headers={"From": f"Greater RJ Appliance and Trading Corporation <{EMAIL_USER}>"}
        )

        cur.close()
        conn.close()

        flash("Loan approved successfully, stock updated, schedule created, and email sent!", "success")
        return redirect(url_for("admin_loans"))

    except Exception as e:
        return f"Error approving loan: {str(e)}"


from io import BytesIO
from flask import send_file



@app.route("/deny_loan/<int:loan_id>", methods=["POST"])
def deny_loan(loan_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(MySQLdb.cursors.DictCursor)

        # Get loan info
        cur.execute("""
            SELECT l.*, u.full_name, u.email, a.appliance_name
            FROM loans l
            JOIN users u ON l.user_id = u.id
            JOIN appliances a ON l.appliance_id = a.id
            WHERE l.id = %s
        """, (loan_id,))

        loan = cur.fetchone()

        if not loan:
            cur.close()
            conn.close()
            return "Loan not found", 404

        # Update status
        cur.execute("""
            UPDATE loans SET status='Denied'
            WHERE id=%s
        """, (loan_id,))

        conn.commit()

        # EMAIL
        yag = yagmail.SMTP(EMAIL_USER, EMAIL_APP_PASSWORD)

        subject = "Loan Application Update"

        body = f"""
Hello {loan['full_name']},

We regret to inform you that your loan for:

Appliance: {loan['appliance_name']}

Has been DENIED.

Thank you,
Greater RJ Appliance and Trading Corporation
        """

        yag.send(
            to=loan['email'],
            subject=subject,
            contents=body,
            headers={"From": f"Greater RJ Appliance and Trading Corporation <{EMAIL_USER}>"}
        )

        cur.close()
        conn.close()

        return redirect(url_for("admin_loans"))

    except Exception as e:
        return f"Error denying loan: {str(e)}"

@app.route('/payments')
def payments():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # Fetch loans
    cur.execute("""
        SELECT * FROM loans
        WHERE user_id=%s
    """, (user_id,))
    loans = cur.fetchall()

    for loan in loans:

        cur.execute("""
            SELECT *
            FROM payments
            WHERE loan_id=%s
            ORDER BY month_no ASC
        """, (loan['id'],))
        loan['payments'] = cur.fetchall()

        cur.execute("""
            SELECT SUM(paid_amount) as total_paid
            FROM payments
            WHERE loan_id=%s
        """, (loan['id'],))

        total = cur.fetchone()
        loan['paid_amount_sum'] = total['total_paid'] or 0

        loan['balance'] = float(loan['amount']) - float(loan['paid_amount_sum'])

    cur.close()
    conn.close()

    return render_template("payments.html", loans=loans)
    
# Update a specific payment from admin panel
@app.route('/update_partial_payments/<int:user_id>', methods=['POST'])
def update_partial_payments(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(MySQLdb.cursors.DictCursor)

        payment_id = request.form.get('update_payment')

        if not payment_id:
            cur.close()
            conn.close()
            flash("No payment selected.", "danger")
            return redirect(url_for('view_customer_payments', user_id=user_id))

        # ===== GET PAYMENT =====
        cur.execute("SELECT * FROM payments WHERE id=%s", (payment_id,))
        payment = cur.fetchone()

        if not payment:
            cur.close()
            conn.close()
            flash("Payment not found.", "danger")
            return redirect(url_for('view_customer_payments', user_id=user_id))

        # ===== GET INPUT =====
        try:
            paid_amount = float(request.form.get(f"paid_{payment_id}", 0) or 0)
        except:
            cur.close()
            conn.close()
            flash("Invalid payment amount.", "danger")
            return redirect(url_for('view_customer_payments', user_id=user_id))

        # ✅ SAFE current_due
        current_due = float(payment.get('amount_due') or 0)

        arrears = max(current_due - paid_amount, 0)
        overpayment = max(paid_amount - current_due, 0)
        adjustment = arrears - overpayment

        # ===== STATUS =====
        if paid_amount >= current_due:
            status = 'paid'
            paid_at = datetime.now()
            payment_type = "Paid in Full ✅"

        elif paid_amount > 0:
            status = 'partial'
            paid_at = None
            payment_type = "Partial Payment ⚠️"

        else:
            status = 'not_paid'
            paid_at = None
            payment_type = "Not Paid ❌"

        # ===== UPDATE CURRENT PAYMENT =====
        cur.execute("""
            UPDATE payments
            SET paid_amount=%s,
                status=%s,
                arrears=%s,
                paid_at=%s
            WHERE id=%s
        """, (paid_amount, status, arrears, paid_at, payment_id))

        # ===== NEXT PAYMENT =====
        cur.execute("""
            SELECT * FROM payments
            WHERE loan_id=%s AND month_no=%s
        """, (payment['loan_id'], payment['month_no'] + 1))

        next_payment = cur.fetchone()
        next_due_msg = ""

        if next_payment:
            base_due = float(next_payment.get('original_amount_due') or next_payment.get('amount_due') or 0)

            next_due = base_due + adjustment
            next_due = max(next_due, 0)

            cur.execute("""
                UPDATE payments
                SET amount_due=%s
                WHERE id=%s
            """, (next_due, next_payment['id']))

            next_due_msg = f"\nNext Month's Adjusted Due: ₱{next_due:.2f}"

        conn.commit()

        # ===== EMAIL SECTION =====
        try:
            cur.execute("""
                SELECT u.full_name, u.email, a.appliance_name
                FROM loans l
                JOIN users u ON l.user_id = u.id
                JOIN appliances a ON l.appliance_id = a.id
                WHERE l.id = %s
            """, (payment['loan_id'],))

            info = cur.fetchone()

            if info:
                pdf_buffer = io.BytesIO()
                c = canvas.Canvas(pdf_buffer, pagesize=(400, 420))

                receipt_no = f"RJ-{int(payment_id):06d}"
                today = datetime.now().strftime("%B %d, %Y")

                # ✅ SAFE due_date
                due_date_value = payment.get('due_date')
                if due_date_value:
                    if isinstance(due_date_value, str):
                        due_date = due_date_value
                    else:
                        due_date = due_date_value.strftime("%B %d, %Y")
                else:
                    due_date = "N/A"

                c.rect(10, 10, 380, 400)

                c.setFont("Helvetica-Bold", 12)
                c.drawCentredString(200, 380, "GREATER RJ Appliance & Trading Corp")

                c.setFont("Helvetica", 10)
                c.drawString(20, 335, f"Receipt No : {receipt_no}")
                c.drawString(20, 320, f"Date       : {today}")
                c.drawString(20, 295, f"Customer   : {info['full_name']}")
                c.drawString(20, 280, f"Appliance  : {info['appliance_name']}")
                c.drawString(20, 255, f"Due Date   : {due_date}")

                c.drawString(20, 225, f"Amount Due : ₱{current_due:,.2f}")
                c.drawString(20, 210, f"Amount Paid: ₱{paid_amount:,.2f}")

                c.showPage()
                c.save()
                pdf_buffer.seek(0)

                body = f"""
Hello {info['full_name']},

Your payment of ₱{paid_amount:.2f} has been updated.
Status: {payment_type}
{next_due_msg}

Thank you,
Greater RJ Appliance and Trading Corporation
                """

                yag = yagmail.SMTP(EMAIL_USER, EMAIL_APP_PASSWORD)

                yag.send(
                    to=info['email'],
                    subject="Payment Update",
                    contents=body,
                    attachments=[pdf_buffer]
                )

        except Exception as e:
            print("Email error:", e)

        cur.close()
        conn.close()

        flash("Payment updated successfully ✅", "success")
        return redirect(url_for('view_customer_payments', user_id=user_id))

    except Exception as e:
        import traceback
        print("CRASH:", e)
        traceback.print_exc()
        return str(e)




@app.route("/customer/history")
def customer_history():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # LOANS
    cur.execute("""
        SELECT l.*, a.appliance_name
        FROM loans l
        JOIN appliances a ON l.appliance_id = a.id
        WHERE l.user_id = %s
        ORDER BY l.created_at DESC
    """, (user_id,))
    loans = cur.fetchall()

    for loan in loans:

        cur.execute("""
            SELECT month_no, amount_due, due_date, status
            FROM payments
            WHERE loan_id = %s
            ORDER BY month_no ASC
        """, (loan["id"],))

        payments = cur.fetchall()

        for p in payments:
            if p["due_date"]:
                p["due_date"] = p["due_date"].strftime("%B %d, %Y")

        loan["payments"] = payments

        # FIXED: sum PAID AMOUNT (not amount_due)
        cur.execute("""
            SELECT SUM(paid_amount) as total_paid
            FROM payments
            WHERE loan_id=%s
        """, (loan["id"],))

        paid = cur.fetchone()["total_paid"] or 0

        loan["paid"] = float(paid)
        loan["balance"] = float(loan["amount"]) - float(paid)

    # ORDERS
    cur.execute("""
        SELECT * FROM orders
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))
    orders = cur.fetchall()

    for order in orders:
        cur.execute("""
            SELECT appliance_name, price, quantity
            FROM order_items
            WHERE order_id = %s
        """, (order["id"],))   # FIXED: was order_id
        order["items"] = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("customer_history.html", loans=loans, orders=orders)

def get_appliances():

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT *
        FROM appliances
        WHERE status = 'Available' AND stock > 0
        ORDER BY created_at DESC
    """)

    appliances = cur.fetchall()

    cur.close()
    conn.close()

    return appliances


@app.route("/appliances")
def appliances_iframe():
    appliances = get_appliances()
    return render_template("appliances_center.html", appliances=appliances)

@app.context_processor
def inject_cart_count():
    if "user_id" in session:
        user_id = session["user_id"]
        conn = get_db_connection()
        cur = conn.cursor(MySQLdb.cursors.DictCursor)

        cur.execute("""
            SELECT SUM(quantity) AS total_qty 
            FROM cart
            WHERE user_id = %s
        """, (user_id,))

        result = cur.fetchone()
        cur.close()
        conn.close()

        count = result["total_qty"] if result and result["total_qty"] else 0
    else:
        count = 0

    return dict(cart_count=count)




@app.route("/admin/edit_appliance/<int:appliance_id>", methods=["GET", "POST"])
def edit_appliance(appliance_id):

    if "user_id" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT * FROM appliances WHERE id=%s", (appliance_id,))
    appliance = cur.fetchone()

    if not appliance:
        cur.close()
        conn.close()
        flash("Appliance not found", "danger")
        return redirect(url_for("admin_appliances"))

    if request.method == "POST":
        name = request.form["appliance_name"]
        category = request.form["category"]
        price = request.form["price"]
        new_stock = int(request.form["stock"])
        image = request.files.get("image")

        image_path_db = appliance["image"]

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(image_path)
            image_path_db = f"uploads/appliances/{filename}"

        old_stock = appliance["stock"]
        difference = new_stock - old_stock

        cur.execute("""
            UPDATE appliances
            SET appliance_name=%s,
                category=%s,
                price=%s,
                stock=%s,
                image=%s
            WHERE id=%s
        """, (name, category, price, new_stock, image_path_db, appliance_id))

        if difference != 0:
            movement_type = "stock_in" if difference > 0 else "stock_out"

            cur.execute("""
                INSERT INTO stock_movements 
                (appliance_id, movement_type, quantity, reference_note)
                VALUES (%s, %s, %s, %s)
            """, (
                appliance_id,
                movement_type,
                abs(difference),
                "Manual stock adjustment (Admin Edit)"
            ))

        conn.commit()
        cur.close()
        conn.close()

        flash("Appliance updated successfully", "success")
        return redirect(url_for("admin_appliances"))

    cur.close()
    conn.close()
    return render_template("edit_appliance.html", appliance=appliance)






@app.route("/admin/reports/loan_decisions", methods=["GET"])
def report_loan_decisions():

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    status = request.args.get("status")

    query = """
        SELECT l.id, l.user_id, u.full_name, a.appliance_name,
               l.amount, l.months, l.status, l.applied_on
        FROM loans l
        JOIN users u ON l.user_id = u.id
        JOIN appliances a ON l.appliance_id = a.id
        WHERE 1=1
    """

    params = []

    if from_date:
        query += " AND DATE(l.applied_on) >= %s"
        params.append(from_date)

    if to_date:
        query += " AND DATE(l.applied_on) <= %s"
        params.append(to_date)

    if status:
        query += " AND l.status = %s"
        params.append(status)

    query += " ORDER BY l.applied_on DESC"

    cur.execute(query, params)
    loans = cur.fetchall()

    # ================= COUNTS =================
    approved_count = sum(1 for l in loans if l["status"].lower() == "approved")
    denied_count = sum(1 for l in loans if l["status"].lower() == "denied")
    pending_count = sum(1 for l in loans if l["status"].lower() == "pending")

    cur.close()
    conn.close()

    # ================= DATE FORMATTING =================
    def format_date(d):
        if not d:
            return None
        return datetime.strptime(str(d), "%Y-%m-%d").strftime("%B %d, %Y")

    from_date_long = format_date(from_date)
    to_date_long = format_date(to_date)

    # ================= SMART HEADER =================
    status_text = "ALL LOANS"
    if status:
        status_text = f"{status.upper()} LOANS"

    if from_date_long and to_date_long:
        date_text = f"From {from_date_long} to {to_date_long}"
    elif from_date_long:
        date_text = f"From {from_date_long}"
    elif to_date_long:
        date_text = f"Until {to_date_long}"
    else:
        date_text = "Full History"

    generated_at = datetime.now().strftime("%B %d, %Y %I:%M %p")

    report_title = f"Loan Report for {status_text}"

    return render_template(
        "admin_reports_loan_decisions.html",
        loans=loans,
        approved_count=approved_count,
        denied_count=denied_count,
        pending_count=pending_count,
        report_title=report_title,
        date_text=date_text,
        generated_at=generated_at
    )
    

from datetime import datetime
import MySQLdb.cursors

@app.route("/admin/reports/customers")
def report_customers():
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT id, full_name, email, contact_number, address, status, created_at
        FROM users
        WHERE role = 'customer'
        ORDER BY created_at DESC
    """)
    customers = cur.fetchall()
    cur.close()
    conn.close()

    generated_at = datetime.now().strftime("%B %d, %Y %I:%M %p")

    return render_template(
        "report_customers.html",
        customers=customers,
        generated_at=generated_at
    )


@app.route("/admin/order_receipt/<int:order_id>")
def order_receipt(order_id):
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT o.order_id, o.total_amount, o.status, o.created_at,
               u.full_name, u.email
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.order_id = %s
    """, (order_id,))
    order = cur.fetchone()

    if not order or order["status"] != "Approved":
        flash("Order is not approved yet!", "error")
        return redirect(url_for("admin_orders"))

    cur.execute("""
        SELECT appliance_name, price, quantity,
               (price * quantity) AS subtotal
        FROM order_items
        WHERE order_id = %s
    """, (order_id,))
    items = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("order_receipt.html", order=order, items=items)


@app.route("/admin/payment_transactions")
def payment_transactions():

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    customer = request.args.get("customer")

    query = """
        SELECT 
            l.id AS loan_id,
            u.full_name,
            u.email,
            a.appliance_name,
            l.amount AS loan_amount,
            p.id AS payment_id,
            p.month_no,
            p.amount_due,
            p.paid_amount,
            p.due_date,
            p.status
        FROM users u
        LEFT JOIN loans l ON u.id = l.user_id
        LEFT JOIN appliances a ON l.appliance_id = a.id
        LEFT JOIN payments p ON l.id = p.loan_id
    """

    params = []

    if customer:
        query += " WHERE u.full_name LIKE %s"
        params.append(f"%{customer}%")

    query += " ORDER BY u.full_name, p.due_date"

    cur.execute(query, params)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    loans_dict = {}

    for row in rows:

        loan_id = row["loan_id"]

        if loan_id not in loans_dict:
            loans_dict[loan_id] = {
                "loan_id": loan_id,
                "full_name": row["full_name"],
                "email": row["email"],
                "appliance_name": row["appliance_name"],
                "amount": float(row["loan_amount"] or 0),
                "payments": [],
                "total_paid": 0
            }

        if row["payment_id"]:

            amount_due = float(row["amount_due"] or 0)
            paid_amount = float(row["paid_amount"] or 0)

            arrears = round(amount_due - paid_amount, 2)

            loans_dict[loan_id]["payments"].append({
                "payment_id": row["payment_id"],
                "month_no": row["month_no"],
                "amount_due": amount_due,
                "paid_amount": paid_amount,
                "arrears": arrears,
                "due_date": row["due_date"],
                "status": row["status"]
            })

            loans_dict[loan_id]["total_paid"] += paid_amount

    for loan in loans_dict.values():
        loan["balance"] = loan["amount"] - loan["total_paid"]

    loans = list(loans_dict.values())

    return render_template(
        "admin_payment_transactions.html",
        loans=loans
    )



from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
from collections import defaultdict
import MySQLdb.cursors
import os
import io
import base64
import cv2
import numpy as np
import yagmail
from functools import wraps

# =========================
# CONTEXT PROCESSOR
# =========================
@app.context_processor
def inject_cart_count():
    if "user_id" in session:
        user_id = session["user_id"]
        conn = get_db_connection()
        cur = conn.cursor(MySQLdb.cursors.DictCursor)

        cur.execute("""
            SELECT SUM(quantity) AS total_qty 
            FROM cart
            WHERE user_id = %s
        """, (user_id,))

        result = cur.fetchone()

        cur.close()
        conn.close()

        count = result["total_qty"] if result and result["total_qty"] else 0
    else:
        count = 0

    return dict(cart_count=count)

# =========================
# CART COUNT API
# =========================
@app.route("/cart/count")
def cart_count_route():
    cart = session.get("cart", {})
    return {"count": sum(cart.values())}

# =========================
# APPLY LOAN PAGE
# =========================
@app.route("/customer/apply-loan")
def apply_loan_page():
    if "user_id" not in session:
        flash("Please log in first", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT * 
        FROM appliances 
        WHERE status = 'Available' AND stock > 0
    """)
    appliances = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("apply_loan.html", appliances=appliances)

# =========================
# CUSTOMER ORDERS
# =========================
@app.route("/orders")
def customer_orders():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT order_id, total_amount, status, created_at
        FROM orders
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))
    orders = cur.fetchall()

    for order in orders:
        cur.execute("""
            SELECT appliance_name, price, quantity
            FROM order_items
            WHERE order_id = %s
        """, (order["order_id"],))
        order["items"] = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("orders.html", orders=orders)

# =========================
# CUSTOMER PAYMENTS
# =========================
@app.route("/payments")
def customer_payments():
    if "user_id" not in session:
        flash("Please log in first", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT l.*, a.appliance_name
        FROM loans l
        JOIN appliances a ON l.appliance_id = a.id
        WHERE l.user_id = %s
        ORDER BY l.created_at DESC
    """, (user_id,))

    loans = cur.fetchall()

    for loan in loans:
        cur.execute("""
            SELECT id, month_no, amount_due, due_date, status, payment_proof
            FROM payments
            WHERE loan_id = %s
            ORDER BY month_no ASC
        """, (loan["id"],))

        loan["payments"] = cur.fetchall()

        paid = sum(
            p["amount_due"]
            for p in loan["payments"]
            if p["status"] == "paid"
        )

        loan["paid"] = paid
        loan["balance"] = loan["amount"] - paid

    cur.close()
    conn.close()

    return render_template("payments.html", loans=loans)

# =========================
# STOCK MOVEMENTS
# =========================
# =========================
# STOCK MOVEMENTS
# =========================
@app.route("/admin/stock_movements/<int:appliance_id>")
def appliance_stock_movements(appliance_id):

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # ---------------- MOVEMENTS ----------------
    query = """
        SELECT sm.*, a.appliance_name, a.stock
        FROM stock_movements sm
        JOIN appliances a ON sm.appliance_id = a.id
        WHERE sm.appliance_id = %s
    """

    params = [appliance_id]

    if start_date and end_date:
        query += " AND DATE(sm.movement_date) BETWEEN %s AND %s"
        params.extend([start_date, end_date])

    query += " ORDER BY sm.movement_date DESC"

    cur.execute(query, params)
    movements = cur.fetchall()

    # ---------------- SUMMARY ----------------
    summary_query = """
    SELECT 
        a.appliance_name,
        a.stock AS current_stock,
        COALESCE(SUM(CASE WHEN sm.movement_type='stock_in' THEN sm.quantity ELSE 0 END),0) AS total_in,
        COALESCE(SUM(CASE WHEN sm.movement_type='stock_out' THEN sm.quantity ELSE 0 END),0) AS total_out
    FROM appliances a
    LEFT JOIN stock_movements sm ON a.id = sm.appliance_id
    WHERE a.id = %s
    """

    if start_date and end_date:
        summary_query += " AND DATE(sm.movement_date) BETWEEN %s AND %s"
        summary_params = [appliance_id, start_date, end_date]
    else:
        summary_params = [appliance_id]

    cur.execute(summary_query, summary_params)
    summary = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "stock_movements.html",
        movements=movements,
        summary=summary,
        start_date=start_date,
        end_date=end_date
    )

# =========================
# INVENTORY REPORT
# =========================
@app.route("/admin/inventory-report")
def inventory_report():

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # ================= FILTER VALUES =================
    selected_category = request.args.get("category", "")
    selected_appliance = request.args.get("appliance_name", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    # ================= CATEGORY LIST =================
    cur.execute("SELECT DISTINCT category FROM appliances ORDER BY category")
    categories = cur.fetchall()

    # ================= APPLIANCE LIST (DEPENDENT DROPDOWN FIX) =================
    appliance_query = "SELECT DISTINCT appliance_name FROM appliances WHERE 1=1"
    appliance_params = []

    if selected_category:
        appliance_query += " AND category = %s"
        appliance_params.append(selected_category)

    appliance_query += " ORDER BY appliance_name"

    cur.execute(appliance_query, appliance_params)
    appliance_list = cur.fetchall()

    # ================= MAIN INVENTORY QUERY =================
    query = "SELECT * FROM appliances WHERE 1=1"
    params = []

    if selected_category:
        query += " AND category = %s"
        params.append(selected_category)

    if selected_appliance:
        query += " AND appliance_name = %s"
        params.append(selected_appliance)

    query += " ORDER BY appliance_name"

    cur.execute(query, params)
    appliances = cur.fetchall()

    # ================= PRINT LABEL =================
    from datetime import datetime

    print_label = "Full Inventory Overview"

    if start_date and end_date:
        s = datetime.strptime(start_date, "%Y-%m-%d")
        e = datetime.strptime(end_date, "%Y-%m-%d")
        print_label = f"Inventory Report from {s.strftime('%b %d, %Y')} to {e.strftime('%b %d, %Y')}"

    elif start_date:
        s = datetime.strptime(start_date, "%Y-%m-%d")
        print_label = f"Inventory starting {s.strftime('%b %d, %Y')}"

    elif end_date:
        e = datetime.strptime(end_date, "%Y-%m-%d")
        print_label = f"Inventory until {e.strftime('%b %d, %Y')}"

    cur.close()
    conn.close()

    return render_template(
        "inventory_report.html",
        appliances=appliances,
        categories=categories,
        appliance_list=appliance_list,
        selected_category=selected_category,
        selected_appliance=selected_appliance,
        start_date=start_date,
        end_date=end_date,
        print_label=print_label
    )
# =========================
# MONTHLY SALES REPORT
# =========================
from collections import defaultdict
from datetime import datetime

@app.route("/admin/reports/monthly_sales", methods=["GET"])
def admin_reports_monthly_sales():
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    try:
        # =========================
        # FILTERS
        # =========================
        month_str = request.args.get("month", datetime.now().strftime("%Y-%m"))
        category_filter = request.args.get("category", "")

        try:
            year, month = map(int, month_str.split("-"))
        except:
            year, month = datetime.now().year, datetime.now().month

        # =========================
        # MAIN REPORT QUERY
        # =========================
        query = """
            SELECT 
                a.appliance_name,
                a.category,
                SUM(l.amount) AS total_loan,
                SUM(COALESCE(p.paid_amount,0)) AS total_collected,
                COUNT(DISTINCT l.id) AS stocks_released
            FROM loans l
            JOIN appliances a ON l.appliance_id = a.id
            LEFT JOIN payments p ON p.loan_id = l.id
            WHERE l.status = 'Approved'
              AND (
                    (MONTH(p.due_date) = %s AND YEAR(p.due_date) = %s)
                    OR p.id IS NULL
                  )
        """

        params = [month, year]

        if category_filter:
            query += " AND a.category = %s"
            params.append(category_filter)

        query += " GROUP BY a.id ORDER BY stocks_released DESC, a.appliance_name ASC"

        cur.execute(query, tuple(params))
        reports = cur.fetchall()

        # =========================
        # SAFE TOTALS (FIXED ERROR SOURCE)
        # =========================
        grand_total_collected = sum(r["total_collected"] or 0 for r in reports)
        grand_total_loan = sum(r["total_loan"] or 0 for r in reports)
        grand_total_stocks = sum(r["stocks_released"] or 0 for r in reports)

        # =========================
        # CATEGORIES DROPDOWN
        # =========================
        cur.execute("SELECT DISTINCT category FROM appliances ORDER BY category ASC")
        categories = cur.fetchall()

        # =========================
        # YEARLY DATA (CHART)
        # =========================
        yearly_data = defaultdict(float)

        for m in range(1, 13):
            yearly_query = """
                SELECT SUM(COALESCE(p.paid_amount,0)) AS total_collected
                FROM loans l
                JOIN appliances a ON l.appliance_id = a.id
                LEFT JOIN payments p ON p.loan_id = l.id
                WHERE l.status = 'Approved'
                  AND MONTH(p.due_date) = %s
                  AND YEAR(p.due_date) = %s
            """

            params_yearly = [m, year]

            if category_filter:
                yearly_query += " AND a.category = %s"
                params_yearly.append(category_filter)

            cur.execute(yearly_query, tuple(params_yearly))
            result = cur.fetchone()

            yearly_data[m] = float(result["total_collected"] or 0)

        # =========================
        # RETURN TEMPLATE
        # =========================
        return render_template(
            "admin_reports_monthly_sales.html",
            reports=reports,
            selected_month=month_str,
            selected_category=category_filter,
            categories=categories,
            grand_total_collected=grand_total_collected,
            grand_total_loan=grand_total_loan,
            grand_total_stocks=grand_total_stocks,
            yearly_data=yearly_data
        )

    finally:
        cur.close()
        conn.close()

# =========================
# ORDER RECEIPTS REPORT
# =========================
@app.route("/reports/order_receipts")
def order_receipts_report():
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT o.order_id, o.user_id, o.total_amount, o.created_at,
               u.full_name, u.email
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.status = 'Approved'
        ORDER BY o.created_at DESC
    """)
    orders = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin_order_receipts.html", orders=orders)

from datetime import datetime, timedelta
import MySQLdb.cursors
from flask import request, render_template, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash

# =========================
# REMINDER FUNCTION
# =========================
def get_upcoming_due_payments(user_id=None):
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    target_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    query = """
        SELECT 
            p.id AS payment_id,
            p.amount_due,
            p.due_date,
            u.full_name,
            u.email,
            a.appliance_name
        FROM payments p
        JOIN loans l ON p.loan_id = l.id
        JOIN users u ON l.user_id = u.id
        JOIN appliances a ON l.appliance_id = a.id
        WHERE p.status = 'not paid'
          AND DATE(p.due_date) = %s
          AND p.reminder_sent = 0
    """

    params = [target_date]

    if user_id:
        query += " AND u.id = %s"
        params.append(user_id)

    cur.execute(query, params)
    results = cur.fetchall()

    cur.close()
    conn.close()

    return results


# =========================
# ACCOUNT SECURITY
# =========================
@app.route("/account/security", methods=["GET", "POST"])
def account_security():
    user_id = session.get("user_id")

    if not user_id:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        cur.execute("SELECT password FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()

        if not user:
            flash("User not found.", "error")

        elif not check_password_hash(user["password"], current_password):
            flash("Current password is incorrect.", "error")

        elif new_password != confirm_password:
            flash("New passwords do not match.", "error")

        else:
            hashed = generate_password_hash(new_password)

            cur.execute("""
                UPDATE users 
                SET password = %s 
                WHERE id = %s
            """, (hashed, user_id))

            conn.commit()
            flash("Password successfully updated!", "success")
            return redirect(url_for("account_security"))

    cur.close()
    conn.close()

    return render_template("account_security.html")

@app.route("/account/emails")
def account_emails():
    user_id = session.get("user_id")  # or however you track the logged-in customer
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)
    
    cur.execute("""
        SELECT reminder_email_content
        FROM payments
        WHERE reminder_sent = 1
          AND loan_id IN (
              SELECT id FROM loans WHERE user_id = %s
          )
        ORDER BY due_date DESC
    """, (user_id,))
    
    emails = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template("account_emails.html", emails=emails)


@app.route("/customer/account", methods=["GET", "POST"])
def account_profile():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        password = request.form.get("password")  # optional

        # Update password only if provided
        if password:
            hashed_pw = generate_password_hash(password)
            cur.execute("""
                UPDATE users
                SET full_name=%s, email=%s, password=%s
                WHERE id=%s
            """, (full_name, email, hashed_pw, user_id))
        else:
            cur.execute("""
                UPDATE users
                SET full_name=%s, email=%s
                WHERE id=%s
            """, (full_name, email, user_id))

        conn.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("account_profile"))

    # GET: Fetch user info
    cur.execute("""
        SELECT id, full_name, email
        FROM users
        WHERE id=%s
    """, (user_id,))
    user = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("account_profile.html", user=user)

@app.route('/admin/loan/<int:loan_id>')
def admin_loan_details(loan_id):
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # Fetch the loan along with user and appliance info
    cur.execute("""
        SELECT l.*, u.full_name, u.email,
               a.appliance_name, a.category, a.price AS appliance_price, a.stock
        FROM loans l
        JOIN users u ON l.user_id = u.id
        JOIN appliances a ON l.appliance_id = a.id
        WHERE l.id = %s
    """, (loan_id,))
    
    loan = cur.fetchone()

    cur.close()
    conn.close()

    if not loan:
        flash("Loan not found", "danger")
        return redirect(url_for('admin_loans'))

    return render_template("admin_loan_details.html", loan=loan)

from werkzeug.utils import secure_filename
import os

@app.route('/admin/notifications/json')
def admin_notifications_json():

    if 'user_id' not in session:
        return jsonify([])

    admin_id = session['user_id']

    if admin_id != 42:
        return jsonify([])

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT 
            id,
            message,
            link,
            is_read,
            created_at
        FROM admin_notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 10
    """, (admin_id,))

    notifications = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(notifications)

@app.route('/admin/notifications/mark_all_read', methods=['POST'])
def mark_all_notifications_read():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    admin_id = session['user_id']

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE admin_notifications
        SET is_read = 1
        WHERE user_id = %s AND is_read = 0
    """, (admin_id,))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True})

@app.route('/admin/notifications/delete/<int:notification_id>')
def delete_notification(notification_id):

    if 'user_id' not in session or session['user_id'] != 42:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM admin_notifications
        WHERE id = %s AND user_id = %s
    """, (notification_id, 42))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('admin_dashboard'))
    return '', 204

@app.route("/upload_payment/<int:payment_id>", methods=["POST"])
def upload_payment(payment_id):

    # Check if file exists
    if 'payment_screenshot' not in request.files:
        flash("No file uploaded.", "danger")
        return redirect(request.referrer)

    file = request.files['payment_screenshot']

    if file.filename == '':
        flash("No selected file.", "danger")
        return redirect(request.referrer)

    # Save file
    filename = secure_filename(file.filename)
    filepath = os.path.join('static/uploads', filename)
    file.save(filepath)

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # 1️⃣ Update payment proof
    cur.execute("""
        UPDATE payments
        SET payment_proof = %s
        WHERE id = %s
    """, (filename, payment_id))

    # 2️⃣ Get payment + user + appliance info
    cur.execute("""
        SELECT 
            p.id,
            p.loan_id,
            p.due_date,
            u.id AS user_id,
            u.full_name,
            a.appliance_name
        FROM payments p
        JOIN loans l ON p.loan_id = l.id
        JOIN users u ON l.user_id = u.id
        JOIN appliances a ON l.appliance_id = a.id
        WHERE p.id = %s
    """, (payment_id,))

    info = cur.fetchone()

    # 3️⃣ Insert admin notification
    if info:
        message = f"Payment proof uploaded by {info['full_name']} for {info['appliance_name']} (Due {info['due_date'].strftime('%B %d, %Y')})"

        cur.execute("""
            INSERT INTO admin_notifications (user_id, payment_id, message, link, is_read, created_at)
            VALUES (%s, %s, %s, %s, 0, NOW())
        """, (
            42,
            payment_id,
            message,
            f"/admin/payments/{info['user_id']}/view"
        ))

    conn.commit()
    cur.close()
    conn.close()

    flash("Payment proof uploaded successfully!", "success")
    return redirect(request.referrer)

@app.route('/debug-session')
def debug_session():
    return f"Logged in user_id: {session.get('user_id')}"

@app.route('/admin/customer_ledger')
def customer_ledger():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    search_query = request.args.get('q', '').strip()

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    base_sql = """
        SELECT 
            u.id AS user_id,
            u.full_name AS customer_name,
            a.appliance_name,
            l.amount AS total_amount,
            IFNULL(SUM(p.paid_amount),0) AS total_payments,
            l.amount - IFNULL(SUM(p.paid_amount),0) AS balance
        FROM loans l
        JOIN users u ON l.user_id = u.id
        JOIN appliances a ON l.appliance_id = a.id
        LEFT JOIN payments p ON p.loan_id = l.id
    """

    params = []

    if search_query:
        base_sql += """
            WHERE u.full_name LIKE %s 
               OR a.appliance_name LIKE %s
        """
        params = [f"%{search_query}%", f"%{search_query}%"]

    base_sql += """
        GROUP BY l.id
        ORDER BY u.full_name, a.appliance_name
    """

    cur.execute(base_sql, params)

    ledger = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'customer_ledger.html',
        ledger=ledger,
        search_query=search_query
    )

# --- Detailed Ledger (JSON) ---
from datetime import date

@app.route("/admin/customer_ledger/<int:user_id>")
def customer_ledger_user(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(MySQLdb.cursors.DictCursor)

        # GET LOAN + UPDATED APPLIANCE NAME
        cur.execute("""
            SELECT 
                l.id AS loan_id,
                u.full_name AS customer,
                a.appliance_name,
                l.amount,
                l.months,
                l.created_at
            FROM loans l
            JOIN users u ON l.user_id = u.id
            JOIN appliances a ON l.appliance_id = a.id
            WHERE l.user_id = %s
            LIMIT 1
        """, (user_id,))

        summary = cur.fetchone()

        if not summary:
            cur.close()
            conn.close()
            return jsonify({"error": "No loan found"}), 404

        # TOTAL PAYMENTS
        cur.execute("""
            SELECT IFNULL(SUM(paid_amount),0) AS total_paid
            FROM payments
            WHERE loan_id = %s
        """, (summary["loan_id"],))

        payment_data = cur.fetchone()
        total_paid = float(payment_data["total_paid"] or 0)

        balance = float(summary["amount"]) - total_paid

        # COMPUTE TERM END
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        created_at = summary["created_at"]

        if isinstance(created_at, str):
            created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")

        term_end = created_at + relativedelta(months=int(summary["months"]))

        # GET PAYMENT DETAILS
        cur.execute("""
            SELECT 
                month_no,
                amount_due,
                paid_amount,
                due_date
            FROM payments
            WHERE loan_id = %s
            ORDER BY month_no ASC
        """, (summary["loan_id"],))

        payments = cur.fetchall()

        # RUNNING BALANCE
        running_balance = float(summary["amount"])
        details = []

        for p in payments:
            paid = float(p["paid_amount"] or 0)
            due = float(p["amount_due"] or 0)

            running_balance -= paid

            details.append({
                "month": p["month_no"],
                "appliance_name": summary["appliance_name"],
                "description": f"Payment for Month {p['month_no']}",
                "amount_due": due,
                "amount_paid": paid,
                "arrears_overpay": paid - due,
                "balance": running_balance,
                "due_date": p["due_date"]
            })

        cur.close()
        conn.close()

        return jsonify({
            "customer": summary["customer"],
            "summary": {
                "customer": summary["customer"],
                "balance": balance,
                "appliance_name": summary["appliance_name"],
                "date_granted": created_at.strftime("%Y-%m-%d"),
                "months": summary["months"],
                "term_end": term_end.strftime("%Y-%m-%d")
            },
            "details": details
        })

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


from flask import render_template, session, redirect, url_for
from dateutil.relativedelta import relativedelta
from datetime import date
import MySQLdb


@app.route("/customer/ledger/<int:loan_id>")
def customer_ledger_view(loan_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # ================= LOAN INFO =================
    cur.execute("""
        SELECT l.*, a.appliance_name
        FROM loans l
        JOIN appliances a ON l.appliance_id = a.id
        WHERE l.id = %s
    """, (loan_id,))
    loan = cur.fetchone()

    if not loan:
        cur.close()
        conn.close()
        return "Loan not found"

    # ================= PAYMENTS =================
    cur.execute("""
        SELECT *
        FROM payments
        WHERE loan_id = %s
        ORDER BY month_no ASC
    """, (loan_id,))
    payments = cur.fetchall()

    # ================= CALCULATIONS =================
    total_paid = sum(p["paid_amount"] or 0 for p in payments)
    outstanding_balance = loan["amount"] - total_paid

    running_balance = loan["amount"]

    # ================= MONTH NAME GENERATION =================
    start_date = loan["applied_on"].replace(day=1)

    for p in payments:
        paid = p["paid_amount"] or 0
        due = p["amount_due"] or 0

        # Running balance
        p["balance"] = running_balance - paid
        running_balance = p["balance"]

        # Difference / arrears logic
        p["difference"] = paid - due

        if paid < due:
            p["arrears"] = due - paid
        else:
            p["arrears"] = 0

        # ✅ MONTH NAME (FIXED HERE — NO JINJA ERROR ANYMORE)
        month_date = start_date + relativedelta(months=p["month_no"] - 1)
        p["month_name"] = month_date.strftime("%B %Y")

    cur.close()
    conn.close()

    return render_template(
        "customer_soa.html",
        loan=loan,
        payments=payments,
        total_paid=total_paid,
        outstanding_balance=outstanding_balance
    )

@app.route("/customer/ledger")
def customer_ledger_list():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT l.id, a.appliance_name, l.amount, l.months, l.applied_on
        FROM loans l
        JOIN appliances a ON l.appliance_id = a.id
        WHERE l.user_id = %s AND l.status = 'Approved'
        ORDER BY l.applied_on DESC
    """, (user_id,))

    loans = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("customer_ledger_list.html", loans=loans)



@app.route("/test_reminder")
def test_reminder():
    auto_send_reminders()
    return "Reminder function executed!"
scheduler = BackgroundScheduler()
scheduler.add_job(func=auto_send_reminders, trigger="interval", minutes=5)
scheduler.start()
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)