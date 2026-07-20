"""Extra commands: plan, user-status, admin, activate, deactivate."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from rocket.users.tiers import TIER_DISPLAY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# /plan — show plans to any user
# ---------------------------------------------------------------------------

async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show subscription plans."""
    plan_text = (
        "💰 *Stock Scan Pro — Planer*\n\n"
        f"*{TIER_DISPLAY['free']['emoji']} {TIER_DISPLAY['free']['name']}*\n"
        f"  {TIER_DISPLAY['free']['desc']}\n"
        f"  Pris: {TIER_DISPLAY['free']['price']}\n"
        f"  Bli med nu — helt gratis!\n\n"
        f"*{TIER_DISPLAY['premium']['emoji']} {TIER_DISPLAY['premium']['name']}*\n"
        f"  {TIER_DISPLAY['premium']['desc']}\n"
        f"  Pris: {TIER_DISPLAY['premium']['price']}/mån\n\n"
        "_För att uppgradera:_\n"
        "1. Skicka ETH till [din address]\n"
        "2. Skicka /activate <chat_id> premium\n\n"
        "🔜 Beta — gratis för alla nu!"
    )
    await update.message.reply_text(plan_text, parse_mode="Markdown")
    logger.info(f"User {update.effective_user.id} (/plan)")


# ---------------------------------------------------------------------------
# /user-status — show current user's status
# ---------------------------------------------------------------------------

async def user_status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, store
) -> None:
    """Show the user's current tier and subscription count."""
    chat_id = update.effective_user.id
    user = store.get_user(chat_id) or store.create_user(chat_id)

    tier = TIER_DISPLAY.get(user.tier.value, TIER_DISPLAY["free"])
    count = store.count_subscriptions(chat_id)
    max_subs = "∞" if user.max_subscriptions >= 100 else str(user.max_subscriptions)

    status_text = (
        f"👤 *Din Status*\n\n"
        f"Tier: {tier['emoji']} {tier['name']}\n"
        f"Subscriptioner: {count}/{max_subs}\n"
        f"Medlem sedan: {user.subscribed_at or 'just nu'}"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")
    logger.info(f"User {chat_id} (/user-status) tier={user.tier.value}")


# ---------------------------------------------------------------------------
# /admin — list all users (admin only)
# ---------------------------------------------------------------------------

async def admin_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all registered users (admin)."""
    from rocket.telegram_bot.handlers import _get_user_store

    store = _get_user_store()

    rows = store.db.execute(
        "SELECT chat_id, username, tier, max_subscriptions, subscribed_at, "
        "activated_at FROM users ORDER BY chat_id"
    ).fetchall()

    lines = ["👥 *Användare (admin):*\n"]
    for row in rows:
        cid, uname, tier, max_sub, sub_at, act_at = row
        tier_name = TIER_DISPLAY.get(tier, {}).get("name", tier)
        sub_count = store.count_subscriptions(cid)
        user_tag = f"@{uname}" if uname else "?"
        lines.append(
            f"  {cid} {user_tag} | {tier_name} | {sub_count}/{max_sub} | sedan: {sub_at or '?'}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    logger.info(f"Admin {update.effective_user.id} listed {len(rows)} users")


# ---------------------------------------------------------------------------
# /activate — activate premium (admin only)
# ---------------------------------------------------------------------------

async def activate_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, store
) -> None:
    """Activate premium for a user."""
    chat_id = update.effective_user.id
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Usage: /activate <chat_id> premium\n"
            "Exempel: /activate 123456789 premium"
        )
        return

    target_id = int(args[0])
    tier = args[1].lower()

    if tier not in ("premium", "free"):
        await update.message.reply_text(
            "Ogiltig tier. Använd 'premium' eller 'free'."
        )
        return

    if tier == "premium":
        store.upgrade_to_premium(target_id)
        await update.message.reply_text(
            f"✅ Användare {target_id} uppgraderad till "
            f"{TIER_DISPLAY['premium']['emoji']} "
            f"{TIER_DISPLAY['premium']['name']}!"
        )
    else:
        store.deactivate_premium(target_id)
        await update.message.reply_text(
            f"⬇️ Användare {target_id} nedgraderad till "
            f"{TIER_DISPLAY['free']['emoji']} "
            f"{TIER_DISPLAY['free']['name']}."
        )

    logger.info(f"Admin {chat_id} activated/deactivated {target_id} → {tier}")


# ---------------------------------------------------------------------------
# /deactivate — alias for /activate with free
# ---------------------------------------------------------------------------

async def deactivate_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, store
) -> None:
    """Deactivate premium — same as /activate <chat_id> free."""
    chat_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /deactivate <chat_id>")
        return

    target_id = int(args[0])
    store.deactivate_premium(target_id)
    await update.message.reply_text(
        f"⬇️ Användare {target_id} nedgraderad till gratisnivå."
    )
    logger.info(f"Admin {chat_id} deactivated {target_id}")
