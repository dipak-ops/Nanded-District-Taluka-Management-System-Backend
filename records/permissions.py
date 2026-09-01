from rest_framework.permissions import BasePermission


class CanAccessRecord(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_super_admin:
            return True
        return obj.taluka_id == user.taluka_id


class CanEditRecord(BasePermission):
    """Check if user can edit a record based on workflow status and role."""
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Super admin can always edit
        if user.is_super_admin:
            return True
        
        # Only Taluka users can edit
        if not user.is_taluka_user:
            return False
        
        # Must be in same Taluka
        if obj.taluka_id != user.taluka_id:
            return False
        
        # Can only edit DRAFT or CORRECTION_REQUIRED records
        if obj.status not in [obj.Status.DRAFT, obj.Status.CORRECTION_REQUIRED]:
            return False
        
        # If CORRECTION_REQUIRED, must be the creator (or a user in the Taluka)
        if obj.status == obj.Status.CORRECTION_REQUIRED:
            return True
        
        # If DRAFT, can edit if it's their own record
        return obj.created_by_id == user.id


class CanSubmitRecord(BasePermission):
    """Check if user can submit a record."""
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_taluka_user:
            return False
        
        if obj.taluka_id != user.taluka_id:
            return False
        
        if obj.created_by_id != user.id:
            return False
        
        return obj.status in [obj.Status.DRAFT, obj.Status.CORRECTION_REQUIRED]


class CanReviewRecord(BasePermission):
    """Check if user can review a record."""
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_tahsildar:
            return False
        
        if obj.taluka_id != user.taluka_id:
            return False
        
        return obj.status == obj.Status.SUBMITTED


class CanApproveRecord(BasePermission):
    """Check if user can approve a record."""
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_tahsildar:
            return False
        
        if obj.taluka_id != user.taluka_id:
            return False
        
        return obj.status == obj.Status.UNDER_REVIEW


class CanForwardRecord(BasePermission):
    """Check if user can forward a record."""
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_tahsildar:
            return False
        
        if obj.taluka_id != user.taluka_id:
            return False
        
        return obj.status == obj.Status.APPROVED


class CanFinalizeRecord(BasePermission):
    """Check if user can finalize a record."""
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_super_admin:
            return False
        
        return obj.status == obj.Status.FORWARDED
