from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('soil-test-choice/', views.soil_test_choice, name='soil_test_choice'),
    path('results/', views.results, name='results'),
]
