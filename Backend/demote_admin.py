
import sys
from database import SessionLocal
from models import User

def demote_admin(email):
    db = SessionLocal()

    try:
        email = email.strip().lower()
        user = db.query(User).filter(User.email == email).first()

        if not user:
            print(f"No user found with email: {email}")
            return

        if user.role != "admin":
            print(f"This account already has the role: {user.role}")
            return

        user.role = "recruiter"
        db.commit()

        print(f"Admin access removed for {email}.")
        print("New role: recruiter")

    except Exception as e:
        db.rollback()
        print("Error:", e)

    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python demote_admin.py your_email@example.com")
    else:
        demote_admin(sys.argv[1])