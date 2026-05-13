from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from ..forms import ClientRegistrationForm, LawyerRegistrationForm, LoginForm
from ..models import LawCategory
from ..audit import audit_event, security_event
from ..rate_limit import RateLimitExceeded, consume_rate_limit, rate_limit
from ..services.auth import get_dashboard_route, is_lawyer_user, register_client_user, register_lawyer_user
from ..services.auth_security import send_verification_email, verify_email_token
from ..utils import mark_user_offline, mark_user_online


@rate_limit("client_register", limit=5, period=300)
def register(request):
    form = ClientRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        email = form.cleaned_data["email"].lower()

        if User.objects.filter(username=username).exists():
            form.add_error("username", "Username already exists")
        elif User.objects.filter(email=email).exists():
            form.add_error("email", "Email already exists")
        else:
            user = register_client_user(form.cleaned_data)
            send_verification_email(request, user)
            login(request, user)
            mark_user_online(user)
            audit_event("client_registered", request=request, actor=user)
            return redirect("dashboard")

    return render(request, "register.html", {"form": form, "error": form.first_error()})


@rate_limit("login", limit=8, period=300)
def login_page(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
        )
        if user is None:
            security_event("login_failed", request=request, username=form.cleaned_data["username"])
            form.add_error(None, "Invalid login credentials")
        else:
            login(request, user)
            mark_user_online(user)
            audit_event("login_success", request=request, actor=user)
            return redirect(get_dashboard_route(user))

    return render(request, "login.html", {"form": form, "error": form.first_error()})


@rate_limit("lawyer_login", limit=8, period=300)
def lawyer_login(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
        )
        if user is None or not is_lawyer_user(user):
            security_event("lawyer_login_failed", request=request, username=form.cleaned_data["username"])
            form.add_error(None, "Lawyer account not found or inactive")
        else:
            login(request, user)
            mark_user_online(user)
            audit_event("lawyer_login_success", request=request, actor=user)
            return redirect("lawyer_dashboard")

    return render(request, "lawyer_login.html", {"form": form, "error": form.first_error()})


@rate_limit("lawyer_register", limit=4, period=600)
def lawyer_register(request):
    form = LawyerRegistrationForm(request.POST or None, request.FILES or None)
    form.fields["category"].queryset = LawCategory.objects.all()

    if request.method == "POST" and form.is_valid():
        try:
            user, success_message = register_lawyer_user(form.cleaned_data)
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            send_verification_email(request, user)
            audit_event("lawyer_registered_for_review", request=request, actor=user)
            messages.success(request, success_message)
            return redirect("lawyer_login")

    return render(
        request,
        "lawyer_register.html",
        {
            "form": form,
            "categories": LawCategory.objects.all(),
            "error": form.first_error(),
        },
    )


@login_required
def logout_user(request):
    mark_user_offline(request.user)
    logout(request)
    return redirect("home")


@rate_limit("email_verification_link", limit=20, period=300, methods=("GET",))
def verify_email(request, uidb64, token):
    user = verify_email_token(uidb64, token, request=request)
    if user is None:
        messages.error(request, "Email verification link is invalid or expired.")
        return redirect("login")
    messages.success(request, "Email verified successfully.")
    return redirect(get_dashboard_route(user) if request.user == user else "login")


@login_required
@rate_limit("email_verification_resend", limit=3, period=900)
def resend_verification_email(request):
    if request.method != "POST":
        return redirect(get_dashboard_route(request.user))
    if request.user.profile.email_verified:
        messages.info(request, "Your email is already verified.")
        return redirect(get_dashboard_route(request.user))
    send_verification_email(request, request.user)
    messages.success(request, "Verification email sent. Check the console email backend in local development.")
    return redirect(get_dashboard_route(request.user))


class RateLimitedPasswordResetView(PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")

    def post(self, request, *args, **kwargs):
        try:
            consume_rate_limit(request, "password_reset", limit=4, period=900)
        except RateLimitExceeded as exc:
            security_event("password_reset_rate_limited", request=request)
            messages.error(request, str(exc))
            return render(request, self.template_name, {"form": self.get_form(), "error": str(exc)}, status=429)
        audit_event("password_reset_requested", request=request)
        return super().post(request, *args, **kwargs)
