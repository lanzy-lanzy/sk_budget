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
