from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.conf import settings
from django.utils.text import get_valid_filename

from .forms import InformationForm

# Extra translation dependencies
from googletrans import Translator
import fitz  # PyMuPDF
import os

# Home page view
def home(request):
    return render(request, 'app/home.html')

# Fill out patient information
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

    context = {'form': form}
    return render(request, 'app/information.html', context)

# User registration
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

    context = {
        'form': form,
        'page': 'register'
    }
    return render(request, 'app/login_register.html', context)

# User logout
def logoutUser(request):
    if request.method == 'POST':
        logout(request)
        return redirect('app:home')
    return render(request, 'app/logout.html')

# User login
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

@login_required
def upload_translate_view(request):
    translated_text = ""
    available_forms = []

    # Static folder path
    static_forms_path = os.path.join(settings.BASE_DIR, 'static', 'forms', 'english')

    # Get list of static forms
    if os.path.exists(static_forms_path):
        available_forms = [f for f in os.listdir(static_forms_path) if f.endswith('.pdf')]

    if request.method == 'POST':
        lang = request.POST.get('language', 'es')

        # Case 1: File was uploaded
        if request.FILES.get('pdf_file'):
            uploaded_file = request.FILES['pdf_file']
            file_path = default_storage.save(uploaded_file.name, uploaded_file)
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)

        # Case 2: Static form was selected
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
            translator = Translator()
            translated = translator.translate(full_text, dest=lang)
            translated_text = translated.text
        except Exception as e:
            messages.error(request, f"Translation failed: {e}")

    return render(request, 'app/upload.html', {
        'translated_text': translated_text,
        'available_forms': available_forms,
        'selected_static_form': request.POST.get('static_form', '')
    })

