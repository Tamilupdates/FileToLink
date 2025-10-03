# KPS/bot/plugins/admin.py

import asyncio
import html
import os
import shutil
import sys
import time
from io import BytesIO

import psutil
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from KPS import StartTime, __version__
from KPS.bot import StreamBot, multi_clients, work_loads
from KPS.utils.bot_utils import reply
from KPS.utils.broadcast import broadcast_message
from KPS.utils.database import db
from KPS.utils.handler import handle_flood_wait
from KPS.utils.human_readable import humanbytes
from KPS.utils.logger import LOG_FILE, logger
from KPS.utils.messages import (
    MSG_ADMIN_AUTH_LIST_HEADER, MSG_ADMIN_NO_BAN_REASON,
    MSG_ADMIN_USER_BANNED, MSG_ADMIN_USER_UNBANNED, MSG_AUTHORIZE_FAILED,
    MSG_AUTHORIZE_SUCCESS, MSG_AUTHORIZE_USAGE, MSG_AUTH_USER_INFO,
    MSG_BAN_REASON_SUFFIX, MSG_BAN_USAGE, MSG_BUTTON_CLOSE,
    MSG_CANNOT_BAN_OWNER, MSG_CHANNEL_BANNED, MSG_CHANNEL_BANNED_REASON_SUFFIX,
    MSG_CHANNEL_NOT_BANNED, MSG_CHANNEL_UNBANNED, MSG_DB_ERROR, MSG_DB_STATS,
    MSG_DEAUTHORIZE_FAILED, MSG_DEAUTHORIZE_SUCCESS,
    MSG_DEAUTHORIZE_USAGE, MSG_ERROR_GENERIC, MSG_INVALID_USER_ID,
    MSG_LOG_FILE_CAPTION, MSG_LOG_FILE_EMPTY, MSG_LOG_FILE_MISSING,
    MSG_NO_AUTH_USERS, MSG_RESTARTING, MSG_SHELL_ERROR,
    MSG_SHELL_EXECUTING, MSG_SHELL_NO_OUTPUT, MSG_SHELL_OUTPUT,
    MSG_SHELL_OUTPUT_STDERR, MSG_SHELL_OUTPUT_STDOUT, MSG_SHELL_USAGE,
    MSG_STATUS_ERROR, MSG_SYSTEM_STATS, MSG_SYSTEM_STATUS,
    MSG_UNBAN_USAGE, MSG_USER_BANNED_NOTIFICATION,
    MSG_USER_NOT_IN_BAN_LIST, MSG_USER_UNBANNED_NOTIFICATION,
    MSG_WORKLOAD_ITEM
)
from KPS.utils.time_format import get_readable_time
from KPS.utils.tokens import authorize, deauthorize, list_allowed
from KPS.vars import Var

owner_filter = filters.private & filters.user(Var.OWNER_ID)


@StreamBot.on_message(filters.command("users") & owner_filter)
async def get_total_users(client: Client, message: Message):
    try:
        total = await db.total_users_count()
        await reply(message,
                    text=MSG_DB_STATS.format(total_users=total),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(MSG_BUTTON_CLOSE, callback_data="close_panel")]]))
    except Exception as e:
        logger.error(f"Error in get_total_users: {e}", exc_info=True)
        await reply(message, text=MSG_DB_ERROR)


@StreamBot.on_message(filters.command("broadcast") & owner_filter)
async def broadcast_handler(client: Client, message: Message):
    await broadcast_message(client, message)


@StreamBot.on_message(filters.command("status") & owner_filter)
async def show_status(client: Client, message: Message):
    try:
        uptime_str = get_readable_time(int(time.time() - StartTime))
        workload_items = ""
        sorted_workloads = sorted(work_loads.items(), key=lambda item: item[0])
        for client_id, load_val in sorted_workloads:
            workload_items += MSG_WORKLOAD_ITEM.format(
                bot_name=f"🔹 Client {client_id}", load=load_val)

        total_workload = sum(work_loads.values())
        status_text_str = MSG_SYSTEM_STATUS.format(
            uptime=uptime_str, active_bots=len(multi_clients),
            total_workload=total_workload, workload_items=workload_items,
            version=__version__)
        await reply(message,
                    text=status_text_str,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(MSG_BUTTON_CLOSE, callback_data="close_panel")]]))
    except Exception as e:
        logger.error(f"Error in show_status: {e}", exc_info=True)
        await reply(message, text=MSG_STATUS_ERROR)


@StreamBot.on_message(filters.command("stats") & owner_filter)
async def show_stats(client: Client, message: Message):
    try:
        sys_uptime = await asyncio.to_thread(psutil.boot_time)
        sys_uptime_str = get_readable_time(int(time.time() - sys_uptime))
        bot_uptime_str = get_readable_time(int(time.time() - StartTime))
        net_io_counters = await asyncio.to_thread(psutil.net_io_counters)
        cpu_percent = await asyncio.to_thread(psutil.cpu_percent, interval=0.5)
        cpu_cores = await asyncio.to_thread(psutil.cpu_count, logical=False)
        cpu_freq = await asyncio.to_thread(psutil.cpu_freq)
        cpu_freq_ghz = f"{cpu_freq.current / 1000:.2f}" if cpu_freq else "N/A"
        ram_info = await asyncio.to_thread(psutil.virtual_memory)
        ram_total = humanbytes(ram_info.total)
        ram_used = humanbytes(ram_info.used)
        ram_free = humanbytes(ram_info.free)

        total_disk, used_disk, free_disk = await asyncio.to_thread(
            shutil.disk_usage, '.')

        stats_text_val = MSG_SYSTEM_STATS.format(
            sys_uptime=sys_uptime_str,
            bot_uptime=bot_uptime_str,
            cpu_percent=cpu_percent,
            cpu_cores=cpu_cores,
            cpu_freq=cpu_freq_ghz,
            ram_total=ram_total,
            ram_used=ram_used,
            ram_free=ram_free,
            disk_percent=psutil.disk_usage('.').percent,
            total=humanbytes(total_disk),
            used=humanbytes(used_disk),
            free=humanbytes(free_disk),
            upload=humanbytes(net_io_counters.bytes_sent),
            download=humanbytes(net_io_counters.bytes_recv)
        )

        await reply(message,
                    text=stats_text_val,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(MSG_BUTTON_CLOSE, callback_data="close_panel")]]))
    except Exception as e:
        logger.error(f"Error in show_stats: {e}", exc_info=True)
        await reply(message, text=MSG_STATUS_ERROR)


@StreamBot.on_message(filters.command("restart") & owner_filter)
async def restart_bot(client: Client, message: Message):
    msg = await reply(message, text=MSG_RESTARTING)
    await db.add_restart_message(msg.id, message.chat.id)
    os.execv(sys.executable, [sys.executable, "-m", "KPS"])


@StreamBot.on_message(filters.command("log") & owner_filter)
async def send_logs(client: Client, message: Message):
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        await reply(
            message,
            text=(MSG_LOG_FILE_MISSING if not os.path.exists(LOG_FILE) else MSG_LOG_FILE_EMPTY)
        )
        return
    
    try:
        await handle_flood_wait(
            message.reply_document, LOG_FILE,
            caption=MSG_LOG_FILE_CAPTION)
    except Exception as e:
        logger.error(f"Error sending log file: {e}", exc_info=True)
        await reply(message, text=MSG_ERROR_GENERIC)


@StreamBot.on_message(filters.command("authorize") & owner_filter)
async def authorize_command(client: Client, message: Message):
    if len(message.command) != 2:
        return await reply(
            message, text=MSG_AUTHORIZE_USAGE, parse_mode=ParseMode.MARKDOWN)
    
    try:
        user_id = int(message.command[1])
        success = await authorize(user_id, message.from_user.id)
        await reply(message,
                    text=((MSG_AUTHORIZE_SUCCESS.format(user_id=user_id) if success else MSG_AUTHORIZE_FAILED.format(user_id=user_id))))
    except ValueError:
        await reply(message, text=MSG_INVALID_USER_ID)
    except Exception as e:
        logger.error(f"Error in authorize_command: {e}", exc_info=True)
        await reply(message, text=MSG_ERROR_GENERIC)


@StreamBot.on_message(filters.command("deauthorize") & owner_filter)
async def deauthorize_command(client: Client, message: Message):
    if len(message.command) != 2:
        return await reply(
            message, text=MSG_DEAUTHORIZE_USAGE, parse_mode=ParseMode.MARKDOWN)
    
    try:
        user_id = int(message.command[1])
        success = await deauthorize(user_id)
        await reply(message,
                    text=((MSG_DEAUTHORIZE_SUCCESS.format(user_id=user_id) if success else MSG_DEAUTHORIZE_FAILED.format(user_id=user_id))))
    except ValueError:
        await reply(message, text=MSG_INVALID_USER_ID)
    except Exception as e:
        logger.error(f"Error in deauthorize_command: {e}", exc_info=True)

        await reply(message, text=MSG_ERROR_GENERIC)


@StreamBot.on_message(filters.command("listauth") & owner_filter)
async def list_authorized_command(client: Client, message: Message):
    users = await list_allowed()
    if not users:
        return await reply(
            message, text=MSG_NO_AUTH_USERS)
    
    text = MSG_ADMIN_AUTH_LIST_HEADER
    for i, user in enumerate(users, 1):
        text += MSG_AUTH_USER_INFO.format(
            i=i, user_id=user['user_id'],
            authorized_by=user['authorized_by'],
            auth_time=user['authorized_at']
        )
    
    await reply(message,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(MSG_BUTTON_CLOSE, callback_data="close_panel")]]))


@StreamBot.on_message(filters.command("ban") & owner_filter)
async def ban_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await reply(message, text=MSG_BAN_USAGE)

    try:
        target_id = int(message.command[1])
        reason = " ".join(message.command[2:]) or MSG_ADMIN_NO_BAN_REASON
        banned_by_id = message.from_user.id if message.from_user else None

        if target_id == Var.OWNER_ID:
            return await reply(message, text=MSG_CANNOT_BAN_OWNER)

        if target_id < 0:
            await db.add_banned_channel(
                channel_id=target_id,
                reason=reason,
                banned_by=banned_by_id
            )
            text = MSG_CHANNEL_BANNED.format(channel_id=target_id)
            if reason != MSG_ADMIN_NO_BAN_REASON:
                text += MSG_CHANNEL_BANNED_REASON_SUFFIX.format(reason=reason)
            await reply(message, text=text)
            try:
                await handle_flood_wait(client.leave_chat, target_id)
            except Exception as e:
                logger.warning(f"Could not leave banned channel {target_id}: {e}", exc_info=True)
        else:
            await db.add_banned_user(
                user_id=target_id,
                reason=reason,
                banned_by=banned_by_id
            )
            text = MSG_ADMIN_USER_BANNED.format(user_id=target_id)
            if reason != MSG_ADMIN_NO_BAN_REASON:
                text += MSG_BAN_REASON_SUFFIX.format(reason=reason)
            await reply(message, text=text)
            try:
                await handle_flood_wait(client.send_message, target_id, MSG_USER_BANNED_NOTIFICATION)
            except Exception as e:
                logger.warning(f"Could not notify banned user {target_id}: {e}", exc_info=True)

    except ValueError:
        await reply(message, text=MSG_INVALID_USER_ID)
    except Exception as e:
        logger.error(f"Error in ban_command: {e}", exc_info=True)
        await reply(message, text=MSG_ERROR_GENERIC)


@StreamBot.on_message(filters.command("unban") & owner_filter)
async def unban_command(client: Client, message: Message):
    if len(message.command) != 2:
        return await reply(message, text=MSG_UNBAN_USAGE)

    try:
        target_id = int(message.command[1])

        if target_id < 0:
            if await db.remove_banned_channel(channel_id=target_id):
                await reply(message, text=MSG_CHANNEL_UNBANNED.format(channel_id=target_id))
            else:
                await reply(message, text=MSG_CHANNEL_NOT_BANNED.format(channel_id=target_id))
        else:
            if await db.remove_banned_user(user_id=target_id):
                await reply(message, text=MSG_ADMIN_USER_UNBANNED.format(user_id=target_id))
                try:
                    await handle_flood_wait(client.send_message, target_id, MSG_USER_UNBANNED_NOTIFICATION)
                except Exception as e:
                    logger.warning(f"Could not notify unbanned user {target_id}: {e}", exc_info=True)
            else:
                await reply(message, text=MSG_USER_NOT_IN_BAN_LIST.format(user_id=target_id))
    except ValueError:
        await reply(message, text=MSG_INVALID_USER_ID)
    except Exception as e:
        logger.error(f"Error in unban_command: {e}", exc_info=True)
        await reply(message, text=MSG_ERROR_GENERIC)


@StreamBot.on_message(filters.command("shell") & owner_filter)
async def run_shell_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await reply(
            message, text=MSG_SHELL_USAGE, parse_mode=ParseMode.HTML)
    
    command = " ".join(message.command[1:])
    status_msg = await reply(message,
                text=MSG_SHELL_EXECUTING.format(
                    command=html.escape(command)),
                parse_mode=ParseMode.HTML)
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        output = ""
        if stdout:
            output += MSG_SHELL_OUTPUT_STDOUT.format(
                output=html.escape(stdout.decode(errors='ignore')))
        if stderr:
            output += MSG_SHELL_OUTPUT_STDERR.format(
                error=html.escape(stderr.decode(errors='ignore')))
        
        output = output.strip() or MSG_SHELL_NO_OUTPUT
        
        await handle_flood_wait(status_msg.delete)
        
        if len(output) > 4096:
            file = BytesIO(output.encode())
            file.name = "shell_output.txt"
            await handle_flood_wait(
                message.reply_document, file,
                caption=MSG_SHELL_OUTPUT.format(
                    command=html.escape(command)))
        else:
            await reply(message, text=output, parse_mode=ParseMode.HTML)
            
    except Exception as e:
        try:
            await handle_flood_wait(
                status_msg.edit_text,
                MSG_SHELL_ERROR.format(error=html.escape(str(e))),
                parse_mode=ParseMode.HTML)
        except Exception:
            await reply(
                message,
                text=MSG_SHELL_ERROR.format(error=html.escape(str(e))),
                parse_mode=ParseMode.HTML)
