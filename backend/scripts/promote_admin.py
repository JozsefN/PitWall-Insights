"""Promote a uniquely identified existing account in the configured database."""
from argparse import ArgumentParser
from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select

from modules.identity_auth.application.security import hash_password
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.storage.infrastructure.db import SessionLocal


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--create", action="store_true", help="Create a new administrator with an interactive password.")
    args = parser.parse_args()
    try:
        email = TypeAdapter(EmailStr).validate_python(args.email).lower()
    except ValidationError:
        parser.exit(1, "Enter a valid email address.\n")
    with SessionLocal() as db:
        accounts = db.scalars(select(UserRecord).where(func.lower(UserRecord.email) == email).with_for_update()).all()
        if args.create:
            if accounts:
                parser.exit(1, "That account already exists. Use the promotion command for an existing account.\n")
            password = getpass("New administrator password: ")
            if not 12 <= len(password.encode()) <= 72 or password != getpass("Confirm password: "):
                parser.exit(1, "Passwords must match and contain 12–72 bytes.\n")
            db.add(UserRecord(email=email, password_hash=hash_password(password), role="admin"))
        elif len(accounts) == 1:
            accounts[0].role = "admin"
        else:
            parser.exit(1, "An existing account must match the email exactly once.\n")
        db.commit()
    print(f"Administrator role assigned to {email}.")


if __name__ == "__main__":
    main()
