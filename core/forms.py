from django import forms
from vacancies.models import Vacancy
from interviews.models import Interview


class DailySchedulingScheduleForm(forms.Form):
    """Change the daily interview scheduling run time (hour and minute)."""
    hour = forms.IntegerField(min_value=0, max_value=23, widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 23}))
    minute = forms.IntegerField(min_value=0, max_value=59, widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 59}))


class InterviewEditForm(forms.ModelForm):
    """Edit interview date/time and duration (used on dashboard and portal)."""
    scheduled_at = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'],
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'form-control'},
            format='%Y-%m-%dT%H:%M',
        ),
    )

    class Meta:
        model = Interview
        fields = ['scheduled_at', 'duration_minutes']
        widgets = {
            'duration_minutes': forms.NumberInput(attrs={'min': 15, 'max': 180, 'step': 15, 'class': 'form-control'}),
        }


class VacancyForm(forms.ModelForm):
    class Meta:
        model = Vacancy
        fields = ['title', 'department', 'status', 'keywords', 'require_dob_in_cv', 'require_egyptian', 'require_relevant_university', 'require_relevant_major', 'questionnaire_template']
        widgets = {
            'keywords': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Comma-separated keywords'}),
            'questionnaire_template': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Enter questions or JSON'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add 'form-control' class to all inputs for styling
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-control'
            else:
                field.widget.attrs['class'] = 'form-check-input'
