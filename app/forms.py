from django.forms import ModelForm
from .models import UserProfile
from django import forms
from django.contrib.auth.models import User


class InformationForm(ModelForm):
    class Meta:
        model = UserProfile
        fields = "__all__"
        exclude = ['user']

class UploadFileForm(forms.Form):
    file = forms.FileField()
