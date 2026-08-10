from rest_framework import serializers

from .models import BookingRequest, LSAProfile, Parent, Payment


class ParentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parent
        fields = ['id', 'name', 'email', 'phone', 'created_at']
        read_only_fields = ['id', 'created_at']


class LSAProfileSerializer(serializers.ModelSerializer):
    skills = serializers.SlugRelatedField(many=True, read_only=True, slug_field='name')

    class Meta:
        model = LSAProfile
        fields = ['id', 'name', 'skills', 'is_available', 'created_at']
        read_only_fields = ['id', 'created_at']


class BookingRequestSerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(source='parent', queryset=Parent.objects.all())
    lsa_id = serializers.PrimaryKeyRelatedField(source='lsa', queryset=LSAProfile.objects.all())

    class Meta:
        model = BookingRequest
        fields = ['id', 'parent_id', 'lsa_id', 'start_time', 'end_time', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']

    def validate(self, attrs):
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({'end_time': 'end_time must be after start_time.'})
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'booking', 'amount', 'status', 'provider_reference', 'created_at']
        read_only_fields = ['id', 'booking', 'status', 'created_at']


class PaymentWebhookSerializer(serializers.Serializer):
    booking_id = serializers.PrimaryKeyRelatedField(queryset=BookingRequest.objects.all())
    status = serializers.ChoiceField(choices=['success', 'failure'])
    amount = serializers.DecimalField(max_digits=8, decimal_places=2)
    provider_reference = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
