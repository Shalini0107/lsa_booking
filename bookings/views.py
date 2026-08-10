import logging

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BookingRequest, LSAProfile, Payment
from .serializers import BookingRequestSerializer, LSAProfileSerializer, PaymentSerializer, PaymentWebhookSerializer
from .services.external_service import ExternalServiceError, verify_lsa_for_booking

logger = logging.getLogger(__name__)

ACTIVE_BOOKING_STATUSES = [BookingRequest.Status.PENDING, BookingRequest.Status.CONFIRMED]


class BookingCreateView(APIView):
    def post(self, request):
        serializer = BookingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lsa = serializer.validated_data['lsa']
        start_time = serializer.validated_data['start_time']
        end_time = serializer.validated_data['end_time']

        try:
            verify_lsa_for_booking(lsa, start_time, end_time)
        except ExternalServiceError:
            logger.warning('Booking rejected: verification service unavailable for lsa_id=%s', lsa.id)
            return Response(
                {'detail': 'Unable to verify LSA availability with the external verification service. Please try again.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        with transaction.atomic():
            locked_lsa = LSAProfile.objects.select_for_update().get(pk=lsa.pk)

            has_conflict = BookingRequest.objects.filter(
                lsa=locked_lsa,
                status__in=ACTIVE_BOOKING_STATUSES,
                start_time__lt=end_time,
                end_time__gt=start_time,
            ).exists()

            if has_conflict:
                return Response(
                    {'detail': 'This LSA already has a booking that overlaps the requested time range.'},
                    status=status.HTTP_409_CONFLICT,
                )

            booking = serializer.save()

        return Response(BookingRequestSerializer(booking).data, status=status.HTTP_201_CREATED)


class LSASearchView(APIView):
    def get(self, request):
        queryset = LSAProfile.objects.filter(is_available=True).prefetch_related('skills')

        skills_param = request.query_params.get('skills')
        if skills_param:
            skill_names = [name.strip() for name in skills_param.split(',') if name.strip()]
            if skill_names:
                queryset = queryset.filter(skills__name__in=skill_names).distinct()

        serializer = LSAProfileSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PaymentWebhookView(APIView):
    def post(self, request):
        serializer = PaymentWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        booking = serializer.validated_data['booking_id']
        event_status = serializer.validated_data['status']
        amount = serializer.validated_data['amount']
        provider_reference = serializer.validated_data['provider_reference']

        if event_status == 'success':
            payment_status = Payment.Status.SUCCEEDED
            booking_status = BookingRequest.Status.CONFIRMED
        else:
            payment_status = Payment.Status.FAILED
            booking_status = BookingRequest.Status.CANCELLED

        with transaction.atomic():
            payment, _ = Payment.objects.update_or_create(
                booking=booking,
                defaults={
                    'amount': amount,
                    'status': payment_status,
                    'provider_reference': provider_reference,
                },
            )
            booking.status = booking_status
            booking.save(update_fields=['status'])

        logger.info(
            'Payment webhook processed for booking_id=%s: event=%s -> booking_status=%s',
            booking.id, event_status, booking_status,
        )

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)
