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

class DynamicForm(forms.Form):
    def __init__(self, *args, field_dict=None, **kwargs):
        super().__init__(*args, **kwargs)
        if field_dict:
            for label in field_dict:
                field_label = label.strip(":")
                self.fields[field_label] = forms.CharField(
                    required=False,
                    label=field_label,
                    widget=forms.TextInput(attrs={"class": "form-control"})
                )
