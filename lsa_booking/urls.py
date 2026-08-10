"""
URL configuration for lsa_booking project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from bookings.views import BookingCreateView, PaymentWebhookView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('bookings.urls')),
    path('api/payments/webhook/', PaymentWebhookView.as_view(), name='payment-webhook'),
    # Alias for the unversioned path named in the assignment's "Outcome" summary
    # section, which lists /api/bookings/ while the itemized task list specifies
    # /api/v1/bookings/. Both route to the same view so either is accepted.
    path('api/bookings/', BookingCreateView.as_view(), name='booking-create-unversioned'),
]
