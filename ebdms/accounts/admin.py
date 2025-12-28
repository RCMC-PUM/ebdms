from django.db import models
from django.contrib import admin

from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.core.exceptions import PermissionDenied

from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from unfold.admin import ModelAdmin

from unfold.contrib.forms.widgets import WysiwygWidget
from reversion.admin import VersionAdmin

from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_totp.admin import TOTPDeviceAdmin


class UnfoldReversionAdmin(VersionAdmin, ModelAdmin):
    formfield_overrides = {models.TextField: {"widget": WysiwygWidget}}

    def _reversion_allowed(self, request):
        return request.user.is_active and request.user.is_superuser

    def history_view(self, request, object_id, extra_context=None):
        if not self._reversion_allowed(request):
            raise PermissionDenied
        return super().history_view(request, object_id, extra_context=extra_context)

    def recoverlist_view(self, request, extra_context=None):
        if not self._reversion_allowed(request):
            raise PermissionDenied
        return super().recoverlist_view(request, extra_context=extra_context)

    def recover_view(self, request, version_id, extra_context=None):
        if not self._reversion_allowed(request):
            raise PermissionDenied
        return super().recover_view(request, version_id, extra_context=extra_context)

    def revision_view(self, request, object_id, version_id, extra_context=None):
        if not self._reversion_allowed(request):
            raise PermissionDenied
        return super().revision_view(request, object_id, extra_context=extra_context)


User = get_user_model()

# ---- unregister defaults (Django auth registers these automatically) ----
for model in (User, Group, TOTPDevice):
    try:
        admin.site.unregister(model)
    except admin.sites.NotRegistered:
        pass


# ---- register Unfold + Reversion versions ----
class UserAdmin(DjangoUserAdmin, UnfoldReversionAdmin):
    # Forms loaded from `unfold.forms`
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


class GroupAdmin(DjangoGroupAdmin, UnfoldReversionAdmin):
    pass


admin.site.register(User, UserAdmin)
admin.site.register(Group, GroupAdmin)


# ---- TOTP devices ----
class MyTOTPDeviceAdmin(TOTPDeviceAdmin, UnfoldReversionAdmin):
    pass


admin.site.register(TOTPDevice, MyTOTPDeviceAdmin)
