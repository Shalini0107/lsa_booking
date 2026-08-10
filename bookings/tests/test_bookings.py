from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from bookings.models import BookingRequest, LSAProfile, Parent
from bookings.services.external_service import ExternalServiceError


class BookingCreateTests(TestCase):
    """Covers T-01, T-02, T-03, and the view-level half of T-06 (SRS Section 15)."""

    def setUp(self):
        self.client = APIClient()
        self.parent = Parent.objects.create(name='Jane Doe', email='jane@example.com')
        self.lsa = LSAProfile.objects.create(name='Alex Smith', is_available=True)
        self.url = reverse('booking-create')
        self.base_start = timezone.now() + timedelta(days=30)
        self.base_end = self.base_start + timedelta(hours=1)

        # Isolate booking logic from the real external call for every test in
        # this class; the external service itself is tested separately in
        # test_external_service.py.
        patcher = patch('bookings.views.verify_lsa_for_booking', return_value={'status': 'verified'})
        self.mock_verify = patcher.start()
        self.addCleanup(patcher.stop)

    def _payload(self, start=None, end=None, **overrides):
        payload = {
            'parent_id': self.parent.id,
            'lsa_id': self.lsa.id,
            'start_time': (start or self.base_start).isoformat(),
            'end_time': (end or self.base_end).isoformat(),
        }
        payload.update(overrides)
        return payload

    def test_valid_booking_is_created(self):
        # T-01
        response = self.client.post(self.url, self._payload(), format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BookingRequest.objects.count(), 1)
        booking = BookingRequest.objects.get()
        self.assertEqual(booking.parent_id, self.parent.id)
        self.assertEqual(booking.lsa_id, self.lsa.id)
        self.assertEqual(booking.status, BookingRequest.Status.PENDING)
        self.mock_verify.assert_called_once()

    def test_end_before_start_is_rejected(self):
        # T-02
        response = self.client.post(
            self.url,
            self._payload(start=self.base_end, end=self.base_start),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_missing_field_is_rejected(self):
        # T-02 (variant)
        payload = self._payload()
        del payload['lsa_id']

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_unknown_parent_is_rejected(self):
        # T-02 (variant): parent_id must reference an existing record
        response = self.client.post(self.url, self._payload(parent_id=99999), format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_overlapping_booking_is_rejected(self):
        # T-03
        BookingRequest.objects.create(
            parent=self.parent, lsa=self.lsa,
            start_time=self.base_start, end_time=self.base_end,
        )

        response = self.client.post(
            self.url,
            self._payload(
                start=self.base_start + timedelta(minutes=30),
                end=self.base_end + timedelta(minutes=30),
            ),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(BookingRequest.objects.count(), 1)

    def test_adjacent_non_overlapping_booking_is_accepted(self):
        # Boundary case for T-03: a slot starting exactly when the previous
        # one ends must not be treated as a conflict (half-open interval).
        BookingRequest.objects.create(
            parent=self.parent, lsa=self.lsa,
            start_time=self.base_start, end_time=self.base_end,
        )

        response = self.client.post(
            self.url,
            self._payload(start=self.base_end, end=self.base_end + timedelta(hours=1)),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BookingRequest.objects.count(), 2)

    def test_verification_failure_returns_502_and_creates_no_booking(self):
        # T-06 (view-level): a failed external verification must not crash
        # the request and must not leave a phantom booking behind.
        self.mock_verify.side_effect = ExternalServiceError('unreachable')

        response = self.client.post(self.url, self._payload(), format='json')

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(BookingRequest.objects.count(), 0)
