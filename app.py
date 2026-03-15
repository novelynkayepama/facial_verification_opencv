from flask import Flask, render_template, request, jsonify
import cv2
import os
import numpy as np
import base64
from flask_mysqldb import MySQL
import mysql
from functools import wraps
from flask import session, redirect, url_for
from werkzeug.security import generate_password_hash
import MySQLdb.cursors
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os
from datetime import date
from dateutil.relativedelta import relativedelta
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import MySQLdb
import yagmail
from flask import Blueprint, jsonify
from flask import flash, redirect, request
from io import BytesIO
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from email.message import EmailMessage
import smtplib
import MySQLdb.cursors
import io
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

import yagmail
app = Flask(__name__)



EMAIL_USER = "novelynkaye2003@gmail.com"
EMAIL_APP_PASSWORD = "ovln uzvs ldkk kxwz"

app.secret_key = "supersecretkey"
@app.route("/test-db")
def test_db():
    cur = mysql.connection.cursor()
    cur.execute("SELECT DATABASE()")
    db = cur.fetchone()
    cur.close()
    return f"Connected to database: {db}"

import MySQLdb

def get_db_connection():
    return MySQLdb.connect(
        host="localhost",
        user="root",
        passwd="",          # XAMPP default
        db="appliance_loan_db",
        charset="utf8mb4"
    )


app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""   # default XAMPP
app.config["MYSQL_DB"] = "appliance_loan_db"
app.config["MYSQL_CURSORCLASS"] = "DictCursor"


mysql = MySQL(app)





# Admin inventory page
@app.route("/admin/appliances")
def admin_appliances():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM appliances")
    appliances = cur.fetchall()
    cur.close()
    return render_template("admin_appliances.html", appliances=appliances)

    
@app.route("/")
@app.route("/index1")
def index1():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM appliances")
    appliances = cur.fetchall()
    cur.close()

    cart = session.get("cart", {})
    cart_count = sum(cart.values())  # 👈 TOTAL quantity

    return render_template(
        "index1.html",
        appliance=appliances,
        cart_count=cart_count
    )

@app.route("/admin/edit_customer/<int:user_id>", methods=["GET", "POST"])
def edit_customer(user_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

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
        mysql.connection.commit()
        cur.close()

        flash("Customer updated successfully!", "success")
        return redirect(url_for("admin_customers"))

    cur.execute("SELECT id, full_name, email, contact_number, address FROM users WHERE id=%s", (user_id,))
    customer = cur.fetchone()
    cur.close()

    return render_template("edit_customer.html", customer=customer)

    
@app.route("/admin/delete_customer/<int:user_id>")
def delete_customer(user_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    mysql.connection.commit()
    cur.close()

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

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO users (full_name, email, contact_number, address, password, role)
        VALUES (%s, %s, %s, %s, %s, 'customer')
    """, (name, email, contact_number, address, hashed_password))
    mysql.connection.commit()
    cur.close()

    flash("Customer added successfully!", "success")
    return redirect(url_for("admin_customers"))

#BLOCK CUSTOMERS 
@app.route("/admin/block/<int:user_id>")
def block_user(user_id):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status='blocked' WHERE id=%s", (user_id,))
    conn.commit()
    return redirect("/admin/customers")
#UNBLOCK 
@app.route("/admin/unblock/<int:user_id>")
def unblock_user(user_id):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status='active' WHERE id=%s", (user_id,))
    conn.commit()
    return redirect("/admin/customers")
#GET APPLIANCES
# ---------------- Admin Dashboard ----------------
@app.route("/admin")
def admin_dashboard():
    cur = mysql.connection.cursor()
    # Get appliances
    cur.execute("SELECT * FROM appliances")
    appliances = cur.fetchall()

    # Get customers
    cur.execute("SELECT * FROM users")
    customers = cur.fetchall()

    # Get loan applications
    cur.execute("SELECT * FROM loans")
    loans = cur.fetchall()

    # Get payments
    cur.execute("SELECT * FROM payments")
    payments = cur.fetchall()

    cur.execute("SELECT * FROM orders")
    orders = cur.fetchall()

    cur.close()
    return render_template(
        "admin.html",
        appliances=appliances,
        customers=customers,
        loans=loans,
        payments=payments,
        order=orders
    )
# Add new appliance


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

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(image_path)
            image_path_db = f"uploads/appliances/{filename}"

        cur = mysql.connection.cursor()

        # 1️⃣ Insert appliance
        cur.execute("""
            INSERT INTO appliances (appliance_name, category, price, stock, image)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, category, price, stock, image_path_db))

        appliance_id = cur.lastrowid  # get inserted appliance ID

        # 2️⃣ Insert stock movement (STOCK IN)
        cur.execute("""
            INSERT INTO stock_movements (appliance_id, movement_type, quantity, reference_note)
            VALUES (%s, %s, %s, %s)
        """, (appliance_id, 'stock_in', stock, 'Initial stock added'))

        mysql.connection.commit()
        cur.close()

        flash("Appliance added successfully with stock recorded.", "success")
        return redirect(url_for("admin_appliances"))

    return render_template("admin_appliances.html")





#DELETE APPLIANCES
# Delete appliance
@app.route("/admin/appliances/delete/<int:appliance_id>")
def delete_appliance(appliance_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM appliances WHERE id = %s", (appliance_id,))
    mysql.connection.commit()
    cur.close()
    flash("Appliance deleted successfully!", "success")
    return redirect(url_for("admin_appliances"))


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrap
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrap

# 4️⃣ SIGNUP
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        contact_number = request.form.get("contact_number")
        address = request.form.get("address")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Check for empty fields
        if not full_name or not email or not password or not confirm_password or not contact_number or not address:
            return "All fields are required"

        # Check if passwords match
        if password != confirm_password:
            return "Passwords do not match"

        hashed_password = generate_password_hash(password)

        try:
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO users (full_name, email, contact_number, address, password) VALUES (%s, %s, %s, %s, %s)",
                (full_name, email, contact_number, address, hashed_password)
            )
            mysql.connection.commit()
            cur.close()

            return redirect(url_for("login"))

        except Exception as e:
            return f"Signup error: {e}"

    return render_template("signup.html")

from werkzeug.security import generate_password_hash

hashed = generate_password_hash("admin123")
print(hashed)




# 5️⃣ LOGIN

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user is None:
            flash("Email not found", "danger")
            return render_template("login.html")

        db_password = user["password"]

        # Verify the password
        if check_password_hash(db_password, password):
            # Save user info in session
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            session["role"] = user["role"]

            # Redirect based on role
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))  # Make sure this route exists
            elif user["role"] == "customer":
                return redirect(url_for("customer_dashboard"))
            else:
                flash("Your account role is not recognized.", "warning")
                return redirect(url_for("login"))

        else:
            flash("Incorrect password", "danger")
            return render_template("login.html")

    return render_template("login.html")

@app.route('/check-session')
def check_session():
    return str(session.get('user_id'))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index1"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load cascades
FACE_CASCADE = cv2.CascadeClassifier(os.path.join(BASE_DIR, "haarcascades", "haarcascade_frontalface_default.xml"))
EYE_CASCADE = cv2.CascadeClassifier(os.path.join(BASE_DIR, "haarcascades", "haarcascade_eye.xml"))

# Create uploads folder
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Blink tracking
blink_detected = False

@app.route("/")
def home():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM appliances")
    appliances = cur.fetchall()
    cur.close()

    return render_template("index1.html", appliance=appliances)

# -------- Upload ID (no redirect) --------
@app.route("/train", methods=["POST"])
def train():
    file = request.files.get("id_photo")
    if not file:
        return jsonify({"success": False, "message": "No ID uploaded."})
    id_path = os.path.join(UPLOADS_DIR, "id.jpg")
    file.save(id_path)
    return jsonify({"success": True, "message": "ID uploaded successfully."})


# -------- Blink check --------
@app.route("/blink_check", methods=["POST"])
def blink_check():
    global blink_detected
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


# -------- Verify selfie vs ID --------
UPLOADS_DIR = "static/uploads"  # Make sure this exists and is writable

@app.route("/verify", methods=["POST"])
def verify():
    global blink_detected
    if not blink_detected:
        return jsonify({"success": False, "message": "Blink not detected yet."})

    # Get selfie image
    image_data = request.form.get("image_data").split(",")[1]
    img_bytes = base64.b64decode(image_data)
    np_img = np.frombuffer(img_bytes, np.uint8)
    selfie = cv2.imdecode(np_img, cv2.IMREAD_GRAYSCALE)

    # Load uploaded ID
    id_path_temp = os.path.join(UPLOADS_DIR, "id.jpg")
    if not os.path.exists(id_path_temp):
        return jsonify({"success": False, "message": "ID not uploaded."})

    id_img = cv2.imread(id_path_temp, cv2.IMREAD_GRAYSCALE)

    # Resize to same size
    id_img = cv2.resize(id_img, (selfie.shape[1], selfie.shape[0]))

    # Compute similarity
    diff = cv2.absdiff(selfie, id_img)
    score = np.sum(diff)
    max_diff = selfie.shape[0] * selfie.shape[1] * 255
    similarity = 100 - (score / max_diff * 100)

    if similarity >= 70:
        loan = session.get("loan_data")
        if loan is None:
            return jsonify({"success": False, "message": "Loan data missing. Please apply again."})

        cur = mysql.connection.cursor()

        # 1️⃣ Insert loan
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

        mysql.connection.commit()

        loan_id = cur.lastrowid  # Get inserted loan ID

        # 2️⃣ Save ID and selfie
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

        # 3️⃣ Update loan with file paths
        cur.execute("""
            UPDATE loans
            SET id_photo_path=%s, selfie_path=%s
            WHERE id=%s
        """, (id_path, selfie_path, loan_id))

        mysql.connection.commit()

        # 🔔 Create admin notification after loan submission
        message = f"{loan['full_name']} applied for a loan on {loan['appliance_name']}"

        cur.execute("""
        INSERT INTO admin_notifications
        (user_id, payment_id, message, is_read, created_at, link, loan_id)
        VALUES (%s,%s,%s,%s,NOW(),%s,%s)
        """, (
        42,        # admin
        None,      # payment_id
        message,
        0,
        f"/admin/loan/{loan_id}",
        loan_id
        ))

        mysql.connection.commit()

        cur.close()

        # Clear session
        session.pop("loan_data", None)

        return jsonify({
            "success": True,
            "message": "✅ Face matched! Your loan has been submitted and is pending admin approval."
        })

    else:
        return jsonify({
            "success": False,
            "message": f"❌ Face does not match! Similarity: {similarity:.1f}%"
        })

@app.route("/admin/loan_details/<int:loan_id>")
def loan_details(loan_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT *, id_photo_path, selfie_path
        FROM loans
        WHERE id=%s
    """, (loan_id,))
    loan = cur.fetchone()
    cur.close()
    return render_template("admin_loan_details.html", loan=loan)



def auto_send_reminders():
    print("🔔 Auto reminder check running...")

    try:
        with app.app_context():

            cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

            # Get payments due in next 7 days and not yet paid
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
                return

            # Connect to Gmail SMTP
            yag = yagmail.SMTP(user=EMAIL_USER, password=EMAIL_APP_PASSWORD)

            for p in payments:

                days_left = (p['due_date'] - datetime.now()).days
                long_due_date = p['due_date'].strftime("%B %d, %Y")

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

                # Send email with custom sender name
                yag.send(
                    to=p['email'],
                    subject=subject,
                    contents=body,
                    headers={"From": "Greater RJ Appliance and Trading Corporation <{}>".format(EMAIL_USER)}
                )

                # Update reminder_sent_date
                update_cur = mysql.connection.cursor()
                update_cur.execute("""
                    UPDATE payments
                    SET reminder_sent_date = NOW()
                    WHERE id = %s
                """, (p['payment_id'],))
                mysql.connection.commit()
                update_cur.close()

            cur.close()
            print(f"Sent {len(payments)} reminder(s).")

    except Exception as e:
        print("Reminder Error:", e)
from flask import request, render_template

@app.route("/admin/payments")
def admin_payments():
    loan_id = request.args.get('loan_id', type=int)

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    if loan_id:
        # Fetch payments for this loan
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
            'status': 'ongoing',  # optional, compute actual
            'amount': 0,  # optional
            'paid_amount_sum': 0,
            'balance': 0,
            'payments': payments
        }])

    # Otherwise show all customers
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

    # Get payments for that customer
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
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # 1️⃣ Fetch payment details with customer info
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
            flash("Payment not found ❌", "danger")
            return redirect(request.referrer)

        # 2️⃣ Update payment status to 'paid'
        cur.execute("""
            UPDATE payments 
            SET status = 'paid', paid_at = NOW()
            WHERE id = %s
        """, (payment_id,))
        mysql.connection.commit()
        cur.close()

        # 3️⃣ Generate PDF receipt in memory
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=(300, 350))  # small receipt
        c.setFont("Helvetica-Bold", 12)
        c.drawString(20, 220, "Greater RJ Appliance and Trading Corporation")
        c.setFont("Helvetica", 10)
        c.drawString(20, 200, f"Customer: {payment['full_name']}")
        c.drawString(20, 185, f"Appliance: {payment['appliance_name']}")
        c.drawString(20, 170, f"Amount Paid: ₱{payment['amount_due']:.2f}")
        c.drawString(20, 155, f"Payment Date: {datetime.now().strftime('%B %d, %Y')}")
        c.drawString(20, 140, f"Receipt #: {payment_id}")
        c.drawString(20, 120, "Thank you for your payment!")
        c.showPage()
        c.save()
        pdf_buffer.seek(0)  # rewind buffer

        # 4️⃣ Send email with PDF receipt attached
        yag = yagmail.SMTP(EMAIL_USER, EMAIL_APP_PASSWORD)
        subject = f"Payment Receipt – {payment['appliance_name']}"
        body = f"""
Hello {payment['full_name']},

Your payment of ₱{payment['amount_due']:.2f} for "{payment['appliance_name']}" has been received.

Attached is your official receipt.

Thank you,
Greater RJ Appliance and Trading Corporation
        """
        yag.send(
                    to=p['email'],
                    subject=subject,
                    contents=body,
                    headers={"From": "Greater RJ Appliance and Trading Corporation <{}>".format(EMAIL_USER)}
                , attachments=[pdf_buffer])

        flash(f"Payment marked as paid ✅ and receipt sent to {payment['full_name']}.", "success")
        return redirect(request.referrer)

    except Exception as e:
        flash(f"Error marking payment as paid ❌: {str(e)}", "danger")
        return redirect(request.referrer)




@app.route("/admin/loans")
def admin_loans():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        UPDATE payments
        SET status = 'overdue'
        WHERE status = 'pending'
        AND due_date < %s
    """, (date.today(),))
    mysql.connection.commit()
 # 2️⃣ Get overdue payments (for notifications)
    cur.execute("""
        SELECT p.id, l.user_id, p.amount_due, p.due_date
        FROM payments p
        JOIN loans l ON p.loan_id = l.id
        WHERE p.status = 'overdue'
    """)
    overdues = cur.fetchall()

    # 3️⃣ Insert notifications
    for o in overdues:
        msg = f"Your payment of ₱{o['amount_due']:.2f} due on {o['due_date']} is OVERDUE."

        cur.execute("""
            INSERT INTO notifications (user_id, message)
            VALUES (%s, %s)
        """, (o['user_id'], msg))

    mysql.connection.commit()
    for o in overdues:
        cur.execute("""
    UPDATE payments
    SET notified = 1
    WHERE id = %s
    """, (o['id'],))

    cur.execute("""
        SELECT loans.id, loans.status, loans.amount,loans.months, users.full_name, appliances.appliance_name
        FROM loans
        JOIN users ON loans.user_id = users.id
        JOIN appliances ON loans.appliance_id = appliances.id
        ORDER BY loans.id DESC
    """)
    loans = cur.fetchall()
    cur.close()
    return render_template("admin_loans.html", loan=loans)


@app.route("/customer_loans")
def customer_loans():
    if "user_id" not in session:
        flash("Please log in first", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get all loans for this user
    cur.execute("""
        SELECT loans.id, a.appliance_name, loans.amount, loans.months, loans.status
        FROM loans 
        JOIN appliances a ON loans.appliance_id = a.id
        WHERE loans.user_id = %s
    """, (user_id,))
    loans = cur.fetchall()

    # Optionally, get payment schedule
    for loan in loans:
        cur.execute("""
            SELECT month_no, amount_due, due_date, status
            FROM payments
            WHERE loan_id=%s
            ORDER BY month_no
        """, (loan['id'],))
        loan['payments'] = cur.fetchall()

    cur.close()
    return render_template("customer_loans.html", loans=loans)



from flask import flash

@app.route("/add_to_cart/<int:appliance_id>", methods=["POST"])
def add_to_cart(appliance_id):

    if "user_id" not in session:
        flash("Please log in first", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Check if item already in cart
    cur.execute("""
        SELECT * FROM cart
        WHERE user_id = %s AND appliance_id = %s
    """, (user_id, appliance_id))

    existing = cur.fetchone()

    if existing:
        # Update quantity
        cur.execute("""
            UPDATE cart
            SET quantity = quantity + 1
            WHERE user_id = %s AND appliance_id = %s
        """, (user_id, appliance_id))

        flash("Item quantity updated in cart 🛒", "success")

    else:
        # Insert new row
        cur.execute("""
            INSERT INTO cart (user_id, appliance_id, quantity, date_added)
            VALUES (%s, %s, 1, NOW())
        """, (user_id, appliance_id))

        flash("Item successfully added to cart 🛒", "success")

    mysql.connection.commit()
    cur.close()

    return redirect(url_for("index1"))



@app.route("/cart")
def cart():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT c.appliance_id, c.quantity,
               a.appliance_name, a.price, a.image
        FROM cart c
        JOIN appliances a ON c.appliance_id = a.id
        WHERE c.user_id = %s
    """, (user_id,))

    items = cur.fetchall()
    cur.close()

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

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

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

        # Remove if quantity <= 0
        cur.execute("""
            DELETE FROM cart
            WHERE user_id = %s AND appliance_id = %s AND quantity <= 0
        """, (user_id, appliance_id))

    elif action == "remove":
        cur.execute("""
            DELETE FROM cart
            WHERE user_id = %s AND appliance_id = %s
        """, (user_id, appliance_id))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for("cart"))

@app.route("/checkout", methods=["POST"])
def checkout():

    # 1️⃣ Must be logged in
    if "user_id" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    cart = session.get("cart", {})

    if not cart:
        flash("Your cart is empty", "warning")
        return redirect(url_for("customer"))

    # 2️⃣ Fetch appliance details from DB
    ids = list(cart.keys())

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute(
        f"SELECT * FROM appliances WHERE id IN ({','.join(['%s'] * len(ids))})",
        ids
    )
    appliances = cur.fetchall()

    if not appliances:
        flash("Invalid cart items. Please try again.", "danger")
        session.pop("cart", None)
        return redirect(url_for("customer"))

    # 3️⃣ Compute total
    total_amount = 0

    for a in appliances:
        qty = cart[str(a["id"])]
        total_amount += float(a["price"]) * qty

    # 4️⃣ Insert into ORDERS table
    cur.execute("""
        INSERT INTO orders (user_id, full_name, email, total_amount, status)
        VALUES (%s, %s, %s, %s, 'pending')
    """, (
        session["user_id"],
        session.get("full_name"),
        session.get("email"),
        total_amount
    ))

    order_id = cur.lastrowid

    # 5️⃣ Insert into ORDER_ITEMS table
    for a in appliances:
        qty = cart[str(a["id"])]

        cur.execute("""
            INSERT INTO order_items
            (order_id, appliance_id, appliance_name, price, quantity)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            order_id,
            a["id"],
            a["appliance_name"],
            a["price"],
            qty
        ))

        # Optional but recommended: reduce stock
        cur.execute("""
            UPDATE appliances
            SET stock = stock - %s
            WHERE id = %s
        """, (qty, a["id"]))

    mysql.connection.commit()
    cur.close()

    # 6️⃣ Clear cart
    session.pop("cart", None)

    flash("✅ Order placed successfully!", "success")
    return redirect(url_for("index1"))




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
        cur.execute("""
            SELECT 
                a.appliance_name,
                a.category,
                oi.price,
                oi.quantity
            FROM order_items oi
            JOIN appliances a ON oi.appliance_id = a.id
            WHERE oi.order_id = %s
        """, (order["order_id"],))

        items = cur.fetchall()

        total = 0
        for item in items:
            item["subtotal"] = item["price"] * item["quantity"]
            total += item["subtotal"]

        order["items"] = items
        order["total_amount"] = total

    cur.close()
    conn.close()

    return render_template("admin_orders.html", orders=orders)












@app.route("/dashboard")
def dashboard():
    # Example: get some stats for admin dashboard
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # Example counts
    cur.execute("SELECT COUNT(*) AS total_customers FROM users")
    total_customers = cur.fetchone()["total_customers"]

    cur.execute("SELECT COUNT(*) AS total_loans FROM loans")
    total_loans = cur.fetchone()["total_loans"]

    cur.close()
    conn.close()

    return render_template("admin_dashboard.html", 
                           total_customers=total_customers,
                           total_loans=total_loans)


@app.route('/customer/dashboard')
def customer_dashboard():
    return render_template('customer_dashboard.html')

@app.route('/customer')
def customer():
    return render_template('customer.html')



 



@app.route('/admin/payment_schedule/<int:loan_id>')
def admin_payment_schedule(loan_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT * FROM payment_schedule
        WHERE loan_id = %s
        ORDER BY due_date
    """, (loan_id,))
    schedule = cursor.fetchall()

    cursor.close()
    return render_template('admin_payment_schedule.html', schedule=schedule)

@app.route('/proceed_face_verification', methods=['POST'])
def proceed_face_verification():
    session['loan_data'] = dict(request.form)
    return redirect(url_for('index'))

@app.route('/face_verified')
def face_verified():
    data = session.get('loan_data')

    cursor = mysql.connection.cursor()
    cursor.execute("""
        INSERT INTO loans (user_id, appliance_id, amount, status)
        VALUES (%s, %s, %s, 'Pending')
    """, (
        session['user_id'],
        data['appliance_id'],
        data['price']
    ))
    mysql.connection.commit()
    cursor.close()

    flash("Loan application submitted successfully!", "success")
    return redirect(url_for('customer_dashboard'))

@app.route("/verify")
def index():
    return render_template("verify.html")

@app.route("/apply-loan/<int:appliance_id>", methods=["GET"])
def apply_loan(appliance_id):
    if "user_id" not in session:
        flash("Please log in first", "danger")
        return redirect(url_for("login"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM appliances WHERE id = %s", (appliance_id,))
    appliance = cur.fetchone()
    cur.close()

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

    # Get form data
    appliance_id = int(request.form["appliance_id"])
    months = int(request.form["months"])
    amount = float(request.form["amount"])
    full_name = request.form["full_name"]
    email = request.form["email"]
    mobile = request.form["mobile"]
    occupation = request.form["occupation"]
    salary = float(request.form["salary"])

    # Fetch appliance details from DB
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT appliance_name, category FROM appliances WHERE id = %s", (appliance_id,))
    appliance = cur.fetchone()
    cur.close()

    if not appliance:
        flash("Appliance not found.", "danger")
        return redirect(url_for("customer_dashboard"))

    # Store all loan data in session for facial verification
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
    return redirect(url_for("verify"))  # Page with facial verification




@app.route("/loan-face-success")
def loan_face_success():
    if "loan_data" not in session:
        flash("Loan session expired", "danger")
        return redirect(url_for("index1"))

    data = session.pop("loan_data")
    user_id = session["user_id"]

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO loans (user_id, appliance_id, amount, installment_months, status)
        VALUES (%s, %s, %s, %s, 'Pending')
    """, (
        user_id,
        data["appliance_id"],
        data["amount"],
        data["months"]
    ))

    mysql.connection.commit()
    cur.close()

    flash("Loan application submitted successfully!", "success")
    return redirect(url_for("index1"))






@app.route("/approve_loan/<int:loan_id>", methods=["POST"])
def approve_loan(loan_id):
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # 1️⃣ Get the loan + user info + appliance name
        cur.execute("""
            SELECT l.*, u.full_name, u.email, a.appliance_name
            FROM loans l
            JOIN users u ON l.user_id = u.id
            JOIN appliances a ON l.appliance_id = a.id
            WHERE l.id = %s
        """, (loan_id,))
        loan = cur.fetchone()

        if not loan:
            flash("Loan not found.", "danger")
            return redirect(url_for("admin_loans"))

        if loan['status'] == 'Approved':
            flash("Loan is already approved.", "info")
            return redirect(url_for("admin_loans"))

        # 2️⃣ Check appliance stock
        cur.execute("SELECT stock FROM appliances WHERE id=%s", (loan['appliance_id'],))
        appliance = cur.fetchone()

        if not appliance:
            flash("Appliance not found.", "danger")
            return redirect(url_for("admin_loans"))

        if appliance['stock'] <= 0:
            flash("Insufficient stock to approve this loan.", "danger")
            return redirect(url_for("admin_loans"))

        # 3️⃣ Update loan status to Approved
        cur.execute("UPDATE loans SET status='Approved' WHERE id=%s", (loan_id,))

        # 4️⃣ Reduce appliance stock by 1
        quantity = 1  # If later you support multiple quantity, change this
        new_stock = appliance['stock'] - quantity

        cur.execute("""
            UPDATE appliances
            SET stock=%s
            WHERE id=%s
        """, (new_stock, loan['appliance_id']))

        # 4️⃣.5️⃣ INSERT STOCK MOVEMENT RECORD (🔥 NEW ADDITION)
        cur.execute("""
    INSERT INTO stock_movements
        (appliance_id, movement_type, quantity, reference_note, movement_date)
    VALUES (%s, 'OUT', %s, %s, NOW())
    """, (
    loan['appliance_id'],
    quantity,
    f"Loan Approved (Loan ID: {loan_id})"
    ))

        # 5️⃣ Delete any existing payment schedule (prevents duplicates)
        cur.execute("DELETE FROM payments WHERE loan_id=%s", (loan_id,))

        # 6️⃣ Generate payment schedule
        amount = float(loan['amount'])
        months = int(loan['months'])
        monthly_payment = round(amount / months, 2)
        start_date = date.today()

        for i in range(1, months + 1):
            due_date = start_date + relativedelta(months=i)

            cur.execute("""
                INSERT INTO payments (loan_id, month_no, amount_due, due_date, status)
                VALUES (%s, %s, %s, %s, 'not_paid')
            """, (loan['id'], i, monthly_payment, due_date))

        # 7️⃣ Commit all changes
        mysql.connection.commit()

        # 8️⃣ SEND EMAIL NOTIFICATION
        yag = yagmail.SMTP(EMAIL_USER, EMAIL_APP_PASSWORD)

        subject = "Loan Application Approved 🎉"
        body = f"""
Hello {loan['full_name']},

Good news! 🎉

Your loan application for:
Appliance: {loan['appliance_name']}

Has been APPROVED.

Loan Amount: ₱{loan['amount']:.2f}
Months to Pay: {loan['months']}

Your payment schedule has been generated and is available in your account dashboard.

Thank you for choosing Greater RJ Appliance and Trading Corporation.
        """

        yag.send(to=loan['email'], subject=subject, contents=body,
                    headers={"From": "Greater RJ Appliance and Trading Corporation <{}>".format(EMAIL_USER)}
                )

        cur.close()

        flash("Loan approved, stock updated, movement logged, payment schedule created, and email sent!", "success")
        return redirect(url_for("admin_loans"))

    except Exception as e:
        return f"Error approving loan: {str(e)}"

import qrcode
from io import BytesIO
from flask import send_file

@app.route("/generate_qr/<int:payment_id>")
def generate_qr(payment_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT amount_due FROM payments WHERE id=%s", (payment_id,))
    payment = cur.fetchone()
    cur.close()

    if not payment:
        return "Payment not found", 404

    amount = payment['amount_due']

    # Format the QR text (for GCash / Instapay)
    # You can customize based on your preferred format
    qr_text = f"GCash Payment\nAmount: {amount:.2f}\nReference: Payment#{payment_id}"

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=2
    )
    qr.add_data(qr_text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)

    return send_file(buf, mimetype='image/png')

@app.route("/deny_loan/<int:loan_id>", methods=["POST"])
def deny_loan(loan_id):
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Get loan + user info
        cur.execute("""
            SELECT l.*, u.full_name, u.email, a.appliance_name
            FROM loans l
            JOIN users u ON l.user_id = u.id
            JOIN appliances a ON l.appliance_id = a.id
            WHERE l.id = %s
        """, (loan_id,))
        loan = cur.fetchone()

        if not loan:
            return "Loan not found", 404

        # Update status
        cur.execute("UPDATE loans SET status = 'Denied' WHERE id = %s", (loan_id,))
        mysql.connection.commit()

        # 📧 SEND EMAIL
        yag = yagmail.SMTP(EMAIL_USER, EMAIL_APP_PASSWORD)

        subject = "Loan Application Update"
        body = f"""
Hello {loan['full_name']},

We regret to inform you that your loan application for:

Appliance: {loan['appliance_name']}

Has been DENIED.

If you have questions, please contact our office.

Thank you,
Greater RJ Appliance and Trading Corporation
        """

        yag.send(to=loan['email'], subject=subject, contents=body,
                    headers={"From": "Greater RJ Appliance and Trading Corporation <{}>".format(EMAIL_USER)})

        cur.close()
        return redirect(url_for("admin_loans"))

    except Exception as e:
        return f"Error denying loan: {str(e)}"



from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
import MySQLdb.cursors


@app.route('/payments')
def payments():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch loans
    cur.execute("""
        SELECT * FROM loans
        WHERE user_id=%s
    """, (user_id,))
    loans = cur.fetchall()

    for loan in loans:
        # Fetch payments per loan
        cur.execute("""
            SELECT *
            FROM payments
            WHERE loan_id=%s
            ORDER BY month_no ASC
        """, (loan['id'],))
        loan['payments'] = cur.fetchall()

        # Calculate total paid from DB values
        cur.execute("""
            SELECT SUM(paid_amount) as total_paid
            FROM payments
            WHERE loan_id=%s
        """, (loan['id'],))
        total = cur.fetchone()
        loan['paid_amount_sum'] = total['total_paid'] or 0

        loan['balance'] = float(loan['amount']) - float(loan['paid_amount_sum'])

    cur.close()

    return render_template("payments.html", loans=loans)
# Update a specific payment from admin panel
@app.route('/update_partial_payments/<int:user_id>', methods=['POST'])
def update_partial_payments(user_id):
    payment_id = request.form.get('update_payment')
    if not payment_id:
        flash("No payment selected.", "danger")
        return redirect(url_for('view_customer_payments', user_id=user_id))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM payments WHERE id=%s", (payment_id,))
    payment = cur.fetchone()
    if not payment:
        cur.close()
        flash("Payment not found.", "danger")
        return redirect(url_for('view_customer_payments', user_id=user_id))

    try:
        paid_amount = float(request.form.get(f"paid_{payment_id}", 0))
    except:
        cur.close()
        flash("Invalid payment amount.", "danger")
        return redirect(url_for('view_customer_payments', user_id=user_id))

    # Base original_amount_due
    amount_due = float(payment['original_amount_due'])
    overpayment = max(paid_amount - amount_due, 0)
    arrears = max(amount_due - paid_amount, 0)

    # Determine status
    if paid_amount >= amount_due:
        status = 'paid'
        paid_at = datetime.now()
        payment_type = "Paid in Full ✅"
    elif paid_amount > 0:
        status = 'Insufficient payment.'
        paid_at = None
        payment_type = "Partial Payment ⚠️"
    else:
        status = 'not_paid'
        paid_at = None
        payment_type = "Not Paid ❌"

    # Update current payment
    cur.execute("""
        UPDATE payments
        SET paid_amount=%s, status=%s, arrears=%s, paid_at=%s
        WHERE id=%s
    """, (paid_amount, status, arrears, paid_at, payment_id))

    # Adjust next month payment
    cur.execute("SELECT * FROM payments WHERE loan_id=%s AND month_no=%s",
                (payment['loan_id'], payment['month_no'] + 1))
    next_payment = cur.fetchone()
    next_due_msg = ""

    if next_payment:
        next_due = float(next_payment['original_amount_due']) + arrears - overpayment
        next_due = max(next_due, 0)

        cur.execute("UPDATE payments SET amount_due=%s WHERE id=%s",
                    (next_due, next_payment['id']))

        next_due_msg = f"\nNext Month's Adjusted Due: ₱{next_due:.2f}"

    mysql.connection.commit()
    cur.close()

    # ===== SEND SMART EMAIL =====
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cur.execute("""
            SELECT u.full_name, u.email, a.appliance_name
            FROM loans l
            JOIN users u ON l.user_id = u.id
            JOIN appliances a ON l.appliance_id = a.id
            WHERE l.id = %s
        """, (payment['loan_id'],))

        info = cur.fetchone()
        cur.close()

        if info:

            # ===== PDF RECEIPT =====
            pdf_buffer = io.BytesIO()
            c = canvas.Canvas(pdf_buffer, pagesize=(400, 420))

            receipt_no = f"RJ-{int(payment_id):06d}"
            today = datetime.now().strftime("%B %d, %Y")
            due_date = payment['due_date'].strftime("%B %d, %Y")

            # Border
            c.rect(10, 10, 380, 400, stroke=1, fill=0)

            # Header
            c.setFont("Helvetica-Bold", 12)
            c.drawCentredString(200, 380, "GREATER RJ Appliance & Trading Corp")

            c.setFont("Helvetica-Bold", 11)
            c.drawCentredString(200, 365, "OFFICIAL RECEIPT")

            c.line(20, 355, 380, 355)

            # Receipt info
            c.setFont("Helvetica", 10)
            c.drawString(20, 335, f"Receipt No : {receipt_no}")
            c.drawString(20, 320, f"Date       : {today}")

            # Customer
            c.drawString(20, 295, f"Customer   : {info['full_name'].upper()}")
            c.drawString(20, 280, f"Appliance  : {info['appliance_name'].upper()}")

            c.drawString(20, 255, f"Due Date   : {due_date}")

            c.line(20, 245, 380, 245)

            # Amounts
            c.drawString(20, 225, f"Amount Due : ₱{amount_due:,.2f}")
            c.drawString(20, 210, f"Amount Paid: ₱{paid_amount:,.2f}")

            # Status
            if status == "paid":
                receipt_status = "FULLY PAID"
            elif paid_amount > 0:
                receipt_status = "PARTIAL PAYMENT"
            else:
                receipt_status = "NOT PAID"

            c.drawString(20, 190, f"Status     : {receipt_status}")

            c.line(20, 180, 380, 180)

            c.setFont("Helvetica-Oblique", 9)
            c.drawString(20, 160, "Thank you for your payment!")

            c.showPage()
            c.save()
            pdf_buffer.seek(0)

            # Email body
            body = f"""
Hello {info['full_name']},

Your payment of ₱{paid_amount:.2f} for "{info['appliance_name']}" has been received.
Payment Status: {payment_type}
{next_due_msg}

Attached is your official receipt.

Thank you,
Greater RJ Appliance and Trading Corporation
            """

            yag = yagmail.SMTP(EMAIL_USER, EMAIL_APP_PASSWORD)

            yag.send(
                to=info['email'],
                subject=f"Payment Update – {info['appliance_name']}",
                contents=body,
                headers={"From": f"Greater RJ Appliance and Trading Corporation <{EMAIL_USER}>"},
                attachments=[pdf_buffer]
            )

    except Exception as e:
        print("Error sending email:", e)

    flash("Payment updated successfully and notification sent ✅.", "success")
    return redirect(url_for('view_customer_payments', user_id=user_id))



from datetime import datetime, timedelta

def send_due_payment_reminders():
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)
    
    # Get loans with payments due in 7 days
    upcoming_date = (datetime.now() + timedelta(days=7)).date()
    cur.execute("""
        SELECT l.user_id, l.loan_id, l.due_date
        FROM loans l
        WHERE l.due_date = %s
    """, (upcoming_date,))
    
    loans = cur.fetchall()
    for loan in loans:
        message = f"Reminder: Your payment for Loan #{loan['loan_id']} is due on {loan['due_date']}."
        create_notification(loan['user_id'], message)
    
    cur.close()
    conn.close()



@app.route("/customer/history")
def customer_history():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # =========================
    # GET LOANS
    # =========================
    cur.execute("""
        SELECT l.*, a.appliance_name
        FROM loans l
        JOIN appliances a ON l.appliance_id = a.id
        WHERE l.user_id = %s
        ORDER BY l.created_at DESC
    """, (user_id,))
    loans = cur.fetchall()

    # =========================
    # GET PAYMENTS PER LOAN
    # =========================
    for loan in loans:
        cur.execute("""
            SELECT month_no, amount_due, due_date, status
            FROM payments
            WHERE loan_id = %s
            ORDER BY month_no ASC
        """, (loan["id"],))
        
        payments = cur.fetchall()

        # ✅ Convert due_date to Long Date Format
        for p in payments:
            if p["due_date"]:
                p["due_date"] = p["due_date"].strftime("%B %d, %Y")

        loan["payments"] = payments

        # =========================
        # CALCULATE PAID & BALANCE
        # =========================
        paid = sum(
            float(p["amount_due"])
            for p in payments
            if p["status"] == "paid"
        )

        loan["paid"] = paid
        loan["balance"] = float(loan["amount"]) - paid

    # =========================
    # GET ORDERS
    # =========================
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
        """, (order["order_id"],))
        order["items"] = cur.fetchall()

    cur.close()

    return render_template(
        "customer_history.html",
        loans=loans,
        orders=orders
    )

def get_appliances():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT *
        FROM appliances
        WHERE status = 'Available' AND stock > 0
        ORDER BY created_at DESC
    """)
    appliances = cur.fetchall()
    cur.close()
    return appliances

@app.route("/appliances")
def appliances_iframe():
    appliances = get_appliances()
    return render_template("appliances_center.html", appliances=appliances)

@app.context_processor
def inject_cart_count():
    if "user_id" in session:
        user_id = session["user_id"]
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("""
            SELECT SUM(quantity) AS total_qty 
            FROM cart
            WHERE user_id = %s
        """, (user_id,))
        result = cur.fetchone()
        cur.close()

        # If user has no cart items, show 0
        count = result["total_qty"] if result and result["total_qty"] else 0
    else:
        count = 0

    return dict(cart_count=count)

@app.route("/cart/count")
def cart_count_route():
    cart = session.get("cart", {})
    return {"count": sum(cart.values())}

@app.route("/customer/apply-loan")
def apply_loan_page():
    if "user_id" not in session:
        flash("Please log in first", "danger")
        return redirect(url_for("login"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM appliances WHERE status='Available' AND stock > 0")
    appliances = cur.fetchall()
    cur.close()

    return render_template("apply_loan.html", appliances=appliances)


@app.route("/orders")
def customer_orders():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]  # ✅ FIX

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # Get orders of this customer
    cur.execute("""
        SELECT order_id, total_amount, status, created_at
        FROM orders
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))
    orders = cur.fetchall()

    # Attach items per order
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



@app.route("/payments")
def customer_payments():
    if "user_id" not in session:
        flash("Please log in first", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get loans for the user
    cur.execute("""
        SELECT l.*, a.appliance_name
        FROM loans l
        JOIN appliances a ON l.appliance_id = a.id
        WHERE l.user_id = %s
        ORDER BY l.created_at DESC
    """, (user_id,))
    loans = cur.fetchall()

    # Get payments for each loan
    for loan in loans:
        cur.execute("""
            SELECT id, month_no, amount_due, due_date, status, payment_proof
            FROM payments
            WHERE loan_id = %s
            ORDER BY month_no ASC
        """, (loan["id"],))
        loan["payments"] = cur.fetchall()

        # Calculate paid & balance
        paid = sum(
            p["amount_due"] for p in loan["payments"] 
            if p["status"] == "paid"
        )
        loan["paid"] = paid
        loan["balance"] = loan["amount"] - paid

    cur.close()
    return render_template("payments.html", loans=loans)

@app.route("/admin/stock_movements/<int:appliance_id>")
def appliance_stock_movements(appliance_id):

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT sm.*, a.appliance_name
        FROM stock_movements sm
        JOIN appliances a ON sm.appliance_id = a.id
        WHERE sm.appliance_id = %s
        ORDER BY sm.movement_date DESC
    """, (appliance_id,))

    movements = cur.fetchall()
    cur.close()

    return render_template("stock_movements.html", movements=movements)

@app.route("/admin/edit_appliance/<int:appliance_id>", methods=["GET", "POST"])
def edit_appliance(appliance_id):

    if "user_id" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch appliance
    cur.execute("SELECT * FROM appliances WHERE id = %s", (appliance_id,))
    appliance = cur.fetchone()

    if not appliance:
        flash("Appliance not found", "error")
        return redirect(url_for("admin_appliances"))

    if request.method == "POST":
        name = request.form["appliance_name"]
        category = request.form["category"]
        price = request.form["price"]
        new_stock = int(request.form["stock"])
        image = request.files.get("image")

        image_path_db = appliance["image"]  # keep old image

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(image_path)
            image_path_db = f"uploads/appliances/{filename}"

        old_stock = appliance["stock"]
        difference = new_stock - old_stock

        # Update appliance
        cur.execute("""
            UPDATE appliances
            SET appliance_name=%s,
                category=%s,
                price=%s,
                stock=%s,
                image=%s
            WHERE id=%s
        """, (name, category, price, new_stock, image_path_db, appliance_id))

        # 🔥 RECORD STOCK MOVEMENT
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

        mysql.connection.commit()
        cur.close()

        flash("Appliance updated successfully", "success")
        return redirect(url_for("admin_appliances"))

    cur.close()
    return render_template("edit_appliance.html", appliance=appliance)


@app.route("/admin/inventory-report")
def inventory_report():
    conn = get_db_connection()
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Get selected category from GET parameters
    selected_category = request.args.get("category", "")
    
    # Get all unique categories for the dropdown
    cur.execute("SELECT DISTINCT category FROM appliances ORDER BY category")
    categories = cur.fetchall()  # list of dicts: [{'category': 'Refrigerator'}, ...]
    
    # Get appliances filtered by category if selected
    if selected_category:
        cur.execute("SELECT * FROM appliances WHERE category = %s ORDER BY appliance_name", (selected_category,))
    else:
        cur.execute("SELECT * FROM appliances ORDER BY appliance_name")
    appliances = cur.fetchall()
    
    # Get stock movements for each appliance
    for a in appliances:
        cur.execute("""
            SELECT movement_date, movement_type, quantity, reference_note
            FROM stock_movements
            WHERE appliance_id = %s
            ORDER BY movement_date DESC
        """, (a['id'],))
        a['movements'] = cur.fetchall()
    
    cur.close()
    
    return render_template(
        'inventory_report.html',
        appliances=appliances,
        categories=categories,
        selected_category=selected_category,
        generated_at=datetime.now()
    )


    






@app.route("/admin/reports/loan_decisions", methods=["GET", "POST"])
def report_loan_decisions():
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    status = request.args.get("status")  # NEW: filter by status

    # Base query
    query = """
        SELECT l.id, l.user_id, u.full_name, a.appliance_name, l.amount, l.months, l.status, l.applied_on
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

    if status in ["Approved", "Pending", "Denied"]:
        query += " AND l.status = %s"
        params.append(status)

    query += " ORDER BY l.applied_on DESC"

    cur.execute(query, params)
    loans = cur.fetchall()  # renamed to plural for clarity

    # Calculate summary totals
    approved_count = sum(1 for l in loans if l["status"].strip().lower() == "approved")
    denied_count   = sum(1 for l in loans if l["status"].strip().lower() == "denied")
    pending_count  = sum(1 for l in loans if l['status'].strip().lower() == "pending")

    cur.close()
    conn.close()

    return render_template(
        "admin_reports_loan_decisions.html",
        loans=loans,  # send filtered loans
        from_date=from_date,
        to_date=to_date,
        selected_status=status,  # for keeping dropdown selected
        approved_count=approved_count,
        denied_count=denied_count,
        pending_count=pending_count
    )
from datetime import datetime
import MySQLdb.cursors

@app.route("/admin/reports/customers")
def report_customers():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT id, full_name, email, contact_number, address, status, created_at
        FROM users
        WHERE role = 'customer'
        ORDER BY created_at DESC
    """)
    customers = cur.fetchall()
    cur.close()

    generated_at = datetime.now().strftime("%B %d, %Y %I:%M %p")

    return render_template(
        "report_customers.html",
        customers=customers,
        generated_at=generated_at
    )


@app.route("/admin/order_receipt/<int:order_id>")
def order_receipt(order_id):
    cur = mysql.connection.cursor()
    
    # Fetch order details
    cur.execute("""
        SELECT o.user_id, o.user_id, o.total_amount, o.status, o.created_at, 
               u.full_name, u.email
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.order_id = %s
    """, (order_id,))
    order = cur.fetchone()
    
    if not order or order['status'] != 'Approved':
        flash("Order is not approved yet!", "error")
        return redirect(url_for('admin_orders'))
    
    # Fetch order items
    cur.execute("""
        SELECT appliance_name, price, quantity, (price * quantity) as subtotal
        FROM order_items
        WHERE order_id = %s
    """, (order_id,))
    items = cur.fetchall()
    
    cur.close()
    
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

    if customer:
        query += " WHERE u.full_name LIKE %s"
        cur.execute(query + " ORDER BY u.full_name, p.due_date",
                    (f"%{customer}%",))
    else:
        cur.execute(query + " ORDER BY u.full_name, p.due_date")

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

            # 🔴 ARREARS CALCULATION
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

    # balance
    for loan in loans_dict.values():
        loan["balance"] = loan["amount"] - loan["total_paid"]

    loans = list(loans_dict.values())

    return render_template(
        "admin_payment_transactions.html",
        loans=loans
    )



from collections import defaultdict
from datetime import datetime

@app.route("/admin/reports/monthly_sales", methods=["GET"])
def admin_reports_monthly_sales():
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # Get filter values
    month_str = request.args.get("month", datetime.now().strftime("%Y-%m"))
    category_filter = request.args.get("category", "")

    try:
        year, month = map(int, month_str.split("-"))
    except:
        year, month = datetime.now().year, datetime.now().month

    # Monthly appliance report: only approved loans
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
          AND (MONTH(p.due_date) = %s AND YEAR(p.due_date) = %s OR p.id IS NULL)
    """
    params = [month, year]

    # Apply category filter if selected
    if category_filter:
        query += " AND a.category = %s"
        params.append(category_filter)

    query += " GROUP BY a.id ORDER BY stocks_released DESC, a.appliance_name ASC"
    cur.execute(query, tuple(params))
    reports = cur.fetchall()

    # Compute grand totals
    grand_total_collected = sum(r['total_collected'] for r in reports)
    grand_total_loan = sum(r['total_loan'] for r in reports)
    grand_total_stocks = sum(r['stocks_released'] for r in reports)

    # Categories for filter dropdown
    cur.execute("SELECT DISTINCT category FROM appliances ORDER BY category ASC")
    categories = cur.fetchall()

    # Yearly collected data per month (only approved loans)
    yearly_data = defaultdict(float)
    for m in range(1, 13):
        yearly_query = """
            SELECT SUM(COALESCE(p.paid_amount,0)) AS total_collected
            FROM loans l
            JOIN appliances a ON l.appliance_id = a.id
            LEFT JOIN payments p ON p.loan_id = l.id
            WHERE l.status = 'Approved'
              AND MONTH(p.due_date)=%s AND YEAR(p.due_date)=%s
        """
        params_yearly = [m, year]
        if category_filter:
            yearly_query += " AND a.category=%s"
            params_yearly.append(category_filter)

        cur.execute(yearly_query, tuple(params_yearly))
        result = cur.fetchone()
        yearly_data[m] = result['total_collected'] if result['total_collected'] else 0

    cur.close()
    conn.close()

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

@app.route("/reports/order_receipts")
def order_receipts_report():
    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # Fetch all approved orders with customer info
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

# --- Reminder functions ---
def get_upcoming_due_payments(user_id=None):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

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
    return results



@app.route("/account/security", methods=["GET", "POST"])
def account_security():
    user_id = session.get('user_id')  # Assuming you store logged-in user ID in session
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # Fetch current password hash
        cur.execute("SELECT password FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()

        if not check_password_hash(user['password'], current_password):
            flash("Current password is incorrect.", "error")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "error")
        else:
            hashed = generate_password_hash(new_password)
            cur.execute("UPDATE users SET password = %s WHERE id = %s", (hashed, user_id))
            conn.commit()
            flash("Password successfully updated!", "success")
            return redirect(url_for('account_security'))

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
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

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

    if not loan:
        flash("Loan not found", "danger")
        return redirect(url_for('admin_loans'))

    # Render the details page
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

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

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

    return jsonify(notifications)

@app.route('/admin/notifications/mark_all_read', methods=['POST'])
def mark_all_notifications_read():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    admin_id = session['user_id']

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE admin_notifications
        SET is_read = 1
        WHERE user_id = %s AND is_read = 0
    """, (admin_id,))
    mysql.connection.commit()
    cur.close()

    return jsonify({"success": True})


@app.route('/admin/notifications/delete/<int:notification_id>')
def delete_notification(notification_id):

    if 'user_id' not in session or session['user_id'] != 42:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    cur.execute("""
        DELETE FROM admin_notifications
        WHERE id = %s AND user_id = %s
    """, (notification_id, 42))

    mysql.connection.commit()
    cur.close()

    return '', 204
@app.route("/upload_payment/<int:payment_id>", methods=["POST"])
def upload_payment(payment_id):
    # Check if a file was uploaded
    if 'payment_screenshot' not in request.files:
        flash("No file uploaded.", "danger")
        return redirect(request.referrer)

    file = request.files['payment_screenshot']

    if file.filename == '':
        flash("No selected file.", "danger")
        return redirect(request.referrer)

    # Save the uploaded file
    filename = secure_filename(file.filename)
    filepath = os.path.join('static/uploads', filename)
    file.save(filepath)

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # 1️⃣ Update payment record with uploaded proof
    cur.execute("""
        UPDATE payments
        SET payment_proof = %s
        WHERE id = %s
    """, (filename, payment_id))

    # 2️⃣ Get payment + user + appliance info (include user_id!)
    cur.execute("""
        SELECT 
            p.id,
            p.loan_id,
            p.due_date,
            u.id AS user_id,        -- important fix
            u.full_name,
            a.appliance_name
        FROM payments p
        JOIN loans l ON p.loan_id = l.id
        JOIN users u ON l.user_id = u.id
        JOIN appliances a ON l.appliance_id = a.id
        WHERE p.id = %s
    """, (payment_id,))

    info = cur.fetchone()

    if info:
        # Prepare notification message
        message = f"Payment proof uploaded by {info['full_name']} for {info['appliance_name']} (Due {info['due_date'].strftime('%B %d, %Y')})"

        # 3️⃣ Insert notification for admin
        cur.execute("""
            INSERT INTO admin_notifications (user_id, payment_id, message, link, is_read, created_at)
            VALUES (%s, %s, %s, %s, 0, NOW())
        """, (
            42,  # admin user ID
            payment_id,
            message,
            f"/admin/payments/{info['user_id']}/view"  # link to admin_customer_payments
        ))

    # Commit changes and close cursor
    mysql.connection.commit()
    cur.close()

    flash("Payment proof uploaded successfully!", "success")
    return redirect(request.referrer)

@app.route('/debug-session')
def debug_session():
    return f"Logged in user_id: {session.get('user_id')}"

@app.route('/admin/customer_ledger')
def customer_ledger():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    admin_id = session['user_id']

    search_query = request.args.get('q', '').strip()  # get search term

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    base_sql = """
        SELECT 
            u.full_name AS customer_name,
            a.appliance_name,
            l.amount AS total_amount,
            IFNULL(SUM(p.paid_amount), 0) AS total_payments,
            l.amount - IFNULL(SUM(p.paid_amount), 0) AS balance
        FROM loans l
        JOIN users u ON l.user_id = u.id
        JOIN appliances a ON l.appliance_id = a.id
        LEFT JOIN payments p ON p.loan_id = l.id
    """

    if search_query:
        # filter by customer name or appliance name
        base_sql += " WHERE u.full_name LIKE %s OR a.appliance_name LIKE %s"

        cur.execute(base_sql + " GROUP BY l.id ORDER BY u.full_name, a.appliance_name",
                    ('%' + search_query + '%', '%' + search_query + '%'))
    else:
        cur.execute(base_sql + " GROUP BY l.id ORDER BY u.full_name, a.appliance_name")

    ledger = cur.fetchall()
    cur.close()

    return render_template('customer_ledger.html', ledger=ledger, search_query=search_query)

@app.route("/test_reminder")
def test_reminder():
    auto_send_reminders()
    return "Reminder function executed!"
scheduler = BackgroundScheduler()
scheduler.add_job(func=auto_send_reminders, trigger="interval", hours=24)
scheduler.start()
if __name__ == "__main__":
    import os
    app.run(
        host="0.0.0.0",                     # allow external access
        port=int(os.environ.get("PORT", 5000)),  # use Render's port
        debug=True
    )   
