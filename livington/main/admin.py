

# main/admin.py
from django.contrib import admin
from .models import *
from import_export.admin import ExportMixin, ImportExportModelAdmin
from import_export import resources


class PropertyImageInline(admin.TabularInline):
    model = PropertyImages
    extra = 3

admin.site.register(Developer)

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug','district']
    list_filter = ['title','created_at']
    search_fields = ['title', 'location', 'description']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [PropertyImageInline]



@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'submitted_at', 'is_read']
    list_filter = ['is_read', 'submitted_at']
    search_fields = ['name', 'email', 'message']
    list_editable = ['is_read']
    date_hierarchy = 'submitted_at'
    readonly_fields = ['name', 'email', 'phone', 'message', 'submitted_at']

@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ['email', 'subscribed_at', 'is_active']
    list_filter = ['is_active', 'subscribed_at']
    search_fields = ['email']
    list_editable = ['is_active']
    date_hierarchy = 'subscribed_at'

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display= ['name','slug']

@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display= ['name']


class FAQInline(admin.TabularInline):
    model = FAQ
    extra = 1

class BlogResource(resources.ModelResource):
    class Meta:
        model = BlogPost

@admin.register(BlogPost)
class BlogAdmin(ImportExportModelAdmin):
    resource_class = BlogResource
    list_display = ['title', 'author', 'views', 'published_at']
    inlines = [FAQInline]