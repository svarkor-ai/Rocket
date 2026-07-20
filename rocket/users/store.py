"""User persistence — simple SQLite store."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from .models import User, UserTier


class UserStore:
    """Simple user store using SQLite (single file, thread-safe).

    Tables:
    - users: chat_id (PK), username, tier, subscribed_at, activated_at, max_subscriptions
    - user_subscriptions: chat_id, ticker (PK) — tracks what each user is subscribed to
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                username TEXT,
                tier TEXT NOT NULL DEFAULT 'free',
                subscribed_at TEXT,
                activated_at TEXT,
                max_subscriptions INTEGER NOT NULL DEFAULT 3
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                chat_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                PRIMARY KEY (chat_id, ticker),
                FOREIGN KEY (chat_id) REFERENCES users(chat_id) ON DELETE CASCADE
            )
        """)
        self.db.commit()

    def get_user(self, chat_id: int) -> Optional[User]:
        row = self.db.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
        if row:
            return User.from_dict(dict(row))
        return None

    def create_user(self, chat_id: int, username: Optional[str] = None) -> User:
        """Create or return existing user. Auto-creates on first /start."""
        existing = self.get_user(chat_id)
        if existing:
            return existing
        user = User(chat_id=chat_id, username=username)
        self.db.execute(
            "INSERT INTO users (chat_id, username, tier, max_subscriptions) VALUES (?, ?, ?, ?)",
            (chat_id, username, user.tier.value, user.max_subscriptions),
        )
        self.db.commit()
        return user

    def update_user(self, user: User):
        self.db.execute(
            "UPDATE users SET username=?, tier=?, subscribed_at=?, activated_at=?, max_subscriptions=? WHERE chat_id=?",
            (user.username, user.tier.value, user.subscribed_at, user.activated_at, user.max_subscriptions, user.chat_id),
        )
        self.db.commit()

    def upgrade_to_premium(self, chat_id: int):
        from datetime import datetime, timezone
        user = self.get_user(chat_id)
        if not user:
            return
        user.tier = UserTier.PREMIUM
        user.max_subscriptions = 999
        user.activated_at = datetime.now(timezone.utc).isoformat()
        self.update_user(user)

    def deactivate_premium(self, chat_id: int):
        user = self.get_user(chat_id)
        if not user:
            return
        user.tier = UserTier.FREE
        user.max_subscriptions = 3
        self.update_user(user)

    def add_subscription(self, chat_id: int, ticker: str):
        """Add a subscription. Raises ValueError if free-tier limit reached."""
        user = self.get_user(chat_id)
        if not user:
            user = self.create_user(chat_id)

        if user.tier == UserTier.FREE:
            current_count = self.count_subscriptions(chat_id)
            if current_count >= user.max_subscriptions:
                raise ValueError(
                    f"Gratisnivå har max {user.max_subscriptions} ticker-subscriptioner. "
                    f"Uppgradera till premium för obegränsade. Skicka /plan för mer info."
                )

        self.db.execute(
            "INSERT OR REPLACE INTO user_subscriptions (chat_id, ticker) VALUES (?, ?)",
            (chat_id, ticker),
        )
        self.db.commit()

    def remove_subscription(self, chat_id: int, ticker: str):
        self.db.execute(
            "DELETE FROM user_subscriptions WHERE chat_id = ? AND ticker = ?",
            (chat_id, ticker),
        )
        self.db.commit()

    def count_subscriptions(self, chat_id: int) -> int:
        return self.db.execute(
            "SELECT COUNT(*) FROM user_subscriptions WHERE chat_id = ?", (chat_id,)
        ).fetchone()[0]

    def list_subscriptions(self, chat_id: int) -> list[str]:
        rows = self.db.execute(
            "SELECT ticker FROM user_subscriptions WHERE chat_id = ? ORDER BY ticker",
            (chat_id,),
        ).fetchall()
        return [r["ticker"] for r in rows]

    def close(self):
        self.db.close()
