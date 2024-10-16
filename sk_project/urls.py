from django.urls import path
from sk_project import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.user_login, name='login'),
    path('register/', views.register, name='register'),
    path('create-main-budget/', views.create_main_budget, name='create_main_budget'),
    path('create-project/', views.create_project, name='create_project'),
]
