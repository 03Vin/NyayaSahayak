from django.urls import path
from . import views

urlpatterns = [
    path('ask/', views.ask_view, name='ask'),
    path('history/', views.history_view, name='history'),
    path('history/<int:query_id>/', views.query_detail_view, name='query_detail'),
]

