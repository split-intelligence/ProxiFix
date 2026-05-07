from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import ApplicationForm, JobForm, ProfileForm, RegistrationForm, ReviewForm, WalletTopUpForm
from .models import Job, JobApplication, Profile
from .services import (
    APPLICATION_CREDIT_COST,
    BOOST_VISIBILITY_CREDIT_COST,
    JOB_POST_CREDIT_COST,
    award_xp,
    complete_job,
    get_fixpoint_package,
    get_fixpoint_packages,
    get_level_metadata,
    initialize_paystack_topup,
    record_credit_change,
    recommend_workers,
    sort_jobs_for_profile,
    sort_workers_for_profile,
    verify_paystack_topup,
)


def get_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user, defaults={'role': Profile.CUSTOMER})
    return profile


def ensure_role(request, *roles):
    profile = get_profile(request.user)
    if profile.role not in roles:
        messages.error(request, 'That action is only available for the right account type.')
        return None
    return profile


def home(request):
    featured_workers = Profile.objects.filter(role=Profile.WORKER).select_related('user')[:6]
    open_jobs = Job.objects.filter(status=Job.OPEN).select_related('customer__user')[:6]
    level_preview = [get_level_metadata(points) for points in (0, 50, 150, 500, 1500)]
    return render(
        request,
        'marketplace/home.html',
        {
            'featured_workers': featured_workers,
            'open_jobs': open_jobs,
            'level_preview': level_preview,
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Your ProxiFix account is live. We added 50 welcome FixPoints to your wallet, and you can top up anytime.')
        return redirect('dashboard')
    return render(request, 'marketplace/register.html', {'form': form})


@login_required
def dashboard(request):
    profile = get_profile(request.user)
    context = {'profile': profile}

    if profile.role == Profile.CUSTOMER:
        jobs = (
            Job.objects.filter(customer=profile)
            .select_related('selected_worker__user')
            .prefetch_related('applications__worker__user')
        )
        context.update(
            {
                'jobs': jobs[:5],
                'open_count': jobs.filter(status=Job.OPEN).count(),
                'completed_count': jobs.filter(status=Job.COMPLETED).count(),
                'applications_received': JobApplication.objects.filter(job__customer=profile).count(),
                'recommended_workers': sort_workers_for_profile(
                    profile,
                    Profile.objects.filter(role=Profile.WORKER).select_related('user'),
                    limit=5,
                ),
                'is_customer': True,
            }
        )
    else:
        applications = (
            JobApplication.objects.filter(worker=profile)
            .select_related('job__customer__user')
            .order_by('-created_at')
        )
        job_history = applications.filter(status=JobApplication.ACCEPTED)
        open_jobs = Job.objects.filter(status=Job.OPEN).exclude(customer=profile).select_related('customer__user')
        available_jobs = sort_jobs_for_profile(profile, open_jobs, limit=24)
        context.update(
            {
                'applications': applications[:5],
                'available_jobs': available_jobs[:5],
                'job_history': job_history[:6],
                'accepted_jobs': applications.filter(status=JobApplication.ACCEPTED).count(),
                'pending_jobs': applications.filter(status=JobApplication.PENDING).count(),
                'is_customer': False,
            }
        )

    return render(request, 'marketplace/dashboard.html', context)


@login_required
def profile_edit(request):
    profile = get_profile(request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your profile has been refreshed.')
        return redirect('dashboard')
    return render(request, 'marketplace/profile_form.html', {'form': form, 'profile': profile})


def job_list(request):
    jobs = Job.objects.filter(status=Job.OPEN).select_related('customer__user', 'selected_worker__user')
    query = request.GET.get('q', '').strip()
    city = request.GET.get('city', '').strip()
    urgency = request.GET.get('urgency', '').strip()
    category = request.GET.get('category', '').strip()

    if query:
        jobs = jobs.filter(Q(title__icontains=query) | Q(description__icontains=query))
    if city:
        jobs = jobs.filter(
            Q(location_label__icontains=city)
            | Q(location_address__icontains=city)
            | Q(customer__city__icontains=city)
        )
    if urgency:
        jobs = jobs.filter(urgency=urgency)
    if category:
        jobs = jobs.filter(category=category)

    profile = get_profile(request.user) if request.user.is_authenticated else None
    applied_ids = set()
    if profile and profile.role == Profile.WORKER:
        applied_ids = set(profile.applications.values_list('job_id', flat=True))
        jobs = sort_jobs_for_profile(profile, jobs)

    return render(
        request,
        'marketplace/job_list.html',
        {
            'jobs': jobs,
            'profile': profile,
            'applied_ids': applied_ids,
        },
    )


def worker_directory(request):
    workers = Profile.objects.filter(role=Profile.WORKER).select_related('user')
    query = request.GET.get('q', '').strip()
    city = request.GET.get('city', '').strip()

    if query:
        workers = workers.filter(Q(skills__icontains=query) | Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query))
    if city:
        workers = workers.filter(city__icontains=city)
    profile = get_profile(request.user) if request.user.is_authenticated else None
    workers = sort_workers_for_profile(profile, workers)

    return render(request, 'marketplace/worker_directory.html', {'workers': workers})


@login_required
def job_create(request):
    profile = ensure_role(request, Profile.CUSTOMER)
    if not profile:
        return redirect('dashboard')

    form = JobForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                job = form.save(commit=False)
                job.customer = profile
                job.location_label = job.location_label or profile.city
                if not job.has_coordinates:
                    job.latitude = profile.latitude
                    job.longitude = profile.longitude
                job.credits_spent = JOB_POST_CREDIT_COST
                job.save()
                record_credit_change(profile, -JOB_POST_CREDIT_COST, f'Posted job: {job.title}', related_job=job)
                profile.jobs_posted += 1
                profile.save(update_fields=['jobs_posted', 'updated_at'])
                award_xp(profile, 5, 'Posted a new job', related_job=job)
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, 'Job posted. Workers can discover it immediately.')
            return redirect(job)

    return render(request, 'marketplace/job_form.html', {'form': form})


def job_detail(request, pk):
    job = get_object_or_404(
        Job.objects.select_related('customer__user', 'selected_worker__user').prefetch_related('applications__worker__user'),
        pk=pk,
    )
    profile = get_profile(request.user) if request.user.is_authenticated else None
    is_job_owner = bool(profile and profile.role == Profile.CUSTOMER and profile.id == job.customer_id)
    is_selected_worker = bool(profile and profile.role == Profile.WORKER and profile.id == job.selected_worker_id)
    applications = job.applications.all() if is_job_owner else job.applications.none()
    recommendations = recommend_workers(job, limit=6) if is_job_owner else []
    has_applied = False
    worker_application = None
    application_form = None

    if profile and profile.role == Profile.WORKER:
        worker_application = job.applications.filter(worker=profile).select_related('worker__user').first()
        has_applied = worker_application is not None
        if job.is_open and not has_applied and job.customer_id != profile.id:
            application_form = ApplicationForm()

    review_form = None
    can_view_contacts = False
    if (
        profile
        and profile.role == Profile.CUSTOMER
        and job.customer_id == profile.id
        and job.status == Job.COMPLETED
        and job.selected_worker
        and not hasattr(job, 'review')
    ):
        review_form = ReviewForm()

    if profile and job.selected_worker_id:
        can_view_contacts = is_job_owner or is_selected_worker

    return render(
        request,
        'marketplace/job_detail.html',
        {
            'job': job,
            'applications': applications,
            'recommendations': recommendations,
            'profile': profile,
            'is_job_owner': is_job_owner,
            'has_applied': has_applied,
            'worker_application': worker_application,
            'application_form': application_form,
            'review_form': review_form,
            'can_view_contacts': can_view_contacts,
        },
    )


@login_required
def apply_to_job(request, pk):
    profile = ensure_role(request, Profile.WORKER)
    if not profile:
        return redirect('dashboard')

    job = get_object_or_404(Job, pk=pk)
    if not job.is_open:
        messages.error(request, 'This job is no longer accepting applications.')
        return redirect(job)
    if job.customer_id == profile.id:
        return HttpResponseForbidden('You cannot apply to your own job.')
    if JobApplication.objects.filter(job=job, worker=profile).exists():
        messages.info(request, 'You have already applied to this job.')
        return redirect(job)

    form = ApplicationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                application = form.save(commit=False)
                application.job = job
                application.worker = profile
                application.credits_spent = APPLICATION_CREDIT_COST
                ranked = recommend_workers(job, queryset=Profile.objects.filter(pk=profile.pk), limit=1)
                application.match_score_snapshot = ranked[0]['score'] if ranked else 0
                application.save()
                record_credit_change(
                    profile,
                    -APPLICATION_CREDIT_COST,
                    f'Applied to job: {job.title}',
                    related_job=job,
                )
                award_xp(profile, 3, 'Submitted a job proposal', related_job=job)
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, 'Proposal sent. Your application is now in the queue.')
            return redirect(job)

    return render(request, 'marketplace/job_form.html', {'form': form, 'mode': 'apply', 'job': job})


@login_required
def accept_application(request, job_pk, application_pk):
    profile = ensure_role(request, Profile.CUSTOMER)
    if not profile:
        return redirect('dashboard')

    job = get_object_or_404(Job, pk=job_pk, customer=profile)
    application = get_object_or_404(JobApplication, pk=application_pk, job=job)

    with transaction.atomic():
        job.selected_worker = application.worker
        job.status = Job.IN_PROGRESS
        job.save(update_fields=['selected_worker', 'status', 'updated_at'])
        job.applications.exclude(pk=application.pk).update(status=JobApplication.REJECTED)
        application.status = JobApplication.ACCEPTED
        application.save(update_fields=['status', 'updated_at'])
        award_xp(application.worker, 10, 'Customer selected your proposal', related_job=job)

    messages.success(request, f'{application.worker.display_name} is now assigned to this job. Contact details are now visible to both sides.')
    return redirect(job)


@login_required
def boost_job(request, pk):
    profile = ensure_role(request, Profile.CUSTOMER)
    if not profile:
        return redirect('dashboard')

    job = get_object_or_404(Job, pk=pk, customer=profile, status=Job.OPEN)
    try:
        with transaction.atomic():
            record_credit_change(
                profile,
                -BOOST_VISIBILITY_CREDIT_COST,
                f'Boosted job visibility: {job.title}',
                related_job=job,
            )
            job.is_boosted = True
            job.boost_credits_spent += BOOST_VISIBILITY_CREDIT_COST
            job.save(update_fields=['is_boosted', 'boost_credits_spent', 'updated_at'])
            award_xp(profile, 2, 'Boosted a job listing', related_job=job)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Job visibility boosted. It will now appear ahead of regular listings.')
    return redirect(job)


@login_required
def update_job_status(request, pk, status):
    profile = get_profile(request.user)
    job = get_object_or_404(Job, pk=pk)

    can_manage = profile.id == job.customer_id or (job.selected_worker_id and profile.id == job.selected_worker_id)
    if not can_manage:
        return HttpResponseForbidden('You do not have permission to update this job.')

    if status == Job.IN_PROGRESS and job.status == Job.OPEN:
        job.status = Job.IN_PROGRESS
        job.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Job is now marked as in progress.')
    elif status == Job.COMPLETED:
        complete_job(job)
        messages.success(request, 'Job completed. XP and work history have been updated.')
    return redirect(job)


@login_required
def submit_review(request, pk):
    profile = ensure_role(request, Profile.CUSTOMER)
    if not profile:
        return redirect('dashboard')

    job = get_object_or_404(Job, pk=pk, customer=profile, status=Job.COMPLETED)
    if not job.selected_worker or hasattr(job, 'review'):
        messages.info(request, 'A review already exists for this job.')
        return redirect(job)

    form = ReviewForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        review = form.save(commit=False)
        review.job = job
        review.reviewer = profile
        review.reviewee = job.selected_worker
        review.save()
        if review.rating >= 4:
            award_xp(job.selected_worker, 5, 'Excellent customer review', related_job=job)
        messages.success(request, 'Review saved. This helps the ranking system stay fair.')
    return redirect(job)


@login_required
def wallet(request):
    profile = get_profile(request.user)
    topup_form = WalletTopUpForm(request.POST or None)
    if request.method == 'POST' and topup_form.is_valid():
        try:
            package = get_fixpoint_package(topup_form.cleaned_data['package'])
            callback_url = request.build_absolute_uri(reverse('wallet-paystack-callback'))
            _, authorization_url = initialize_paystack_topup(profile, package, callback_url)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            return redirect(authorization_url)

    return render(
        request,
        'marketplace/wallet.html',
        {
            'profile': profile,
            'credit_events': profile.credit_transactions.all()[:12],
            'xp_events': profile.xp_events.all()[:12],
            'topup_form': topup_form,
            'packages': get_fixpoint_packages(),
            'recent_topups': profile.wallet_topups.all()[:8],
        },
    )


@login_required
def wallet_paystack_callback(request):
    profile = get_profile(request.user)
    reference = request.GET.get('reference', '').strip()
    if not reference:
        messages.error(request, 'Missing Paystack transaction reference.')
        return redirect('wallet')

    try:
        topup = verify_paystack_topup(reference)
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        if topup.profile_id != profile.id:
            messages.info(request, 'Payment verified, but it belongs to a different wallet owner.')
        else:
            messages.success(request, f'{topup.credits} FixPoints added after Paystack payment confirmation.')
    return redirect('wallet')


def leaderboard(request):
    workers = Profile.objects.filter(role=Profile.WORKER).select_related('user')
    workers = sorted(
        workers,
        key=lambda worker: (worker.xp, worker.average_rating, worker.completed_jobs),
        reverse=True,
    )
    return render(request, 'marketplace/leaderboard.html', {'workers': workers})
