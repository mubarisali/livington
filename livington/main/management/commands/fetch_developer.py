import os
import requests
import logging
from django.core.management.base import BaseCommand
from dotenv import load_dotenv
from dateutil import parser as date_parser
from main.models import Developer

# Load .env values
load_dotenv()

logger = logging.getLogger(__name__)

ESTATY_API_BASE_URL = os.getenv("ESTATY_API_BASE_URL")
ESTATY_API_KEY = os.getenv("ESTATY_API_KEY")

FILTERS_URL = f"{ESTATY_API_BASE_URL}/getFilters"

HEADERS = {
    "App-key": ESTATY_API_KEY,
    "Content-Type": "application/json",
}

class Command(BaseCommand):
    help = "Fetch and update developer companies from Estaty API"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("📡 Fetching developer companies..."))

        try:
            response = requests.post(FILTERS_URL, headers=HEADERS, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"❌ Error while calling developer API: {e}")
            self.stderr.write(self.style.ERROR(f"Failed to fetch data: {e}"))
            return

        data = response.json()

        developers = data.get("developer_companies", [])
        if not developers:
            self.stdout.write(self.style.WARNING("⚠ No developers found in the response."))
            return

        created = 0
        updated = 0

        for dev in developers:
            if not dev.get("id"):
                continue

            developer_obj, is_created = Developer.objects.update_or_create(
                    id=dev["id"],
                    defaults={
                        "name": dev.get("name"),
                        "slug": dev.get("slug"),
                        "logo": dev.get("logo"),
                        "address": dev.get("address"),
                        "phone": dev.get("phone"),
                        "email": dev.get("email"),
                        "website": dev.get("website"),
                        "overview": dev.get("overview"),
                        "created_at": date_parser.parse(dev["created_at"]) if dev.get("created_at") else None,
                        "updated_at": date_parser.parse(dev["updated_at"]) if dev.get("updated_at") else None,
                    }
                )

            if is_created:
                created += 1
            else:
                updated += 1

            self.stdout.write(f"✅ {'Created' if is_created else 'Updated'}: {developer_obj.name}")

        self.stdout.write(self.style.SUCCESS(
            f"🎉 Completed. Developers created: {created}, updated: {updated}"
        ))