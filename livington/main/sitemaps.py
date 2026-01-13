from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import BlogPost, Property, Developer


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'monthly'

    def items(self):
        return [
            'main:home', 
            'main:about',
            'main:all_communities',  
            'main:blog', 
            'main:contact', 
            'main:developer',  
            'main:properties'
        

        ]

    def location(self, item):
        return reverse(item)


class BlogPostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return BlogPost.objects.all()

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()  # Make sure your BlogPost model defines get_absolute_url()


class PropertySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Property.objects.all()

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        # ✅ FIX: use slug instead of external_id
        return reverse('main:properties_detail', args=[obj.slug])


class DeveloperSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Developer.objects.all()

    def location(self, obj):
        # ✅ FIX: use slug instead of id
        return reverse('main:developer_detail', args=[obj.slug])


sitemaps = {
    'static': StaticViewSitemap,
    'blogs': BlogPostSitemap,
    'properties': PropertySitemap,
    'developers': DeveloperSitemap,
}