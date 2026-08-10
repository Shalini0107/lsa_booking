import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ExternalServiceError(Exception):
    """Raised when the external verification service cannot confirm a booking."""


def verify_lsa_for_booking(lsa, start_time, end_time):
    """
    Calls a mock third-party verification service (e.g. a background-check /
    compliance provider) to confirm the LSA is cleared to take this booking.

    Raises ExternalServiceError for every failure mode - timeout, connection
    error, non-2xx response, or a malformed response - so callers only need
    to handle one exception type regardless of what went wrong inside
    `requests`.
    """
    url = settings.EXTERNAL_VERIFICATION_SERVICE_URL
    timeout = settings.EXTERNAL_VERIFICATION_SERVICE_TIMEOUT
    payload = {
        'lsa_id': lsa.id,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        logger.error('Verification service timed out for lsa_id=%s', lsa.id)
        raise ExternalServiceError('Verification service timed out.') from exc
    except requests.exceptions.RequestException as exc:
        logger.error('Verification service request failed for lsa_id=%s: %s', lsa.id, exc)
        raise ExternalServiceError('Verification service request failed.') from exc

    try:
        data = response.json()
    except ValueError as exc:
        logger.error('Verification service returned a non-JSON response for lsa_id=%s', lsa.id)
        raise ExternalServiceError('Verification service returned an invalid response.') from exc

    logger.info('Verification service confirmed lsa_id=%s (status=%s)', lsa.id, response.status_code)
    return data
