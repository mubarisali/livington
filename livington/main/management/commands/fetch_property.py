import requests
import logging
from datetime import datetime
from django.utils.timezone import make_aware, now, is_naive
from django.utils.dateparse import parse_datetime
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from dateutil import parser as date_parser
from django.db import transaction
import os
from dotenv import load_dotenv

from main.models import (
    City, District, Developer, PropertyType, PropertyStatus, SalesStatus,
    Facility, Property, GroupedApartment, PropertyImages,
    PaymentPlan, PaymentPlanValue
)

load_dotenv()

# Environment variables
ESTATY_API_BASE_URL = os.getenv("ESTATY_API_BASE_URL")
ESTATY_API_KEY = os.getenv("ESTATY_API_KEY")
ESTATY_PAGE_SIZE = int(os.getenv("ESTATY_PAGE_SIZE", 50))

# API URLs
LISTING_URL = f"{ESTATY_API_BASE_URL}/getProperties"
DETAIL_URL = f"{ESTATY_API_BASE_URL}/getProperty"

HEADERS = {
    "App-key": ESTATY_API_KEY,
    "Content-Type": "application/json",
}

log = logging.getLogger(__name__)

# ---------------- Utility Functions ----------------
def convert_mm_yyyy_to_date(date_str: str):
    """Convert MM/YYYY string to Python date (first day of month)."""
    try:
        month, year = date_str.strip().split('/')
        return datetime(int(year), int(month), 1).date()
    except Exception:
        return None

def convert_mm_yyyy_to_yyyymm(date_str: str):
    try:
        month, year = date_str.strip().split('/')
        return int(f"{year}{int(month):02d}")
    except Exception:
        return None

# ---------------- Management Command ----------------
class Command(BaseCommand):
    help = "Import and save Estaty properties"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("✅ Starting Estaty property import..."))
        page = 1
        total_imported = 0

        while True:
            properties = self.fetch_property_ids(page)
            if not properties:
                break

            for prop in properties:
                prop_id = prop.get("id")
                if not prop_id:
                    continue

                # Skip if property with external_id already exists
                if Property.objects.filter(external_id=prop_id).exists():
                    continue

                detail = self.fetch_property_details(prop_id)
                if detail:
                    print(f"📦 Fetched property ID: {prop_id} - {detail.get('title', 'No Title')}")
                    self.save_property_to_db(detail)
                    total_imported += 1

            page += 1

        self.stdout.write(self.style.SUCCESS(f"🏑 Done! Total properties saved: {total_imported}"))

    # ---------------- Fetch Properties ----------------
    def fetch_property_ids(self, page=1):
        try:
            url = f"{LISTING_URL}?page={page}" if page > 1 else LISTING_URL
            response = requests.post(url, headers=HEADERS, json={})
            response.raise_for_status()
            data = response.json()
            return data.get("properties", {}).get("data", [])
        except Exception as e:
            log.error(f"❌ Error fetching property list (page {page}): {e}")
            return []

    # ---------------- Fetch Property Details ----------------
    def fetch_property_details(self, prop_id):
        try:
            response = requests.post(DETAIL_URL, headers=HEADERS, json={"id": prop_id})
            response.raise_for_status()
            return response.json().get("property")
        except Exception as e:
            log.error(f"❌ Error fetching details for ID {prop_id}: {e}")
            return None

    # ---------------- Save Property to Database ----------------
    def save_property_to_db(self, data):
        if not data.get("id"):
            log.warning(f"⚠ Skipping invalid property (missing ID): {data}")
            return None

        external_id = data["id"]
        title = data.get("title") or f"Untitled Property {external_id}"

        # ---------------- Developer ----------------
        developer_data = data.get("developer_company") or {}
        developer, _ = Developer.objects.update_or_create(
            id=developer_data.get("id"),
            defaults={"name": developer_data.get("name") or "Unnamed Developer"}
        )

        # ---------------- City ----------------
        city_data = data.get("city") or {}
        city, _ = City.objects.update_or_create(
            id=city_data.get("id"),
            defaults={"name": city_data.get("name") or "Unnamed City"}
        )

        # ---------------- District ----------------
        district_data = data.get("district") or {}
        district_id = district_data.get("id")
        if not district_id:
            log.warning(f"⚠ Skipping property due to missing district ID: {district_data}")
            return None

        District.objects.filter(id=district_id).update(
            name=district_data.get("name") or "Unnamed District",
            city=city
        )
        district, _ = District.objects.get_or_create(
            id=district_id,
            defaults={"name": district_data.get("name") or "Unnamed District", "city": city}
        )

        # ---------------- Property Type ----------------
        prop_type_data = data.get("property_type") or {}
        prop_type, _ = PropertyType.objects.update_or_create(
            id=prop_type_data.get("id"),
            defaults={"name": prop_type_data.get("name") or "Unknown Type"}
        )

        # ---------------- Property Status ----------------
        prop_status_data = data.get("property_status") or {}
        prop_status, _ = PropertyStatus.objects.update_or_create(
            id=prop_status_data.get("id"),
            defaults={"name": prop_status_data.get("name") or "Unnamed Status"}
        )

        # ---------------- Sales Status ----------------
        sales_status_data = data.get("sales_status") or {}
        sales_status, _ = SalesStatus.objects.update_or_create(
            id=sales_status_data.get("id"),
            defaults={"name": sales_status_data.get("name") or "Unnamed Sales Status"}
        )

        updated_at_raw = parse_datetime(data.get("updated_at")) or now()
        updated_at = make_aware(updated_at_raw) if is_naive(updated_at_raw) else updated_at_raw

        # ---------------- Save Property ----------------
        with transaction.atomic():
            # ---------------- Unique Slug First ----------------
            base_slug = slugify(title)
            slug = base_slug
            num = 1
            while Property.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{num}"
                num += 1

            prop, created = Property.objects.update_or_create(
                external_id=external_id,
                defaults={
                    "title": title,
                    "slug": slug,  # <- assign the slug here before save
                    "description": data.get("description") or "",
                    "cover": data.get("cover"),
                    "address": data.get("address"),
                    "address_text": data.get("address_text"),
                    "delivery_date": convert_mm_yyyy_to_date(data.get("delivery_date")),
                    "low_price": data.get("low_price") or 0,
                    "min_area": data.get("min_area") or 0,
                    "payment_plan": data.get("payment_plan") == 1,
                    "post_delivery": data.get("post_delivery") == 1,
                    "payment_minimum_down_payment": data.get("payment_minimum_down_payment") or 0,
                    "guarantee_rental_guarantee": data.get("guarantee_rental_guarantee") == 1,
                    "guarantee_rental_guarantee_value": data.get("guarantee_rental_guarantee_value") or 0,
                    "down_payment": data.get("downPayment") or 0,
                    "updated_at": updated_at,
                    "city": city,
                    "district": district,
                    "developer": developer,
                    "property_type": prop_type,
                    "property_status": prop_status,
                    "sales_status": sales_status
                }
            )

            # ---------------- Ensure Unique Slug ----------------
            if not prop.slug:
                base_slug = slugify(prop.title)
                slug = base_slug
                num = 1
                while Property.objects.exclude(pk=prop.pk).filter(slug=slug).exists():
                    slug = f"{base_slug}-{num}"
                    num += 1
                prop.slug = slug
                prop.save(update_fields=["slug"])

            # ---------------- Facilities ----------------
            prop.facilities.clear()
            for f in data.get("property_facilities", []):
                facility_data = f.get("facility", {})
                facility_id = facility_data.get("id")
                facility_name = facility_data.get("name")
                if facility_id:
                    facility_obj, _ = Facility.objects.get_or_create(
                        id=facility_id,
                        defaults={"name": facility_name}
                    )
                    prop.facilities.add(facility_obj)

            # ---------------- Grouped Apartments ----------------
            prop.grouped_apartments.all().delete()
            for g in data.get("grouped_apartments") or []:
                rooms = g.get("Rooms") or 0
                GroupedApartment.objects.create(
                    property=prop,
                    unit_type=g.get("Unit_Type"),
                    rooms=rooms,
                    min_price=g.get("min_price") or 0,
                    min_area=g.get("min_area") or 0
                )

            # ---------------- Property Images ----------------
            prop.property_images.all().delete()
            for img in data.get("property_images") or []:
                PropertyImages.objects.create(
                    property=prop,
                    image=img.get("image")
                )

            # ---------------- Payment Plans ----------------
            prop.payment_plans.all().delete()
            for plan in data.get("payment_plans") or []:
                pp = PaymentPlan.objects.create(
                    id=plan.get("id"),
                    property=prop,
                    name=plan.get("name"),
                    description=plan.get("description")
                )
                for val in plan.get("values", []):
                    PaymentPlanValue.objects.create(
                        id=val.get("id"),
                        payment_plan=pp,
                        name=val.get("name"),
                        value=val.get("value")
                    )

        return prop