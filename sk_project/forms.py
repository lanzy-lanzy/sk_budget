from django import forms
from .models import MainBudget

class MainBudgetForm(forms.ModelForm):
    class Meta:
        model = MainBudget
        fields = ['year', 'total_budget']


from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)

from django import forms
from .models import Project

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'budget', 'start_date', 'end_date']

from django import forms
from .models import Expense

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['item_name', 'quantity', 'description', 'amount', 'date_incurred']
        widgets = {
            'item_name': forms.TextInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'description': forms.TextInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'amount': forms.NumberInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'date_incurred': forms.DateInput(attrs={'type': 'date', 'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
        }
