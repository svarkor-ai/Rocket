"""Telegram notification helper for Rocket Stock Scanner.

Sends messages to Telegram via Bot API using the BOT_TOKEN from environment.
Designed for use in cron jobs and background tasks (sync-compatible).
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _get_bot_token() -> str:
    token = os.environ.get("ROCKET_TELEGRAM_BOT_TOKEN")
    if not token:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("ROCKET_TELEGRAM_BOT_TOKEN not set")
    return token


def _get_chat_id() -> str:
    chat_id = os.environ.get("ROCKET_TELEGRAM_CHAT_ID")
    if not chat_id:
        raise ValueError("ROCKET_TELEGRAM_CHAT_ID not set")
    return chat_id


def send_notification(message: str, parse_mode: str = "HTML") -> bool:
    """Send a notification to Telegram."""
    try:
        import requests
        token = _get_bot_token()
        chat_id = _get_chat_id()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": parse_mode}
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Telegram notification sent: %s", message[:50])
        return True
    except ImportError:
        logger.error("requests library not installed")
        return False
    except Exception as e:
        logger.error("Failed to send Telegram notification: %s", e)
        return False


class TelegramNotifier:
    """Telegram notification helper for Rocket Stock Scanner."""

    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        self.bot_token = bot_token or _get_bot_token()
        self.chat_id = chat_id or _get_chat_id()
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram."""
        try:
            import requests
            payload = {"chat_id": self.chat_id, "text": message, "parse_mode": parse_mode}
            response = requests.post(self.api_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Telegram notification sent: %s", message[:50])
            return True
        except ImportError:
            logger.error("requests library not installed")
            return False
        except Exception as e:
            logger.error("Failed to send Telegram notification: %s", e)
            return False

    def send_top_signals(self, signals: list[dict[str, Any]]) -> bool:
        """Send top N buy signals to Telegram."""
        if not signals:
            return self.send("No signals to report.")
        buy_signals = [s for s in signals if s.get("signal") == "BUY"]
        sell_signals = [s for s in signals if s.get("signal") == "SELL"]
        hold_signals = [s for s in signals if s.get("signal") == "HOLD"]
        msg = f"Rocket Scanner - Top Signals\n\n"
        msg += f"BUY: {len(buy_signals)} | SELL: {len(sell_signals)} | HOLD: {len(hold_signals)}\n\n"
        if buy_signals:
            msg += "Top Buys:\n"
            for s in buy_signals[:5]:
                ticker = s.get("ticker", "N/A")
                score = s.get("composite_score", 0)
                momentum = s.get("momentum_score", 0)
                trend = s.get("trend_score", 0)
                msg += f"  {ticker} - Score: {score:.3f} (Mom: {momentum:.2f}, Trend: {trend:.2f})\n"
        if sell_signals:
            msg += "\nTop Sells:\n"
            for s in sell_signals[:3]:
                ticker = s.get("ticker", "N/A")
                score = s.get("composite_score", 0)
                msg += f"  {ticker} - Score: {score:.3f}\n"
        msg += f"\n{signals[0].get('timestamp', 'N/A')[:19]}"
        return self.send(msg)

    def send_signal_alert(self, ticker: str, old_signal: str, new_signal: str, score: float, reason: str = "") -> bool:
        """Send alert for signal change."""
        emoji = {"BUY": "BUY", "SELL": "SELL", "HOLD": "HOLD"}
        old_emoji = emoji.get(old_signal, "N/A")
        new_emoji = emoji.get(new_signal, "N/A")
        msg = f"{old_emoji} -> {new_emoji} {ticker}\nSignal: {old_signal} -> {new_signal}\nScore: {score:.3f}"
        if reason:
            msg += f"\nReason: {reason}"
        return self.send(msg)