import json
import secrets
from math import asin, cos, radians, sin, sqrt
from urllib import error, request

from django.conf import settings
from django.db import transaction

from .models import CreditTransaction, Job, Profile, WalletTopUp, XPEvent

DEFAULT_SIGNUP_CREDITS = 50
JOB_POST_CREDIT_COST = 2
APPLICATION_CREDIT_COST = 1
BOOST_VISIBILITY_CREDIT_COST = 3
FIXPOINT_PACKAGES = (
    {'code': 'starter', 'name': 'Starter Pack', 'naira_amount': 500, 'credits': 50},
    {'code': 'value', 'name': 'Value Pack', 'naira_amount': 1000, 'credits': 110},
    {'code': 'pro', 'name': 'Pro Pack', 'naira_amount': 2000, 'credits': 250},
)

LEVELS = (
    {
        'threshold': 0,
        'name': 'Starter',
        'badge': 'Start',
        'benefit': 'Visible on the board and eligible for entry-level jobs.',
    },
    {
        'threshold': 50,
        'name': 'Verified',
        'badge': 'Verified',
        'benefit': 'Priority visibility and stronger social proof.',
    },
    {
        'threshold': 150,
        'name': 'Trusted',
        'badge': 'Trusted',
        'benefit': 'Higher ranking weight and better shortlist odds.',
    },
    {
        'threshold': 500,
        'name': 'Elite',
        'badge': 'Elite',
        'benefit': 'Premium ranking and stronger repeat-customer visibility.',
    },
    {
        'threshold': 1500,
        'name': 'Elite Pro',
        'badge': 'Pro',
        'benefit': 'Top-tier exposure across the marketplace leaderboard.',
    },
)


def get_level_metadata(xp):
    current = LEVELS[0]
    for rank, level in enumerate(LEVELS):
        if xp >= level['threshold']:
            current = {**level, 'rank': rank}
    next_level = None
    for level in LEVELS:
        if level['threshold'] > xp:
            next_level = level
            break
    progress = 100
    if next_level:
        lower = current['threshold']
        span = next_level['threshold'] - lower
        progress = int(((xp - lower) / span) * 100) if span else 100
    return {**current, 'next_level': next_level, 'progress': max(0, min(progress, 100))}


def get_fixpoint_packages():
    return FIXPOINT_PACKAGES


def get_fixpoint_package(package_code):
    for package in FIXPOINT_PACKAGES:
        if package['code'] == package_code:
            return package
    raise ValueError('Invalid FixPoints package selected.')


def haversine_distance(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
    radius = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return radius * c


def _distance_component(worker, job):
    distance = haversine_distance(worker.latitude, worker.longitude, job.latitude, job.longitude)
    if distance is not None:
        return max(0, 1 - min(distance, 50) / 50), round(distance, 1)
    if worker.city and job.display_location and worker.city.lower() in job.display_location.lower():
        return 0.85, None
    return 0.45, None


def score_worker_for_job(worker, job):
    level_component = worker.level_rank / max(len(LEVELS) - 1, 1)
    rating_component = (worker.average_rating or 3.5) / 5
    response_component = max(0, 1 - min(worker.response_time_hours or 24, 24) / 24)
    distance_component, distance = _distance_component(worker, job)
    score = (
        (level_component * 0.4)
        + (rating_component * 0.3)
        + (response_component * 0.2)
        + (distance_component * 0.1)
    )
    category_text = f'{job.category} {job.description}'.lower()
    if any(skill.lower() in category_text for skill in worker.skill_list):
        score += 0.05
    return {
        'worker': worker,
        'score': round(score * 100, 2),
        'distance_km': distance,
        'rating': round(worker.average_rating or 0, 1),
    }


def recommend_workers(job, queryset=None, limit=6):
    workers = queryset or Profile.objects.filter(role=Profile.WORKER).select_related('user')
    if job.selected_worker_id:
        workers = workers.exclude(pk=job.selected_worker_id)
    ranked = [score_worker_for_job(worker, job) for worker in workers]
    ranked.sort(key=lambda item: item['score'], reverse=True)
    return ranked[:limit]


def _text_location_priority(city='', address='', location_text=''):
    city = (city or '').strip().lower()
    address = (address or '').strip().lower()
    location_text = (location_text or '').strip().lower()
    if address and address in location_text:
        return 0
    if city and city in location_text:
        return 1
    return 2


def worker_location_sort_key(reference_profile, worker):
    distance = haversine_distance(
        getattr(reference_profile, 'latitude', None),
        getattr(reference_profile, 'longitude', None),
        worker.latitude,
        worker.longitude,
    )
    if distance is not None:
        return (0, round(distance, 1))
    return (
        1 + _text_location_priority(
            getattr(reference_profile, 'city', ''),
            getattr(reference_profile, 'address', ''),
            f'{worker.city} {worker.address}',
        ),
        0,
    )


def job_location_sort_key(reference_profile, job):
    distance = haversine_distance(
        getattr(reference_profile, 'latitude', None),
        getattr(reference_profile, 'longitude', None),
        job.latitude,
        job.longitude,
    )
    if distance is not None:
        return (0, round(distance, 1))
    return (
        1 + _text_location_priority(
            getattr(reference_profile, 'city', ''),
            getattr(reference_profile, 'address', ''),
            job.display_location,
        ),
        0,
    )


def sort_workers_for_profile(reference_profile, queryset=None, limit=None):
    workers = list(queryset or Profile.objects.filter(role=Profile.WORKER).select_related('user'))
    if reference_profile:
        workers.sort(key=lambda worker: worker_location_sort_key(reference_profile, worker))
    if limit is not None:
        return workers[:limit]
    return workers


def sort_jobs_for_profile(reference_profile, queryset=None, limit=None):
    jobs = list(queryset or Job.objects.filter(status=Job.OPEN).select_related('customer__user', 'selected_worker__user'))
    if reference_profile:
        jobs.sort(key=lambda job: job_location_sort_key(reference_profile, job))
    if limit is not None:
        return jobs[:limit]
    return jobs


@transaction.atomic
def record_credit_change(profile, delta, reason, related_job=None):
    new_balance = profile.wallet_credits + delta
    if new_balance < 0:
        raise ValueError('Not enough FixPoints in your wallet to perform this action.')
    profile.wallet_credits = new_balance
    profile.save(update_fields=['wallet_credits', 'updated_at'])
    return CreditTransaction.objects.create(
        profile=profile,
        delta=delta,
        balance_after=new_balance,
        reason=reason,
        related_job=related_job,
    )


@transaction.atomic
def award_xp(profile, amount, reason, related_job=None):
    if amount <= 0:
        return None
    profile.xp += amount
    profile.save(update_fields=['xp', 'updated_at'])
    return XPEvent.objects.create(profile=profile, amount=amount, reason=reason, related_job=related_job)


@transaction.atomic
def complete_job(job):
    if job.status == Job.COMPLETED:
        return job

    job.status = Job.COMPLETED
    job.save(update_fields=['status', 'updated_at'])
    if job.selected_worker:
        worker = job.selected_worker
        worker.completed_jobs += 1
        worker.save(update_fields=['completed_jobs', 'updated_at'])
        accepted = job.applications.filter(worker=worker).first()
        if accepted:
            accepted.status = accepted.ACCEPTED
            accepted.save(update_fields=['status', 'updated_at'])
        award_xp(worker, 15, 'Completed a customer job', related_job=job)
    award_xp(job.customer, 5, 'Closed a job successfully', related_job=job)
    return job


def _paystack_headers():
    if not settings.PAYSTACK_SECRET_KEY:
        raise ValueError('Paystack is not configured yet. Add PAYSTACK_SECRET_KEY to your environment settings.')
    return {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
        'User-Agent': "Split"
    }


def _paystack_request(url, payload=None, method='GET'):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
    req = request.Request(url, data=data, method=method, headers=_paystack_headers())
    try:
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='ignore')
        try:
            parsed = json.loads(body)
            message = parsed.get('message', body)
        except json.JSONDecodeError:
            message = f'Paystack API error: {exc.code} {exc.reason}'
        raise ValueError(message) from exc
    except error.URLError as exc:
        raise ValueError(message) from exc


def initialize_paystack_topup(profile, package, callback_url):
    reference = f'PFX-TOPUP-{profile.user_id}-{secrets.token_hex(8).upper()}'
    topup = WalletTopUp.objects.create(
        profile=profile,
        reference=reference,
        package_name=package['name'],
        naira_amount=package['naira_amount'],
        credits=package['credits'],
    )
    response = _paystack_request(
        'https://api.paystack.co/transaction/initialize',
        payload={
            'email': profile.user.email,
            'amount': package['naira_amount'] * 100,
            'currency': 'NGN',
            'reference': reference,
            'callback_url': callback_url,
            'metadata': {
                'topup_reference': reference,
                'profile_id': profile.pk,
                'credits': package['credits'],
            },
        },
        method='POST',
    )
    data = response.get('data') or {}
    topup.paystack_access_code = data.get('access_code', '')
    topup.save(update_fields=['paystack_access_code', 'updated_at'])
    return topup, data.get('authorization_url')


@transaction.atomic
def verify_paystack_topup(reference):
    topup = WalletTopUp.objects.select_for_update().select_related('profile__user').get(reference=reference)
    response = _paystack_request(f'https://api.paystack.co/transaction/verify/{reference}')
    data = response.get('data') or {}
    transaction_status = data.get('status')
    paid_amount = int(data.get('amount') or 0)
    expected_amount = topup.naira_amount * 100

    if transaction_status != 'success' or paid_amount != expected_amount:
        topup.status = WalletTopUp.FAILED
        topup.paystack_transaction_id = str(data.get('id') or '')
        topup.save(update_fields=['status', 'paystack_transaction_id', 'updated_at'])
        raise ValueError('Payment was not successful, so no FixPoints were added.')

    topup.status = WalletTopUp.SUCCESS
    topup.paystack_transaction_id = str(data.get('id') or '')
    topup.save(update_fields=['status', 'paystack_transaction_id', 'updated_at'])

    if not topup.fulfilled:
        record_credit_change(
            topup.profile,
            topup.credits,
            f'Paystack top-up: {topup.package_name}',
        )
        topup.fulfilled = True
        topup.save(update_fields=['fulfilled', 'updated_at'])

    return topup
