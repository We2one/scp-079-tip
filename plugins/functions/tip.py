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
from typing import List, Optional

from pyrogram import ChatMember, Client, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import glovar
from .etc import code, get_full_name, get_length, get_now, lang, mention_id, mention_name
from .file import save
from .group import delete_message
from .telegram import edit_message_text, export_chat_invite_link, send_message


# Enable logging
logger = logging.getLogger(__name__)


def get_invite_link(client: Client, the_type: str, gid: int, manual: bool = False, reason: str = "") -> bool:
    # Get a new invite link
    result = False

    glovar.locks["channel"].acquire()

    try:
        # Basic data
        now = get_now()

        # Read the config
        cid = glovar.configs[gid].get("channel")
        channel_text = glovar.configs[gid].get("channel_text")
        channel_button = glovar.configs[gid].get("channel_button")
        mid, time = glovar.message_ids[gid].get("channel", (0, 0))

        # Check the config
        if not cid:
            return False

        # Check the link time
        if not manual and the_type != "send" and now - time < glovar.time_channel:
            return False

        # Generate link
        link = export_chat_invite_link(client, gid)

        # Check the link
        if link is False:
            glovar.configs[gid]["channel"] = 0
            save("configs")
            glovar.message_ids[gid]["channel"] = (0, 0)
            save("message_ids")
            delete_message(client, cid, mid)
            return False
        elif not link:
            return False

        # Update the link
        glovar.configs[gid]["channel_link"] = link
        save("configs")

        # Generate text and markup
        text = channel_text
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=channel_button,
                        url=link
                    )
                ]
            ]
        )

        # Edit message
        if the_type in {"close", "edit", "open"} and mid:
            if the_type == "close":
                text = f"{lang('description')}{lang('colon')}{code(lang('description_close'))}\n"

                if reason:
                    text += f"{lang('reason')}{lang('colon')}{code(reason)}\n"

                markup = None

            result = edit_message_text(client, cid, mid, text, markup)

            if result:
                glovar.message_ids[gid]["channel"] = (mid, now)
                save("message_ids")
                return True

        # Send new message
        result = send_message(client, cid, text, None, markup)

        if not result:
            return False

        glovar.message_ids[gid]["channel"] = (result.message_id, now)
        save("message_ids")
        mid and delete_message(client, cid, mid)

        result = True
    except Exception as e:
        logger.warning(f"New invite link error: {e}", exc_info=True)
    finally:
        glovar.locks["channel"].release()

    return result


def get_keywords(text: str) -> dict:
    # Get keywords
    result = {}
    try:
        # Check the text
        if not text:
            return {}

        text_list = [t for t in text.split("\n+++") if t]

        if not text_list or len(text_list) % 2 != 0:
            return {}

        # Get keyword_list
        keyword_list = [t.strip() for t in text_list[0::2]]
        reply_list = [t.strip() for t in text_list[1::2]]

        # Get keyword dict
        result = {}

        for i in range(len(keyword_list)):
            keyword = keyword_list[i]
            reply = reply_list[i]

            k_list = [k.strip() for k in keyword.split("||") if k.strip()]

            for k in k_list:
                result[k.lower()] = reply
    except Exception as e:
        logger.warning(f"Get keywords error: {e}", exc_info=True)

    return result


def get_markup(the_type: str, gid: int) -> Optional[InlineKeyboardMarkup]:
    # Get the group button config
    result = None

    try:
        text = glovar.configs[gid].get(f"{the_type}_button")
        link = glovar.configs[gid].get(f"{the_type}_link")

        if not text or not link:
            return None

        text_list = [u.strip() for u in text.split("||") if u.strip()]
        link_list = [u.strip() for u in link.split("||") if u.strip()]

        if len(text_list) != len(link_list) or len(text_list) > 6:
            return None

        length = len(text_list)
        markup_list: List[List[InlineKeyboardButton]] = [[]]

        for i in range(len(text_list)):
            text = text_list[i]
            link = link_list[i]

            if length <= 6 and (length % 3) and not (length % 2) and len(markup_list[-1]) == 2:
                markup_list.append([])

            elif len(markup_list[-1]) == 3:
                markup_list.append([])

            elif (len(markup_list[-1]) == 2
                  and get_length(text) <= 12
                  and all(get_length(m.text) <= 12 for m in markup_list[-1])):
                pass

            elif (len(markup_list[-1]) == 1
                  and get_length(text) <= 18
                  and get_length(markup_list[-1][-1].text) <= 18):
                pass

            elif markup_list[-1]:
                markup_list.append([])

            markup_list[-1].append(
                InlineKeyboardButton(
                    text=text,
                    url=link
                )
            )

        result = InlineKeyboardMarkup(markup_list)
    except Exception as e:
        logger.warning(f"Get button config error: {e}", exc_info=True)

    return result


def tip_keyword(client: Client, message: Message, text: str, mid: int) -> bool:
    # Send keyword tip
    try:
        # Basic data
        gid = message.chat.id

        if mid:
            delete_message(client, gid, message.message_id)
        else:
            uid = message.from_user.id

            if text in glovar.keyworded_ids[gid].get(uid, set()):
                return True

            if not glovar.keyworded_ids[gid].get(uid, set()):
                glovar.keyworded_ids[gid][uid] = set()

            glovar.keyworded_ids[gid][uid].add(text)
            mid = message.message_id

        now = get_now()

        # Get the markup
        markup = get_markup("keyword", gid)

        # Send the tip
        result = send_message(client, gid, text, mid, markup)

        if result:
            mid, _ = glovar.message_ids[gid]["keyword"]
            mid and delete_message(client, gid, mid)
            glovar.message_ids[gid]["keyword"] = (result.message_id, now)
            save("message_ids")
        
        return True
    except Exception as e:
        logger.warning(f"Tip keyword error: {e}", exc_info=True)

    return False


def tip_ot(client: Client, gid: int, mid: int = None) -> bool:
    # Send OT tip
    try:
        # Basic data
        now = get_now()
        
        # Get the markup
        markup = get_markup("ot", gid)
        
        # Read the config
        text = glovar.configs[gid].get("ot_text")

        # Check the config
        if not glovar.configs[gid].get("ot") or not text:
            return True
        
        # Send the tip
        result = send_message(client, gid, text, mid, markup)

        if result:
            mid, _ = glovar.message_ids[gid]["ot"]
            mid and delete_message(client, gid, mid)
            glovar.message_ids[gid]["ot"] = (result.message_id, now)
            save("message_ids")
        
        return True
    except Exception as e:
        logger.warning(f"Tip ot error: {e}", exc_info=True)

    return False


def tip_rm(client: Client, gid: int, text: str, mid: int = None) -> bool:
    # Send RM tip
    try:
        # Basic data
        now = get_now()

        # Check the config
        if not glovar.configs[gid].get("rm"):
            return True

        # Check the text
        if not text or not text.strip():
            return True

        # Get the markup
        markup = get_markup("rm", gid)

        # Send the tip
        result = send_message(client, gid, text, mid, markup)

        if result:
            mid, _ = glovar.message_ids[gid]["rm"]
            mid and delete_message(client, gid, mid)
            glovar.message_ids[gid]["rm"] = (result.message_id, now)
            save("message_ids")
        
        return True
    except Exception as e:
        logger.warning(f"Tip rm error: {e}", exc_info=True)
    
    return False


def tip_welcome(client: Client, message: Message = None,
                member: ChatMember = None, gid: int = 0, mid: int = None, force: bool = False) -> bool:
    # Send welcome tip
    try:
        # Basic data
        if message:
            if message.new_chat_members:
                user = message.new_chat_members[0]
            else:
                user = message.from_user

            gid = message.chat.id
            uid = user.id
            mid = message.message_id
        elif member and gid:
            if member.status not in {"member", "restricted"}:
                return True

            user = member.user
            uid = user.id
        else:
            return True

        name = get_full_name(user)
        now = get_now()

        # Check welcome status
        if not force and uid in glovar.welcomed_ids[gid]:
            return True
        else:
            glovar.welcomed_ids[gid].add(uid)

        # Get the markup
        markup = get_markup("welcome", gid)

        # Read the config
        text = glovar.configs[gid].get("welcome_text")

        # Check the config
        if not text:
            return True

        if glovar.configs[gid].get("alone"):
            mid = None

        # Replace
        text = text.replace("$code_id", code(uid))
        text = text.replace("$code_name", code(name))
        text = text.replace("$mention_id", mention_id(uid))
        text = text.replace("$mention_name", mention_name(user))

        # Send the tip
        result = send_message(client, gid, text, mid, markup)

        if result:
            mid, _ = glovar.message_ids[gid]["welcome"]
            mid and delete_message(client, gid, mid)
            glovar.message_ids[gid]["welcome"] = (result.message_id, now)
            save("message_ids")

        return True
    except Exception as e:
        logger.warning(f"Tip welcome error: {e}", exc_info=True)

    return False
