from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.conf import settings

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

# PDF form translation view
@login_required
def upload_translate_view(request):
    translated_text = ""

    if request.method == 'POST' and request.FILES.get('pdf_file'):
        uploaded_file = request.FILES['pdf_file']
        lang = request.POST.get('language', 'es')

        # Save uploaded PDF
        file_path = default_storage.save(uploaded_file.name, uploaded_file)
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)

        # Extract text from PDF
        doc = fitz.open(full_path)
        full_text = "\n".join([page.get_text() for page in doc])

        # Translate
        translator = Translator()
        translated = translator.translate(full_text, dest=lang)
        translated_text = translated.text

    return render(request, 'app/upload.html', {'translated_text': translated_text})
