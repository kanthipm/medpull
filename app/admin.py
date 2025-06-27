from django.contrib import admin
from .models import UserProfile, UploadedFile, ExtractedForm, DynamicFormSubmission
# Register your models here.

admin.site.register(UserProfile)
admin.site.register(UploadedFile)
admin.site.register(ExtractedForm)
admin.site.register(DynamicFormSubmission)
