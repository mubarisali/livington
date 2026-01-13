
# main/models.py
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.safestring import mark_safe
import markdown
import re
from django_ckeditor_5.fields import CKEditor5Field

# Create your models here.

class City(models.Model):
    name = models.CharField(max_length=255,null=True,blank=True)
    slug = models.SlugField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class District(models.Model):
    name = models.CharField(max_length=255,null=True,blank=True)
    slug = models.SlugField(blank=True, null=True)
    city = models.ForeignKey(City,on_delete=models.CASCADE,related_name='districts',null=True,blank=True)
    class Meta:
        indexes = [
            models.Index(fields=['city'], name='district_city_idx'),
        ]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        
    def _str_(self):
        return self.name
    
class Developer(models.Model):
    name = models.CharField(max_length=255,null=True, blank=True)
    slug = models.SlugField(max_length=255, null=True, blank=True)
    logo = models.URLField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    overview = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['slug'], name='developer_slug_idx'),
            models.Index(fields=['name'], name='developer_name_idx'),
        ]

    def __str__(self):
        return self.name
    
class PropertyType(models.Model):
    name = models.CharField(max_length=255,null=True,blank=True)
    
    def __str__(self):
        return self.name or "Unnamed PropertyType"
    
class PropertyStatus(models.Model):
    name = models.CharField(max_length=255,null=True,blank=True)
    
    def _str_(self):
        return self.name
    
class SalesStatus(models.Model):
    name = models.CharField(max_length=155,null=True,blank=True)
    
    def _str_(self):
        return self.name
    
class Facility(models.Model):
    id = models.BigIntegerField(primary_key=True,blank=True)
    name = models.CharField(max_length=255,null=True,blank=True)
    
    def _str_(self):
        return self.name

class Property(models.Model):
    external_id = models.BigIntegerField(primary_key=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True)
    title = models.CharField(max_length=255,null=True,blank=True)
    description = models.TextField(null=True,blank=True)
    cover = models.URLField(null=True,blank=True)
    address = models.CharField(max_length=255,null=True,blank=True)
    address_text = models.TextField(null=True,blank=True)
    delivery_date = models.DateField(null=True,blank=True)
    low_price = models.BigIntegerField(null=True,blank=True)
    min_area = models.IntegerField(null=True,blank=True)
    payment_plan = models.BooleanField(default=False)
    post_delivery = models.BooleanField(default=False)
    payment_minimum_down_payment = models.PositiveIntegerField(null=True,blank=True)  
    guarantee_rental_guarantee = models.BooleanField(default=False)
    guarantee_rental_guarantee_value = models.PositiveIntegerField(null=True,blank=True)  
    down_payment = models.PositiveIntegerField(null=True,blank=True)  
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True,blank=True)
    city = models.ForeignKey(City,on_delete=models.CASCADE,related_name='properties',null=True)
    district = models.ForeignKey(District,on_delete=models.CASCADE,related_name='properties',null=True)
    developer = models.ForeignKey(Developer,on_delete=models.CASCADE,related_name='properties',null=True)
    property_type =  models.ForeignKey(PropertyType,on_delete=models.CASCADE,related_name='properties',null=True)
    property_status = models.ForeignKey(PropertyStatus,on_delete=models.CASCADE,related_name='properties',null=True)
    sales_status = models.ForeignKey(SalesStatus,on_delete=models.CASCADE,related_name='properties',null=True)
    facilities = models.ManyToManyField(Facility, related_name='properties')
    
    class Meta:
        indexes = [
            models.Index(fields=['-created_at'], name='property_created_idx'),
            models.Index(fields=['slug'], name='property_slug_idx'),
            models.Index(fields=['city', 'district'], name='property_location_idx'),
            models.Index(fields=['developer'], name='property_dev_idx'),
            models.Index(fields=['low_price'], name='property_price_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class PropertyFacility(models.Model):
    property_id = models.ForeignKey(Property,on_delete=models.CASCADE)
    facility_id = models.ForeignKey(Facility,on_delete=models.CASCADE)
    
class PropertyImages(models.Model):
    property = models.ForeignKey(Property,on_delete=models.CASCADE,related_name='property_images')
    image = models.URLField()
        
class GroupedApartment(models.Model):
    property = models.ForeignKey(Property, related_name='grouped_apartments', on_delete=models.CASCADE)
    unit_type = models.CharField(max_length=255, null=True, blank=True)
    rooms = models.CharField(max_length=255,null=True,blank=True)
    min_price = models.CharField(max_length=255,null=True,blank=True)
    min_area = models.PositiveIntegerField(null=True,blank=True)

    def _str_(self):
        return self.unit_type

class PaymentPlan(models.Model):
    id = models.BigIntegerField(primary_key=True,blank=True)  
    property = models.ForeignKey(Property, related_name='payment_plans', on_delete=models.CASCADE)
    name = models.CharField(max_length=255,null=True,blank=True)
    description = models.TextField(blank=True, null=True)

    def _str_(self):
        return f"{self.name} ({self.property})"


class PaymentPlanValue(models.Model):
    id = models.BigIntegerField(primary_key=True,blank=True)  
    payment_plan = models.ForeignKey(PaymentPlan, related_name='values', on_delete=models.CASCADE)
    name = models.CharField(max_length=255,null=True,blank=True)
    value = models.CharField(max_length=20,null=True,blank=True) 

    def _str_(self):
        return f"{self.name}: {self.value}"


class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    excerpt = models.TextField(max_length=300, null=True)
    content = CKEditor5Field('Content', config_name='default')
    featured_image = models.ImageField(upload_to='blog/', blank=True)
    author = models.CharField(max_length=255, default='Admin')
    views = models.IntegerField(default=0)
    published_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    meta_title = models.CharField(max_length=500,null=True,blank=True)
    meta_description = models.TextField(null=True,blank=True)

    class Meta:
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['-published_at'], name='blog_published_idx'),
            models.Index(fields=['slug'], name='blog_slug_idx'),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('main:blog_detail', args=[self.slug])

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while BlogPost.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class ContactSubmission(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    message = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"Contact from {self.name} - {self.submitted_at.strftime('%Y-%m-%d')}"


class Newsletter(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.email
    
class FAQ(models.Model):
    blog = models.ForeignKey(BlogPost, related_name='faqs', on_delete=models.CASCADE)
    question = models.CharField(max_length=255)
    answer = models.TextField()

    def __str__(self):
        return self.question    
