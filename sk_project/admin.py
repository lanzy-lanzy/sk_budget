from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, MainBudget, Project, Expense, AccomplishmentReport, Profile

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_chairman', 'is_staff')
    list_filter = ('is_chairman', 'is_staff', 'is_superuser')
    fieldsets = UserAdmin.fieldsets + (
        ('SK Chairman Info', {'fields': ('is_chairman',)}),
    )

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'

class CustomUserWithProfileAdmin(CustomUserAdmin):
    inlines = (ProfileInline,)

class ExpenseInline(admin.TabularInline):
    model = Expense
    extra = 1

class AccomplishmentReportInline(admin.StackedInline):
    model = AccomplishmentReport
    extra = 1

@admin.register(MainBudget)
class MainBudgetAdmin(admin.ModelAdmin):
    list_display = ('year', 'total_budget', 'chairman', 'created_at', 'updated_at')
    list_filter = ('year', 'chairman')
    search_fields = ('year', 'chairman__username')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'budget', 'main_budget', 'chairman', 'start_date', 'end_date', 'remaining_budget')
    list_filter = ('main_budget', 'chairman', 'start_date', 'end_date')
    search_fields = ('name', 'description', 'chairman__username')
    inlines = [ExpenseInline, AccomplishmentReportInline]

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('project', 'description', 'amount', 'date_incurred')
    list_filter = ('project', 'date_incurred')
    search_fields = ('project__name', 'description')

@admin.register(AccomplishmentReport)
class AccomplishmentReportAdmin(admin.ModelAdmin):
    list_display = ('project', 'report_date', 'created_at', 'updated_at')
    list_filter = ('project', 'report_date')
    search_fields = ('project__name', 'report_details')

admin.site.register(User, CustomUserWithProfileAdmin)
