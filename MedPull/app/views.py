from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import InformationForm


# Create your views here.

def home(request):
    return render(request, 'app/home.html')

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
            messages.error(request, 'An error occured when fillig out your information.')

    context = {
        'form': form
    }

    return render(request, 'app/information.html', context)
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
            messages.error(request, 'An error occured when logging in!')

    context = {
        'form': form,
        'page': 'register'
    }    

    return render(request, 'app/login_register.html', context)

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
            user = User.objects.get(username = username) 
        except:
            messages.error(request, 'User does not exist')
            
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('app:home')
        else:
            messages.error(request, "User name or password does not exist")


    
    return render(request, 'app/login_register.html')