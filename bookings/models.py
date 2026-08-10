from django.db import models


class Parent(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class LSAProfile(models.Model):
    name = models.CharField(max_length=255)
    skills = models.ManyToManyField(Skill, related_name='lsa_profiles', blank=True)
    is_available = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class BookingRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'

    parent = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name='bookings')
    lsa = models.ForeignKey(LSAProfile, on_delete=models.CASCADE, related_name='bookings')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['lsa', 'start_time', 'end_time'], name='booking_lsa_time_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(start_time__lt=models.F('end_time')),
                name='booking_start_before_end',
            ),
        ]

    def __str__(self):
        return f'{self.parent} -> {self.lsa} ({self.start_time} to {self.end_time})'


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'

    booking = models.OneToOneField(BookingRequest, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider_reference = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Payment for booking {self.booking_id} ({self.status})'
