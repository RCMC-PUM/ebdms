from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice


class OTPVerifyForm(forms.Form):
    token = forms.CharField(
        max_length=6,
        min_length=6,
        strip=True,
        widget=forms.TextInput(
            attrs={"autocomplete": "one-time-code", "inputmode": "numeric"}
        ),
    )


@staff_member_required
@require_http_methods(["GET", "POST"])
def admin_otp_verify(request):
    # already verified -> go to admin index (root)
    if hasattr(request.user, "is_verified") and request.user.is_verified():
        return redirect("/")

    qs = TOTPDevice.objects.filter(user=request.user, confirmed=True)

    if not qs.exists():
        messages.warning(request, "No confirmed TOTP device. Add one to continue.")
        # IMPORTANT: app_label for TOTPDevice is otp_totp
        return redirect(reverse("admin:otp_totp_totpdevice_add"))

    form = OTPVerifyForm(request.POST or None)
    next_url = request.GET.get("next") or request.POST.get("next") or "/"

    if request.method == "POST" and form.is_valid():
        token = form.cleaned_data["token"]

        for device in qs:
            if device.verify_token(token):
                otp_login(request, device)  # marks session as verified
                return redirect(next_url)

        form.add_error("token", "Invalid code. Try again.")

    return render(
        request,
        "admin/mfa.html",
        {"form": form, "next": next_url, "title": "Two-factor verification"},
    )
