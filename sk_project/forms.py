from django import forms
from .models import MainBudget, AccomplishmentReport, AccomplishmentReportImage

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

class ProjectCompletionForm(forms.ModelForm):
    """Form for completing a project and uploading final image"""
    class Meta:
        model = Project
        fields = ['status', 'final_image']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select rounded-lg border-gray-300 focus:border-tertiary focus:ring focus:ring-tertiary/50'}),
            'final_image': forms.FileInput(attrs={'class': 'form-input rounded-lg border-gray-300 focus:border-tertiary focus:ring focus:ring-tertiary/50'})
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        final_image = cleaned_data.get('final_image')
        
        if status == 'completed' and not final_image and not self.instance.final_image:
            # Check if there's a latest accomplishment report image
            latest_report = self.instance.accomplishment_reports.order_by('-report_date').first()
            if latest_report:
                latest_image = latest_report.report_images.order_by('-created_at').first()
                if latest_image:
                    cleaned_data['final_image'] = latest_image.image
                else:
                    raise forms.ValidationError("Please upload a final image or add an accomplishment report with images before completing the project.")
            else:
                raise forms.ValidationError("Please upload a final image or add an accomplishment report with images before completing the project.")
        
        return cleaned_data

from django import forms
from .models import Expense

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['item_name', 'price_per_unit', 'quantity', 'description', 'amount', 'date_incurred']
        widgets = {
            'item_name': forms.TextInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'price_per_unit': forms.NumberInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'description': forms.TextInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'amount': forms.NumberInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary', 'inputmode': 'numeric', 'pattern': '[0-9]*', 'onkeyup': 'this.value=this.value.replace(/\\B(?=(\\d{3})+(?!\\d))/g, ",")'}),
            'date_incurred': forms.DateInput(attrs={'type': 'date', 'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
        }

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class AccomplishmentReportForm(forms.ModelForm):
    class Meta:
        model = AccomplishmentReport
        fields = ['report_date', 'report_details']
        widgets = {
            'report_date': forms.DateInput(attrs={'type': 'date'}),
            'report_details': forms.Textarea(attrs={'rows': 4}),
        }

class AccomplishmentReportImageForm(forms.Form):
    images = forms.FileField(
        widget=MultipleFileInput(attrs={'class': 'sr-only', 'accept': 'image/*', 'multiple': True}),
        required=False
    )

from django import forms
from .models import Profile
from django import forms
from .models import User
from django import forms
from .models import User

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'profile_picture', 'address', 'contact_number']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'email': forms.EmailInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'contact_number': forms.TextInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
        }
