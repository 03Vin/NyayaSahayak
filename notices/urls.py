from django.urls import path
from . import views

urlpatterns = [
    path('', views.notice_list_view, name='notice_list'),
    path('create/<str:notice_type>/', views.notice_create_view, name='notice_create'),
    path('<int:draft_id>/', views.notice_detail_view, name='notice_detail'),
    path('<int:draft_id>/pdf/', views.notice_export_pdf_view, name='notice_export_pdf'),
]
