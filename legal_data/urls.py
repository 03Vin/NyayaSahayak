from django.urls import path
from . import views

urlpatterns = [
    path('laws-covered/', views.laws_covered_view, name='laws_covered'),
]

