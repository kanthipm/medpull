from django.db import models
from django.contrib.auth.models import User
# Create your models here.

class UserProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    firstName = models.CharField(max_length=200)
    middleName = models.CharField(max_length=200)
    lastName = models.CharField(max_length=200)
    address = models.CharField(max_length=200)

    def __str__(self):
        return self.user

class UploadedFile(models.Model):
    uploaded_file = models.FileField(null=True)

class ExtractedForm(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    field_data = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)

