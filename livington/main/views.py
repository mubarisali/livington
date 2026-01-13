from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Prefetch, Count, Min, Max, Avg, Q, FloatField
from django.http import JsonResponse
from .models import *
from django.views.decorators.csrf import csrf_exempt
import json
from django.utils.html import strip_tags
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Min, Max, Avg, Q
import re
from django.db.models import Case, When, Value, IntegerField
from django.http import HttpResponse
import random



def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Allow: /",
        "Sitemap: https://www.buyoffplanuae.com/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


ALL_UNIT_TYPES = [
    'Apartment',
    'Penthouse',
    'Duplex',
    'Villa',
    'Townhouse',
    'Land/Plot',
    'Shop',
    'Retail',
    'Hotel Apartment',
    'Office'
]

def base(request):
    canonical_url = request.build_absolute_uri()

    context = {
        'canonical_url': canonical_url,
    }
    return render(request, 'base.html', context )


def home(request):
    """Render the home page with complete filtering + city/district tabs"""

    # ---------------------------
    # EXISTING PROPERTY FILTERING
    # ---------------------------
    all_properties = Property.objects.all()
    total_count = all_properties.count()
    print(total_count,'count')

    filtered_properties = all_properties

    search_query = request.GET.get('search', '').strip()
    developer_filter = request.GET.get('developer')
    type_filter = request.GET.get('type', '')
    location_filter = request.GET.get('location', '')
    status_filter = request.GET.get('status', '')
    unit_type_filter = request.GET.get('unit_type', '').strip()  # NEW: Unit type filter
    
    # NEW: Price Range Slider Filters
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    
    # Legacy price filter (for backward compatibility)
    price_filter = request.GET.get('price', '')

    has_filters = any([
        search_query, price_filter, developer_filter,
        type_filter, location_filter, status_filter,
        min_price, max_price, unit_type_filter  # Add to has_filters check
    ])
    

    if search_query:
        filtered_properties = filtered_properties.filter(
            Q(title__icontains=search_query) |
            Q(developer__name__icontains=search_query) |
            Q(city__name__icontains=search_query) |
            Q(district__name__icontains=search_query)
        )

    # NEW: PRICE RANGE SLIDER FILTER (Priority)
    if min_price or max_price:
        try:
            min_val = int(min_price) if min_price else 0
            max_val = int(max_price) if max_price else 250000000

            filtered_properties = filtered_properties.filter(
                low_price__gte=min_val,
                low_price__lte=max_val
            )
        except (ValueError, TypeError):
            pass

    # LEGACY: Preset Price Range Filters (fallback if slider not used)
    elif price_filter:
        if price_filter == 'under_500k':
            filtered_properties = filtered_properties.filter(low_price__lt=500000)
        elif price_filter == '500k_1m':
            filtered_properties = filtered_properties.filter(low_price__gte=500000, low_price__lt=1000000)
        elif price_filter == '1m_2m':
            filtered_properties = filtered_properties.filter(low_price__gte=1000000, low_price__lt=2000000)
        elif price_filter == '2m_3m':
            filtered_properties = filtered_properties.filter(low_price__gte=2000000, low_price__lt=3000000)
        elif price_filter == '3m_4m':
            filtered_properties = filtered_properties.filter(low_price__gte=3000000, low_price__lt=4000000)
        elif price_filter == '4m_5m':
            filtered_properties = filtered_properties.filter(low_price__gte=4000000, low_price__lt=5000000)
        elif price_filter == 'above_5m':
            filtered_properties = filtered_properties.filter(low_price__gte=5000000)

    # NEW: UNIT TYPE FILTER - Handles all unit types
    if unit_type_filter:
        filtered_properties = (
            filtered_properties
            .annotate(
                distinct_unit_types=Count(
                    'grouped_apartments__unit_type',
                    distinct=True
                )
            )
            .filter(
                distinct_unit_types=1,  # ✅ ONLY ONE unit type allowed
                grouped_apartments__unit_type__iexact=unit_type_filter
            )
        )

    # OTHER FILTERS
    if developer_filter:
        filtered_properties = filtered_properties.filter(developer__name__icontains=developer_filter)

    if type_filter:
        filtered_properties = filtered_properties.filter(property_type_id=type_filter)

    if location_filter:
        filtered_properties = filtered_properties.filter(city_id=location_filter)

    if status_filter:
        filtered_properties = filtered_properties.filter(sales_status_id=status_filter)

    filtered_count = filtered_properties.count()
    has_more_properties = filtered_count > 8

    # CHANGED: Sort by low_price ascending (lowest to highest)
    offplan = filtered_properties.filter(
        low_price__gte=200000,
        low_price__lte=1000000
    ).order_by('low_price')[:8]

    # --------------------------------------
    # NEW: CITY & DISTRICT TAB FUNCTIONALITY
    # --------------------------------------

    cities = (
        City.objects
        .exclude(name__iexact='Unnamed City')
        .exclude(name__iexact='Fujairah')
        .annotate(
            dubai_first=Case(
                When(name__iexact='Dubai', then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by('dubai_first', 'name')
    )

    # Priority mapping for major cities (includes all unit types)
    priority_map = {
        'dubai': ['Villa', 'Penthouse', 'Townhouse', 'Duplex','Office' ],
        'abu dhabi': ['Apartment', 'Villa', 'Penthouse', 'Townhouse', 'Duplex'],
        'sharjah': ['Apartment', 'Villa', 'Townhouse', 'Shop', 'Office', 
                   'Land/Plot', 'Retail', 'Duplex',],
        'ajman': ['Apartment', 'Villa', 'Townhouse', 'Shop', 'Office', 
                 'Land/Plot', 'Retail', 'Hotel Apartment'],
        'ras al khaimah': ['Apartment', 'Villa', 'Townhouse', 'Land/Plot', 
                          'Penthouse', 'Duplex'],
        'umm al quwain': ['Apartment', 'Villa', 'Townhouse', 'Land/Plot'],
    }

    for city in cities:
        # Get all unit types available in this city
        unit_types = (
            GroupedApartment.objects.filter(
                property__district__city=city
            )
            .values_list('unit_type', flat=True)
            .distinct()
            .order_by('unit_type')
        )

        # Clean and filter out None/empty values
        unit_types = [ut for ut in unit_types if ut]

        city_name_lower = city.name.lower()

        if city_name_lower in priority_map:
            # Create case-insensitive lookup
            unit_types_lower = {ut.lower(): ut for ut in unit_types}

            # Get prioritized unit types that exist in this city
            city.unit_types = [
                ut for ut in priority_map[city_name_lower]
                if ut.lower() in unit_types_lower
            ]
        else:
            # For other cities, use the global priority order
            unit_types_lower = {ut.lower(): ut for ut in unit_types}
            city.unit_types = [
                ut for ut in ALL_UNIT_TYPES
                if ut.lower() in unit_types_lower
            ][:8]  # Limit to 8 types for other cities

    # Get active city from GET parameter
    active_city_slug = request.GET.get("city", None)

    if active_city_slug:
        active_city = City.objects.filter(slug=active_city_slug).first()
    else:
        active_city = cities.first()

    # Districts with average price + property count + unit types
    if active_city:
        districts = (
            active_city.districts.all()
            .annotate(
                property_count=Count('properties'),
                avg_price=Coalesce(Avg('properties__low_price'), 0, output_field=FloatField())
            )
            .order_by("name")[:8]
        )
        
        # Add unit types to each district
        for district in districts:
            # Get unique unit types from grouped apartments for this district's properties
            unit_types = GroupedApartment.objects.filter(
                property__district=district
            ).values_list('unit_type', flat=True).distinct().order_by('unit_type')
            
            # Filter out None/empty values
            available_types = [ut for ut in unit_types if ut]
            
            # Prioritize unit types based on global list
            unit_types_lower = {ut.lower(): ut for ut in available_types}
            district.unit_types = [
                ut for ut in ALL_UNIT_TYPES
                if ut.lower() in unit_types_lower
            ][:8]  # Limit to 8 types per district
            
    else:
        districts = District.objects.none()
    
    # --------------------------------------
    # CONTEXT
    # --------------------------------------
    context = {
        # FILTER SYSTEM
        'offplan': offplan,
        
        'developers': Developer.objects.all(),
        'types': PropertyType.objects.all().exclude(name__iexact='Unknown Type'),
        'location': City.objects.all().exclude(name__iexact='Unnamed City'),
        'status': SalesStatus.objects.all(),
        'selected_price': price_filter,
        'selected_developer': developer_filter,
        'selected_type': type_filter,
        'selected_location': location_filter,
        'selected_status': status_filter,
        'search_query': search_query,
        'filtered_count': filtered_count,
        'total_count': total_count,
        'has_filters': has_filters,
        'has_more_properties': has_more_properties,
        'selected_unit_type': unit_type_filter,  # NEW

        # NEW - CITY / DISTRICTS TAB DATA
        'cities': cities,
        'active_city': active_city,
        'districts': districts,
        'all_unit_types': ALL_UNIT_TYPES,  # NEW

        # SEO
        'page_title': 'Home - Off Plan UAE',
        'meta_description': 'Discover premium off-plan properties in UAE',
    }

    return render(request, 'main/home.html', context)




def get_price_statistics():
    """
    Get min/max prices from database for dynamic slider configuration
    Use this if you want the slider bounds to be based on actual data
    """
    from django.db.models import Min, Max
    
    stats = Property.objects.filter(low_price__isnull=False).aggregate(
        min_price=Min('low_price'),
        max_price=Max('low_price')
    )
    
    return {
        'min_price': stats['min_price'] or 0,
        'max_price': stats['max_price'] or 250000000,
    }





def about(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        messages.success(request, 'Thank you for subscribing!')
        return redirect('about')
    
    context = {
        'page_title': 'About Us - OffPlanUAE.ai',
        'meta_description': 'Learn about OffPlanUAE.ai - transforming property discovery in UAE with AI technology.',
    }
    return render(request, 'main/about.html', context)


# ========================================
# UPDATED BLOG VIEW - OPTIMIZED SEO TITLES
# ========================================
def blog(request):
    """Render the blog page with all blog posts from database"""
    # Get all blog posts from database, ordered by published date
    blog_posts = BlogPost.objects.all().order_by('-published_at')
    
    # Pagination - 6 posts per page
    paginator = Paginator(blog_posts, 6)
    page_number = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    # ========================================
    # OPTIMIZED SEO TITLE (50 chars max)
    # ========================================
    # OLD (88 chars - TOO LONG): ❌
    # "BuyOffPlanUAE.com - Insights, Expertise, and Opportunities in Dubai Off-Plan Real Estate"
    
    # NEW (50 chars - OPTIMAL): ✅
    if int(page_number) == 1:
        page_title = "Dubai Off-Plan Property Blog | BuyOffPlanUAE"
    else:
        page_title = f"Dubai Off-Plan Blog Page {page_number} | BuyOffPlanUAE"
    
    # Optimized meta description
    meta_description = (
        "Explore Dubai off-plan properties with expert insights, market trends, "
        "investment opportunities, trusted developers, and easy step-by-step buying guides."
    )
    
    context = {
        'page_title': page_title,
        'meta_description': meta_description,
        'blog_posts': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'main/blog.html', context)


# ========================================
# UPDATED BLOG DETAIL VIEW - OPTIMIZED TITLES
# ========================================
def blog_detail(request, slug):
    """Render individual blog post detail page from database"""

    blog_post = get_object_or_404(BlogPost, slug=slug)
    full_image_url = request.build_absolute_uri(blog_post.featured_image.url)

    # Increment view count
    blog_post.views += 1
    blog_post.save(update_fields=['views'])

    # Related posts (exclude current)
    related_posts = (
        BlogPost.objects
        .exclude(id=blog_post.id)
        .order_by('-published_at')[:3]
    )

    # Handle contact form submission
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        message = request.POST.get('message')

        if name and email and phone and message:
            ContactSubmission.objects.create(
                name=name,
                email=email,
                phone=phone,
                message=f"Blog Contact Form - {blog_post.title}\n\n{message}"
            )
            messages.success(
                request,
                'Thank you for contacting us! We will get back to you within 24 hours.'
            )
            return redirect(blog_post.get_absolute_url())

    # ========================================
    # OPTIMIZED PAGE TITLE (MAX 60 CHARS)
    # ========================================
    max_title_length = 45  # Leave room for " | BuyOffPlanUAE"
    
    if len(blog_post.title) <= max_title_length:
        page_title = f"{blog_post.title} | BuyOffPlanUAE"
    else:
        # Truncate at word boundary
        short_title = blog_post.title[:max_title_length]
        last_space = short_title.rfind(' ')
        if last_space > 0:
            short_title = short_title[:last_space]
        page_title = f"{short_title}... | BuyOffPlanUAE"
    
    # Ensure title doesn't exceed 60 characters
    if len(page_title) > 60:
        page_title = page_title[:57] + "..."

    context = {
        'page_title': page_title,
        'meta_description': (
            blog_post.excerpt
            if blog_post.excerpt
            else strip_tags(blog_post.content)[:160]
        ),
        'blog_post': blog_post,
        'related_posts': related_posts,
        'full_image_url': full_image_url
    }

    return render(request, 'main/blog_detail.html', context)


@csrf_exempt
def contact(request):
    """Handle contact form submission"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            email = data.get('email', '').strip()
            phone = data.get('phone', '').strip()
            subject = data.get('subject', '').strip()
            message = data.get('message', '').strip()
            
            errors = {}
            if not name:
                errors['name'] = 'Name is required'
            if not email or '@' not in email:
                errors['email'] = 'Valid email is required'
            if not phone:
                errors['phone'] = 'Phone number is required'
            if not subject:
                errors['subject'] = 'Subject is required'
            if not message:
                errors['message'] = 'Message is required'
            
            if errors:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Please fill all required fields',
                    'errors': errors
                }, status=400)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Thank you for contacting us! We will get back to you within 24 hours.'
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request format'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': 'An error occurred. Please try again later.'
            }, status=500)
    
    context = {
        'page_title': 'Contact Us - Off Plan UAE',
        'meta_description': 'Get in touch with Off Plan UAE for property inquiries',
    }
    return render(request, 'main/contact.html', context)

def clean_description(text):
    if not text:
        return ""

    # Remove HTML tags
    text = strip_tags(text)

    # Remove CSS property-like junk inside text
    text = re.sub(r"[a-zA-Z\-]+:\s*[^;]+;", "", text)

    # Remove leftover symbols, brackets, and extra spaces
    text = re.sub(r"[<>]", "", text)
    text = text.replace("&nbsp;", " ").replace("\xa0", " ")

    # Normalize spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text



from django.core.paginator import Paginator
from django.db.models import Q



def properties(request):
    """
    Properties listing page with comprehensive filtering
    Handles both hero section filters and properties page filters
    """
    # ---------------------------
    # Base queryset
    # ---------------------------
    project = Property.objects.all()
    
    # ---------------------------
    # Get filter parameters
    # ---------------------------
    price_filter = request.GET.get('price', '')  # Dropdown price filter
    developer_filter = request.GET.get('developer', '')
    type_filter = request.GET.get('type', '')  # Can be either footer link (string) or property type ID
    location_filter = request.GET.get('location', '')
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    # NEW: Price range slider from hero section
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    
    # ---------------------------
    # Apply search filter
    # ---------------------------
    if search_query:
        project = project.filter(
            Q(title__icontains=search_query) |
            Q(developer__name__icontains=search_query) |
            Q(city__name__icontains=search_query) |
            Q(district__name__icontains=search_query)
        )
    
    # ---------------------------
    # Apply price filters
    # Priority: min/max slider > dropdown filter
    # ---------------------------
    if min_price or max_price:
        # Handle price range slider from hero section
        try:
            min_val = int(min_price) if min_price else 0
            max_val = int(max_price) if max_price else 250000000
            
            # Apply filter only if values differ from defaults
            if min_val > 0 or max_val < 250000000:
                project = project.filter(
                    Q(low_price__gte=min_val) & Q(low_price__lte=max_val)
                )
        except (ValueError, TypeError):
            pass  # Skip if conversion fails
    elif price_filter:
        # Handle dropdown price filter (fallback)
        if price_filter == 'under_500k':
            project = project.filter(low_price__lt=500000)
        elif price_filter == '500k_1m':
            project = project.filter(low_price__gte=500000, low_price__lt=1000000)
        elif price_filter == '1m_2m':
            project = project.filter(low_price__gte=1000000, low_price__lt=2000000)
        elif price_filter == '2m_3m':
            project = project.filter(low_price__gte=2000000, low_price__lt=3000000)
        elif price_filter == '3m_4m':
            project = project.filter(low_price__gte=3000000, low_price__lt=4000000)
        elif price_filter == '4m_5m':
            project = project.filter(low_price__gte=4000000, low_price__lt=5000000)
        elif price_filter == 'above_5m':
            project = project.filter(low_price__gte=5000000)
    
    # ---------------------------
    # Apply developer filter
    # ---------------------------
    if developer_filter:
        project = project.filter(developer__name=developer_filter)
    
    # ---------------------------
    # Apply property type filter
    # Handles both footer links (string) and dropdown (ID)
    # ---------------------------
    if type_filter:
        # Check if it's a footer unit type (string like 'Villa', 'Apartment')
        allowed_types = ['Villa', 'Apartment', 'Townhouse', 'Penthouse', 'Studio', 'Duplex']
        if type_filter in allowed_types:
            project = project.filter(grouped_apartments__unit_type__iexact=type_filter).distinct()
        else:
            # Try as property type ID
            try:
                project = project.filter(property_type__name=type_filter)
            except:
                pass
    
    # ---------------------------
    # Apply location filter
    # ---------------------------
    if location_filter:
        try:
            # Try filtering by city ID first
            project = project.filter(city_id=int(location_filter))
        except (ValueError, TypeError):
            # Fallback to city name
            project = project.filter(city__name=location_filter)
    
    # ---------------------------
    # Apply status filter
    # ---------------------------
    if status_filter:
        try:
            # Try filtering by status ID first
            project = project.filter(sales_status_id=int(status_filter))
        except (ValueError, TypeError):
            # Fallback to status name
            project = project.filter(sales_status__name=status_filter)
    
    # ---------------------------
    # Pagination
    # ---------------------------
    paginator = Paginator(project, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # ---------------------------
    # Context
    # ---------------------------
    context = {
        'project': page_obj,
        'types': PropertyType.objects.all().exclude(name__iexact='Unknown Type'),
        'developers': Developer.objects.all(),
        'location': City.objects.all().exclude(name__iexact='Unnamed City'),
        'status': SalesStatus.objects.all(),
        'selected_price': price_filter,
        'selected_developer': developer_filter,
        'selected_type': type_filter,
        'selected_location': location_filter,
        'selected_status': status_filter,
        'search_query': search_query,
        'min_price': min_price,  # Pass to template for display
        'max_price': max_price,  # Pass to template for display
        'footer_property_types': GroupedApartment.objects.all().exclude(unit_type__iexact='Unknown Type'),
    } 
    return render(request, 'main/properties.html', context)

from collections import defaultdict

def properties_detail(request, slug):

    property_obj = (
        Property.objects.select_related(
            "developer", "city", "district",
            "property_type", "property_status",
            "sales_status"
        )
        .prefetch_related(
            "property_images",
            "facilities",
            Prefetch("grouped_apartments", queryset=GroupedApartment.objects.all())
        )
        .filter(slug=slug)
        .first()
    )

    if not property_obj:
        return render(request, "404.html", status=404)

    # -------------------------------------
    # Parse latitude, longitude
    # -------------------------------------
    if property_obj.address:
        try:
            lat, lng = [coord.strip() for coord in property_obj.address.split(",")]
        except:
            lat, lng = None, None
    else:
        lat, lng = None, None

    # -------------------------------------
    # CLEAN DESCRIPTION (SEO SAFE)
    # -------------------------------------
    text = property_obj.description or ""

    text = re.sub(r'style="[^"]*"', "", text, flags=re.IGNORECASE)
    text = re.sub(r'class="[^"]*"', "", text, flags=re.IGNORECASE)
    text = re.sub(r"[a-zA-Z\-]+\s*:\s*[^;]+;", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()

    property_obj.description = text  # NOT SAVED TO DB

    # -------------------------------------
    # CONTACT FORM
    # -------------------------------------
    if request.method == "POST":
        messages.success(request, "Thank you! We will contact you soon.")
        return redirect("main:properties_detail", slug=slug)

    # -------------------------------------
    # GROUP UNITS BY BEDROOM
    # -------------------------------------
    bedroom_units = defaultdict(list)
    for unit in property_obj.grouped_apartments.all():
        if unit.rooms and unit.rooms.split()[0].isdigit():
            bedrooms = int(unit.rooms.split()[0])
            bedroom_units[bedrooms].append(unit)

    bedroom_units = dict(sorted(bedroom_units.items()))

    # -------------------------------------
    # SEO TITLE & META DESCRIPTION (LIMIT SAFE)
    # -------------------------------------
    project_name = property_obj.title.strip()
    district = property_obj.district.name.strip() if property_obj.district else ""
    city = property_obj.city.name.strip() if property_obj.city else "Dubai"

    def word_count(value):
        return len(value.split())

    # ---------- TITLE (MAX 60 WORDS) ----------
    title_variants = [
        f"{project_name} in {district},  ",
        f"{project_name} in {city} | Off-Plan Property Dubai",
        f"{project_name} | Off-Plan Property Dubai",
        project_name
    ]

    seo_title = next(
        (t for t in title_variants if word_count(t) <= 60),
        project_name
    )

    # ---------- META DESCRIPTION (MAX 160 CHARS) ----------
    SEO_DESCRIPTIONS = [
        "Discover premium off-plan living with flexible payment plans and high ROI potential.",
        "A modern residential project offering luxury amenities in a prime location.",
        "Ideal for investors and end-users seeking comfort and long-term value.",
        "Experience contemporary architecture with world-class facilities.",
        "An exclusive development designed for smart property investment."
    ]

    desc_variants = [
        f"{project_name} located in {district}, {city}. {random.choice(SEO_DESCRIPTIONS)}",
        f"{project_name} located in {district}, {city}.",
        f"{project_name} located in {city}.",
        project_name
    ]

    seo_description = next(
        (d for d in desc_variants if len(d) <= 160),
        project_name
    )

    # -------------------------------------
    # CONTEXT
    # -------------------------------------
    context = {
        "property": property_obj,
        "page_title": seo_title,
        "meta_description": seo_description,
        "images": property_obj.property_images.all(),
        "facilities": property_obj.facilities.all(),
        "units": property_obj.grouped_apartments.all(),
        "units_by_bedroom": bedroom_units,
        "lat": lat,
        "lng": lng,
        "clean_description": text,
    }

    return render(request, "main/properties_detail.html", context)

def community_properties(request, slug):
    """Show all properties in a specific community (district)"""
    
    district = get_object_or_404(District, slug=slug)
    print(district.slug,'communities')
    
    properties = Property.objects.filter(
        district=district
    ).select_related(
        'developer', 'city', 'district', 
        'property_type', 'property_status', 'sales_status'
    ).prefetch_related('property_images')
    
    price_filter = request.GET.get('price', '')
    developer_filter = request.GET.get('developer', '')
    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    
    if price_filter == 'under_500k':
        properties = properties.filter(low_price__lt=500000)
    elif price_filter == '500k_1m':
        properties = properties.filter(low_price__gte=500000, low_price__lt=1000000)
    elif price_filter == '1m_2m':
        properties = properties.filter(low_price__gte=1000000, low_price__lt=2000000)
    elif price_filter == '2m_3m':
        properties = properties.filter(low_price__gte=2000000, low_price__lt=3000000)
    elif price_filter == '3m_4m':
        properties = properties.filter(low_price__gte=3000000, low_price__lt=4000000)
    elif price_filter == '4m_5m':
        properties = properties.filter(low_price__gte=4000000, low_price__lt=5000000)
    elif price_filter == 'above_5m':
        properties = properties.filter(low_price__gte=5000000)
    
    if developer_filter:
        properties = properties.filter(developer_id=developer_filter)
    
    if type_filter:
        properties = properties.filter(property_type_id=type_filter)
    
    if status_filter:
        properties = properties.filter(sales_status_id=status_filter)
    
    total_count = properties.count()
    min_price = properties.aggregate(Min('low_price'))['low_price__min'] or 0
    avg_price = properties.aggregate(Avg('low_price'))['low_price__avg'] or 0
    
    paginator = Paginator(properties.order_by('-low_price'), 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'district': district,
        'properties': page_obj,
        'total_count': total_count,
        'min_price': min_price,
        'avg_price': int(avg_price),
        'developers': Developer.objects.filter(
            properties__district=district
        ).distinct(),
        'types': PropertyType.objects.filter(
            properties__district=district
        ).distinct().exclude(name__iexact='Unknown Type'),
        'status': SalesStatus.objects.filter(
            properties__district=district
        ).distinct(),
        'selected_price': price_filter,
        'page_title': f'{district.name} - Properties',
        'meta_description': f'Explore {total_count} properties in {district.name}, {district.city.name if district.city else "UAE"}',
    }
    
    return render(request, 'main/community_properties.html', context)
  

def all_communities(request):
    """Display all communities with filtering, sorting, and pagination"""
    communities = District.objects.exclude(
        slug__isnull=True
    ).exclude(slug="")
    print(communities,'commm')

    # Get all cities excluding unnamed
    cities = City.objects.all().order_by("name").exclude(name__iexact='Unnamed City')
    
    # Get all districts with aggregated data
    all_districts = (
        District.objects.all()
        .select_related('city')
        .prefetch_related('properties')
        .annotate(
            property_count=Count('properties'),
            avg_price=Coalesce(Avg('properties__low_price'), 0, output_field=FloatField())
        )
        .filter(property_count__gt=0)  # Only show districts with properties
        .order_by('name')
    )
    
    # Filter by city if requested
    city_filter = request.GET.get('city', '')
    if city_filter:
        all_districts = all_districts.filter(city__slug=city_filter)
    
    # Sorting
    sort_by = request.GET.get('sort', 'name-asc')
    if sort_by == 'name-desc':
        all_districts = all_districts.order_by('-name')
    elif sort_by == 'projects-desc':
        all_districts = all_districts.order_by('-property_count')
    elif sort_by == 'projects-asc':
        all_districts = all_districts.order_by('property_count')
    elif sort_by == 'price-desc':
        all_districts = all_districts.order_by('-avg_price')
    elif sort_by == 'price-asc':
        all_districts = all_districts.order_by('avg_price')
    else:  # name-asc (default)
        all_districts = all_districts.order_by('name')
    
    # Pagination - 12 communities per page
    paginator = Paginator(all_districts, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Prepare community data for template
    communities = []
    for district in page_obj:
        first_property = district.properties.first()
        communities.append({
            'id': district.id,
            'name': district.name,
            'slug':district.slug,
            'city_name': district.city.name if district.city else 'UAE',
            'city_slug': district.city.slug if district.city else 'uae',
            'property_count': district.property_count,
              'avg_price': district.avg_price if district.avg_price > 0 else None, 
            'first_property_cover': first_property.cover if first_property else '/static/images/no-image.jpg',
        })
    
    # Calculate totals
    total_communities = all_districts.count()
    total_properties = Property.objects.filter(district__in=all_districts).count()
    
    context = {
        'communities': communities,
        'cities': cities,
        'total_communities': total_communities,
        'total_properties': total_properties,
        'page_obj': page_obj,
        'selected_city': city_filter,
        'selected_sort': sort_by,
        'page_title': 'All Communities - UAE Real Estate',
        'meta_description': f'Explore {total_communities} communities across UAE with {total_properties} premium properties',
    }
    
    return render(request, 'main/all_communities.html', context)  


def city_properties(request, slug):
    """View to display all properties in a specific city with unit type filtering"""
    # Get the city by slug
    city = get_object_or_404(City, slug=slug)
    
    # Get all properties in this city
    properties_list = Property.objects.filter(city=city).select_related(
        'developer', 'property_type', 'property_status', 'district', 'city'
    )
    
    # Apply filters
    selected_price = request.GET.get('price', '')
    developer_id = request.GET.get('developer', '')
    type_id = request.GET.get('type', '')
    status_id = request.GET.get('status', '')
    unit_type = request.GET.get('unit_type', '').strip()  # Unit type filter

    if developer_id:
        properties_list = properties_list.filter(developer_id=developer_id)
    if type_id:
        properties_list = properties_list.filter(property_type_id=type_id)
    if status_id:
        properties_list = properties_list.filter(property_status_id=status_id)
    
    # NEW: Unit type filter - handles all 10 types
    if unit_type:
        properties_list = (
            properties_list
            .annotate(
                distinct_unit_types=Count(
                    'grouped_apartments__unit_type',
                    distinct=True
                )
            )
            .filter(
                distinct_unit_types=1,  # ✅ ONLY ONE unit type allowed
                grouped_apartments__unit_type__iexact=unit_type
            )
        )

    
    # Price filtering
    if selected_price == 'under_500k':
        properties_list = properties_list.filter(low_price__lt=500000)
    elif selected_price == '500k_1m':
        properties_list = properties_list.filter(low_price__gte=500000, low_price__lt=1000000)
    elif selected_price == '1m_2m':
        properties_list = properties_list.filter(low_price__gte=1000000, low_price__lt=2000000)
    elif selected_price == '2m_3m':
        properties_list = properties_list.filter(low_price__gte=2000000, low_price__lt=3000000)
    elif selected_price == '3m_4m':
        properties_list = properties_list.filter(low_price__gte=3000000, low_price__lt=4000000)
    elif selected_price == '4m_5m':
        properties_list = properties_list.filter(low_price__gte=4000000, low_price__lt=5000000)
    elif selected_price == 'above_5m':
        properties_list = properties_list.filter(low_price__gte=5000000)
    
    # Calculate statistics before pagination
    total_count = properties_list.count()
    avg_price = properties_list.aggregate(Avg('low_price'))['low_price__avg'] or 0
    
    # Get filter options (only from properties in this city)
    developers = Developer.objects.filter(properties__city=city).distinct()
    types = PropertyType.objects.filter(properties__city=city).exclude(name__iexact='Unknown Type').distinct()
    status = PropertyStatus.objects.filter(properties__city=city).distinct()
    
    # NEW: Get available unit types for this city
    available_unit_types_raw = (
        GroupedApartment.objects.filter(
            property__city=city
        )
        .values_list('unit_type', flat=True)
        .distinct()
    )
    
    # Filter and prioritize unit types
    available_types = [ut for ut in available_unit_types_raw if ut]
    unit_types_lower = {ut.lower(): ut for ut in available_types}
    
    # Prioritize based on ALL_UNIT_TYPES order
    available_unit_types = [
        ut for ut in ALL_UNIT_TYPES
        if ut.lower() in unit_types_lower
    ]
    
    # Pagination
    paginator = Paginator(properties_list, 12)
    page = request.GET.get('page')
    querydict = request.GET.copy()
    querydict.pop('page', None)  # remove page if exists

    filter_query = querydict.urlencode()
        
    try:
        properties_list = paginator.page(page)
    except PageNotAnInteger:
        properties_list = paginator.page(1)
    except EmptyPage:
        properties_list = paginator.page(paginator.num_pages)
    
    # Build page title and meta description based on unit type
    if unit_type:
        page_title = f'{unit_type} for sale in {city.name} | Off Plan UAE'
        meta_description = f'Discover premium {unit_type.lower()}s for sale in {city.name}. Browse {total_count} off-plan properties with flexible payment plans.'
    else:
        page_title = f'Properties for sale in {city.name} | Off Plan UAE'
        meta_description = f'Browse {total_count} off-plan properties for sale in {city.name}. Find apartments, villas, townhouses and more.'
    
    context = {
        'city': city,
        'properties': properties_list,
        'total_count': total_count,
        'avg_price': avg_price,
        'developers': developers,
        'types': types,
        'status': status,
        'selected_price': selected_price,
        'selected_unit_type': unit_type,  # Pass to template
        'available_unit_types': available_unit_types,  # NEW: Available unit types for filters
        'all_unit_types': ALL_UNIT_TYPES,  # NEW: All possible unit types
        'page_title': page_title,  # Dynamic page title
        'meta_description': meta_description,  # Dynamic meta description
        'filter_query': filter_query,
    }
    
    return render(request, 'main/city_properties.html', context)

def developer(request):
    developers_list = Developer.objects.all().order_by('name')
    
    # Add property count for each developer
    for dev in developers_list:
        dev.property_count = dev.properties.count()
    
    # Pagination - 8 developers per page
    paginator = Paginator(developers_list, 9)
    page_number = request.GET.get('page')
    developers = paginator.get_page(page_number)
    
    context = {
        'developers': developers,
        'total_developers': developers_list.count()
    }
    
    return render(request, 'main/developer.html', context)


def developer_detail(request, slug):
    """Show all properties by a specific developer"""

    developer = get_object_or_404(Developer, slug=slug)
    full_image_url = request.build_absolute_uri(developer.logo)
    # -------------------------------------
    # GET ALL PROPERTIES BY DEVELOPER
    # -------------------------------------
    properties = Property.objects.filter(
        developer=developer
    ).select_related(
        'city', 'district', 'property_type',
        'property_status', 'sales_status'
    ).prefetch_related('property_images')

    # -------------------------------------
    # FILTERS
    # -------------------------------------
    price_filter = request.GET.get('price', '')
    type_filter = request.GET.get('type', '')
    location_filter = request.GET.get('location', '')
    status_filter = request.GET.get('status', '')

    if price_filter == 'under_500k':
        properties = properties.filter(low_price__lt=500000)
    elif price_filter == '500k_1m':
        properties = properties.filter(low_price__gte=500000, low_price__lt=1000000)
    elif price_filter == '1m_2m':
        properties = properties.filter(low_price__gte=1000000, low_price__lt=2000000)
    elif price_filter == '2m_3m':
        properties = properties.filter(low_price__gte=2000000, low_price__lt=3000000)
    elif price_filter == '3m_4m':
        properties = properties.filter(low_price__gte=3000000, low_price__lt=4000000)
    elif price_filter == '4m_5m':
        properties = properties.filter(low_price__gte=4000000, low_price__lt=5000000)
    elif price_filter == 'above_5m':
        properties = properties.filter(low_price__gte=5000000)

    if type_filter:
        properties = properties.filter(property_type_id=type_filter)

    if location_filter:
        properties = properties.filter(city_id=location_filter)

    if status_filter:
        properties = properties.filter(sales_status_id=status_filter)

    total_count = properties.count()

    # -------------------------------------
    # PAGINATION
    # -------------------------------------
    paginator = Paginator(properties.order_by('-low_price'), 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # -------------------------------------
    # SEO TITLE (COMMON + SAFE)
    # -------------------------------------
    developer_name = developer.name.strip()

    title_variants = [
        f"{developer_name} | Real Estate Developer in Dubai",
        f"{developer_name} | Premium Property Developer Dubai",
        f"{developer_name} | Trusted Dubai Property Developer",
        f"{developer_name} | Off-Plan Property Developer Dubai",
    ]

    page_title = next(
        (t for t in title_variants if len(t) <= 60),
        developer_name[:60]
    )

    # -------------------------------------
    # META DESCRIPTION (MAX 160 CHARS)
    # -------------------------------------
    description_variants = [
    f"{developer_name} is a trusted real estate developer in Dubai, offering premium residential and off-plan investment properties.",
    f"Discover luxury and investment properties by {developer_name}, a leading Dubai real estate developer.",
    f"{developer_name} develops high-quality residential projects in Dubai, ideal for investors and homebuyers.",
    f"Explore premium real estate developments by {developer_name} with strong ROI potential in Dubai."
]

    meta_description = next(
        (d for d in description_variants if len(d) <= 160),
        description_variants[0][:160]
    )

    # -------------------------------------
    # CONTEXT
    # -------------------------------------
    context = {
        'developer': developer,
        'properties': page_obj,
        'total_count': total_count,
        'types': PropertyType.objects.filter(properties__developer=developer).distinct(),
        'locations': City.objects.filter(properties__developer=developer).distinct(),
        'status': SalesStatus.objects.filter(properties__developer=developer).distinct(),
        'selected_price': price_filter,
        'selected_type': type_filter,
        'selected_location': location_filter,
        'selected_status': status_filter,
        'page_title': page_title,
        'meta_description': meta_description,
        'full_image_url': full_image_url,
    }

    return render(request, 'main/developer_detail.html', context)

def privacy_policy(request):
    return render(request, 'main/privacy_policy.html')


def terms_and_conditions(request):
    return render(request, 'main/terms_and_conditions.html')