"""Creates (or resets) an admin user. Run after the schema is loaded:
    python scripts/create_admin.py <username> "<display name>" <password>
Example:
    python scripts/create_admin.py admin "Site Admin" a-strong-password-here
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from app.db.session import SessionLocal
from app.db.models import User
from app.auth import hash_password


def main():
    if len(sys.argv) != 4:
        print('Usage: python scripts/create_admin.py <username> "<display name>" <password>')
        sys.exit(1)

    username, display_name, password = sys.argv[1], sys.argv[2], sys.argv[3]
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        sys.exit(1)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        hashed = hash_password(password)
        if user:
            user.password_hash = hashed
            user.role = "admin"
        else:
            user = User(username=username, display_name=display_name, password_hash=hashed, role="admin")
            db.add(user)
        db.commit()
        print(f'Admin user "{username}" is ready.')
    finally:
        db.close()


if __name__ == "__main__":
    main()
