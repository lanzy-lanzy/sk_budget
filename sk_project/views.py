from django.shortcuts import render
from django.db.models import Sum
from django.utils import timezone
from .models import MainBudget, Project, Expense

def dashboard(request):
    try:
        main_budget = MainBudget.objects.latest('year')
    except MainBudget.DoesNotExist:
        main_budget = None

    active_projects_count = Project.objects.filter(end_date__gte=timezone.now().date()).count()
    total_expenses = Expense.objects.aggregate(total=Sum('amount'))['total'] or 0

    recent_activities = [
        {'title': 'New Project Added', 'description': 'Project XYZ was added to the system.'},
        {'title': 'Expense Recorded', 'description': 'New expense of ₱5000 recorded for Project ABC.'},
        {'title': 'Budget Update', 'description': 'Main budget for 2023 has been updated.'},
    ]

    context = {
        'main_budget': main_budget,
        'active_projects_count': active_projects_count,
        'total_expenses': total_expenses,
        'recent_activities': recent_activities,
    }

    return render(request, 'dashboard.html', context)

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import MainBudget
from .forms import MainBudgetForm

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
