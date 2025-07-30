from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.conf import settings
from django.utils.text import get_valid_filename
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import UploadedFile, DynamicFormSubmission
from .forms import InformationForm, UploadFileForm
from django import forms
import base64
import fitz
import os
import json
import faiss
import numpy as np
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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
            User.objects.get(username=username)
        except User.DoesNotExist:
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
    local_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        response = local_client.chat.completions.create(
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

def build_dynamic_form(fields: dict):
    fields_dict = {}
    for label in fields:
        field_label = label.strip(":")
        fields_dict[field_label] = forms.CharField(
            required=False,
            label=field_label,
            widget=forms.TextInput(attrs={"class": "form-control"})
        )
    DynamicForm = type("DynamicForm", (forms.Form,), fields_dict)
    return DynamicForm

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
    local_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        response = local_client.chat.completions.create(
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

def chunk_text(text, max_chunk_size=500):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_chunk_size):
        chunk = " ".join(words[i:i+max_chunk_size])
        chunks.append(chunk)
    return chunks

@login_required
def upload_file(request):
    inferred_fields = request.session.get("inferred_fields", {})
    uploaded_instance = None
    if_uploaded = False
    dynamic_form = None
    form = UploadFileForm()

    file_id = request.session.get("uploaded_file_id")
    if file_id:
        try:
            uploaded_instance = UploadedFile.objects.get(id=file_id)
            if_uploaded = True
        except UploadedFile.DoesNotExist:
            uploaded_instance = None

    if request.method == "GET" and "autofilled_data" in request.session:
        ai_guess = request.session.pop("autofilled_data")
        if inferred_fields:
            DynamicFormClass = build_dynamic_form(inferred_fields)
            dynamic_form = DynamicFormClass(initial=ai_guess)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "upload" and 'file' in request.FILES:
            form = UploadFileForm(request.POST, request.FILES)

            if form.is_valid():
                uploaded_file = request.FILES['file']
                uploaded_instance = UploadedFile.objects.create(uploaded_file=uploaded_file)
                file_path = uploaded_instance.uploaded_file.path
                request.session['uploaded_file_id'] = uploaded_instance.id
                if_uploaded = True

                with fitz.open(file_path) as doc:
                    full_text = "\n".join([page.get_text("text") for page in doc])
                inferred_fields = infer_form_fields_with_llm(full_text)
                request.session["inferred_fields"] = inferred_fields
                DynamicFormClass = build_dynamic_form(inferred_fields)
                dynamic_form = DynamicFormClass()
                chunks = chunk_text(full_text)
                embedding_responses = []

                for chunk in chunks:
                    response = client.embeddings.create(
                        input=chunk,
                        model="text-embedding-3-small"
                    )
                    embedding_responses.append(response.data[0].embedding)
                chunk_embeddings = np.array(embedding_responses, dtype='float32')
                request.session['doc_chunks'] = chunks
                encoded_embeddings = base64.b64encode(chunk_embeddings.tobytes()).decode('utf-8')
                request.session['doc_embeddings'] = encoded_embeddings

        elif action == "save":
            DynamicFormClass = build_dynamic_form(inferred_fields)
            dynamic_form = DynamicFormClass(request.POST)
            if dynamic_form.is_valid():
                DynamicFormSubmission.objects.create(
                    user=request.user,
                    data=dynamic_form.cleaned_data
                )
                return redirect("app:home")
            
        elif action == "autofill_ai":
            DynamicFormClass = build_dynamic_form(inferred_fields)
            previous_submissions = DynamicFormSubmission.objects.filter(user=request.user)
            if previous_submissions.exists():
                previous_data = [s.data for s in previous_submissions]
                prompt = f"""
You are an intelligent autofill assistant. Based on these past submissions:
{json.dumps(previous_data, indent=2)}
Fill in this form with these fields:
{json.dumps(list(inferred_fields.keys()), indent=2)}
Rules:
- Match fields case-insensitively.
- If unsure, use "".
- Do NOT add new fields.
Output only a JSON object.
"""
                try:
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                        max_tokens=800
                    )
                    ai_guess = json.loads(response.choices[0].message.content)
                    request.session["autofilled_data"] = ai_guess
                    return redirect("app:extract")
                except Exception as e:
                    print("AI Error:", e)
                    dynamic_form = DynamicFormClass()
            else:
                dynamic_form = DynamicFormClass()



    context = {
        "form": form,
        "uploaded": if_uploaded,
        "getFile": uploaded_instance,
        "dynamic_form": dynamic_form,
    }

    return render(request, "app/extract_document.html", context)

@login_required
@csrf_exempt
def rag_query(request):
    if request.method != "POST":
        return JsonResponse({'error': 'POST method required'}, status=400)

    data = json.loads(request.body)
    question = data.get('question', '').strip()

    if not question:
        return JsonResponse({'answer': 'Please provide a question.'})

    chunks = request.session.get('doc_chunks')
    encoded_embeddings = request.session.get('doc_embeddings')

    if not chunks or not encoded_embeddings:
        return JsonResponse({'answer': 'No document loaded. Please upload a PDF first.'})

    embeddings_bytes = base64.b64decode(encoded_embeddings.encode('utf-8'))
    emb_array = np.frombuffer(embeddings_bytes, dtype='float32').reshape(len(chunks), -1)
    dimension = emb_array.shape[1]

    index = faiss.IndexFlatL2(dimension)
    index.add(emb_array)

    embedding_response = client.embeddings.create(
        input=[question],
        model="text-embedding-3-small"
    )
    query_embedding = np.array(embedding_response.data[0].embedding, dtype='float32').reshape(1, -1)

    k = 3
    _, top_indices = index.search(query_embedding, k)
    retrieved_chunks = "\n\n".join(chunks[i] for i in top_indices[0])

    prompt = f"""
You are an assistant that answers questions based ONLY on the provided document context.

Context:
{retrieved_chunks}

Question:
{question}

Answer:
"""

    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500,
    )

    answer = completion.choices[0].message.content.strip()

    return JsonResponse({'answer': answer})