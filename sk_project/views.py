from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import MainBudget, Project
from .forms import MainBudgetForm, ProjectForm
from django.db import models
from django.shortcuts import get_object_or_404
from .forms import ExpenseForm, AccomplishmentReportForm

@login_required
def dashboard(request):
    main_budget = MainBudget.objects.filter(chairman=request.user).latest('year') if MainBudget.objects.filter(chairman=request.user).exists() else None

    projects = Project.objects.filter(chairman=request.user).annotate(
        total_expenses=models.Sum('expenses__amount')
    )

    total_expenses = sum(project.total_expenses or 0 for project in projects)
    active_projects_count = projects.count()  # Consider all projects as active

    context = {
        'main_budget': main_budget,
        'projects': projects,
        'total_expenses': total_expenses,
        'active_projects_count': active_projects_count,
    }
    return render(request, 'dashboard.html', context)



@login_required


def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    expenses = project.expenses.all()
    context = {
        'project': project,
        'expenses': expenses,
    }
    return render(request, 'project_detail.html', context)


from django.db import transaction

@login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                project = form.save(commit=False)
                project.chairman = request.user
                main_budget = MainBudget.objects.select_for_update().latest('year')
                
                if main_budget.total_budget >= project.budget:
                    main_budget.total_budget -= project.budget
                    main_budget.save()
                    
                    project.main_budget = main_budget
                    project.save()
                    
                    messages.success(request, 'Project created successfully and budget deducted from main budget!')
                else:
                    messages.error(request, 'Insufficient funds in the main budget for this project.')
        else:
            messages.error(request, 'Error creating project. Please check your input.')
    return redirect('dashboard')

@login_required
def create_main_budget(request):
    if request.method == 'POST':
        form = MainBudgetForm(request.POST)
        if form.is_valid():
            main_budget = form.save(commit=False)
            main_budget.chairman = request.user
            main_budget.save()
            messages.success(request, 'Main budget created successfully!')
        else:
            messages.error(request, 'Error creating main budget. Please check your input.')
    return redirect('dashboard')

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User

from .forms import CustomUserCreationForm

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

@login_required
def add_expense(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.project = project
            if expense.amount <= project.remaining_budget:
                expense.save()
                messages.success(request, 'Expense added successfully!')
            else:
                messages.error(request, 'Expense amount exceeds remaining budget!')
            return redirect('project_detail', project_id=project.id)
    else:
        form = ExpenseForm()
    return render(request, 'add_expense.html', {'form': form, 'project': project})

@login_required
def all_projects(request):
    projects = Project.objects.filter(chairman=request.user).annotate(
        total_expenses=models.Sum('expenses__amount')
    ).order_by('-created_at')
    
    context = {
        'projects': projects,
    }
    return render(request, 'all_projects.html', context)

@login_required
def all_expenses(request):
    projects = Project.objects.filter(chairman=request.user).prefetch_related('expenses')
    total_expenses = sum(expense.amount for project in projects for expense in project.expenses.all())
    
    context = {
        'projects': projects,
        'total_expenses': total_expenses,
    }
    return render(request, 'all_expenses.html', context)

@login_required
def project_accomplishment_report(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    accomplishment_reports = project.accomplishment_reports.all().order_by('-report_date')
    
    context = {
        'project': project,
        'accomplishment_reports': accomplishment_reports,
    }
    return render(request, 'project_accomplishment_report.html', context)

@login_required


@login_required
def add_accomplishment_report(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    if request.method == 'POST':
        form = AccomplishmentReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.project = project
            report.save()
            return redirect('project_accomplishment_report', project_id=project.id)
    else:
        form = AccomplishmentReportForm()
    
    context = {
        'form': form,
        'project': project,
    }
    return render(request, 'add_accomplishment_report.html', context)
