from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.conf import settings
from django.utils.text import get_valid_filename
from .models import UploadedFile, DynamicFormSubmission
from .forms import InformationForm, UploadFileForm, DynamicForm
from django import forms

import fitz  
import os
import json

import openai
import json
import os
from openai import OpenAI
from django import forms

def home(request):
    return render(request, 'app/home.html')

@login_required
def fillOutInfo(request):
    form = InformationForm()
    if request.method == 'POST':
        form = InformationForm(request.POST)
        if form.is_valid():
            info = form.save(commit=False)
            info.user = request.user
            info.save()
            return redirect('app:home')
        else:
            messages.error(request, 'An error occurred when filling out your information.')
    return render(request, 'app/information.html', {'form': form})

def registerUser(request):
    form = UserCreationForm()
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.save()
            login(request, user)
            return redirect('app:home')
        else:
            messages.error(request, 'An error occurred when registering!')
    return render(request, 'app/login_register.html', {'form': form, 'page': 'register'})

def logoutUser(request):
    if request.method == 'POST':
        logout(request)
        return redirect('app:home')
    return render(request, 'app/logout.html')

def loginUser(request):
    if request.user.is_authenticated:
        return redirect('app:home')

    if request.method == 'POST':
        username = request.POST.get('username').lower()
        password = request.POST.get('password')

        try:
            user = User.objects.get(username=username)
        except:
            messages.error(request, 'User does not exist')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('app:home')
        else:
            messages.error(request, "Username or password is incorrect")

    return render(request, 'app/login_register.html')

def translate_text_with_openai(text, lang):
    prompt = f"""Translate this to {lang}:
            \n{text[:3000]}"""

    api_key = os.getenv("OPENAI_API_KEY")

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Translation error:", e)
        return ""

@login_required
def upload_translate_view(request):
    translated_text = ""
    available_forms = []
    static_forms_path = os.path.join(settings.BASE_DIR, 'static', 'forms', 'english')

    if os.path.exists(static_forms_path):
        available_forms = [f for f in os.listdir(static_forms_path) if f.endswith('.pdf')]

    if request.method == 'POST':
        lang = request.POST.get('language', 'es')

        if request.FILES.get('pdf_file'):
            uploaded_file = request.FILES['pdf_file']
            file_path = default_storage.save(uploaded_file.name, uploaded_file)
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)

        elif request.POST.get('static_form'):
            static_filename = get_valid_filename(request.POST.get('static_form'))
            full_path = os.path.join(static_forms_path, static_filename)
            if not os.path.exists(full_path):
                messages.error(request, "Selected form does not exist.")
                return redirect('app:upload')
        else:
            messages.error(request, "No file provided for translation.")
            return redirect('app:upload')

        try:
            doc = fitz.open(full_path)
            full_text = "\n".join([page.get_text() for page in doc])
            translated_text = translate_text_with_openai(full_text, lang)
        except Exception as e:
            messages.error(request, f"Translation failed: {e}")

    return render(request, 'app/upload.html', {
        'translated_text': translated_text,
        'available_forms': available_forms,
        'selected_static_form': request.POST.get('static_form', '')
    })

def infer_form_fields_with_llm(text):
    prompt = f"""
You are an intelligent form assistant. Your job is to extract structured fields from messy, OCR-style or text-extracted PDF documents.

This PDF contains a non-interactive form. Based on the text, identify all **inputtable fields** that a user would be expected to fill in. These include:

- Text fields (e.g. name, address, date of birth)
- Checkboxes or multiple choice options (e.g. marital status, gender, race)
- Yes/No questions
- Contact details

Follow these rules:

1. Do NOT invent fields. Only include what clearly looks like a form input.
2. For multi-option fields (checkboxes, yes/no, race, etc), list **all options**.
3. The value for every field should be an empty string initially.
4. Return a JSON object like:
   {{
     "Last Name": "",
     "First Name": "",
     "Gender (Female, Male)": "",
     "Race (White, Black, Asian, etc)": "",
     "Phone Number": "",
     ...
   }}

Example output:
```json
{{
  "Last Name": "",
  "First Name": "",
  "Gender (Female, Male)": "",
  "Street Address": "",
  "City": "",
  "State": "",
  "Zip Code": "",
  "Home Phone": "",
  "Cell Phone": "",
  "Email Address": "",
  "Marital Status (Single, Married, Divorced, Separated, Widow, Domestic Partner)": "",
  "Race (White, Black, Asian, American Indian, Pacific Islander, Alaskan Native, Refuse, Unknown)": "",
  "Ethnicity (Hispanic, Not Hispanic, Unknown/Refuse)": "",
  "Have you received services at San Jose? (Yes, No)": "",
  ...
}}

Text:
\"\"\"
{text[:3000]}
\"\"\"
"""

    api_key = "OPENAI_API_KEY"
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=500
        )
        json_output = response.choices[0].message.content
        fields = json.loads(json_output)

        return fields
    except Exception as e:
        print("Error parsing LLM response:", e)
        return {}

def upload_file(request):
    inferred_fields = {}
    uploaded_instance = None
    if_uploaded = False
    dynamic_form = None

    if request.method == 'POST':
        if 'file' in request.FILES:
            form = UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                file = request.FILES['file']
                uploaded_instance = UploadedFile.objects.create(uploaded_file=file)
                if_uploaded = True
                file_path = uploaded_instance.uploaded_file.path

                with fitz.open(file_path) as doc:
                    full_text = "\n".join([page.get_text("text") for page in doc])

                inferred_fields = infer_form_fields_with_llm(full_text)
                request.session['inferred_fields'] = inferred_fields  
                DynamicFormClass = DynamicForm(field_dict=inferred_fields)
                dynamic_form = DynamicFormClass()
        else:
            inferred_fields = request.session.get('inferred_fields', {})
            dynamic_form = DynamicForm(request.POST, field_dict=inferred_fields)

            if dynamic_form.is_valid():
                DynamicFormSubmission.objects.create(
                    user=request.user,
                    data=dynamic_form.cleaned_data
                )
                messages.success(request, "Form saved successfully!")
                return redirect('app:home') 
    else:
        form = UploadFileForm()

    context = {
        'form': form,
        'uploaded': if_uploaded,
        'getFile': uploaded_instance,
        'form_fields': inferred_fields,
        'dynamic_form': dynamic_form,
    }

    return render(request, 'app/extract_document.html', context)

