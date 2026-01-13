from .models import Developer
from django.db.models import Count


def global_context(request):
    """Add featured developers for footer"""
    return {
        'featured_developers' : Developer.objects.annotate(project_count=Count('properties')).order_by('-project_count')[:5]
    }