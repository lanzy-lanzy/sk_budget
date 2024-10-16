from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """
    User model to represent SK chairmen.
    """
    is_chairman = models.BooleanField(default=False)

    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name='sk_user_set',
        related_query_name='sk_user',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='sk_user_set',
        related_query_name='sk_user',
    )

    def __str__(self):
        return self.username

class MainBudget(models.Model):
    """
    Main budget model to represent the total budget for a specific year.
    """
    year = models.PositiveIntegerField(unique=True)
    total_budget = models.DecimalField(max_digits=10, decimal_places=2)
    chairman = models.ForeignKey(User, related_name='main_budgets', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Main Budget for {self.year} - Total: {self.total_budget}"

    class Meta:
        verbose_name_plural = "Main Budgets"


class Project(models.Model):
    """
    Project model to represent individual projects funded from the main budget.
    """
    name = models.CharField(max_length=255)
    description = models.TextField()
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    main_budget = models.ForeignKey(MainBudget, related_name='projects', on_delete=models.CASCADE)
    chairman = models.ForeignKey(User, related_name='projects', on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def remaining_budget(self):
        total_expenses = self.expenses.aggregate(models.Sum('amount'))['amount__sum'] or 0
        return self.budget - total_expenses

    class Meta:
        ordering = ['start_date']


class Expense(models.Model):
    """
    Expense model to track expenditures related to projects.
    """
    project = models.ForeignKey(Project, related_name='expenses', on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_incurred = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.description} - {self.amount} (Date: {self.date_incurred})"

    class Meta:
        ordering = ['date_incurred']


class AccomplishmentReport(models.Model):
    """
    Accomplishment report model to represent project achievements.
    """
    project = models.ForeignKey(Project, related_name='accomplishment_reports', on_delete=models.CASCADE)
    report_date = models.DateField()
    report_details = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Accomplishment Report for {self.project.name} on {self.report_date}"

    class Meta:
        ordering = ['report_date']


class Profile(models.Model):
    """
    Profile model for additional user information.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    class Meta:
        verbose_name_plural = "Profiles"