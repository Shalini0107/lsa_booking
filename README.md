**Shalini Hariharan** — shalinih001@gmail.com

# LSA Service Booking Module

Backend prototype for HabotConnect's LSA (Learning Support Assistant) booking platform — built for the HabotConnect Python Backend Developer hiring project. It exposes REST APIs to create bookings between Parents and LSAs, search available LSAs by skill, and process mock payment events via a webhook.

## Overview

Parents book time with LSAs for children with learning difficulties. This module owns three things:

1. Taking a booking request, validating it, checking it against the assigned LSA for external verification, and rejecting any request that overlaps an existing booking for that LSA.
2. Letting a client search for available LSAs, filtered by skill, without an N+1 query per LSA.
3. Accepting a mock payment gateway webhook and transitioning the linked booking's status accordingly.

## Features

- `Parent`, `LSA_Profile` (with a `Skill` many-to-many), `Booking_Request`, and `Payment` models — normalized, indexed, migrated.
- `POST /api/v1/bookings/` — create a booking with payload validation and race-safe double-booking prevention.
- `GET /api/v1/lsas/search/` — search available LSAs by skill, N+1-safe.
- `POST /api/payments/webhook/` — mock payment event ingestion that confirms or cancels the linked booking.
- Mock third-party verification call (via `requests`) on every booking attempt, with timeout/exception handling and logging.
- 19 automated tests (`unittest`, via Django's test runner) covering success, validation failure, overlap, search, and external-service failure paths.
- GitHub Actions CI running the full suite against a real MySQL service container on every push.

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.10 |
| Framework | Django 5.2 + Django REST Framework |
| Database | MySQL 8.0 |
| HTTP client | `requests` (mock external service) |
| Testing | Django's `unittest`-based `TestCase` |
| CI | GitHub Actions |

## Project Structure

```
lsa_booking/
├── manage.py
├── requirements.txt
├── .env                          # local config, not committed
├── .github/workflows/ci.yml      # CI: install deps, run tests
├── lsa_booking/                  # project settings
│   ├── settings.py
│   └── urls.py                   # project-level routes (webhook, /api/bookings/ alias)
└── bookings/                     # the app
    ├── models.py                 # Parent, Skill, LSAProfile, BookingRequest, Payment
    ├── serializers.py
    ├── views.py                  # BookingCreateView, LSASearchView, PaymentWebhookView
    ├── urls.py                   # /api/v1/ routes
    ├── services/
    │   └── external_service.py   # mock verification call, isolated from the view
    ├── migrations/
    └── tests/
        ├── test_bookings.py
        ├── test_search.py
        ├── test_external_service.py
        └── test_payments.py
```

## Setup Instructions

### 1. Create and activate a virtual environment

```
python -m venv venv
```

Windows:
```
venv\Scripts\activate
```
macOS/Linux:
```
source venv/bin/activate
```

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Configure `.env`

Create a `.env` file in the project root:

```
DB_NAME=lsa_booking
DB_USER=lsa_booking_user
DB_PASSWORD= YOUR DB PASSWORD
DB_HOST=localhost
DB_PORT=3306
EXTERNAL_VERIFICATION_SERVICE_URL=https://httpbin.org/post
EXTERNAL_VERIFICATION_SERVICE_TIMEOUT=5
```

The last two are optional — they default to the values shown above if omitted.

### 4. Create the MySQL database and user

Connect as an admin/root MySQL user and run:

```sql
CREATE DATABASE IF NOT EXISTS lsa_booking CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'lsa_booking_user'@'localhost' IDENTIFIED BY 'changeme';
GRANT ALL PRIVILEGES ON lsa_booking.* TO 'lsa_booking_user'@'localhost';
FLUSH PRIVILEGES;
```

To run the automated test suite, also grant privileges on the test database Django creates automatically (`test_` + `DB_NAME`):

```sql
GRANT ALL PRIVILEGES ON test_lsa_booking.* TO 'lsa_booking_user'@'localhost';
FLUSH PRIVILEGES;
```

### 5. Run migrations

```
python manage.py migrate
```

### 6. Run the server

```
python manage.py runserver
```

The API is now available at `http://127.0.0.1:8000/`.

## API Endpoints

### `POST /api/v1/bookings/`

Creates a booking. Also available at `POST /api/bookings/` — see [Path decision](#apibookings-vs-apiv1bookings) below.

**Request**
```json
{
  "parent_id": 1,
  "lsa_id": 1,
  "start_time": "2026-09-01T10:00:00Z",
  "end_time": "2026-09-01T11:00:00Z"
}
```

**Response — 201 Created**
```json
{
  "id": 1,
  "parent_id": 1,
  "lsa_id": 1,
  "start_time": "2026-09-01T10:00:00Z",
  "end_time": "2026-09-01T11:00:00Z",
  "status": "pending",
  "created_at": "2026-08-10T16:34:41.698016Z"
}
```

**Failure responses**
- `400 Bad Request` — invalid payload (missing field, `end_time` before `start_time`, unknown `parent_id`/`lsa_id`):
  ```json
  {"end_time": ["end_time must be after start_time."]}
  ```
- `409 Conflict` — the LSA already has a booking overlapping the requested time range:
  ```json
  {"detail": "This LSA already has a booking that overlaps the requested time range."}
  ```
- `502 Bad Gateway` — the mock external verification service failed or timed out:
  ```json
  {"detail": "Unable to verify LSA availability with the external verification service. Please try again."}
  ```

### `GET /api/v1/lsas/search/`

Searches available LSAs, optionally filtered by skill.

**Request**
```
GET /api/v1/lsas/search/?skills=Dyslexia
```

**Response — 200 OK**
```json
[
  {
    "id": 1,
    "name": "Alex Smith",
    "skills": ["Autism Support", "Dyslexia"],
    "is_available": true,
    "created_at": "2026-08-10T16:33:46.238862Z"
  }
]
```

`skills` accepts a comma-separated list (`?skills=Dyslexia,Autism Support`). Omitting it returns all available LSAs. Only LSAs with `is_available=true` are ever returned.

### `POST /api/payments/webhook/` (stretch goal)

Accepts a mock payment event and transitions the linked booking.

**Request**
```json
{
  "booking_id": 1,
  "status": "success",
  "amount": "45.00",
  "provider_reference": "mock-txn-abc"
}
```

**Response — 200 OK**
```json
{
  "id": 1,
  "booking": 1,
  "amount": "45.00",
  "status": "succeeded",
  "provider_reference": "mock-txn-abc",
  "created_at": "2026-08-10T17:23:42.385021Z"
}
```

`status` is `"success"` or `"failure"` — see [Payment/webhook stretch goal](#paymentwebhook-stretch-goal) for how each maps to booking state.

## Testing Instructions

Run the full suite:

```
python manage.py test bookings
```

19 tests across four files:

| File | Covers |
|---|---|
| `test_bookings.py` | Valid booking (201), invalid payload variants (400), overlap rejection (409), adjacent non-overlap (201), verification failure (502) |
| `test_search.py` | Skill filter, no filter, unmatched skill, N+1 query-count assertion |
| `test_external_service.py` | Mock service success, timeout, connection error, non-2xx response, malformed JSON — all mocked via `unittest.mock.patch`, no real network calls |
| `test_payments.py` | Webhook success → booking confirmed, webhook failure → booking cancelled, unknown `booking_id` rejected |

The test runner creates and destroys a real `test_lsa_booking` MySQL database each run (see Setup step 4) — there is no SQLite substitution.

## Query Optimization: the N+1 Problem

`GET /api/v1/lsas/search/` returns LSAs together with their skills (a many-to-many relationship). Naively, fetching N matching LSAs and then looping over each to read `lsa.skills.all()` issues 1 query for the LSAs plus N more — one per LSA — for a total of N+1 queries. At 50 matching LSAs, that's 51 round trips for what should be a single search.

The fix, in `LSASearchView`:

```python
queryset = LSAProfile.objects.filter(is_available=True).prefetch_related('skills')
```

`prefetch_related('skills')` issues exactly **2** queries total, regardless of how many LSAs match: one `SELECT` for the `LSAProfile` rows, and one `SELECT ... WHERE lsa_id IN (...)` that fetches every matching LSA's skills in a single batch. Django then stitches the results together in Python. `LSAProfileSerializer` reads `skills` through a `SlugRelatedField(read_only=True)`, which only touches the already-prefetched in-memory objects — it can't accidentally reintroduce a per-instance query.

This is verified by `test_search_is_n_plus_one_safe` in `test_search.py`, which creates 5 additional matching LSAs and asserts the request still executes in exactly 2 queries via `assertNumQueries(2)`.

## Architecture: MVC vs. MVT

Django follows **MVT (Model-View-Template)**, not MVC, though the two map onto each other closely:

| MVC concept | MVT equivalent here | Role in this project |
|---|---|---|
| Model | Model (`bookings/models.py`) | `Parent`, `LSAProfile`, `Skill`, `BookingRequest`, `Payment` — the only layer that talks to the database, via the Django ORM. |
| Controller | View (`bookings/views.py`) | `BookingCreateView`, `LSASearchView`, `PaymentWebhookView` — DRF `APIView` subclasses that receive the HTTP request, orchestrate validation/business logic/persistence, and return a `Response`. |
| View (rendering) | Template — replaced by the Serializer (`bookings/serializers.py`) | This is a JSON API with no HTML templates. DRF serializers take over the "presentation" role: they render model instances to JSON and, on the way in, validate and parse request payloads. |

The practical difference from classic MVC is where "the controller's" responsibilities land: in MVT, the **View** class is closer to MVC's Controller (it orchestrates), while what MVC calls the "View" (the presentation layer) is handled by the **Serializer**, not a template — there's no server-rendered page in this project, just JSON in and JSON out.

Request flow for `POST /api/v1/bookings/`:

```
Client
  → URL router (lsa_booking/urls.py, bookings/urls.py)
  → BookingCreateView (view/controller)
  → BookingRequestSerializer (validation + JSON parsing)
  → verify_lsa_for_booking() (external service call, isolated in services/)
  → BookingRequest ORM model (persistence, inside an atomic transaction)
  → BookingRequestSerializer (response rendering)
  → Client (JSON response)
```

Business logic (the overlap check, the row lock, the external-service call) is kept in the view rather than the model or serializer, so the model stays a thin data definition and the serializer stays focused on shape/field-level validation.

## Double-Booking Prevention

Two requests to book the same LSA for overlapping times must not both succeed, even if they arrive at almost the same instant. `BookingCreateView` handles this with a locked-row + transaction pattern rather than a plain "check, then insert":

```python
with transaction.atomic():
    locked_lsa = LSAProfile.objects.select_for_update().get(pk=lsa.pk)

    has_conflict = BookingRequest.objects.filter(
        lsa=locked_lsa,
        status__in=[BookingRequest.Status.PENDING, BookingRequest.Status.CONFIRMED],
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).exists()

    if has_conflict:
        return Response({...}, status=409)

    booking = serializer.save()
```

**Why lock the LSA row, not the booking rows:** for a genuinely free time slot, there's no existing `BookingRequest` row to lock — nothing exists yet to prevent a second concurrent request from reading the same "no conflict" result before either commits. Instead, `select_for_update()` locks the **`LSAProfile`** row itself. That serializes every booking attempt against a given LSA: a second concurrent request for the same LSA blocks at `select_for_update()` until the first transaction commits (or rolls back), then re-runs its own conflict check against the now-up-to-date data. This is deliberately the simpler, easier-to-verify design compared to relying on InnoDB's implicit gap-locking behavior over an empty query range.

**Overlap rule:** `start_time__lt=end_time AND end_time__gt=start_time` is a half-open interval overlap test — two ranges intersect if each starts before the other ends. A booking ending exactly when another starts is *not* a conflict (verified by `test_adjacent_non_overlapping_booking_is_accepted`). Only `pending`/`confirmed` bookings block a slot — a `cancelled` booking doesn't (an assumption, see below).

**Defense in depth:** the database also enforces `CHECK (start_time < end_time)` at the schema level (`BookingRequest.Meta.constraints`), so a malformed row can't exist even if application-level validation is ever bypassed.

## Payment/Webhook Stretch Goal

The original assignment document is internally inconsistent about scope: the "What Will Be the Outcome" summary section lists a `Payment` entity and a `POST /api/payments/webhook/` endpoint, but the itemized "You Are Expected To Do" task list — which enumerates the actual graded work — only names 3 entities and 2 endpoints, with no webhook mentioned at all.

I built it anyway, for two reasons: it appears as a named deliverable in the document's own "Outcome" section (not purely invented), and it's a small, self-contained addition once the core booking flow exists. It was **not** treated as a prerequisite for the core deliverables — the booking and search endpoints, double-booking prevention, and N+1 optimization were all built and tested first, independent of this feature.

**Design**: `Payment` is a `OneToOneField` to `BookingRequest` — at most one payment record per booking, enforced at the database level. `PaymentWebhookView` accepts a mock event (`{booking_id, status, amount, provider_reference}`) and:
- `status: "success"` → `Payment.status = succeeded`, `BookingRequest.status = confirmed`
- `status: "failure"` → `Payment.status = failed`, `BookingRequest.status = cancelled`

It uses `Payment.objects.update_or_create(booking=booking, ...)` rather than `create()`, so a retried webhook event for the same booking updates the existing record instead of crashing on the `OneToOneField`'s uniqueness constraint — real payment gateways do retry on timeout, so this needed to be idempotent by design, not just by luck.

## `/api/bookings/` vs `/api/v1/bookings/`

The assignment document names this endpoint two different ways in two places: the "Outcome" section says `/api/bookings/`, while the itemized task list explicitly says `POST /api/v1/bookings/`. Rather than guess which one a grader might actually call, both paths are wired to the same `BookingCreateView`:

```python
urlpatterns = [
    ...
    path('api/v1/', include('bookings.urls')),       # /api/v1/bookings/
    path('api/bookings/', BookingCreateView.as_view()),  # alias
]
```

`/api/v1/bookings/` is treated as the primary, versioned path (matching DRF/REST convention and the more detailed itemized instruction); `/api/bookings/` is a thin alias with no duplicated logic, so there's nothing to keep in sync.

## Key Assumptions

The assignment leaves several details unspecified. Where that happened, I made an explicit, reasonable choice rather than blocking on it:

- **No authentication** on any endpoint — not mentioned anywhere in the assignment; adding it would be scope creep for a time-boxed task.
- **"Available" LSA** = `is_available` boolean flag, not a computed absence of active bookings.
- **Overlap rule** = any intersection of `[start_time, end_time)` ranges (half-open interval); adjacent, non-overlapping bookings are allowed.
- **Cancelled bookings don't block a time slot** — the overlap check only considers `pending`/`confirmed` bookings.
- **Mock external service** = a verification service (not a payment gateway), specifically to avoid conflating it with the separate, genuinely optional `Payment`/webhook feature.
- **`FK on_delete=CASCADE`** for `Booking_Request → Parent/LSA_Profile` — deleting a parent or LSA deletes their bookings, chosen for simplicity over `PROTECT`.
- **Booking `status` is not client-settable** at creation — it always starts `pending`; only the webhook (or future admin action) transitions it.
- **SQLite was not substituted for MySQL** anywhere, including CI — the assignment allows either database, and the project's actual `.env`/`settings.py` were already wired to MySQL from the start, so that was treated as the real target throughout, including in the GitHub Actions service container.

## Future Improvements

- Authentication/authorization on all endpoints (currently explicitly out of scope).
- Pagination on `GET /api/v1/lsas/search/` for large result sets.
- A `PATCH`/cancel endpoint for parents to cancel their own bookings directly, rather than only via the payment webhook.
- Webhook signature verification (HMAC) to authenticate that events genuinely originate from the payment provider, rather than accepting any POST body.
- Replace the `httpbin.org` placeholder verification URL with a real vendor integration when one is chosen.
