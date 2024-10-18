from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models, transaction
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
from .models import MainBudget, Project, User
from .forms import (
    MainBudgetForm,
    ProjectForm,
    ExpenseForm,
    AccomplishmentReportForm,
    CustomUserCreationForm,
    UserProfileForm)
from decimal import Decimal
from django.db.models import Q
from reportlab.platypus import HRFlowable
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse# User Authentication Views
def landing_page(request):
    return render(request, 'landing_page.html')
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
                redirect_url = 'admin_dashboard' if user.is_superuser else 'dashboard'
                return JsonResponse({'success': True, 'redirect_url': reverse(redirect_url)})
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})



def user_logout(request):
    logout(request)
    return redirect('landing_page')

# Dashboard and Budget Management Views

@login_required
def dashboard(request):
    main_budget = MainBudget.objects.filter(chairman=request.user).order_by('-year').first()
    if main_budget:
        remaining_budget = main_budget.remaining_budget
        usage_percentage = main_budget.usage_percentage
    else:
        remaining_budget = 0
        usage_percentage = 0
    projects = Project.objects.filter(chairman=request.user).annotate(
        total_expenses=models.Sum('expenses__amount')
    )

    total_expenses = sum(project.total_expenses or 0 for project in projects)
    active_projects_count = projects.count()
    ongoing_initiatives = projects.filter(end_date__gt=timezone.now()).count()
    projects_in_progress = projects.filter(start_date__lte=timezone.now(), end_date__gte=timezone.now()).count()
    cumulative_spending = total_expenses
    budget_utilization = (total_expenses / main_budget.total_budget * 100) if main_budget else 0

    for project in projects:
        project.budget_utilized = (project.total_expenses or 0) >= project.allocated_budget

    context = {
        'main_budget': main_budget,
        'remaining_budget': remaining_budget,
        'usage_percentage': usage_percentage,
        'projects': projects,
        'total_expenses': total_expenses,
        'active_projects_count': active_projects_count,
        'ongoing_initiatives': ongoing_initiatives,
        'projects_in_progress': projects_in_progress,
        'cumulative_spending': cumulative_spending,
        'budget_utilization': budget_utilization,
    }
    return render(request, 'dashboard.html', context)



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

@login_required
def create_new_year_budget(request):
    if request.method == 'POST':
        form = MainBudgetForm(request.POST)
        if form.is_valid():
            year = form.cleaned_data['year']
            total_budget = form.cleaned_data['total_budget']
            
            with transaction.atomic():
                # Get the previous year's budget
                previous_year_budget = MainBudget.objects.filter(
                    chairman=request.user,
                    year=year-1
                ).first()
                
                # Calculate remaining budget from previous year
                remaining_budget = 0
                if previous_year_budget:
                    remaining_budget = previous_year_budget.remaining_budget
                
                # Add remaining budget to the new total budget
                new_total_budget = total_budget + remaining_budget
                
                main_budget, created = MainBudget.objects.get_or_create(
                    chairman=request.user,
                    year=year,
                    defaults={'total_budget': new_total_budget}
                )
                
                if created:
                    messages.success(request, f'New budget for {year} created successfully! Total budget: ₱{new_total_budget:,.2f} (including ₱{remaining_budget:,.2f} from previous year)')
                else:
                    main_budget.total_budget = new_total_budget
                    main_budget.save()
                    messages.info(request, f'Budget for {year} updated successfully! Total budget: ₱{new_total_budget:,.2f} (including ₱{remaining_budget:,.2f} from previous year)')
        else:
            messages.error(request, 'Error creating new year budget. Please check your input.')
    return redirect('dashboard')



# Project Management Views

@login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                project = form.save(commit=False)
                project.chairman = request.user
                project.allocated_budget = project.budget  # Set allocated_budget
                main_budget = MainBudget.objects.select_for_update().filter(chairman=request.user).latest('year')
                if main_budget.remaining_budget >= project.budget:
                    project.main_budget = main_budget
                    project.save()
                    messages.success(request, 'Project created successfully!')
                else:
                    messages.error(request, 'Insufficient funds in the main budget for this project.')
        else:
            messages.error(request, 'Error creating project. Please check your input.')
    return redirect('dashboard')


@login_required


def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    expenses = project.expenses.all().order_by('-date_incurred')
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
    context = {
        'project': project,
        'expenses': expenses,
        'total_expenses': total_expenses,
    }
    return render(request, 'project_detail.html', context)


def all_projects(request):
    search_query = request.GET.get('search', '')
    projects = Project.objects.filter(chairman=request.user).annotate(
    total_expenses=models.Sum('expenses__amount')
)
    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    context = {
        'projects': projects,
        'search_query': search_query,
    }
    return render(request, 'all_projects.html', context)

# Expense Management Views

@login_required
def add_expense(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.project = project
            expense.amount = expense.price_per_unit * expense.quantity
            total_expenses = project.expenses.aggregate(total=models.Sum('amount'))['total'] or 0
            remaining_budget = project.allocated_budget - total_expenses
            if expense.amount <= remaining_budget:
                expense.save()
                messages.success(request, 'Expense added successfully!')
            else:
                messages.error(request, 'Expense amount exceeds remaining budget!')
            return redirect('project_detail', project_id=project.id)
    else:
        form = ExpenseForm()
    return render(request, 'add_expense.html', {'form': form, 'project': project})

@login_required
def all_expenses(request):
    total_expenses = Project.objects.filter(chairman=request.user).aggregate(total=models.Sum('expenses__amount'))['total'] or 0
    projects = Project.objects.filter(chairman=request.user).annotate(
    total_expenses=models.Sum('expenses__amount')
    )
    
    search_query = request.GET.get('search', '')
    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(expenses__item_name__icontains=search_query) |
            Q(expenses__description__icontains=search_query)
        ).distinct()
    
    context = {
        'projects': projects,
        'total_expenses': total_expenses,
        'search_query': search_query,
    }
    return render(request, 'all_expenses.html', context)



# Accomplishment Report Management Views

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

# Profile Management View

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('dashboard')
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, 'edit_profile.html', {'form': form})

# PDF Export Functionality

@login_required
def export_pdf_report(request):
    buffer = BytesIO()
    projects = Project.objects.filter(chairman=request.user)
    generate_pdf_report(buffer, request.user, projects)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="sk_budget_report.pdf"'
    return response

def generate_pdf_report(response, user, projects):
    doc = SimpleDocTemplate(response, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=28, textColor=colors.HexColor("#2C3E50"), spaceAfter=16, alignment=1)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=20, textColor=colors.HexColor("#34495E"), spaceBefore=16, spaceAfter=8)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor("#2C3E50"), leading=14)
    subheading_style = ParagraphStyle('Subheading', parent=styles['Heading3'], fontSize=16, textColor=colors.HexColor("#16A085"), spaceBefore=12, spaceAfter=6)

    # Add a decorative header
    elements.append(Paragraph("SK Budget Report", title_style))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#3498DB"), spaceAfter=0.2*inch))

    # Chairman information
    elements.append(Paragraph("Chairman Information", heading_style))
    chairman_info = [
        [Paragraph(f"<b>Name:</b> {user.get_full_name()}", normal_style)],
        [Paragraph(f"<b>Email:</b> {user.email}", normal_style)],
        [Paragraph(f"<b>Contact:</b> {user.contact_number}", normal_style)]
    ]
    chairman_table = Table(chairman_info, colWidths=[6*inch])
    chairman_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ECF0F1")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#BDC3C7")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(chairman_table)
    elements.append(Spacer(1, 0.3*inch))

    for project in projects:
        elements.append(Paragraph(f"Project: {project.name}", subheading_style))
        
        # Project summary
        project_data = [
            ["Budget", "Expenses", "Remaining"],
            [f"{project.budget:,.2f}", f"{project.total_expenses():,.2f}", f"{project.remaining_budget:,.2f}"]
        ]
        
        project_table = Table(project_data, colWidths=[2*inch, 2*inch, 2*inch])
        project_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#3498DB")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#ECF0F1")),
            ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor("#2C3E50")),
            ('ALIGN', (0,1), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 11),
            ('TOPPADDING', (0,1), (-1,-1), 6),
            ('BOTTOMPADDING', (0,1), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#BDC3C7"))
        ]))
        elements.append(project_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Expense details
        elements.append(Paragraph("Expense Details", subheading_style))
        expense_data = [["Item Name", "Description", "Quantity", "Price per Unit", "Amount"]]
        for expense in project.expenses.all():
            expense_data.append([
                expense.item_name,
                expense.description,
                str(expense.quantity),
                f"{expense.price_per_unit:,.2f}",
                f"{expense.amount:,.2f}"
            ])

        expense_table = Table(expense_data, colWidths=[1.5*inch, 2*inch, 1*inch, 1.25*inch, 1.25*inch])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#16A085")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 11),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#E8F6F3")),
            ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor("#2C3E50")),
            ('ALIGN', (0,1), (1,-1), 'LEFT'),
            ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('TOPPADDING', (0,1), (-1,-1), 4),
            ('BOTTOMPADDING', (0,1), (-1,-1), 4),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#BDC3C7"))
        ]))
        elements.append(expense_table)
        elements.append(Spacer(1, 0.3*inch))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#BDC3C7"), spaceAfter=0.2*inch))

    # Add page numbers
    def add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#7F8C8D"))
        canvas.drawRightString(7.5*inch, 0.25*inch, text)

    doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)

@login_required
def edit_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, 'Project updated successfully!')
            return redirect('dashboard')
    else:
        form = ProjectForm(instance=project)
    return render(request, 'edit_project.html', {'form': form, 'project': project})

@login_required
def delete_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    project.delete()
    messages.success(request, 'Project deleted successfully!')
    return redirect('dashboard')

from django.contrib.auth.decorators import user_passes_test

@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    search_query = request.GET.get('search', '')
    chairmen = User.objects.filter(is_chairman=True).order_by('last_name', 'first_name')
    
    if search_query:
        chairmen = chairmen.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(projects__name__icontains=search_query)
        ).distinct()
    
    all_projects = Project.objects.all().order_by('chairman__last_name', 'chairman__first_name', 'name')
    all_main_budgets = MainBudget.objects.all().order_by('-year', 'chairman__last_name', 'chairman__first_name')
    total_budget = MainBudget.objects.aggregate(total=Sum('total_budget'))['total'] or 0
    total_expenses = Project.objects.aggregate(total=Sum('expenses__amount'))['total'] or 0

    context = {
        'chairmen': chairmen,
        'all_projects': all_projects,
        'all_main_budgets': all_main_budgets,
        'total_budget': total_budget,
        'total_expenses': total_expenses,
        'search_query': search_query,
    }
    return render(request, 'admin_dashboard.html', context)

