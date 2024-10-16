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
