"""
/group and /thread admin commands for group/thread access control.

/group info                         - show current group config
/group enable                       - enable bot in this group
/group disable                      - disable bot in this group (silences it)
/group allow_pm <on|off>            - toggle PM access for group members
/group nsfw <on|off>                - allow or block NSFW content in this group
/group role <role>                  - set auto_grant_role for new members
/thread allow [thread_id]           - allow this thread (default: current)
/thread deny [thread_id]            - deny this thread (default: current)
/thread list                        - list all thread policies for this group
/thread reset [thread_id]           - remove policy (revert to group default)
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from yoink.bot.middleware import guard_admin, get_settings
from yoink.storage.group_repo import GroupRepo
from yoink.storage.models import UserRole

logger = logging.getLogger(__name__)

_VALID_ROLES = {r.value for r in UserRole}


def _get_group_repo(context: ContextTypes.DEFAULT_TYPE) -> GroupRepo | None:
    return context.bot_data.get("group_repo")


def _current_thread_id(update: Update) -> int | None:
    msg = update.message
    if msg and msg.is_topic_message:
        return msg.message_thread_id
    return None


async def _cmd_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not await guard_admin(update, context):
        return

    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("This command only works in groups.")
        return

    repo = _get_group_repo(context)
    if repo is None:
        await update.message.reply_text("Group support not available.")
        return

    args = context.args or []
    sub = args[0].lower() if args else "info"

    group_id = chat.id

    if sub == "info":
        group = await repo.get(group_id)
        if group is None:
            await update.message.reply_text(
                "Group not registered yet. Send a URL or command to auto-register."
            )
            return
        status = "✅ active" if group.enabled else "⏸ disabled"
        nsfw_status = "✅ allowed" if group.nsfw_allowed else "🚫 blocked"
        await update.message.reply_html(
            f"<b>Group:</b> {group.title or group_id}\n"
            f"<b>Status:</b> {status}\n"
            f"<b>Auto role:</b> <code>{group.auto_grant_role.value}</code>\n"
            f"<b>Allow PM:</b> {group.allow_pm}\n"
            f"<b>NSFW content:</b> {nsfw_status}",
        )

    elif sub in ("enable", "disable"):
        val = sub == "enable"
        await repo.upsert(group_id=group_id, title=chat.title)
        await repo.update(group_id=group_id, enabled=val)
        if val:
            await update.message.reply_text("✅ Bot enabled in this group.")
        else:
            await update.message.reply_text("⏸ Bot disabled in this group. It will ignore all requests here.")

    elif sub == "allow_pm":
        if len(args) < 2 or args[1].lower() not in ("on", "off"):
            await update.message.reply_text("Usage: /group allow_pm <on|off>")
            return
        val = args[1].lower() == "on"
        await repo.upsert(group_id=group_id, title=chat.title)
        await repo.update(group_id=group_id, allow_pm=val)
        await update.message.reply_text(f"PM access: {'enabled' if val else 'disabled'}.")

    elif sub == "nsfw":
        if len(args) < 2 or args[1].lower() not in ("on", "off"):
            await update.message.reply_text("Usage: /group nsfw <on|off>")
            return
        val = args[1].lower() == "on"
        await repo.upsert(group_id=group_id, title=chat.title)
        await repo.update(group_id=group_id, nsfw_allowed=val)
        status = "✅ NSFW content allowed in this group." if val else "🚫 NSFW content blocked in this group."
        await update.message.reply_text(status)

    elif sub == "role":
        if len(args) < 2 or args[1].lower() not in _VALID_ROLES:
            roles = ", ".join(_VALID_ROLES)
            await update.message.reply_text(f"Usage: /group role <role>\nValid: {roles}")
            return
        role = UserRole(args[1].lower())
        await repo.upsert(group_id=group_id, title=chat.title)
        await repo.update(group_id=group_id, auto_grant_role=role)
        await update.message.reply_text(f"Auto role set to <code>{role.value}</code>.", parse_mode="HTML")

    else:
        await update.message.reply_text(
            "Usage:\n"
            "/group info\n"
            "/group allow_pm <on|off>\n"
            "/group nsfw <on|off>\n"
            "/group role <role>"
        )


async def _cmd_thread(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not await guard_admin(update, context):
        return

    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("This command only works in groups.")
        return

    repo = _get_group_repo(context)
    if repo is None:
        await update.message.reply_text("Group support not available.")
        return

    args = context.args or []
    sub = args[0].lower() if args else "list"
    group_id = chat.id

    # Ensure group exists
    await repo.upsert(group_id=group_id, title=chat.title)

    if sub == "list":
        policies = await repo.list_thread_policies(group_id)
        if not policies:
            await update.message.reply_text("No thread policies set. All threads allowed by default.")
            return
        lines = []
        for p in policies:
            tid = p.thread_id if p.thread_id is not None else "main"
            state = "allowed" if p.enabled else "denied"
            lines.append(f"Thread <code>{tid}</code>: {state}")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    elif sub in ("allow", "deny"):
        enabled = sub == "allow"
        # Use explicit thread_id arg, or current thread, or main (None)
        thread_id: int | None
        if len(args) >= 2:
            try:
                thread_id = int(args[1])
            except ValueError:
                await update.message.reply_text("Invalid thread_id.")
                return
        else:
            thread_id = _current_thread_id(update)

        await repo.set_thread_policy(group_id=group_id, thread_id=thread_id, enabled=enabled)
        tid_label = str(thread_id) if thread_id is not None else "main"
        state = "allowed" if enabled else "denied"
        await update.message.reply_text(
            f"Thread <code>{tid_label}</code> is now <b>{state}</b>.",
            parse_mode="HTML",
        )

    elif sub == "reset":
        thread_id = None
        if len(args) >= 2:
            try:
                thread_id = int(args[1])
            except ValueError:
                await update.message.reply_text("Invalid thread_id.")
                return
        else:
            thread_id = _current_thread_id(update)

        removed = await repo.delete_thread_policy(group_id=group_id, thread_id=thread_id)
        tid_label = str(thread_id) if thread_id is not None else "main"
        if removed:
            await update.message.reply_text(
                f"Policy for thread <code>{tid_label}</code> removed (reverts to group default).",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(f"No policy found for thread <code>{tid_label}</code>.", parse_mode="HTML")

    else:
        await update.message.reply_text(
            "Usage:\n"
            "/thread list\n"
            "/thread allow [thread_id]\n"
            "/thread deny [thread_id]\n"
            "/thread reset [thread_id]"
        )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("group", _cmd_group))
    app.add_handler(CommandHandler("thread", _cmd_thread))
