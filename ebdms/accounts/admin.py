from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin

from django.core.exceptions import PermissionDenied
from reversion.admin import VersionAdmin
from unfold.admin import ModelAdmin


# --- Unfold + Reversion Admin Mixin ---
class UnfoldReversionAdmin(VersionAdmin, ModelAdmin):
    """
    Reversion views (history/recover/revision/compare) are accessible only to superusers.
    Staff can still use normal admin CRUD, but won't see or use reversion features.
    Status: experimental
    """

    def _reversion_allowed(self, request):
        return request.user.is_active and request.user.is_superuser

    # django-reversion admin views you want to block:
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
        return super().revision_view(request, object_id, version_id, extra_context=extra_context)


User = get_user_model()

# --- User ---
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin, UnfoldReversionAdmin):
    """
    Django UserAdmin + Unfold styling.
    """


# --- Group ---
try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(Group)
class GroupAdmin(DjangoGroupAdmin, UnfoldReversionAdmin):
    """
    Django GroupAdmin + Unfold styling.
    """
