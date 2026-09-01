from django.urls import include, path
from rest_framework.routers import DefaultRouter

from records.views import RecordViewSet
from records.dashboard import DashboardViewSet

router = DefaultRouter()
router.register("records", RecordViewSet, basename="record")
router.register("dashboard", DashboardViewSet, basename="dashboard")

urlpatterns = [
    path("", include(router.urls)),
]
