from datetime import timedelta
from unittest.mock import Mock, patch

import requests
from django.test import TestCase
from django.utils import timezone

from bookings.models import LSAProfile
from bookings.services.external_service import ExternalServiceError, verify_lsa_for_booking


class VerifyLsaForBookingTests(TestCase):
    """Covers T-05 and T-06 (SRS Section 15) directly against the service module.

    `requests.post` is mocked at the point of use
    (bookings.services.external_service.requests.post) so these tests never
    make a real network call.
    """

    def setUp(self):
        self.lsa = LSAProfile.objects.create(name='Alex Smith', is_available=True)
        self.start_time = timezone.now() + timedelta(days=1)
        self.end_time = self.start_time + timedelta(hours=1)

    @patch('bookings.services.external_service.requests.post')
    def test_success_returns_data_and_logs_info(self, mock_post):
        # T-05
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'status': 'verified'}
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with self.assertLogs('bookings.services.external_service', level='INFO') as logs:
            result = verify_lsa_for_booking(self.lsa, self.start_time, self.end_time)

        self.assertEqual(result, {'status': 'verified'})
        self.assertTrue(any('confirmed' in message for message in logs.output))

    @patch('bookings.services.external_service.requests.post')
    def test_timeout_raises_external_service_error_and_logs(self, mock_post):
        # T-06
        mock_post.side_effect = requests.exceptions.Timeout('timed out')

        with self.assertLogs('bookings.services.external_service', level='ERROR') as logs:
            with self.assertRaises(ExternalServiceError):
                verify_lsa_for_booking(self.lsa, self.start_time, self.end_time)

        self.assertTrue(any('timed out' in message for message in logs.output))

    @patch('bookings.services.external_service.requests.post')
    def test_connection_error_raises_external_service_error(self, mock_post):
        # T-06 (variant): a non-timeout network failure must also be handled.
        mock_post.side_effect = requests.exceptions.ConnectionError('connection refused')

        with self.assertRaises(ExternalServiceError):
            verify_lsa_for_booking(self.lsa, self.start_time, self.end_time)

    @patch('bookings.services.external_service.requests.post')
    def test_non_2xx_response_raises_external_service_error(self, mock_post):
        # T-06 (variant): a reachable service returning an error status
        # must be treated as a failure, not a silent success.
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError('500 Server Error')
        mock_post.return_value = mock_response

        with self.assertRaises(ExternalServiceError):
            verify_lsa_for_booking(self.lsa, self.start_time, self.end_time)

    @patch('bookings.services.external_service.requests.post')
    def test_invalid_json_response_raises_external_service_error(self, mock_post):
        # T-06 (variant): a 200 response with an unparseable body must not
        # be treated as a successful verification.
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError('not valid json')
        mock_post.return_value = mock_response

        with self.assertRaises(ExternalServiceError):
            verify_lsa_for_booking(self.lsa, self.start_time, self.end_time)
