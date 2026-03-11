from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=64, required=True)
    last_name = forms.CharField(max_length=64, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        )


class ParticipantForm(forms.Form):
    first_name = forms.CharField(
        max_length=64,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Imię"}),
    )
    last_name = forms.CharField(
        max_length=64,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nazwisko"}
        ),
    )
    pesel = forms.CharField(
        min_length=11,
        max_length=11,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "PESEL"}),
    )

    def clean_pesel(self):
        pesel = self.cleaned_data["pesel"]
        if pesel and not pesel.isdigit():
            raise forms.ValidationError("Pesel musi składać się wyłącznie z cyfr")
        return pesel
