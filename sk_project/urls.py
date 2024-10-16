from django.urls import path
from sk_project import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
]
