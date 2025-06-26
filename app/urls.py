from django.contrib import admin
from django.urls import path
from .views import home, loginUser, logoutUser, registerUser, fillOutInfo, upload_translate_view, upload_file
from . import views

app_name = 'app'
urlpatterns = [
    path('', home, name='home'),
    path('login/', loginUser, name='login'),
    path('logout/', logoutUser, name='logout'),
    path('register/', registerUser, name='register'),
    path('information/', fillOutInfo, name='information'),
    path('translate/', upload_translate_view, name='translate'),
    path('extract/', upload_file, name='extract') 
] 