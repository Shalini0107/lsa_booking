from django.contrib import admin

from .models import Parent, Skill, LSAProfile, BookingRequest, Payment

admin.site.register(Parent)
admin.site.register(Skill)
admin.site.register(LSAProfile)
admin.site.register(BookingRequest)
admin.site.register(Payment)
