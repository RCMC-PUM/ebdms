from django_otp.admin import OTPAdminSite
from unfold.sites import UnfoldAdminSite


class OTPUnfoldAdminSite(OTPAdminSite, UnfoldAdminSite):
    pass
