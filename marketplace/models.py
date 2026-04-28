from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg
from django.urls import reverse


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Profile(TimeStampedModel):
    CUSTOMER = 'customer'
    WORKER = 'worker'
    ROLE_CHOICES = (
        (CUSTOMER, 'Customer'),
        (WORKER, 'Worker'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=CUSTOMER)
    phone = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    bio = models.TextField(blank=True)
    skills = models.CharField(max_length=255, blank=True, help_text='Comma-separated skills')
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    response_time_hours = models.PositiveSmallIntegerField(default=6)
    wallet_credits = models.PositiveIntegerField(default=0)
    xp = models.PositiveIntegerField(default=0)
    completed_jobs = models.PositiveIntegerField(default=0)
    jobs_posted = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ('-xp', '-completed_jobs', 'user__username')

    def __str__(self):
        return f'{self.display_name} ({self.get_role_display()})'

    @property
    def display_name(self):
        full_name = self.user.get_full_name().strip()
        return full_name or self.user.username

    @property
    def average_rating(self):
        return self.received_reviews.aggregate(score=Avg('rating')).get('score') or 0

    @property
    def skill_list(self):
        return [skill.strip() for skill in self.skills.split(',') if skill.strip()]

    @property
    def level_meta(self):
        from .services import get_level_metadata

        return get_level_metadata(self.xp)

    @property
    def level_name(self):
        return self.level_meta['name']

    @property
    def level_badge(self):
        return self.level_meta['badge']

    @property
    def level_rank(self):
        return self.level_meta['rank']

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None


class Job(TimeStampedModel):
    OPEN = 'open'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (OPEN, 'Open'),
        (IN_PROGRESS, 'In Progress'),
        (COMPLETED, 'Completed'),
        (CANCELLED, 'Cancelled'),
    )

    NORMAL = 'normal'
    PRIORITY = 'priority'
    EMERGENCY = 'emergency'
    URGENCY_CHOICES = (
        (NORMAL, 'Normal'),
        (PRIORITY, 'Priority'),
        (EMERGENCY, 'Emergency'),
    )
    CATEGORY_CHOICES = (
        ('Plumbing', 'Plumbing'),
        ('Electrical', 'Electrical'),
        ('Cleaning', 'Cleaning'),
        ('Painting', 'Painting'),
        ('Carpentry', 'Carpentry'),
        ('Appliance Repair', 'Appliance Repair'),
        ('General Maintenance', 'General Maintenance'),
    )

    category = models.CharField(
        max_length=80,
        choices=CATEGORY_CHOICES,
    )
    customer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='jobs')
    selected_worker = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        related_name='assigned_jobs',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=150)
    description = models.TextField()
    location_label = models.CharField(max_length=150, blank=True)
    location_address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    budget_min = models.DecimalField(max_digits=10, decimal_places=2)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2)
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default=NORMAL)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN)
    credits_spent = models.PositiveIntegerField(default=2)
    is_boosted = models.BooleanField(default=False)
    boost_credits_spent = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('-is_boosted', '-created_at')

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('job-detail', kwargs={'pk': self.pk})

    @property
    def is_open(self):
        return self.status == self.OPEN

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def display_location(self):
        if self.location_label and self.location_address:
            return f'{self.location_label}, {self.location_address}'
        return self.location_label or self.location_address or self.customer.city or 'Flexible'


class JobApplication(TimeStampedModel):
    PENDING = 'pending'
    SHORTLISTED = 'shortlisted'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    WITHDRAWN = 'withdrawn'
    STATUS_CHOICES = (
        (PENDING, 'Pending'),
        (SHORTLISTED, 'Shortlisted'),
        (ACCEPTED, 'Accepted'),
        (REJECTED, 'Rejected'),
        (WITHDRAWN, 'Withdrawn'),
    )

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    worker = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='applications')
    pitch = models.TextField()
    proposed_price = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_days = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    credits_spent = models.PositiveIntegerField(default=1)
    match_score_snapshot = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        ordering = ('-match_score_snapshot', '-created_at')
        constraints = [
            models.UniqueConstraint(fields=('job', 'worker'), name='unique_worker_application')
        ]

    def __str__(self):
        return f'{self.worker.display_name} -> {self.job.title}'


class Review(TimeStampedModel):
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='review')
    reviewer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='authored_reviews')
    reviewee = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='received_reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.job.title} - {self.rating}/5'


class CreditTransaction(TimeStampedModel):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='credit_transactions')
    delta = models.IntegerField()
    balance_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=255)
    related_job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name='credit_events')

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.profile.display_name}: {self.delta:+} credits'


class WalletTopUp(TimeStampedModel):
    PENDING = 'pending'
    SUCCESS = 'success'
    FAILED = 'failed'
    STATUS_CHOICES = (
        (PENDING, 'Pending'),
        (SUCCESS, 'Success'),
        (FAILED, 'Failed'),
    )

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='wallet_topups')
    reference = models.CharField(max_length=100, unique=True)
    package_name = models.CharField(max_length=120)
    naira_amount = models.PositiveIntegerField()
    credits = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    paystack_access_code = models.CharField(max_length=120, blank=True)
    paystack_transaction_id = models.CharField(max_length=120, blank=True)
    fulfilled = models.BooleanField(default=False)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.profile.display_name}: {self.package_name} ({self.reference})'


class XPEvent(TimeStampedModel):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='xp_events')
    amount = models.PositiveIntegerField()
    reason = models.CharField(max_length=255)
    related_job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name='xp_events')

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.profile.display_name}: +{self.amount} XP'
