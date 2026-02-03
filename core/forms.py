from django import forms
from vacancies.models import Vacancy

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
