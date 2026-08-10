from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from bookings.models import BookingRequest, LSAProfile, Parent, Payment


class PaymentWebhookTests(TestCase):
    """Covers the optional Payment/webhook stretch goal (SRS Section 4, 20)."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('payment-webhook')

        parent = Parent.objects.create(name='Jane Doe', email='jane@example.com')
        lsa = LSAProfile.objects.create(name='Alex Smith', is_available=True)
        start_time = timezone.now() + timedelta(days=30)
        self.booking = BookingRequest.objects.create(
            parent=parent, lsa=lsa,
            start_time=start_time, end_time=start_time + timedelta(hours=1),
        )

    def _payload(self, event_status, **overrides):
        payload = {
            'booking_id': self.booking.id,
            'status': event_status,
            'amount': '45.00',
            'provider_reference': 'mock-txn-123',
        }
        payload.update(overrides)
        return payload

    def test_success_event_confirms_booking_and_records_payment(self):
        response = self.client.post(self.url, self._payload('success'), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingRequest.Status.CONFIRMED)

        payment = Payment.objects.get(booking=self.booking)
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(payment.amount, Decimal('45.00'))
        self.assertEqual(payment.provider_reference, 'mock-txn-123')

    def test_failure_event_cancels_booking_and_records_payment(self):
        response = self.client.post(self.url, self._payload('failure'), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingRequest.Status.CANCELLED)

        payment = Payment.objects.get(booking=self.booking)
        self.assertEqual(payment.status, Payment.Status.FAILED)

    def test_unknown_booking_id_is_rejected(self):
        response = self.client.post(self.url, self._payload('success', booking_id=99999), format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 0)
