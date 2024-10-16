from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import MainBudget, Project
from .forms import MainBudgetForm, ProjectForm
from django.db import models
from django.shortcuts import get_object_or_404
from .forms import ExpenseForm, AccomplishmentReportForm

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

    active_projects_count = projects.count()  # Consider all projects as active

    context = {
        'main_budget': main_budget,
        'remaining_budget': remaining_budget,
        'usage_percentage': usage_percentage,
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
from django.db import transaction
from django.utils import timezone

@login_required
def create_new_year_budget(request):
    if request.method == 'POST':
        form = MainBudgetForm(request.POST)
        if form.is_valid():
            year = form.cleaned_data['year']
            total_budget = form.cleaned_data['total_budget']

            with transaction.atomic():
                if MainBudget.objects.filter(chairman=request.user, year=year).exists():
                    messages.error(request, f'A budget for {year} already exists.')
                else:
                    new_budget = MainBudget.objects.create(
                        year=year,
                        total_budget=total_budget,
                        chairman=request.user,
                        created_at=timezone.now(),
                        updated_at=timezone.now()
                    )
                    messages.success(request, f'New budget for {new_budget.year} created successfully! Total budget: ₱{new_budget.total_budget:,.2f}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.capitalize()}: {error}')

    return redirect('dashboard')



@login_required
def create_main_budget(request):
    if request.method == 'POST':
        form = MainBudgetForm(request.POST)
        print("Form data:", request.POST)
        if form.is_valid():
            print("Form is valid")
            main_budget = form.save(commit=False)
            main_budget.chairman = request.user
            main_budget.save()
            messages.success(request, 'Main budget created successfully!')
        else:
            print("Form errors:", form.errors)
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
def user_logout(request):
    logout(request)
    return redirect('login')
@login_required
def add_expense(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.project = project
            expense.amount = expense.price_per_unit * expense.quantity
            if expense.amount <= project.remaining_budget:
                expense.save()
                project.budget -= expense.amount
                project.save()
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

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import UserProfileForm
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



from django.http import FileResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from io import BytesIO
from django.http import HttpResponse

@login_required
def export_pdf_report(request):
    buffer = BytesIO()
    projects = Project.objects.filter(chairman=request.user)
    generate_pdf_report(buffer, request.user, projects)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="sk_budget_report.pdf"'
    return response


from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def generate_pdf_report(response, user, projects):
    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor("#2C3E50"), spaceAfter=12)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=18, textColor=colors.HexColor("#34495E"), spaceBefore=12, spaceAfter=6)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor("#2C3E50"))
    subheading_style = ParagraphStyle('Subheading', parent=styles['Heading3'], fontSize=14, textColor=colors.HexColor("#16A085"), spaceBefore=8, spaceAfter=4)

    elements.append(Paragraph("SK Budget Report", title_style))
    elements.append(Spacer(1, 0.3*inch))

    elements.append(Paragraph(f"Chairman: {user.get_full_name()}", heading_style))
    elements.append(Paragraph(f"Email: {user.email}", normal_style))
    elements.append(Paragraph(f"Contact: {user.contact_number}", normal_style))
    elements.append(Spacer(1, 0.3*inch))

    for project in projects:
        elements.append(Paragraph(f"Project: {project.name}", subheading_style))
        
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
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('TOPPADDING', (0,1), (-1,-1), 6),
            ('BOTTOMPADDING', (0,1), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#BDC3C7"))
        ]))
        elements.append(project_table)
        elements.append(Spacer(1, 0.2*inch))
        
        expense_data = [["Expense Details", "Amount"]]
        for expense in project.expenses.all():
            expense_details = f"{expense.quantity} x {expense.price_per_unit} - {expense.description}"
            expense_data.append([expense_details, f"{expense.amount:,.2f}"])


        
        expense_table = Table(expense_data, colWidths=[4*inch, 2*inch])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#16A085")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 11),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#E8F6F3")),
            ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor("#2C3E50")),
            ('ALIGN', (0,1), (0,-1), 'LEFT'),
            ('ALIGN', (1,1), (1,-1), 'RIGHT'),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('TOPPADDING', (0,1), (-1,-1), 4),
            ('BOTTOMPADDING', (0,1), (-1,-1), 4),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#BDC3C7"))
        ]))
        elements.append(expense_table)
        elements.append(Spacer(1, 0.3*inch))

    doc.build(elements)



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
