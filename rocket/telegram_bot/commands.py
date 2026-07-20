"""Telegram bot command handlers for user management (free/premium tiers)."""
from __future__ import annotations

import os

from ..users.store import UserStore

ADMIN_CHAT_ID: int = int(os.environ.get("SCAN_PRO_ADMIN_CHAT_ID", "0"))


async def _check_admin(update, context) -> bool:
    """Return True if the sender is the admin; reply and return False otherwise."""
    chat_id = update.effective_user.id
    if chat_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Endast admin kan använda detta kommando.")
        return False
    return True


async def plan_command(update, context, store: UserStore):
    """Show available plans — all features free."""
    chat_id = context.user_data.get("chat_id", 0)
    if not chat_id:
        chat_id = update.effective_user.id
    user = store.get_user(chat_id)
    if not user:
        user = store.create_user(chat_id)

    sub_count = store.count_subscriptions(user.chat_id)

    msg = (
        "📊 *Stock Scan Pro*\n\n"
        "🆓 *Gratis* (alla funktioner)\n"
        "  • Max 3 ticker-subscriptioner\n"
        "  • Alla 20+ tekniska indikatorer\n"
        "  • Nyheter+sentiment-korrelation\n"
        "  • Skannas vid behov (/scan)\n\n"
        f"Status: {user.tier.value.upper()} "
        f"({sub_count}/{user.max_subscriptions} subscriptions)\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def admin_list_command(update, context, store: UserStore):
    """List all users (admin only)."""
    if not await _check_admin(update, context):
        return

    rows = store.db.execute(
        "SELECT chat_id, username, tier, max_subscriptions, subscribed_at FROM users"
    ).fetchall()
    if not rows:
        await update.message.reply_text("Inga användare ännu.")
        return

    lines = ["👥 Användare:"]
    for row in rows:
        sub_count = store.count_subscriptions(row["chat_id"])
        tier_icon = "💎" if row["tier"] == "premium" else "🆓"
        username_display = "@" + row["username"] if row["username"] else "?"
        lines.append(
            f"  {tier_icon} chat_id={row['chat_id']} {username_display} "
            f"({row['tier']}, {sub_count} subs)"
        )
    await update.message.reply_text("\n".join(lines))


async def user_status_command(update, context, store: UserStore):
    """Show current user's status."""
    chat_id = update.effective_user.id
    user = store.get_user(chat_id)
    if not user:
        user = store.create_user(chat_id)

    subs = store.list_subscriptions(chat_id)
    limit_icon = "∞" if user.tier.value == "premium" else str(user.max_subscriptions)
    sub_count = len(subs)

    msg = (
        "📊 *Din status*\n\n"
        f"👤 Användare: @{update.effective_user.username or 'okänd'}\n"
        f"🆓 Nivå: *{user.tier.value.upper()}*\n"
        f"📋 Subscriptions: {sub_count}/{limit_icon}\n"
        f"   {', '.join(subs) if subs else 'Inga'}\n\n"
        "📋 Kommandon:\n"
        "  /start — Starta botten\n"
        "  /subscribe <ticker> — Lägg till en ticker\n"
        "  /unsubscribe <ticker> — Ta bort en ticker\n"
        "  /list — Visa dina subscriptions\n"
        "  /status — Visa din status\n"
        "  /plan — Visa planer\n"
        "  /scan <ticker> — Skanna en specifik ticker\n"
        "  /help — Visa hjälptext"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
