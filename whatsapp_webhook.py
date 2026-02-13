import logging

from aiohttp import web

from models import SearchParams
from parser import parse_find_args
from playo_scraper import DEFAULT_CITY, search_courts
from whatsapp import post_to_whatsapp, to_whatsapp_text

log = logging.getLogger(__name__)

WEBHOOK_PORT = 8080


def _format_results(courts, params, city: str, exact_match: bool) -> str:
    has_availability = bool(params.date and params.time)

    if exact_match:
        header = f"Found {len(courts)} court(s) near {params.area}"
    else:
        header = f"No exact match for {params.area} — showing top courts in {city}"

    if has_availability:
        header += f" for {params.time} on {params.date}"
    header += ":\n\n"

    lines = []
    for i, c in enumerate(courts, 1):
        parts = [f"{i}. {c.name}"]
        if c.area:
            parts.append(f"   Area: {c.area}")
        if c.rating:
            parts.append(f"   Rating: {c.rating}")

        if has_availability:
            if c.availability is None:
                parts.append("   Availability: Could not fetch")
            elif len(c.availability) == 0:
                parts.append("   Not bookable online — call venue directly")
            else:
                available = [
                    f"{ca.court_name} — INR {slot.price:.0f}"
                    for ca in c.availability
                    for slot in ca.slots
                    if slot.available
                ]
                if available:
                    parts.append(f"   Available at {params.time}:")
                    parts.extend(f"   + {a}" for a in available)
                else:
                    parts.append(f"   Fully booked at {params.time}")
        else:
            if c.time_slots:
                parts.append(f"   Hours: {', '.join(c.time_slots)}")

        if c.url:
            parts.append(f"   {c.url}")

        lines.append("\n".join(parts))

    return header + "\n\n".join(lines)


async def handle_webhook(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.Response(status=400)

    # Only handle incoming text messages
    if payload.get("typeWebhook") != "incomingMessageReceived":
        return web.Response(status=200)

    msg_data = payload.get("messageData", {})
    if msg_data.get("typeMessage") != "textMessage":
        return web.Response(status=200)

    text = msg_data.get("textMessageData", {}).get("textMessage", "").strip()
    chat_id = payload.get("senderData", {}).get("chatId", "")
    sender = payload.get("senderData", {}).get("senderName", "Someone")

    if not text.lower().startswith("/find"):
        return web.Response(status=200)

    _, _, arg_text = text.partition(" ")

    # Extract city= token
    city = DEFAULT_CITY
    tokens = arg_text.split()
    remaining = []
    for tok in tokens:
        if tok.lower().startswith("city="):
            city = tok.split("=", 1)[1]
        else:
            remaining.append(tok)
    arg_text = " ".join(remaining)

    try:
        params = parse_find_args(arg_text)
    except ValueError as exc:
        await post_to_whatsapp(str(exc), chat_id=chat_id)
        return web.Response(status=200)

    log.info("WA /find from %s: area=%s date=%s time=%s city=%s", sender, params.area, params.date, params.time, city)

    try:
        result = await search_courts(params, city=city)
    except Exception:
        log.exception("WA search failed")
        await post_to_whatsapp("Something went wrong while searching. Please try again.", chat_id=chat_id)
        return web.Response(status=200)

    if not result.courts:
        await post_to_whatsapp(f"No badminton courts found in {city}. Try a different city.", chat_id=chat_id)
        return web.Response(status=200)

    reply = _format_results(result.courts, params, city, result.exact_area_match)
    await post_to_whatsapp(to_whatsapp_text(reply), chat_id=chat_id)
    return web.Response(status=200)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)
    return app
