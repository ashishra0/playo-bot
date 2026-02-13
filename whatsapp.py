import logging
import re

import httpx

from config import GREENAPI_INSTANCE_ID, GREENAPI_TOKEN, WHATSAPP_GROUP_ID

log = logging.getLogger(__name__)


def to_whatsapp_text(text: str) -> str:
    """Convert Telegram markdown links [label](url) to plain URLs for WhatsApp."""
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\2', text)


async def post_to_whatsapp(text: str, chat_id: str = WHATSAPP_GROUP_ID) -> None:
    if not (GREENAPI_INSTANCE_ID and GREENAPI_TOKEN and chat_id):
        return
    url = f"https://api.greenapi.com/waInstance{GREENAPI_INSTANCE_ID}/sendMessage/{GREENAPI_TOKEN}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"chatId": chat_id, "message": text})
            if resp.status_code != 200:
                log.warning("WhatsApp post failed: %s %s", resp.status_code, resp.text)
    except Exception:
        log.warning("WhatsApp post failed", exc_info=True)
