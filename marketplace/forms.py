from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from .models import Job, JobApplication, Profile, Review
from .services import DEFAULT_SIGNUP_CREDITS, award_xp, get_fixpoint_packages, record_credit_change


class RegistrationForm(UserCreationForm):
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES)
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=30)
    city = forms.CharField(max_length=120)
    address = forms.CharField(max_length=255, required=False)
    latitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False, widget=forms.HiddenInput())
    longitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False, widget=forms.HiddenInput())
    bio = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False)
    skills = forms.CharField(required=False, help_text='List worker skills separated by commas.')
    hourly_rate = forms.DecimalField(max_digits=10, decimal_places=2, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'role',
            'phone',
            'city',
            'address',
            'latitude',
            'longitude',
            'bio',
            'skills',
            'hourly_rate',
            'password1',
            'password2',
        )

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        if role == Profile.WORKER and not cleaned_data.get('skills'):
            self.add_error('skills', 'Workers should add at least one skill to be matchable.')
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = self.cleaned_data['role']
        profile.phone = self.cleaned_data['phone']
        profile.city = self.cleaned_data['city']
        profile.address = self.cleaned_data.get('address', '')
        if self.cleaned_data.get('latitude') is not None:
            profile.latitude = self.cleaned_data.get('latitude')
        if self.cleaned_data.get('longitude') is not None:
            profile.longitude = self.cleaned_data.get('longitude')
        profile.bio = self.cleaned_data.get('bio', '')
        profile.skills = self.cleaned_data.get('skills', '')
        profile.hourly_rate = self.cleaned_data.get('hourly_rate')
        profile.is_verified = profile.role == Profile.WORKER
        profile.save()
        if DEFAULT_SIGNUP_CREDITS > 0:
            record_credit_change(profile, DEFAULT_SIGNUP_CREDITS, 'Welcome bonus')
        award_xp(profile, 5, 'Completed onboarding')
        return user


class ProfileForm(forms.ModelForm):
    WORKER_ONLY_FIELDS = ('skills', 'hourly_rate', 'response_time_hours')

    class Meta:
        model = Profile
        fields = (
            'phone',
            'city',
            'address',
            'latitude',
            'longitude',
            'bio',
            'skills',
            'hourly_rate',
            'response_time_hours',
        )
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.role != Profile.WORKER:
            for field_name in self.WORKER_ONLY_FIELDS:
                self.fields.pop(field_name, None)

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.cleaned_data.get('latitude') is None:
            profile.latitude = self.instance.latitude
        if self.cleaned_data.get('longitude') is None:
            profile.longitude = self.instance.longitude
        if commit:
            profile.save()
        return profile


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = (
            'title',
            'category',
            'description',
            'location_label',
            'location_address',
            'latitude',
            'longitude',
            'budget_min',
            'budget_max',
            'urgency',
            'due_date',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }
        labels = {
            'location_label': 'Job city',
            'location_address': 'Job address',
        }
        help_texts = {
            'location_label': 'Optional. Leave blank to use your profile city.',
            'location_address': 'Optional. Add a street or landmark for a more precise job location.',
        }

    def clean(self):
        cleaned_data = super().clean()
        budget_min = cleaned_data.get('budget_min')
        budget_max = cleaned_data.get('budget_max')
        if budget_min and budget_max and budget_min > budget_max:
            self.add_error('budget_max', 'Maximum budget should be greater than or equal to the minimum budget.')
        if cleaned_data.get('location_address') and not cleaned_data.get('location_label'):
            self.add_error('location_label', 'Add the city when you provide a job address.')
        return cleaned_data


class WalletTopUpForm(forms.Form):
    package = forms.ChoiceField(
        choices=[
            (
                package['code'],
                f"{package['name']} - NGN {package['naira_amount']} for {package['credits']} FixPoints",
            )
            for package in get_fixpoint_packages()
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = ('pitch', 'proposed_price', 'estimated_days')
        widgets = {
            'pitch': forms.Textarea(attrs={'rows': 4}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ('rating', 'comment')
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3}),
        }
