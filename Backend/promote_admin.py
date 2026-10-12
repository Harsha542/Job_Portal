
import argparse
import getpass

from database import SessionLocal
from models import User


def main():
    parser = argparse.ArgumentParser(
        description="Promote an existing account to administrator."
    )
    parser.add_argument(
        "email",
        help="Email address of the existing account",
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    confirmation = input(
        f"Promote {email} to admin? Type YES to confirm: "
    )

    if confirmation != "YES":
        print("Cancelled.")
        return

    db = SessionLocal()

    try:
        user = db.query(User).filter(User.email == email).first()

        if user is None:
            print("Account not found. Register the account first.")
            return

        user.role = "admin"
        db.commit()

        print(f"Account {user.email} is now an administrator.")
        print("Sign in again to refresh your access token and role.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()