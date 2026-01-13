
from django.urls import path
from . import views
from django.contrib.sitemaps.views import sitemap
from .views import robots_txt
from .sitemaps import (
    StaticViewSitemap,
    BlogPostSitemap,
    PropertySitemap,
    DeveloperSitemap,
)


app_name = 'main'

sitemaps = {
    'static': StaticViewSitemap,
    'blogs': BlogPostSitemap,
    'properties': PropertySitemap,
    'developers': DeveloperSitemap,
}

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('blog/', views.blog, name='blog'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('contact/', views.contact, name='contact'),
    path('properties/', views.properties, name='properties'),
    # path('properties_detail/', views.properties_detail, name='properties_detail'),
    path('property/<slug:slug>/', views.properties_detail, name='properties_detail'),
    path('community/<slug:slug>/', views.community_properties, name='community_properties'),
    path('communities/', views.all_communities, name='all_communities'),
    path('city/<slug:slug>/', views.city_properties, name='city_properties'),
    path('developer/', views.developer, name='developer'),
    path('developer/<slug:slug>/', views.developer_detail, name='developer_detail'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-and-conditions/', views.terms_and_conditions, name='terms_and_conditions'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
]   
