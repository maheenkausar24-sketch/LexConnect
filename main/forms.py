from datetime import date, time
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import strip_tags

from .models import Booking, LawCategory, LawyerAvailability, Payment
from .validators import validate_chat_file, validate_legal_document


def sanitize_text(value):
    return strip_tags(value or "").strip()


class ErrorListMixin:
    def first_error(self):
        if not self.errors:
            return ""
        return next(iter(self.errors.values()))[0]


class ClientRegistrationForm(ErrorListMixin, forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254)
    password = forms.CharField(min_length=8, widget=forms.PasswordInput)

    def clean_username(self):
        return sanitize_text(self.cleaned_data["username"])


class LoginForm(ErrorListMixin, forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        return sanitize_text(self.cleaned_data["username"])


class LawyerRegistrationForm(ErrorListMixin, forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(min_length=8, widget=forms.PasswordInput)
    name = forms.CharField(max_length=100)
    email = forms.EmailField(max_length=254)
    phone = forms.CharField(max_length=20)
    location = forms.CharField(max_length=100)
    experience = forms.IntegerField(min_value=0)
    fee = forms.DecimalField(min_value=Decimal("100.00"), decimal_places=2, max_digits=10)
    category = forms.ModelChoiceField(queryset=LawCategory.objects.all())
    certification = forms.CharField(max_length=200, required=False)
    certificate_file = forms.FileField(required=False)
    bio = forms.CharField(required=False, widget=forms.Textarea)

    def clean_username(self):
        return sanitize_text(self.cleaned_data["username"])

    def clean_name(self):
        return sanitize_text(self.cleaned_data["name"])

    def clean_phone(self):
        return sanitize_text(self.cleaned_data["phone"])

    def clean_location(self):
        return sanitize_text(self.cleaned_data["location"])

    def clean_bio(self):
        return sanitize_text(self.cleaned_data["bio"])

    def clean_certification(self):
        return sanitize_text(self.cleaned_data["certification"])

    def clean_certificate_file(self):
        file = self.cleaned_data.get("certificate_file")
        validate_legal_document(file)
        return file


class BookingForm(ErrorListMixin, forms.ModelForm):
    slot_choice = forms.ChoiceField(required=False)

    class Meta:
        model = Booking
        fields = ["issue", "appointment_date", "appointment_time"]
        widgets = {
            "issue": forms.Textarea(),
            "appointment_date": forms.DateInput(attrs={"type": "date"}),
            "appointment_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, slot_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.slot_choices = slot_choices or []
        self.fields["slot_choice"].choices = [("", "Select an available slot")] + self.slot_choices
        if self.slot_choices:
            self.fields["appointment_date"].required = False
            self.fields["appointment_time"].required = False

    def clean_issue(self):
        issue = sanitize_text(self.cleaned_data["issue"])
        if len(issue) < 20:
            raise ValidationError("Please describe your issue in a bit more detail.")
        return issue

    def clean(self):
        cleaned_data = super().clean()
        slot_choice = cleaned_data.get("slot_choice")

        if slot_choice:
            try:
                appointment_date_value, appointment_time_value = slot_choice.split("|", 1)
            except ValueError as exc:
                raise ValidationError("Select a valid consultation slot.") from exc
            try:
                cleaned_data["appointment_date"] = date.fromisoformat(appointment_date_value)
                cleaned_data["appointment_time"] = time.fromisoformat(appointment_time_value)
            except ValueError as exc:
                raise ValidationError("Selected slot could not be parsed.") from exc

        if not cleaned_data.get("appointment_date") or not cleaned_data.get("appointment_time"):
            raise ValidationError("Please select one of the lawyer's available consultation slots.")

        return cleaned_data

    def clean_appointment_date(self):
        appointment_date = self.cleaned_data["appointment_date"]
        if not appointment_date:
            return appointment_date
        if appointment_date < timezone.localdate():
            raise ValidationError("Appointment date must be today or later.")
        return appointment_date


class BookingRescheduleForm(ErrorListMixin, forms.ModelForm):
    class Meta:
        model = Booking
        fields = ["appointment_date", "appointment_time"]
        widgets = {
            "appointment_date": forms.DateInput(attrs={"type": "date"}),
            "appointment_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean_appointment_date(self):
        appointment_date = self.cleaned_data["appointment_date"]
        if appointment_date < timezone.localdate():
            raise ValidationError("Appointment date must be today or later.")
        return appointment_date


class BookingCancelForm(ErrorListMixin, forms.Form):
    cancel_reason = forms.CharField(max_length=255, required=False)

    def clean_cancel_reason(self):
        return sanitize_text(self.cleaned_data["cancel_reason"])


class BookingStatusForm(ErrorListMixin, forms.Form):
    status = forms.ChoiceField(
        choices=[
            (Booking.Status.CONFIRMED, "Confirm"),
            (Booking.Status.COMPLETED, "Complete"),
            (Booking.Status.CANCELLED, "Cancel"),
        ]
    )


class PaymentStatusForm(ErrorListMixin, forms.Form):
    payment_status = forms.ChoiceField(
        choices=[
            (Payment.PaymentStatus.AWAITING_VERIFICATION, "Request demo verification"),
        ]
    )


class AdminActionConfirmationForm(ErrorListMixin, forms.Form):
    confirmation_token = forms.CharField(widget=forms.HiddenInput)
    expected_confirmation_token = ""

    def clean_confirmation_token(self):
        token = self.cleaned_data["confirmation_token"]
        if token != self.expected_confirmation_token:
            raise ValidationError("Action confirmation is missing or invalid.")
        return token


class AdminPaymentStatusForm(AdminActionConfirmationForm):
    expected_confirmation_token = "payment-status"
    payment_status = forms.ChoiceField(choices=Payment.PaymentStatus.choices)


class AdminLawyerVerificationForm(AdminActionConfirmationForm):
    expected_confirmation_token = "lawyer-verification"
    is_verified = forms.ChoiceField(
        choices=[
            ("true", "Approve"),
            ("false", "Unverify"),
        ]
    )

    def cleaned_value(self):
        return self.cleaned_data["is_verified"] == "true"


class AdminUserStatusForm(AdminActionConfirmationForm):
    expected_confirmation_token = "user-status"
    is_active = forms.ChoiceField(
        choices=[
            ("true", "Activate"),
            ("false", "Deactivate"),
        ]
    )

    def cleaned_value(self):
        return self.cleaned_data["is_active"] == "true"


class AdminBookingCancelForm(AdminActionConfirmationForm):
    expected_confirmation_token = "booking-cancel"


class MessageForm(ErrorListMixin, forms.Form):
    text = forms.CharField(required=False)
    file = forms.FileField(required=False)

    def clean_text(self):
        return sanitize_text(self.cleaned_data["text"])

    def clean_file(self):
        file = self.cleaned_data.get("file")
        validate_chat_file(file)
        return file

    def clean(self):
        cleaned_data = super().clean()
        text = cleaned_data.get("text")
        file = cleaned_data.get("file")
        if not text and not file:
            raise ValidationError("Message or file is required.")
        return cleaned_data


class ReviewForm(ErrorListMixin, forms.Form):
    booking_id = forms.IntegerField(widget=forms.HiddenInput)
    rating = forms.IntegerField(min_value=1, max_value=5)
    comment = forms.CharField(required=False, widget=forms.Textarea)

    def clean_comment(self):
        return sanitize_text(self.cleaned_data["comment"])


class LawyerAvailabilityForm(ErrorListMixin, forms.ModelForm):
    class Meta:
        model = LawyerAvailability
        fields = ["weekday", "start_time", "end_time", "slot_duration_minutes", "is_active"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        slot_duration = cleaned_data.get("slot_duration_minutes")
        if start_time and end_time and end_time <= start_time:
            raise ValidationError("End time must be after start time.")
        if start_time and end_time and slot_duration:
            start_minutes = start_time.hour * 60 + start_time.minute
            end_minutes = end_time.hour * 60 + end_time.minute
            if (end_minutes - start_minutes) < slot_duration:
                raise ValidationError("Availability window must be at least one full slot long.")
        return cleaned_data


class LawyerSearchForm(ErrorListMixin, forms.Form):
    q = forms.CharField(required=False, max_length=100)
    specialization = forms.CharField(required=False, max_length=100)
    location = forms.CharField(required=False, max_length=100)
    availability = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All verified lawyers"),
            ("online", "Available for chat now"),
        ],
    )
    min_experience = forms.IntegerField(required=False, min_value=0)
    max_experience = forms.IntegerField(required=False, min_value=0)
    min_rating = forms.DecimalField(required=False, min_value=0, max_value=5, decimal_places=1, max_digits=2)
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Recommended"),
            ("rating_desc", "Highest rated"),
            ("experience_desc", "Most experienced"),
        ],
    )

    def clean_q(self):
        return sanitize_text(self.cleaned_data["q"])

    def clean_specialization(self):
        return sanitize_text(self.cleaned_data["specialization"])

    def clean_location(self):
        return sanitize_text(self.cleaned_data["location"])

    def clean(self):
        cleaned_data = super().clean()
        min_experience = cleaned_data.get("min_experience")
        max_experience = cleaned_data.get("max_experience")
        if min_experience is not None and max_experience is not None and max_experience < min_experience:
            raise ValidationError("Maximum experience must be greater than minimum experience.")
        return cleaned_data
