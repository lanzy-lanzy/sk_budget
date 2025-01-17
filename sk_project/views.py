from django.db import models, transaction
from django.db.models import Q, Sum
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import HRFlowable
from io import BytesIO
from datetime import datetime
import os
from django.conf import settings
from .models import MainBudget, Project, User, Expense, AccomplishmentReportImage
from .forms import (
    MainBudgetForm,
    ProjectForm,
    ExpenseForm,
    AccomplishmentReportForm,
    CustomUserCreationForm,
    UserProfileForm,
    AccomplishmentReportImageForm,
    ProjectCompletionForm
)
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

# User Authentication Views
def landing_page(request):
    # Get all completed projects first with related accomplishment reports and images
    completed_projects = Project.objects.filter(
        status='completed'
    ).select_related('chairman').prefetch_related(
        'accomplishment_reports',
        'accomplishment_reports__report_images'
    ).order_by('-end_date')[:6]
    
    projects_data = []
    for project in completed_projects:
        # Get the chairman's full address
        chairman = project.chairman
        address = chairman.address if chairman.address else "Address not available"
        
        # Get the final project image
        image = project.final_image if project.final_image else None
        
        project_info = {
            'title': project.name,
            'image': image,
            'chairman_name': chairman.get_full_name() or chairman.username,
            'address': address,
            'completion_date': project.end_date,
            'description': project.description,
            'allocated_budget': project.allocated_budget,
            'start_date': project.start_date,
            'status': project.status,
            'category': project.category if hasattr(project, 'category') else None,
            'beneficiaries': project.beneficiaries if hasattr(project, 'beneficiaries') else None
        }
        projects_data.append(project_info)
    
    context = {
        'completed_projects': projects_data
    }
    return render(request, 'landing_page.html', context)

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
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid username or password.'
                })
        else:
            errors = dict(form.errors.items())
            return JsonResponse({
                'success': False,
                'error': 'Please correct the errors below.',
                'form_errors': errors
            })
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
    # For admin users, allow viewing any project
    # For chairmen, only allow viewing their own projects
    if request.user.is_superuser:
        project = get_object_or_404(Project, id=project_id)
    else:
        project = get_object_or_404(Project, id=project_id, chairman=request.user)

    expenses = project.expenses.all().order_by('-date_incurred')
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
    remaining_budget = project.allocated_budget - total_expenses
    accomplishment_reports = project.accomplishment_reports.prefetch_related('report_images').all().order_by('-report_date')

    context = {
        'project': project,
        'expenses': expenses,
        'total_expenses': total_expenses,
        'remaining_budget': remaining_budget,
        'accomplishment_reports': accomplishment_reports,
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
        image_form = AccomplishmentReportImageForm(request.POST, request.FILES)
        
        if form.is_valid():
            with transaction.atomic():
                # Save the report first
                report = form.save(commit=False)
                report.project = project
                report.save()
                
                # Handle multiple image uploads
                if 'images' in request.FILES:
                    for image in request.FILES.getlist('images'):
                        AccomplishmentReportImage.objects.create(
                            report=report,
                            image=image
                        )
                
            messages.success(request, 'Accomplishment report added successfully.')
            return redirect('project_accomplishment_report', project_id=project.id)
    else:
        form = AccomplishmentReportForm()
        image_form = AccomplishmentReportImageForm()
    
    return render(request, 'add_accomplishment_report.html', {
        'form': form,
        'image_form': image_form,
        'project': project
    })

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
def export_project_pdf(request, project_id):
    # Get project and related data
    project = get_object_or_404(Project, pk=project_id)
    expenses = project.expenses.all().order_by('date_incurred')
    accomplishment_reports = project.accomplishment_reports.all().order_by('-report_date')
    total_expenses = project.expenses.aggregate(total=Sum('amount'))['total'] or 0

    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{project.name}_report.pdf"'

    # Document setup with custom margins
    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=50,
        bottomMargin=80  # Increased bottom margin for footer
    )

    # Modern professional color palette
    brand_colors = {
        'primary': colors.HexColor('#1E3D59'),    # Deep Navy
        'secondary': colors.HexColor('#FF6B6B'),   # Coral
        'accent': colors.HexColor('#4CAF50'),      # Success Green
        'warning': colors.HexColor('#FFC107'),     # Warning Yellow
        'text': colors.HexColor('#2C3E50'),        # Dark Text
        'light': colors.HexColor('#F5F7FA'),       # Light Background
        'border': colors.HexColor('#E9ECEF'),      # Border Gray
        'muted': colors.HexColor('#6C757D')        # Muted Text
    }

    # Enhanced styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=brand_colors['primary'],
        fontName='Helvetica-Bold',
        leading=32,
        borderWidth=2,
        borderColor=brand_colors['primary'],
        borderPadding=20,
        backColor=brand_colors['light']
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=18,
        spaceBefore=25,
        spaceAfter=15,
        textColor=brand_colors['primary'],
        fontName='Helvetica-Bold',
        leading=22,
        borderWidth=0,
        borderColor=brand_colors['border'],
        borderPadding=10,
        borderRadius=5,
        leftIndent=0
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        textColor=brand_colors['text'],
        fontName='Helvetica',
        leading=16,
        alignment=TA_JUSTIFY,
        spaceBefore=5,
        spaceAfter=5
    )

    caption_style = ParagraphStyle(
        'ImageCaption',
        parent=styles['Normal'],
        fontSize=10,
        textColor=brand_colors['muted'],
        fontName='Helvetica-Oblique',
        alignment=TA_CENTER,
        spaceBefore=5,
        spaceAfter=15
    )

    elements = []
    temp_files = []  # Keep track of temporary files to close later

    # Add report header with decorative elements
    elements.append(Paragraph(f"Project Report", title_style))
    elements.append(Paragraph(f"{project.name}", heading_style))
    elements.append(HRFlowable(
        width="100%",
        thickness=2,
        color=brand_colors['primary'],
        spaceBefore=10,
        spaceAfter=25,
        lineCap='round'
    ))

    # Project Overview with enhanced styling
    elements.append(Paragraph("Project Overview", heading_style))
    overview_data = [
        ['Chairman', project.chairman.get_full_name()],
        ['Start Date', project.start_date.strftime('%B %d, %Y')],
        ['End Date', project.end_date.strftime('%B %d, %Y')],
        ['Budget', f"₱{project.allocated_budget:,.2f}"],
        ['Total Expenses', f"₱{total_expenses:,.2f}"],
        ['Status', get_project_status(project)]
    ]

    # Enhanced table style
    overview_table = Table(overview_data, colWidths=[150, 300])
    overview_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TEXTCOLOR', (0, 0), (0, -1), brand_colors['primary']),
        ('TEXTCOLOR', (1, 0), (1, -1), brand_colors['text']),
        ('GRID', (0, 0), (-1, -1), 1, brand_colors['border']),
        ('BACKGROUND', (0, 0), (-1, -1), brand_colors['light']),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, brand_colors['light']]),
    ]))
    elements.append(overview_table)
    elements.append(Spacer(1, 25))

    # Project Description with enhanced styling
    if project.description:
        elements.append(Paragraph("Description", heading_style))
        elements.append(Paragraph(project.description, normal_style))
        elements.append(Spacer(1, 25))

    # Expenses Section with enhanced styling
    if expenses:
        elements.append(Paragraph("Expenses", heading_style))
        expense_data = [['Date', 'Item', 'Amount', 'Description']]
        for expense in expenses:
            expense_data.append([
                expense.date_incurred.strftime('%B %d, %Y'),
                expense.item_name,
                f"₱{expense.amount:,.2f}",
                expense.description or ''
            ])

        expense_table = Table(expense_data, colWidths=[100, 120, 100, 200])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), brand_colors['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, brand_colors['light']]),
            ('GRID', (0, 0), (-1, -1), 1, brand_colors['border']),
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
        ]))
        elements.append(expense_table)
        elements.append(Spacer(1, 25))

    # Accomplishment Reports Section with enhanced styling
    if accomplishment_reports:
        elements.append(Paragraph("Accomplishment Reports", heading_style))
        for report in accomplishment_reports:
            # Add report date with special styling
            date_style = ParagraphStyle(
                'ReportDate',
                parent=normal_style,
                textColor=brand_colors['secondary'],
                fontSize=12,
                fontName='Helvetica-Bold'
            )
            elements.append(Paragraph(f"Report Date: {report.report_date.strftime('%B %d, %Y')}", date_style))
            elements.append(Paragraph(report.report_details, normal_style))
            elements.append(Spacer(1, 15))
            
            # Get all images for this report
            report_images = report.report_images.all()
            
            if report_images:
                # Create a list to hold images for this report
                images_data = []
                current_row = []
                
                for i, report_image in enumerate(report_images, 1):
                    try:
                        # Get the absolute filesystem path to the image file
                        image_path = os.path.join(settings.MEDIA_ROOT, str(report_image.image))
                        
                        if not os.path.exists(image_path):
                            print(f"Image not found at path: {image_path}")
                            continue
                        
                        # Try to open and convert image using PIL first
                        from PIL import Image as PILImage
                        with PILImage.open(image_path) as pil_img:
                            # Convert to RGB if necessary
                            if pil_img.mode in ('RGBA', 'P'):
                                pil_img = pil_img.convert('RGB')
                            
                            # Create a temporary file for the converted image
                            temp_io = BytesIO()
                            pil_img.save(temp_io, format='JPEG', quality=85, optimize=True)
                            temp_io.seek(0)
                            
                            # Keep track of the BytesIO object
                            temp_files.append(temp_io)
                            
                            # Create ReportLab image from the temporary file
                            img_for_pdf = Image(temp_io)
                            
                            # Scale image to fit in the page
                            img_width = 250  # Fixed width for 2-column layout
                            img_height = (img_width / pil_img.width) * pil_img.height
                            
                            if img_height > 300:  # Max height
                                img_height = 300
                                img_width = (img_height / pil_img.height) * pil_img.width
                            
                            img_for_pdf.drawHeight = img_height
                            img_for_pdf.drawWidth = img_width
                            
                            # Add image and caption to current row
                            image_cell = [img_for_pdf]
                            if report_image.caption:
                                image_cell.append(Paragraph(report_image.caption, caption_style))
                            current_row.append(image_cell)
                            
                            # Create a new row after every 2 images
                            if len(current_row) == 2:
                                images_data.append(current_row)
                                current_row = []
                            
                    except Exception as e:
                        print(f"Error processing image: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                # Add any remaining images
                if current_row:
                    while len(current_row) < 2:
                        current_row.append([''])  # Add empty cell to complete the row
                    images_data.append(current_row)
                
                # Create table for images (2 columns) with enhanced styling
                if images_data:
                    for row in images_data:
                        image_table = Table(row, colWidths=[250, 250], spaceBefore=15)
                        image_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 10),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                            ('TOPPADDING', (0, 0), (-1, -1), 5),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                        ]))
                        elements.append(image_table)
            
            # Add separator between reports
            elements.append(HRFlowable(
                width="90%",
                thickness=1,
                color=brand_colors['border'],
                spaceBefore=20,
                spaceAfter=20,
                lineCap='round'
            ))

    # Add footer with page numbers, timestamp, and prepared by
    def footer(canvas, doc):
        canvas.saveState()
        
        # Add decorative line
        canvas.setStrokeColor(brand_colors['border'])
        canvas.setLineWidth(2)
        canvas.line(40, 70, doc.pagesize[0] - 40, 70)
        
        # Add prepared by section
        canvas.setFont('Helvetica-Bold', 10)
        canvas.setFillColor(brand_colors['primary'])
        canvas.drawString(40, 40, f"Prepared by: {project.chairman.get_full_name()}")
        
        # Add page number and timestamp on the right
        page_num = canvas.getPageNumber()
        timestamp = datetime.now().strftime("%B %d, %Y %I:%M %p")
        
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(brand_colors['muted'])
        canvas.drawRightString(doc.pagesize[0] - 40, 40, f"Page {page_num}")
        canvas.drawRightString(doc.pagesize[0] - 40, 30, timestamp)
        
        canvas.restoreState()

    try:
        # Build PDF with footer
        doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            temp_file.close()

    return response

@login_required
def export_sk_report(request, project_id):
    # Get project and related data
    project = get_object_or_404(Project, pk=project_id)
    expenses = project.expenses.all().order_by('date_incurred')
    accomplishment_reports = project.accomplishment_reports.all().order_by('-report_date')
    total_expenses = project.expenses.aggregate(total=Sum('amount'))['total'] or 0

    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{project.name}_report.pdf"'

    # Document setup with custom margins
    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=50,
        bottomMargin=80  # Increased bottom margin for footer
    )

    # Modern professional color palette
    brand_colors = {
        'primary': colors.HexColor('#1E3D59'),    # Deep Navy
        'secondary': colors.HexColor('#FF6B6B'),   # Coral
        'accent': colors.HexColor('#4CAF50'),      # Success Green
        'warning': colors.HexColor('#FFC107'),     # Warning Yellow
        'text': colors.HexColor('#2C3E50'),        # Dark Text
        'light': colors.HexColor('#F5F7FA'),       # Light Background
        'border': colors.HexColor('#E9ECEF'),      # Border Gray
        'muted': colors.HexColor('#6C757D')        # Muted Text
    }

    # Enhanced styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=brand_colors['primary'],
        fontName='Helvetica-Bold',
        leading=32,
        borderWidth=2,
        borderColor=brand_colors['primary'],
        borderPadding=20,
        backColor=brand_colors['light']
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=18,
        spaceBefore=25,
        spaceAfter=15,
        textColor=brand_colors['primary'],
        fontName='Helvetica-Bold',
        leading=22,
        borderWidth=0,
        borderColor=brand_colors['border'],
        borderPadding=10,
        borderRadius=5,
        leftIndent=0
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        textColor=brand_colors['text'],
        fontName='Helvetica',
        leading=16,
        alignment=TA_JUSTIFY,
        spaceBefore=5,
        spaceAfter=5
    )

    caption_style = ParagraphStyle(
        'ImageCaption',
        parent=styles['Normal'],
        fontSize=10,
        textColor=brand_colors['muted'],
        fontName='Helvetica-Oblique',
        alignment=TA_CENTER,
        spaceBefore=5,
        spaceAfter=15
    )

    elements = []
    temp_files = []  # Keep track of temporary files to close later

    # Add report header with decorative elements
    elements.append(Paragraph(f"Project Report", title_style))
    elements.append(Paragraph(f"{project.name}", heading_style))
    elements.append(HRFlowable(
        width="100%",
        thickness=2,
        color=brand_colors['primary'],
        spaceBefore=10,
        spaceAfter=25,
        lineCap='round'
    ))

    # Project Overview with enhanced styling
    elements.append(Paragraph("Project Overview", heading_style))
    overview_data = [
        ['Chairman', project.chairman.get_full_name()],
        ['Start Date', project.start_date.strftime('%B %d, %Y')],
        ['End Date', project.end_date.strftime('%B %d, %Y')],
        ['Budget', f"₱{project.allocated_budget:,.2f}"],
        ['Total Expenses', f"₱{total_expenses:,.2f}"],
        ['Status', get_project_status(project)]
    ]

    # Enhanced table style
    overview_table = Table(overview_data, colWidths=[150, 300])
    overview_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TEXTCOLOR', (0, 0), (0, -1), brand_colors['primary']),
        ('TEXTCOLOR', (1, 0), (1, -1), brand_colors['text']),
        ('GRID', (0, 0), (-1, -1), 1, brand_colors['border']),
        ('BACKGROUND', (0, 0), (-1, -1), brand_colors['light']),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, brand_colors['light']]),
    ]))
    elements.append(overview_table)
    elements.append(Spacer(1, 25))

    # Project Description with enhanced styling
    if project.description:
        elements.append(Paragraph("Description", heading_style))
        elements.append(Paragraph(project.description, normal_style))
        elements.append(Spacer(1, 25))

    # Expenses Section with enhanced styling
    if expenses:
        elements.append(Paragraph("Expenses", heading_style))
        expense_data = [['Date', 'Item', 'Amount', 'Description']]
        for expense in expenses:
            expense_data.append([
                expense.date_incurred.strftime('%B %d, %Y'),
                expense.item_name,
                f"₱{expense.amount:,.2f}",
                expense.description or ''
            ])

        expense_table = Table(expense_data, colWidths=[100, 120, 100, 200])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), brand_colors['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, brand_colors['light']]),
            ('GRID', (0, 0), (-1, -1), 1, brand_colors['border']),
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
        ]))
        elements.append(expense_table)
        elements.append(Spacer(1, 25))

    # Accomplishment Reports Section with enhanced styling
    if accomplishment_reports:
        elements.append(Paragraph("Accomplishment Reports", heading_style))
        for report in accomplishment_reports:
            # Add report date with special styling
            date_style = ParagraphStyle(
                'ReportDate',
                parent=normal_style,
                textColor=brand_colors['secondary'],
                fontSize=12,
                fontName='Helvetica-Bold'
            )
            elements.append(Paragraph(f"Report Date: {report.report_date.strftime('%B %d, %Y')}", date_style))
            elements.append(Paragraph(report.report_details, normal_style))
            elements.append(Spacer(1, 15))
            
            # Get all images for this report
            report_images = report.report_images.all()
            
            if report_images:
                # Create a list to hold images for this report
                images_data = []
                current_row = []
                
                for i, report_image in enumerate(report_images, 1):
                    try:
                        # Get the absolute filesystem path to the image file
                        image_path = os.path.join(settings.MEDIA_ROOT, str(report_image.image))
                        
                        if not os.path.exists(image_path):
                            print(f"Image not found at path: {image_path}")
                            continue
                        
                        # Try to open and convert image using PIL first
                        from PIL import Image as PILImage
                        with PILImage.open(image_path) as pil_img:
                            # Convert to RGB if necessary
                            if pil_img.mode in ('RGBA', 'P'):
                                pil_img = pil_img.convert('RGB')
                            
                            # Create a temporary file for the converted image
                            temp_io = BytesIO()
                            pil_img.save(temp_io, format='JPEG', quality=85, optimize=True)
                            temp_io.seek(0)
                            
                            # Keep track of the BytesIO object
                            temp_files.append(temp_io)
                            
                            # Create ReportLab image from the temporary file
                            img_for_pdf = Image(temp_io)
                            
                            # Scale image to fit in the page
                            img_width = 250  # Fixed width for 2-column layout
                            img_height = (img_width / pil_img.width) * pil_img.height
                            
                            if img_height > 300:  # Max height
                                img_height = 300
                                img_width = (img_height / pil_img.height) * pil_img.width
                            
                            img_for_pdf.drawHeight = img_height
                            img_for_pdf.drawWidth = img_width
                            
                            # Add image and caption to current row
                            image_cell = [img_for_pdf]
                            if report_image.caption:
                                image_cell.append(Paragraph(report_image.caption, caption_style))
                            current_row.append(image_cell)
                            
                            # Create a new row after every 2 images
                            if len(current_row) == 2:
                                images_data.append(current_row)
                                current_row = []
                            
                    except Exception as e:
                        print(f"Error processing image: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                # Add any remaining images
                if current_row:
                    while len(current_row) < 2:
                        current_row.append([''])  # Add empty cell to complete the row
                    images_data.append(current_row)
                
                # Create table for images (2 columns) with enhanced styling
                if images_data:
                    for row in images_data:
                        image_table = Table(row, colWidths=[250, 250], spaceBefore=15)
                        image_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 10),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                            ('TOPPADDING', (0, 0), (-1, -1), 5),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                        ]))
                        elements.append(image_table)
            
            # Add separator between reports
            elements.append(HRFlowable(
                width="90%",
                thickness=1,
                color=brand_colors['border'],
                spaceBefore=20,
                spaceAfter=20,
                lineCap='round'
            ))

    # Add footer with page numbers, timestamp, and prepared by
    def footer(canvas, doc):
        canvas.saveState()
        
        # Add decorative line
        canvas.setStrokeColor(brand_colors['border'])
        canvas.setLineWidth(2)
        canvas.line(40, 70, doc.pagesize[0] - 40, 70)
        
        # Add prepared by section
        canvas.setFont('Helvetica-Bold', 10)
        canvas.setFillColor(brand_colors['primary'])
        canvas.drawString(40, 40, f"Prepared by: {project.chairman.get_full_name()}")
        
        # Add page number and timestamp on the right
        page_num = canvas.getPageNumber()
        timestamp = datetime.now().strftime("%B %d, %Y %I:%M %p")
        
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(brand_colors['muted'])
        canvas.drawRightString(doc.pagesize[0] - 40, 40, f"Page {page_num}")
        canvas.drawRightString(doc.pagesize[0] - 40, 30, timestamp)
        
        canvas.restoreState()

    try:
        # Build PDF with footer
        doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            temp_file.close()

    return response

@login_required
def view_image(request, report_id, image_index):
    report = get_object_or_404(AccomplishmentReport, id=report_id)
    
    # Ensure user has access to this report
    if not request.user.is_superuser and report.project.chairman != request.user:
        raise Http404
    
    # Get all images for this report
    images = list(report.report_images.all().order_by('created_at'))
    
    if not images or image_index < 0 or image_index >= len(images):
        raise Http404
    
    current_image = images[image_index]
    
    context = {
        'image_url': current_image.image.url,
        'report_date': report.report_date.strftime("%B %d, %Y"),
        'caption': current_image.caption,
        'report_id': report_id,
        'has_prev': image_index > 0,
        'has_next': image_index < len(images) - 1,
        'prev_index': image_index - 1,
        'next_index': image_index + 1,
    }
    
    return render(request, 'partials/image_modal.html', context)

def get_project_status(project):
    current_date = timezone.now().date()
    if project.end_date < current_date:
        return "Completed"
    elif project.start_date <= current_date <= project.end_date:
        return "In Progress"
    else:
        return "Not Started"

@login_required
def edit_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)
    project = expense.project
    
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully.')
            return redirect('project_detail', project_id=project.id)
    else:
        form = ExpenseForm(instance=expense)
    
    context = {
        'form': form,
        'expense': expense,
        'project': project,
        'is_edit': True
    }
    return render(request, 'add_expense.html', context)

@login_required
def delete_expense(request, expense_id):
    if request.method == 'POST':
        expense = get_object_or_404(Expense, id=expense_id)
        project_id = expense.project.id
        expense.delete()
        messages.success(request, 'Expense deleted successfully.')
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

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

@login_required
def complete_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    
    if request.method == 'POST':
        form = ProjectCompletionForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            project = form.save()
            messages.success(request, 'Project marked as completed successfully.')
            return redirect('project_detail', project_id=project.id)
    else:
        form = ProjectCompletionForm(instance=project)
    
    return render(request, 'complete_project.html', {
        'form': form,
        'project': project
    })

from django.contrib.auth.decorators import user_passes_test

@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    # Get all search parameters
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    min_budget = request.GET.get('min_budget')
    max_budget = request.GET.get('max_budget')
    year = request.GET.get('year')
    
    # Initialize queryset for projects and budgets
    projects = Project.objects.all()
    main_budgets = MainBudget.objects.all()
    
    # Apply search filters
    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(chairman__first_name__icontains=search_query) |
            Q(chairman__last_name__icontains=search_query)
        )
        main_budgets = main_budgets.filter(
            Q(chairman__first_name__icontains=search_query) |
            Q(chairman__last_name__icontains=search_query)
        )
    
    # Apply date filters
    if date_from:
        projects = projects.filter(start_date__gte=date_from)
    if date_to:
        projects = projects.filter(end_date__lte=date_to)
    
    # Apply status filter
    if status:
        today = timezone.now().date()
        if status == 'not_started':
            projects = projects.filter(start_date__gt=today)
        elif status == 'in_progress':
            projects = projects.filter(start_date__lte=today, end_date__gte=today)
        elif status == 'completed':
            projects = projects.filter(end_date__lt=today)
    
    # Apply budget range filters
    if min_budget:
        projects = projects.filter(allocated_budget__gte=Decimal(min_budget))
    if max_budget:
        projects = projects.filter(allocated_budget__lte=Decimal(max_budget))
    
    # Apply year filter
    if year:
        main_budgets = main_budgets.filter(year=year)
        projects = projects.filter(main_budget__year=year)
    
    # Calculate totals
    total_budget = main_budgets.aggregate(total=Sum('total_budget'))['total'] or 0
    total_expenses = projects.aggregate(total=Sum('expenses__amount'))['total'] or 0
    
    # Get available years for the filter dropdown
    available_years = MainBudget.objects.values_list('year', flat=True).distinct().order_by('-year')
    
    # Count results
    results_count = projects.count()
    
    context = {
        'all_projects': projects.order_by('-start_date'),
        'all_main_budgets': main_budgets.order_by('-year'),
        'total_budget': total_budget,
        'total_expenses': total_expenses,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'status': status,
        'min_budget': min_budget,
        'max_budget': max_budget,
        'selected_year': year,
        'available_years': available_years,
        'results_count': results_count,
        'search_applied': any([search_query, date_from, date_to, status, min_budget, max_budget, year])
    }
    
    return render(request, 'admin_dashboard.html', context)

@login_required
def generate_comprehensive_report(request):
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="comprehensive_report.pdf"'

    # Document setup with landscape orientation for better table layout
    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=40,
        leftMargin=40,
        topMargin=50,
        bottomMargin=80
    )

    # Enhanced color palette
    brand_colors = {
        'primary': colors.HexColor('#1E3D59'),    # Deep Navy
        'secondary': colors.HexColor('#FF6B6B'),   # Coral
        'accent': colors.HexColor('#4CAF50'),      # Success Green
        'warning': colors.HexColor('#FFC107'),     # Warning Yellow
        'danger': colors.HexColor('#DC3545'),      # Danger Red
        'text': colors.HexColor('#2C3E50'),        # Dark Text
        'light': colors.HexColor('#F5F7FA'),       # Light Background
        'border': colors.HexColor('#E9ECEF'),      # Border Gray
        'muted': colors.HexColor('#6C757D')        # Muted Text
    }

    # Enhanced styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=brand_colors['primary'],
        fontName='Helvetica-Bold',
        leading=32,
        borderWidth=2,
        borderColor=brand_colors['primary'],
        borderPadding=20,
        backColor=brand_colors['light']
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=15,
        textColor=brand_colors['primary'],
        fontName='Helvetica-Bold',
        leading=22
    )

    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10,
        textColor=brand_colors['secondary'],
        fontName='Helvetica-Bold',
        leading=18
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=brand_colors['text'],
        fontName='Helvetica',
        leading=14
    )

    caption_style = ParagraphStyle(
        'ImageCaption',
        parent=styles['Normal'],
        fontSize=10,
        textColor=brand_colors['muted'],
        fontName='Helvetica-Oblique',
        alignment=TA_CENTER,
        spaceBefore=5,
        spaceAfter=15
    )

    elements = []

    # Report Header
    elements.append(Paragraph("SK Budget Management System", title_style))
    elements.append(Paragraph("Comprehensive Project Report", heading_style))
    current_date = timezone.now().strftime("%B %d, %Y")
    elements.append(Paragraph(f"Generated on: {current_date}", normal_style))
    elements.append(Spacer(1, 20))

    # Overall Budget Summary
    elements.append(Paragraph("Overall Budget Summary", heading_style))
    total_budget = MainBudget.objects.aggregate(total=Sum('total_budget'))['total'] or 0
    total_expenses = Expense.objects.aggregate(total=Sum('amount'))['total'] or 0
    total_projects = Project.objects.count()
    active_projects = Project.objects.filter(end_date__gte=timezone.now()).count()

    summary_data = [
        ['Total Budget', 'Total Expenses', 'Remaining Budget', 'Total Projects', 'Active Projects'],
        [
            f"₱{total_budget:,.2f}",
            f"₱{total_expenses:,.2f}",
            f"₱{total_budget - total_expenses:,.2f}",
            str(total_projects),
            str(active_projects)
        ]
    ]

    summary_table = Table(summary_data, colWidths=[160] * 5)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), brand_colors['primary']),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, brand_colors['border']),
        ('BACKGROUND', (0, 1), (-1, 1), brand_colors['light'])
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 30))

    # Get all chairmen and their projects
    chairmen = User.objects.filter(is_chairman=True).order_by('last_name', 'first_name')

    for chairman in chairmen:
        # Chairman Section
        elements.append(Paragraph(f"Chairman: {chairman.get_full_name()}", subheading_style))
        
        # Chairman Details
        chairman_details = [
            ['Contact Information', 'Budget Overview'],
            [
                f"Address: {chairman.address or 'N/A'}\n" +
                f"Email: {chairman.email or 'N/A'}",
                f"Total Projects: {Project.objects.filter(chairman=chairman).count()}\n" +
                f"Active Projects: {Project.objects.filter(chairman=chairman, end_date__gte=timezone.now()).count()}"
            ]
        ]
        
        details_table = Table(chairman_details, colWidths=[400, 400])
        details_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, brand_colors['border']),
            ('BACKGROUND', (0, 0), (-1, 0), brand_colors['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(details_table)
        elements.append(Spacer(1, 15))

        # Projects Table
        projects = Project.objects.filter(chairman=chairman).order_by('-start_date')
        
        if projects:
            elements.append(Paragraph("Project Details", heading_style))
            
            project_data = [[
                'Project Name',
                'Duration',
                'Budget',
                'Expenses',
                'Remaining',
                'Status',
                'Progress'
            ]]
            
            for project in projects:
                total_expenses = project.expenses.aggregate(total=Sum('amount'))['total'] or 0
                remaining = project.allocated_budget - total_expenses
                status = get_project_status(project)
                
                # Calculate progress
                total_days = (project.end_date - project.start_date).days
                days_passed = (timezone.now().date() - project.start_date).days
                progress = min(100, max(0, (days_passed / total_days * 100))) if total_days > 0 else 0
                
                project_data.append([
                    project.name,
                    f"{project.start_date.strftime('%b %d, %Y')}\nto\n{project.end_date.strftime('%b %d, %Y')}",
                    f"₱{project.allocated_budget:,.2f}",
                    f"₱{total_expenses:,.2f}",
                    f"₱{remaining:,.2f}",
                    status,
                    f"{progress:.1f}%"
                ])

            project_table = Table(project_data, colWidths=[150, 120, 120, 120, 120, 100, 80])
            project_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), brand_colors['primary']),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, brand_colors['border']),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, brand_colors['light']]),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(project_table)
            
            # Add Accomplishment Reports
            accomplishment_reports = project.accomplishment_reports.prefetch_related('report_images').all().order_by('-report_date')[:3]
            if accomplishment_reports:
                elements.append(Spacer(1, 15))
                elements.append(Paragraph("Project Accomplishments", subheading_style))
                
                for report in accomplishment_reports:
                    # Add report date with special styling
                    date_style = ParagraphStyle(
                        'ReportDate',
                        parent=normal_style,
                        textColor=brand_colors['secondary'],
                        fontSize=12,
                        fontName='Helvetica-Bold'
                    )
                    elements.append(Paragraph(f"Report Date: {report.report_date.strftime('%B %d, %Y')}", date_style))
                    elements.append(Paragraph(report.report_details, normal_style))
                    elements.append(Spacer(1, 15))
                    
                    # Get all images for this report
                    report_images = report.report_images.all()
                    
                    if report_images:
                        # Create a list to hold images for this report
                        images_data = []
                        current_row = []
                        
                        for i, report_image in enumerate(report_images, 1):
                            try:
                                # Get the absolute filesystem path to the image file
                                image_path = os.path.join(settings.MEDIA_ROOT, str(report_image.image))
                                
                                if not os.path.exists(image_path):
                                    print(f"Image not found at path: {image_path}")
                                    continue
                                
                                # Try to open and convert image using PIL first
                                from PIL import Image as PILImage
                                with PILImage.open(image_path) as pil_img:
                                    # Convert to RGB if necessary
                                    if pil_img.mode in ('RGBA', 'P'):
                                        pil_img = pil_img.convert('RGB')
                                    
                                    # Create a temporary file for the converted image
                                    temp_io = BytesIO()
                                    pil_img.save(temp_io, format='JPEG', quality=85, optimize=True)
                                    temp_io.seek(0)
                                    
                                    # Keep track of the BytesIO object
                                    temp_files.append(temp_io)
                                    
                                    # Create ReportLab image from the temporary file
                                    img_for_pdf = Image(temp_io)
                                    
                                    # Scale image to fit in the page (landscape mode)
                                    img_width = 350  # Wider for landscape mode
                                    img_height = (img_width / pil_img.width) * pil_img.height
                                    
                                    if img_height > 250:  # Max height for landscape
                                        img_height = 250
                                        img_width = (img_height / pil_img.height) * pil_img.width
                                    
                                    img_for_pdf.drawHeight = img_height
                                    img_for_pdf.drawWidth = img_width
                                    
                                    # Add image and caption to current row
                                    image_cell = [img_for_pdf]
                                    if report_image.caption:
                                        image_cell.append(Paragraph(report_image.caption, caption_style))
                                    current_row.append(image_cell)
                                    
                                    # Create a new row after every 2 images
                                    if len(current_row) == 2:
                                        images_data.append(current_row)
                                        current_row = []
                                    
                            except Exception as e:
                                print(f"Error processing image: {str(e)}")
                                import traceback
                                traceback.print_exc()
                                continue
                        
                        # Add any remaining images
                        if current_row:
                            while len(current_row) < 2:
                                current_row.append([''])  # Add empty cell to complete the row
                            images_data.append(current_row)
                        
                        # Create table for images (2 columns) with enhanced styling
                        if images_data:
                            for row in images_data:
                                image_table = Table(row, colWidths=[350, 350], spaceBefore=15)
                                image_table.setStyle(TableStyle([
                                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                                ]))
                                elements.append(image_table)
                    
                    # Add separator between reports
                    elements.append(HRFlowable(
                        width="90%",
                        thickness=1,
                        color=brand_colors['border'],
                        spaceBefore=20,
                        spaceAfter=20,
                        lineCap='round'
                    ))
            
            # Recent Expenses Chart
            recent_expenses = Expense.objects.filter(
                project__chairman=chairman
            ).order_by('-date_incurred')[:5]
            
            if recent_expenses:
                elements.append(Paragraph("Recent Expenses", heading_style))
                expense_data = {
                    expense.description: float(expense.amount)
                    for expense in recent_expenses
                }
                chart = create_bar_chart(expense_data, brand_colors)
                elements.append(chart)
                elements.append(Spacer(1, 20))

        elements.append(PageBreak())

    # Enhanced footer with more details
    def footer(canvas, doc):
        canvas.saveState()
        
        # Add decorative line
        canvas.setStrokeColor(brand_colors['border'])
        canvas.setLineWidth(2)
        canvas.line(40, 70, doc.pagesize[0] - 40, 70)
        
        # Footer content
        canvas.setFont('Helvetica-Bold', 10)
        canvas.setFillColor(brand_colors['primary'])
        canvas.drawString(40, 50, "SK Budget Management System")
        
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(brand_colors['muted'])
        canvas.drawString(40, 35, f"Generated by: {request.user.get_full_name()}")
        
        # Right side
        page_num = canvas.getPageNumber()
        timestamp = timezone.now().strftime("%B %d, %Y %I:%M %p")
        
        canvas.drawRightString(doc.pagesize[0] - 40, 50, f"Page {page_num}")
        canvas.drawRightString(doc.pagesize[0] - 40, 35, f"Generated on: {timestamp}")
        
        canvas.restoreState()

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    return response

@login_required
def generate_projects_report(request):
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="all_projects_report.pdf"'

    # Create the PDF object using ReportLab
    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=inch/2,
        leftMargin=inch/2,
        topMargin=inch/2,
        bottomMargin=inch/2
    )

    # Container for the 'Flowable' objects
    elements = []

    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#0A6847'),
        spaceAfter=20,
        alignment=TA_CENTER
    )

    # Add the title
    elements.append(Paragraph("Sangguniang Kabataan Projects Report", title_style))
    elements.append(Paragraph(f"Generated on {timezone.now().strftime('%B %d, %Y')}", subtitle_style))
    elements.append(Spacer(1, 20))

    # Get all projects
    projects = Project.objects.all().order_by('-start_date')

    # Summary statistics
    total_projects = projects.count()
    total_budget = projects.aggregate(Sum('allocated_budget'))['allocated_budget__sum'] or 0
    total_expenses = sum(project.expenses.aggregate(Sum('amount'))['amount__sum'] or 0 for project in projects)
    
    # Add summary section
    summary_data = [
        ['Total Projects', str(total_projects)],
        ['Total Budget Allocated', f"₱{total_budget:,.2f}"],
        ['Total Expenses', f"₱{total_expenses:,.2f}"],
        ['Remaining Budget', f"₱{(total_budget - total_expenses):,.2f}"],
    ]

    summary_table = Table(summary_data, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F6E9B2')),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Add projects table
    projects_data = [['Project Name', 'Chairman', 'Budget', 'Expenses', 'Start Date', 'End Date', 'Status']]
    
    for project in projects:
        project_expenses = project.expenses.aggregate(Sum('amount'))['amount__sum'] or 0
        status = get_project_status(project)
        
        projects_data.append([
            project.name,
            project.chairman.get_full_name(),
            f"₱{project.allocated_budget:,.2f}",
            f"₱{project_expenses:,.2f}",
            project.start_date.strftime('%B %d, %Y'),
            project.end_date.strftime('%B %d, %Y'),
            status
        ])

    projects_table = Table(projects_data, repeatRows=1)
    projects_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0A6847')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (2, 1), (3, -1), 'RIGHT'),  # Align budget and expenses to right
    ]))

    elements.append(projects_table)

    # Build the PDF document
    doc.build(elements)
    return response
