from rest_framework.permissions import BasePermission, IsAuthenticated

class IsAccountActive(BasePermission):
    """
    The ultimate guard. Checks the database 'is_active' status on every request.
    """
    message = "This account has been deactivated."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active)

class IsSuperuser(IsAccountActive):
    def has_permission(self, request, view):
        if not super().has_permission(request, view): return False
        return getattr(request.user, 'role', None) == 'superuser'

class IsAdminOrSuperuser(IsAccountActive):
    def has_permission(self, request, view):
        if not super().has_permission(request, view): return False
        return getattr(request.user, 'role', None) in ['admin', 'superuser']