from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from accounts.models import User
from talukas.models import Taluka


class UserSerializer(serializers.ModelSerializer):
    taluka_name = serializers.CharField(source="taluka.name", read_only=True)
    taluka_code = serializers.CharField(source="taluka.code", read_only=True)
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    taluka_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "phone",
            "role",
            "taluka",
            "taluka_id",
            "taluka_name",
            "taluka_code",
            "is_active",
            "created_at",
            "updated_at",
            "last_login",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "last_login"]
        extra_kwargs = {
            "taluka": {"required": False},
            "role": {"required": False},
        }

    def to_internal_value(self, data):
        if "taluka_id" in data and "taluka" not in data:
            mutable = data.copy() if hasattr(data, "copy") else dict(data)
            mutable["taluka"] = data.get("taluka_id")
            data = mutable
        return super().to_internal_value(data)

    def validate(self, attrs):
        request = self.context["request"]
        actor = request.user
        instance = self.instance
        incoming = getattr(self, "initial_data", {}) or {}

        if actor.is_taluka_user:
            if self.instance is None:
                raise PermissionDenied("Taluka users cannot create users.")
            forbidden = {"role", "taluka", "taluka_id", "is_active", "username"}
            if forbidden.intersection(set(incoming.keys())):
                raise PermissionDenied("You cannot change role, taluka, or privileged fields.")
            attrs.pop("role", None)
            attrs.pop("taluka", None)
            if instance and instance.pk != actor.pk:
                raise PermissionDenied("You can only update your own profile.")
            return attrs

        if actor.is_tahsildar:
            requested_taluka = attrs.get("taluka")
            raw_taluka = incoming.get("taluka", incoming.get("taluka_id", serializers.empty))
            if raw_taluka is not serializers.empty and raw_taluka not in (None, ""):
                try:
                    requested_id = int(getattr(raw_taluka, "pk", raw_taluka))
                except (TypeError, ValueError):
                    requested_id = None
                if requested_id is not None and requested_id != actor.taluka_id:
                    raise PermissionDenied("You cannot assign a user to another Taluka.")
            if requested_taluka and requested_taluka.pk != actor.taluka_id:
                raise PermissionDenied("You cannot assign a user to another Taluka.")

            if instance is None:
                attrs["role"] = User.Role.TALUKA_USER
                attrs["taluka"] = actor.taluka
            else:
                if instance.taluka_id != actor.taluka_id:
                    raise PermissionDenied("You cannot modify users from another Taluka.")
                if instance.is_tahsildar or instance.is_super_admin:
                    if "taluka" in incoming or "taluka_id" in incoming:
                        raise PermissionDenied("You cannot change your Taluka.")
                    if incoming.get("role") and incoming.get("role") != instance.role:
                        raise PermissionDenied("You cannot change roles.")
                    attrs.pop("taluka", None)
                    attrs.pop("role", None)
                else:
                    attrs["taluka"] = actor.taluka
                    if incoming.get("role") and incoming.get("role") != User.Role.TALUKA_USER:
                        raise PermissionDenied("You cannot promote users or create Tahsildars.")
                    attrs["role"] = User.Role.TALUKA_USER
            return attrs

        if actor.is_super_admin:
            role = attrs.get("role", getattr(instance, "role", User.Role.TALUKA_USER))
            taluka = attrs.get("taluka", getattr(instance, "taluka", None))
            if role == User.Role.SUPER_ADMIN:
                attrs["taluka"] = None
            elif role in (User.Role.TAHSILDAR, User.Role.TALUKA_USER) and taluka is None:
                raise serializers.ValidationError({"taluka": "Taluka is required for this role."})
            if role == User.Role.TAHSILDAR and taluka is not None:
                qs = User.objects.filter(
                    role=User.Role.TAHSILDAR, taluka=taluka, is_active=True
                )
                if instance:
                    qs = qs.exclude(pk=instance.pk)
                if qs.exists():
                    raise serializers.ValidationError(
                        {"taluka": "This Taluka already has an active primary Tahsildar."}
                    )
        return attrs

    def create(self, validated_data):
        validated_data.pop("taluka_id", None)
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "Password is required."})
        validate_password(password)
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        validated_data.pop("taluka_id", None)
        password = validated_data.pop("password", None)
        previous_role = instance.role
        previous_taluka_id = instance.taluka_id
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            validate_password(password, user=instance)
            instance.set_password(password)
        instance.save()
        instance._role_changed = previous_role != instance.role
        instance._taluka_changed = previous_taluka_id != instance.taluka_id
        return instance


class TahsildarSerializer(UserSerializer):
    def validate(self, attrs):
        request = self.context["request"]
        if not request.user.is_super_admin:
            raise PermissionDenied("Only Super Admin can manage Tahsildars.")
        attrs["role"] = User.Role.TAHSILDAR
        return super().validate(attrs)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["old_password"]):
            raise serializers.ValidationError({"old_password": "Incorrect password."})
        validate_password(attrs["new_password"], user=user)
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class ProfileSerializer(serializers.Serializer):
    """Serializer for /auth/me/ endpoint with permissions."""
    id = serializers.IntegerField()
    username = serializers.CharField()
    role = serializers.CharField()
    taluka = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    def get_taluka(self, obj):
        if obj.taluka:
            return {
                "id": obj.taluka.id,
                "name": obj.taluka.name,
                "code": obj.taluka.code,
            }
        return None

    def get_permissions(self, obj):
        """Return role-based permissions."""
        permissions = []

        if obj.is_taluka_user:
            permissions = [
                "view_own_records",
                "create_record",
                "edit_draft",
                "submit_record",
                "edit_correction_required",
            ]
        elif obj.is_tahsildar:
            permissions = [
                "view_taluka_records",
                "review_records",
                "approve_records",
                "request_correction",
                "forward_approved_records",
                "view_taluka_users",
            ]
        elif obj.is_super_admin:
            permissions = [
                "view_all_talukas",
                "view_all_records",
                "manage_users",
                "manage_tahsildars",
                "finalize_records",
                "view_audit_logs",
            ]

        return permissions
