# SCP-079-TIP - Here's a tip
# Copyright (C) 2019-2020 SCP-079 <https://scp-079.org>
#
# This file is part of SCP-079-TIP.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
from subprocess import run
from time import sleep

from pyrogram import Client

from .. import glovar
from .channel import share_data, share_regex_count
from .etc import code, general_link, get_now, get_readable_time, lang, thread
from .file import move_file, save
from .group import delete_message, leave_group
from .telegram import get_admins, get_group_info, send_message
from .tip import get_invite_link

# Enable logging
logger = logging.getLogger(__name__)


def backup_files(client: Client) -> bool:
    # Backup data files to BACKUP
    try:
        for file in glovar.file_list:
            # Check
            if not eval(f"glovar.{file}"):
                continue

            # Share
            share_data(
                client=client,
                receivers=["BACKUP"],
                action="backup",
                action_type="data",
                data=file,
                file=f"data/{file}"
            )
            sleep(5)

        return True
    except Exception as e:
        logger.warning(f"Backup error: {e}", exc_info=True)

    return False


def interval_min_01(client: Client) -> bool:
    # Execute every minute
    result = True

    glovar.locks["message"].acquire()

    try:
        # Basic data
        now = get_now()

        # Delete tips
        for gid in list(glovar.message_ids):
            if not glovar.configs[gid].get("clean"):
                continue

            for the_type in ["keyword", "ot", "rm", "welcome"]:
                mid, time = glovar.message_ids[gid][the_type]

                if not mid:
                    continue

                if now - time > eval(f"glovar.time_{the_type}"):
                    glovar.message_ids[gid][the_type] = (0, 0)
                    delete_message(client, gid, mid)

        save("message_ids")

        # Generate a new invite link
        for gid in list(glovar.configs):
            if not glovar.configs[gid].get("channel"):
                continue

            thread(get_invite_link, (client, "edit", gid), daemon=False)

        result = True
    except Exception as e:
        logger.warning(f"Interval min 01 error: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return result


def log_rotation() -> bool:
    # Log rotation
    result = False

    try:
        move_file(f"{glovar.LOG_PATH}/log", f"{glovar.LOG_PATH}/log-{get_readable_time(the_format='%Y%m%d')}")

        with open(f"{glovar.LOG_PATH}/log", "w", encoding="utf-8") as f:
            f.write("")

        run(f"find {glovar.LOG_PATH}/log-* -mtime +30 -delete", shell=True)

        result = True
    except Exception as e:
        logger.warning(f"Log rotation error: {e}", exc_info=True)

    return result


def resend_link(client: Client) -> bool:
    # Resend the invite link
    result = False

    glovar.locks["message"].acquire()

    try:
        # Proceed
        for gid in list(glovar.configs):
            if not glovar.configs[gid].get("resend"):
                continue

            get_invite_link(
                client=client,
                the_type="send",
                gid=gid
            )

        return True
    except Exception as e:
        logger.warning(f"Resend link error: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return result


def reset_data(client: Client) -> bool:
    # Reset user data every month
    glovar.locks["message"].acquire()
    try:
        glovar.bad_ids = {
            "users": set()
        }
        save("bad_ids")

        glovar.left_group_ids = set()
        save("left_group_ids")

        glovar.user_ids = {}
        save("user_ids")

        glovar.watch_ids = {
            "ban": {},
            "delete": {}
        }
        save("watch_ids")

        # Send debug message
        text = (f"{lang('project')}{lang('colon')}{general_link(glovar.project_name, glovar.project_link)}\n"
                f"{lang('action')}{lang('colon')}{code(lang('reset'))}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Reset data error: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return False


def send_count(client: Client) -> bool:
    # Send regex count to REGEX
    glovar.locks["regex"].acquire()
    try:
        for word_type in glovar.regex:
            share_regex_count(client, word_type)
            word_list = list(eval(f"glovar.{word_type}_words"))

            for word in word_list:
                eval(f"glovar.{word_type}_words")[word] = 0

            save(f"{word_type}_words")

        return True
    except Exception as e:
        logger.warning(f"Send count error: {e}", exc_info=True)
    finally:
        glovar.locks["regex"].release()

    return False


def update_admins(client: Client) -> bool:
    # Update admin list every day
    glovar.locks["admin"].acquire()
    try:
        group_list = list(glovar.admin_ids)

        for gid in group_list:
            should_leave = True
            reason = "permissions"
            admin_members = get_admins(client, gid)

            if admin_members and any([admin.user.is_self for admin in admin_members]):
                # Admin list
                glovar.admin_ids[gid] = {admin.user.id for admin in admin_members
                                         if (((not admin.user.is_bot and not admin.user.is_deleted)
                                              and admin.can_delete_messages
                                              and admin.can_restrict_members)
                                             or admin.status == "creator"
                                             or admin.user.id in glovar.bot_ids)}
                save("admin_ids")

                # Trust list
                glovar.trust_ids[gid] = {admin.user.id for admin in admin_members
                                         if ((not admin.user.is_bot and not admin.user.is_deleted)
                                             or admin.user.id in glovar.bot_ids)}
                save("trust_ids")

                if glovar.user_id not in glovar.admin_ids[gid]:
                    reason = "user"
                else:
                    for admin in admin_members:
                        if (admin.user.is_self
                                and admin.can_delete_messages
                                and admin.can_invite_users
                                and admin.can_pin_messages):
                            should_leave = False

                if not should_leave:
                    glovar.lack_group_ids.discard(gid)
                    save("lack_group_ids")
                    continue

                if gid in glovar.lack_group_ids:
                    continue

                glovar.lack_group_ids.add(gid)
                save("lack_group_ids")

                group_name, group_link = get_group_info(client, gid)
                share_data(
                    client=client,
                    receivers=["MANAGE"],
                    action="leave",
                    action_type="request",
                    data={
                        "group_id": gid,
                        "group_name": group_name,
                        "group_link": group_link,
                        "reason": reason
                    }
                )
                reason = lang(f"reason_{reason}")
                project_link = general_link(glovar.project_name, glovar.project_link)
                debug_text = (f"{lang('project')}{lang('colon')}{project_link}\n"
                              f"{lang('group_name')}{lang('colon')}{general_link(group_name, group_link)}\n"
                              f"{lang('group_id')}{lang('colon')}{code(gid)}\n"
                              f"{lang('status')}{lang('colon')}{code(reason)}\n")
                thread(send_message, (client, glovar.debug_channel_id, debug_text))
            elif admin_members is False or any([admin.user.is_self for admin in admin_members]) is False:
                # Bot is not in the chat, leave automatically without approve
                group_name, group_link = get_group_info(client, gid)
                leave_group(client, gid)
                share_data(
                    client=client,
                    receivers=["MANAGE"],
                    action="leave",
                    action_type="info",
                    data={
                        "group_id": gid,
                        "group_name": group_name,
                        "group_link": group_link
                    }
                )
                project_text = general_link(glovar.project_name, glovar.project_link)
                debug_text = (f"{lang('project')}{lang('colon')}{project_text}\n"
                              f"{lang('group_name')}{lang('colon')}{general_link(group_name, group_link)}\n"
                              f"{lang('group_id')}{lang('colon')}{code(gid)}\n"
                              f"{lang('status')}{lang('colon')}{code(lang('leave_auto'))}\n"
                              f"{lang('reason')}{lang('colon')}{code(lang('reason_leave'))}\n")
                thread(send_message, (client, glovar.debug_channel_id, debug_text))

        return True
    except Exception as e:
        logger.warning(f"Update admin error: {e}", exc_info=True)
    finally:
        glovar.locks["admin"].release()

    return False


def update_status(client: Client, the_type: str) -> bool:
    # Update running status to BACKUP
    try:
        share_data(
            client=client,
            receivers=["BACKUP"],
            action="backup",
            action_type="status",
            data={
                "type": the_type,
                "backup": glovar.backup
            }
        )

        return True
    except Exception as e:
        logger.warning(f"Update status error: {e}", exc_info=True)

    return False
