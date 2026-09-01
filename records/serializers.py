from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from records.models import Record, RecordHistory, next_record_number
from talukas.models import Taluka


class RecordHistorySerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source="changed_by.username", read_only=True)
    
    class Meta:
        model = RecordHistory
        fields = [
            "id",
            "action",
            "changed_by",
            "changed_by_username",
            "changed_by_role",
            "old_value",
            "new_value",
            "comment",
            "timestamp",
        ]
        read_only_fields = fields


class RecordSerializer(serializers.ModelSerializer):
    taluka_name = serializers.CharField(source="taluka.name", read_only=True)
    taluka_code = serializers.CharField(source="taluka.code", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    updated_by_username = serializers.CharField(source="updated_by.username", read_only=True, default=None)
    reviewed_by_username = serializers.CharField(source="reviewed_by.username", read_only=True, allow_null=True)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True, allow_null=True)
    forwarded_by_username = serializers.CharField(source="forwarded_by.username", read_only=True, allow_null=True)
    finalized_by_username = serializers.CharField(source="finalized_by.username", read_only=True, allow_null=True)
    taluka_id = serializers.IntegerField(write_only=True, required=False)
    history = RecordHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Record
        fields = [
            "id",
            "taluka",
            "taluka_id",
            "taluka_name",
            "taluka_code",
            "created_by",
            "created_by_username",
            "updated_by",
            "updated_by_username",
            "record_number",
            "title",
            "description",
            "status",
            "is_active",
            "deleted_at",
            "created_at",
            "updated_at",
            # Workflow fields
            "reviewed_by",
            "reviewed_by_username",
            "reviewed_at",
            "review_comment",
            "approved_by",
            "approved_by_username",
            "approved_at",
            "forwarded_by",
            "forwarded_by_username",
            "forwarded_at",
            "finalized_by",
            "finalized_by_username",
            "finalized_at",
            "correction_comment",
            "history",
        ]
        extra_kwargs = {"taluka": {"required": False}}
        read_only_fields = [
            "id",
            "created_by",
            "updated_by",
            "record_number",
            "deleted_at",
            "created_at",
            "updated_at",
            "reviewed_by",
            "reviewed_at",
            "approved_by",
            "approved_at",
            "forwarded_by",
            "forwarded_at",
            "finalized_by",
            "finalized_at",
            "history",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        actor = request.user
        incoming = getattr(self, "initial_data", {}) or {}
        supplied = incoming.get("taluka_id", incoming.get("taluka", serializers.empty))

        if actor.is_super_admin:
            if self.instance is None:
                taluka = attrs.get("taluka")
                if supplied is not serializers.empty and supplied not in (None, ""):
                    taluka = Taluka.objects.filter(pk=supplied).first()
                    if not taluka:
                        raise serializers.ValidationError({"taluka": "Invalid Taluka."})
                if taluka is None:
                    raise serializers.ValidationError(
                        {"taluka": "Super Admin must specify taluka or taluka_id when creating a record."}
                    )
                attrs["taluka"] = taluka
            return attrs

        if supplied is not serializers.empty and supplied not in (None, ""):
            try:
                requested_id = int(getattr(supplied, "pk", supplied))
            except (TypeError, ValueError):
                requested_id = None
            if requested_id is not None and requested_id != actor.taluka_id:
                raise PermissionDenied("You cannot create or assign records to another Taluka.")

        attrs["taluka"] = actor.taluka
        if self.instance and self.instance.taluka_id != actor.taluka_id:
            raise PermissionDenied("You cannot modify records from another Taluka.")
        return attrs

    def create(self, validated_data):
        validated_data.pop("taluka_id", None)
        request = self.context["request"]
        taluka = validated_data["taluka"]
        validated_data["created_by"] = request.user
        validated_data["updated_by"] = request.user
        validated_data["record_number"] = next_record_number(taluka)
        # Default to DRAFT for new records
        validated_data.setdefault("status", Record.Status.DRAFT)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("taluka_id", None)
        validated_data.pop("taluka", None)
        validated_data["updated_by"] = self.context["request"].user
        return super().update(instance, validated_data)
