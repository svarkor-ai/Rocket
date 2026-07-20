from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


class UserTier(str, Enum):
    FREE = "free"
    PREMIUM = "premium"


@dataclass
class User:
    chat_id: int
    username: Optional[str] = None
    tier: UserTier = UserTier.FREE
    subscribed_at: Optional[str] = None  # ISO timestamp when first used
    activated_at: Optional[str] = None   # ISO timestamp when upgraded to premium
    max_subscriptions: int = 3  # free users get 3, premium gets 999

    @classmethod
    def from_dict(cls, d: dict) -> "User":
        d["tier"] = UserTier(d["tier"])
        d["subscribed_at"] = d.get("subscribed_at")
        d["activated_at"] = d.get("activated_at")
        d["username"] = d.get("username")
        d["max_subscriptions"] = d.get("max_subscriptions", 3 if d.get("tier", "free") == "free" else 999)
        return cls(**d)

    def to_dict(self) -> dict:
        return {
            "chat_id": self.chat_id,
            "username": self.username,
            "tier": self.tier.value,
            "subscribed_at": self.subscribed_at,
            "activated_at": self.activated_at,
            "max_subscriptions": self.max_subscriptions,
        }
