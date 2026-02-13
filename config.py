import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

GREENAPI_INSTANCE_ID = os.environ.get("GREENAPI_INSTANCE_ID", "")
GREENAPI_TOKEN = os.environ.get("GREENAPI_TOKEN", "")
WHATSAPP_GROUP_ID = os.environ.get("WHATSAPP_GROUP_ID", "")

PLAYO_BASE_URL = "https://playo.co"
PLAYO_SEARCH_API = "https://api.playo.io/venue-public/v2/search"
PLAYO_AVAILABILITY_API = "https://api.playo.io/booking-lab-public/availability/v1"
PLAYO_MOBILE = "8806011009"

MAX_SEARCH_RESULTS = 5
SCRAPER_RETRIES = 3
SCRAPER_BACKOFF_BASE = 2  # seconds
