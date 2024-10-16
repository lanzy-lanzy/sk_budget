from django.urls import path
from sk_project import views


urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.user_login, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.user_logout, name='logout'),
    path('create-main-budget/', views.create_main_budget, name='create_main_budget'),
    path('create-project/', views.create_project, name='create_project'),
    path('project/<int:project_id>/', views.project_detail, name='project_detail'),
    path('project/<int:project_id>/add_expense/', views.add_expense, name='add_expense'),
    path('projects/', views.all_projects, name='all_projects'),
    path('expenses/', views.all_expenses, name='all_expenses'),
    path('project/<int:project_id>/accomplishment-report/', views.project_accomplishment_report, name='project_accomplishment_report'),
    # path('project/<int:project_id>/expenses/', views.project_expenses, name='project_expenses'),
    path('project/<int:project_id>/add-accomplishment-report/', views.add_accomplishment_report, name='add_accomplishment_report'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),

    path('export-pdf-report/', views.export_pdf_report, name='export_pdf_report'),

    path('edit-project/<int:project_id>/', views.edit_project, name='edit_project'),
    path('delete-project/<int:project_id>/', views.delete_project, name='delete_project'),
    path('create-new-year-budget/', views.create_new_year_budget, name='create_new_year_budget'),

]






