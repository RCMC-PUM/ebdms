import os
from django.urls import reverse
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

from django_otp.plugins.otp_totp.models import TOTPDevice


class AdminOTPEnforceMiddleware(MiddlewareMixin):
    def process_request(self, request):
        path = request.path

        # allow these paths always
        if (
            path.startswith("/otp/verify/")
            or path.startswith("/login/")
            or path.startswith("/logout/")
            or path.startswith("/jsi18n/")
            or path.startswith("/static/")
            or path.startswith("/otp_totp/totpdevice/")
        ):
            return None

        user = getattr(request, "user", None)

        # disable in DEBUG mode
        if os.environ.get("MFA").lower().strip() != "true":
            if user.is_staff:
                return None

        # allow admin FK lookups/autocomplete to work autocomplete_fields endpoint
        if path.startswith("/autocomplete/") and user.is_authenticated:
            return None

        # ignore non-staff (theoretical) users
        if not user or not user.is_authenticated or not user.is_staff:
            return None

        # ignore already verified users
        if hasattr(user, "is_verified") and user.is_verified():
            return None

        # If they have no confirmed device yet, push to enroll (works for users with permission)
        if not TOTPDevice.objects.filter(user=user, confirmed=True).exists():
            return redirect(reverse("admin:otp_totp_totpdevice_add"))

        # Otherwise, require OTP verification
        return redirect(reverse("admin-otp-verify"))
