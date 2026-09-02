from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import User
from accounts.permissions import IsSuperAdmin, IsSuperAdminOrTahsildar
from accounts.serializers import (
    ChangePasswordSerializer,
    ProfileSerializer,
    ResetPasswordSerializer,
    TahsildarSerializer,
    UserSerializer,
)
from audit.services import get_client_ip, log_action

UserModel = get_user_model()


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["taluka_id"] = user.taluka_id
        return token


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            username = request.data.get("username")
            user = UserModel.objects.filter(username=username).first()
            if user:
                log_action(
                    user=user,
                    action="LOGIN",
                    target_type="User",
                    target_id=user.pk,
                    taluka=user.taluka,
                    ip_address=get_client_ip(request),
                    metadata={"username": user.username},
                )
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        log_action(
            user=request.user,
            action="LOGOUT",
            target_type="User",
            target_id=request.user.pk,
            taluka=request.user.taluka,
            ip_address=get_client_ip(request),
        )
        return Response({"detail": "Logged out."})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ProfileSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        log_action(
            user=request.user,
            action="PASSWORD_RESET",
            target_type="User",
            target_id=request.user.pk,
            taluka=request.user.taluka,
            ip_address=get_client_ip(request),
            metadata={"self_service": True},
        )
        return Response({"detail": "Password changed."})


def scoped_users(user):
    qs = User.objects.select_related("taluka").all()
    if user.is_super_admin:
        return qs
    if user.is_tahsildar:
        return qs.filter(taluka=user.taluka)
    return qs.filter(pk=user.pk)


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return scoped_users(self.request.user)

    def get_permissions(self):
        if self.action in ("create", "destroy", "activate", "deactivate", "reset_password"):
            return [IsSuperAdminOrTahsildar()]
        return super().get_permissions()

    def perform_create(self, serializer):
        user = serializer.save()
        action_name = "TAHSILDAR_CREATED" if user.is_tahsildar else "USER_CREATED"
        log_action(
            user=self.request.user,
            action=action_name,
            target_type="User",
            target_id=user.pk,
            taluka=user.taluka,
            ip_address=get_client_ip(self.request),
            metadata={"username": user.username, "role": user.role},
        )

    def perform_update(self, serializer):
        user = serializer.save()
        metadata = {"username": user.username}
        action_name = "USER_UPDATED"
        if getattr(user, "_role_changed", False):
            action_name = "ROLE_CHANGED"
            metadata["role"] = user.role
        elif getattr(user, "_taluka_changed", False):
            action_name = "TALUKA_CHANGED"
            metadata["taluka_id"] = user.taluka_id
        if user.is_tahsildar and action_name == "USER_UPDATED":
            action_name = "TAHSILDAR_UPDATED"
        log_action(
            user=self.request.user,
            action=action_name,
            target_type="User",
            target_id=user.pk,
            taluka=user.taluka,
            ip_address=get_client_ip(self.request),
            metadata=metadata,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.user.is_tahsildar and not instance.is_taluka_user:
            raise PermissionDenied("Tahsildars can only deactivate Taluka users.")
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        log_action(
            user=request.user,
            action="USER_DELETED",
            target_type="User",
            target_id=instance.pk,
            taluka=instance.taluka,
            ip_address=get_client_ip(request),
            metadata={"username": instance.username, "soft_delete": True},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        instance = self.get_object()
        if request.user.is_tahsildar and not instance.is_taluka_user:
            raise PermissionDenied("Tahsildars can only activate Taluka users.")
        instance.is_active = True
        instance.save(update_fields=["is_active"])
        log_action(
            user=request.user,
            action="USER_ACTIVATED",
            target_type="User",
            target_id=instance.pk,
            taluka=instance.taluka,
            ip_address=get_client_ip(request),
        )
        return Response(UserSerializer(instance, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        instance = self.get_object()
        if request.user.is_tahsildar and not instance.is_taluka_user:
            raise PermissionDenied("Tahsildars can only deactivate Taluka users.")
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        action_name = "TAHSILDAR_DEACTIVATED" if instance.is_tahsildar else "USER_DEACTIVATED"
        log_action(
            user=request.user,
            action=action_name,
            target_type="User",
            target_id=instance.pk,
            taluka=instance.taluka,
            ip_address=get_client_ip(request),
        )
        return Response(UserSerializer(instance, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def reset_password(self, request, pk=None):
        instance = self.get_object()
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance.set_password(serializer.validated_data["new_password"])
        instance.save(update_fields=["password"])
        log_action(
            user=request.user,
            action="PASSWORD_RESET",
            target_type="User",
            target_id=instance.pk,
            taluka=instance.taluka,
            ip_address=get_client_ip(request),
            metadata={"username": instance.username},
        )
        return Response({"detail": "Password reset."})


class TahsildarViewSet(viewsets.ModelViewSet):
    serializer_class = TahsildarSerializer
    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        return User.objects.filter(role=User.Role.TAHSILDAR).select_related("taluka")

    def perform_create(self, serializer):
        user = serializer.save(role=User.Role.TAHSILDAR)
        log_action(
            user=self.request.user,
            action="TAHSILDAR_CREATED",
            target_type="User",
            target_id=user.pk,
            taluka=user.taluka,
            ip_address=get_client_ip(self.request),
            metadata={"username": user.username},
        )

    def perform_update(self, serializer):
        user = serializer.save(role=User.Role.TAHSILDAR)
        log_action(
            user=self.request.user,
            action="TAHSILDAR_UPDATED",
            target_type="User",
            target_id=user.pk,
            taluka=user.taluka,
            ip_address=get_client_ip(self.request),
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        log_action(
            user=request.user,
            action="TAHSILDAR_DEACTIVATED",
            target_type="User",
            target_id=instance.pk,
            taluka=instance.taluka,
            ip_address=get_client_ip(request),
            metadata={"soft_delete": True},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
