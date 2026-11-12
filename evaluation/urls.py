from django.urls import path
from . import views

urlpatterns = [
    path('results/', views.eval_results_view, name='eval_results'),
]

