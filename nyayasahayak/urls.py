"""
URL configuration for nyayasahayak project.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('accounts/', include('accounts.urls')),
    path('legal/', include('legal_data.urls')),
    path('assistant/', include('assistant.urls')),
    path('notices/', include('notices.urls')),
    path('evaluation/', include('evaluation.urls')),
]
