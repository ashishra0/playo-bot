import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN
from models import Court
from parser import parse_find_args
from playo_scraper import DEFAULT_CITY, search_courts
from whatsapp import post_to_whatsapp, to_whatsapp_text
from whatsapp_webhook import poll_whatsapp

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hey! I help you find badminton courts on Playo.\n\n"
        "Try: /find koramangala 7pm tomorrow\n"
        "Type /help for more options."
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*Usage*\n"
        "`/find <area> <time> <date> [sport=<sport>]`\n\n"
        "*Examples*\n"
        "`/find baner 7pm tomorrow`\n"
        "`/find baner 7pm tomorrow sport=football`\n"
        "`/find hsr layout 7:30pm feb12`\n"
        "`/find kothrud 8am monday sport=tennis`\n\n"
        "*Date formats*\n"
        "today, tomorrow, mon-sun, feb10, 10feb, 2026-02-15\n\n"
        "*Sports*: badminton (default), football, cricket, tennis, squash, basketball\n\n"
        "*City* defaults to Pune. Add `city=bangalore` to search elsewhere.\n\n"
        "With time + date, I'll show available courts and prices!",
        parse_mode="Markdown",
    )


def _format_court_basic(i: int, c: Court) -> str:
    """Format a court without availability info."""
    lines = [f"*{i}. {c.name}*"]
    if c.area:
        lines.append(f"   Area: {c.area}")
    if c.rating:
        lines.append(f"   Rating: {c.rating}")
    if c.time_slots:
        lines.append(f"   Hours: {', '.join(c.time_slots)}")
    if c.url:
        lines.append(f"   [View on Playo]({c.url})")
    return "\n".join(lines)


def _format_court_with_availability(i: int, c: Court, time_filter: str) -> str:
    """Format a court with slot availability for the requested time."""
    lines = [f"*{i}. {c.name}*"]
    if c.area:
        lines.append(f"   Area: {c.area}")
    if c.rating:
        lines.append(f"   Rating: {c.rating}")

    if c.availability is None:
        lines.append(f"   Availability: Could not fetch")
    elif len(c.availability) == 0:
        lines.append(f"   Not bookable online — call venue directly")
    else:
        available_courts = []
        for court_avail in c.availability:
            for slot in court_avail.slots:
                if slot.available:
                    available_courts.append(
                        f"{court_avail.court_name} — INR {slot.price:.0f}"
                    )

        if available_courts:
            lines.append(f"   *Available at {time_filter}:*")
            for ac in available_courts:
                lines.append(f"   ✓ {ac}")
        else:
            lines.append(f"   ✗ Fully booked at {time_filter}")

    if c.url:
        lines.append(f"   [Book on Playo]({c.url})")
    return "\n".join(lines)


async def cmd_find(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    raw_args = update.message.text
    _, _, arg_text = raw_args.partition(" ")

    # Extract city= before passing to parser
    city = DEFAULT_CITY
    tokens = arg_text.split()
    remaining: list[str] = []
    for tok in tokens:
        if tok.lower().startswith("city="):
            city = tok.split("=", 1)[1]
        else:
            remaining.append(tok)
    arg_text = " ".join(remaining)

    try:
        params = parse_find_args(arg_text)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    search_msg = f"Searching for badminton courts near *{params.area}*"
    if params.time and params.date:
        search_msg += f" at {params.time} on {params.date}"
    search_msg += "..."
    status = await update.message.reply_text(search_msg, parse_mode="Markdown")

    try:
        result = await search_courts(params, city=city)
    except Exception:
        log.exception("Search failed")
        await status.edit_text("Something went wrong while searching. Please try again later.")
        return

    if not result.courts:
        await status.edit_text(
            f"No badminton courts found in {city}. Try a different city.",
            parse_mode="Markdown",
        )
        return

    has_availability = params.date and params.time

    if result.exact_area_match:
        header = f"Found *{len(result.courts)}* court(s) near *{params.area}*"
    else:
        header = (
            f"No exact match for *{params.area}* — "
            f"showing top courts in *{city}*"
        )
    if has_availability:
        header += f" for {params.time} on {params.date}"
    header += ":\n\n"

    if has_availability:
        body = "\n\n".join(
            _format_court_with_availability(i, c, params.time)
            for i, c in enumerate(result.courts, 1)
        )
    else:
        body = "\n\n".join(
            _format_court_basic(i, c)
            for i, c in enumerate(result.courts, 1)
        )

    await status.edit_text(header + body, parse_mode="Markdown", disable_web_page_preview=True)
    await post_to_whatsapp(to_whatsapp_text(header + body))


async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set. See .env.example")

    tg_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("help", cmd_help))
    tg_app.add_handler(CommandHandler("find", cmd_find))

    log.info("Bot starting...")
    async with tg_app:
        await tg_app.start()
        await tg_app.updater.start_polling()
        await poll_whatsapp()  # runs forever, polling Green API


if __name__ == "__main__":
    asyncio.run(main())
