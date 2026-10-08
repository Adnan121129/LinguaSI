"""LinguaSI command-line tools.

python -m app.cli seed                      # load / refresh curated content (idempotent)
python -m app.cli create-admin --email you@example.com --name "Your Name"
python -m app.cli demo [--reset] [--days 28] # create the demo learner with weeks of history
python -m app.cli status                    # configuration and database summary
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.models import Profile, User, VocabularyItem
from app.seed.demo import create_demo_learner
from app.seed.loader import load_all


def cmd_seed(_: argparse.Namespace) -> int:
    with SessionLocal() as db:
        counts = load_all(db)
    print("Seed content loaded:")
    for name, n in counts.items():
        print(f"  {name:<20} {n}")
    return 0


def cmd_create_admin(args: argparse.Namespace) -> int:
    email = args.email.strip().lower()
    password = args.password or os.environ.get("LINGUASI_ADMIN_PASSWORD")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is not None:
            user.role = "admin"
            user.is_active = True
            if password:
                user.password_hash = hash_password(password)
            db.commit()
            print(f"{email} is now an admin.")
            return 0
        if not password:
            password = getpass.getpass("Password for the new admin (min 8 characters): ")
        if len(password) < 8:
            print("Password must be at least 8 characters.", file=sys.stderr)
            return 1
        user = User(email=email, name=args.name, password_hash=hash_password(password), role="admin", is_active=True)
        user.profile = Profile(onboarding_completed=True, goal="ielts")
        db.add(user)
        db.commit()
    print(f"Admin account created for {email}.")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    with SessionLocal() as db:
        if (db.scalar(select(func.count(VocabularyItem.id))) or 0) == 0:
            load_all(db)
        try:
            report = create_demo_learner(db, reset=args.reset, days=args.days)
        except AppError as exc:
            print(exc.message, file=sys.stderr)
            return 1
    print(f"Demo learner ready after replaying {report.days} days of activity:")
    for name, n in sorted(report.actions.items()):
        print(f"  {name:<22} {n}")
    print(f"\nSign in with  {report.email}  /  {report.password}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    print(f"Environment:     {settings.environment}")
    print(f"AI provider:     {settings.effective_ai_provider} (configured: {settings.ai_provider}, mock mode: {settings.ai_is_mock})")
    print(f"Models:          fast={settings.model_for_tier('fast')} strong={settings.model_for_tier('strong')}")
    print(f"Speech:          stt={settings.effective_stt_provider} tts={settings.effective_tts_provider}")
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            users = db.scalar(select(func.count(User.id))) or 0
            words = db.scalar(select(func.count(VocabularyItem.id))) or 0
        print(f"Database:        connected ({users} users, {words} vocabulary items)")
    except Exception as exc:  # noqa: BLE001 - report any connection problem to the operator
        print(f"Database:        NOT reachable ({exc.__class__.__name__})")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="LinguaSI management commands")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Load or refresh curated seed content").set_defaults(func=cmd_seed)
    admin = sub.add_parser("create-admin", help="Create an admin account (or promote an existing user)")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", default="Administrator")
    admin.add_argument("--password", help="Defaults to $LINGUASI_ADMIN_PASSWORD, otherwise prompts")
    admin.set_defaults(func=cmd_create_admin)
    demo = sub.add_parser("demo", help="Create the demo learner with several weeks of realistic history")
    demo.add_argument("--reset", action="store_true", help="Delete and recreate the demo learner if it exists")
    demo.add_argument("--days", type=int, default=28, choices=range(7, 61), metavar="7-60")
    demo.set_defaults(func=cmd_demo)
    sub.add_parser("status", help="Show configuration and database status").set_defaults(func=cmd_status)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
