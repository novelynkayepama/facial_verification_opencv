from datetime import datetime, timedelta
import MySQLdb
import yagmail

# DATABASE CONFIG
DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = ""
DB_NAME = "appliance_loan_db"

# EMAIL CONFIG
EMAIL_USER = "novelynkaye2003@gmail.com"
EMAIL_APP_PASSWORD = "ovln uzvs ldkk kxwz"

def get_upcoming_due_payments():
    conn = MySQLdb.connect(
        host=DB_HOST,
        user=DB_USER,
        passwd=DB_PASS,
        db=DB_NAME
    )
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    target_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

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
        WHERE p.status = 'pending'
          AND p.due_date = %s
          AND p.reminder_sent = 0
    """, (target_date,))

    results = cur.fetchall()
    cur.close()
    conn.close()
    return results


def send_reminders():
    payments = get_upcoming_due_payments()

    if not payments:
        print("No upcoming payments found.")
        return

    yag = yagmail.SMTP(EMAIL_USER, EMAIL_APP_PASSWORD)

    for p in payments:
        subject = "Payment Reminder – Due in 7 Days"
        body = f"""
Hello {p['full_name']},

This is a reminder that your payment for the appliance
"{p['appliance_name']}" is due on {p['due_date']}.

Amount Due: ₱{p['amount_due']:.2f}

Please make your payment on or before the due date.

Thank you,
Greater RJ
        """

        yag.send(to=p['email'], subject=subject, contents=body)
        print(f"Reminder sent to {p['email']}")

        # Mark reminder as sent
        conn = MySQLdb.connect(
            host=DB_HOST,
            user=DB_USER,
            passwd=DB_PASS,
            db=DB_NAME
        )
        cur = conn.cursor()
        cur.execute(
            "UPDATE payments SET reminder_sent = 1 WHERE id = %s",
            (p['payment_id'],)
        )
        conn.commit()
        cur.close()
        conn.close()


if __name__ == "__main__":
    send_reminders()
