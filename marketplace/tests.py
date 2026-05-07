from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Job, JobApplication, Profile, WalletTopUp
from .services import complete_job, get_level_metadata, recommend_workers


class MarketplaceSmokeTests(TestCase):
    def test_registration_creates_profile_with_welcome_fixpoints(self):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'worker01',
                'first_name': 'Tolu',
                'last_name': 'Fixer',
                'email': 'tolu@example.com',
                'role': 'worker',
                'phone': '08000000000',
                'city': 'Lagos',
                'address': 'Yaba',
                'latitude': '6.524400',
                'longitude': '3.379200',
                'bio': 'Fast and reliable',
                'skills': 'Electrical, General Maintenance',
                'hourly_rate': '15000',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )
        self.assertRedirects(response, reverse('dashboard'))
        profile = Profile.objects.get(user__username='worker01')
        self.assertEqual(profile.wallet_credits, 50)
        self.assertEqual(profile.role, Profile.WORKER)

    def test_recommend_workers_returns_ranked_results(self):
        customer = User.objects.create_user(username='customer', password='pass12345')
        worker = User.objects.create_user(username='worker', password='pass12345')
        customer_profile = customer.profile
        customer_profile.city = 'Lagos'
        customer_profile.save()
        worker_profile = worker.profile
        worker_profile.role = Profile.WORKER
        worker_profile.city = 'Lagos'
        worker_profile.skills = 'Plumbing'
        worker_profile.xp = 120
        worker_profile.save()
        job = Job.objects.create(
            customer=customer_profile,
            category='Plumbing',
            title='Kitchen sink repair',
            description='Need a plumber for a leaking sink',
            location_label='Lagos',
            budget_min=20000,
            budget_max=40000,
        )
        ranked = recommend_workers(job)
        self.assertEqual(ranked[0]['worker'], worker_profile)

    def test_worker_directory_prioritizes_nearby_workers_before_farther_higher_xp_workers(self):
        customer = User.objects.create_user(username='customer-nearby', password='pass12345')
        customer_profile = customer.profile
        customer_profile.city = 'Lagos'
        customer_profile.address = 'Yaba'
        customer_profile.save()

        far_worker = User.objects.create_user(username='far-elite', password='pass12345')
        far_profile = far_worker.profile
        far_profile.role = Profile.WORKER
        far_profile.city = 'Abuja'
        far_profile.address = 'Wuse'
        far_profile.xp = 500
        far_profile.save()

        lower_xp_near_worker = User.objects.create_user(username='lagos-junior', password='pass12345')
        lower_xp_near_profile = lower_xp_near_worker.profile
        lower_xp_near_profile.role = Profile.WORKER
        lower_xp_near_profile.city = 'Lagos'
        lower_xp_near_profile.address = 'Yaba'
        lower_xp_near_profile.xp = 50
        lower_xp_near_profile.save()

        higher_xp_near_worker = User.objects.create_user(username='lagos-senior', password='pass12345')
        higher_xp_near_profile = higher_xp_near_worker.profile
        higher_xp_near_profile.role = Profile.WORKER
        higher_xp_near_profile.city = 'Lagos'
        higher_xp_near_profile.address = 'Yaba'
        higher_xp_near_profile.xp = 200
        higher_xp_near_profile.save()

        self.client.login(username='customer-nearby', password='pass12345')
        response = self.client.get(reverse('worker-directory'))
        content = response.content.decode('utf-8')

        self.assertLess(content.index('lagos-senior'), content.index('lagos-junior'))
        self.assertLess(content.index('lagos-junior'), content.index('far-elite'))

    def test_level_metadata_advances(self):
        self.assertEqual(get_level_metadata(0)['name'], 'Starter')
        self.assertEqual(get_level_metadata(600)['name'], 'Elite')

    def test_posting_job_costs_two_fixpoints(self):
        user = User.objects.create_user(username='customer01', password='pass12345')
        profile = user.profile
        profile.wallet_credits = 10
        profile.city = 'Lagos'
        profile.save()
        self.client.login(username='customer01', password='pass12345')

        response = self.client.post(
            reverse('job-create'),
            {
                'title': 'Outlet repair',
                'category': 'Electrical',
                'description': 'Fix a faulty wall socket',
                'location_label': 'Lagos',
                'location_address': 'Yaba',
                'budget_min': '5000',
                'budget_max': '12000',
                'urgency': 'normal',
            },
        )

        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        job = Job.objects.get(title='Outlet repair')
        self.assertEqual(profile.wallet_credits, 8)
        self.assertEqual(job.credits_spent, 2)

    def test_job_list_prioritizes_nearby_jobs_for_workers(self):
        worker = User.objects.create_user(username='worker-nearby', password='pass12345')
        worker_profile = worker.profile
        worker_profile.role = Profile.WORKER
        worker_profile.city = 'Lagos'
        worker_profile.address = 'Yaba'
        worker_profile.save()

        far_customer = User.objects.create_user(username='customer-far', password='pass12345')
        far_customer.profile.city = 'Abuja'
        far_customer.profile.address = 'Wuse'
        far_customer.profile.save()
        Job.objects.create(
            customer=far_customer.profile,
            category='Cleaning',
            title='Abuja move-out clean',
            description='Need help cleaning a flat in Abuja',
            location_label='Abuja',
            location_address='Wuse',
            budget_min=18000,
            budget_max=24000,
        )

        near_customer = User.objects.create_user(username='customer-near', password='pass12345')
        near_customer.profile.city = 'Lagos'
        near_customer.profile.address = 'Yaba'
        near_customer.profile.save()
        Job.objects.create(
            customer=near_customer.profile,
            category='Cleaning',
            title='Yaba apartment clean',
            description='Need a cleaner in Yaba this weekend',
            location_label='Lagos',
            location_address='Yaba',
            budget_min=15000,
            budget_max=22000,
        )

        self.client.login(username='worker-nearby', password='pass12345')
        response = self.client.get(reverse('job-list'))
        content = response.content.decode('utf-8')

        self.assertLess(content.index('Yaba apartment clean'), content.index('Abuja move-out clean'))

    def test_existing_wallet_balance_only_changes_after_verified_topup(self):
        customer = User.objects.create_user(
            username='customer02',
            password='pass12345',
            email='customer02@example.com',
        )
        worker = User.objects.create_user(username='worker02', password='pass12345')
        customer_profile = customer.profile
        worker_profile = worker.profile
        customer_profile.wallet_credits = 12
        customer_profile.city = 'Lagos'
        customer_profile.save()
        worker_profile.role = Profile.WORKER
        worker_profile.wallet_credits = 4
        worker_profile.city = 'Lagos'
        worker_profile.save()
        job = Job.objects.create(
            customer=customer_profile,
            selected_worker=worker_profile,
            category='Plumbing',
            title='Pipe replacement',
            description='Replace damaged pipe',
            location_label='Lagos',
            budget_min=10000,
            budget_max=20000,
            status=Job.IN_PROGRESS,
        )

        complete_job(job)
        customer_profile.refresh_from_db()
        worker_profile.refresh_from_db()

        self.assertEqual(customer_profile.wallet_credits, 12)
        self.assertEqual(worker_profile.wallet_credits, 4)

        self.client.login(username='customer02', password='pass12345')

        def fake_paystack(url, payload=None, method='GET'):
            if url == 'https://api.paystack.co/transaction/initialize':
                return {
                    'data': {
                        'access_code': 'ACCESS-123',
                        'authorization_url': 'https://paystack.example/authorize/ACCESS-123',
                    }
                }
            if '/transaction/verify/' in url:
                return {
                    'data': {
                        'status': 'success',
                        'amount': 50000,
                        'id': 'TXN-123',
                    }
                }
            self.fail(f'Unexpected Paystack URL: {url}')

        with patch('marketplace.services.secrets.token_hex', return_value='testref'):
            with patch('marketplace.services._paystack_request', side_effect=fake_paystack):
                response = self.client.post(reverse('wallet'), {'package': 'starter'})

                self.assertRedirects(response, 'https://paystack.example/authorize/ACCESS-123', fetch_redirect_response=False)
                customer_profile.refresh_from_db()
                self.assertEqual(customer_profile.wallet_credits, 12)

                topup = WalletTopUp.objects.get(profile=customer_profile)
                self.assertEqual(topup.reference, f'PFX-TOPUP-{customer.pk}-TESTREF')
                self.assertEqual(topup.credits, 50)
                self.assertEqual(topup.naira_amount, 500)
                self.assertEqual(topup.status, WalletTopUp.PENDING)
                self.assertEqual(topup.paystack_access_code, 'ACCESS-123')

                callback_response = self.client.get(
                    reverse('wallet-paystack-callback'),
                    {'reference': topup.reference},
                )

                self.assertRedirects(callback_response, reverse('wallet'))
                customer_profile.refresh_from_db()
                topup.refresh_from_db()
                self.assertEqual(customer_profile.wallet_credits, 62)
                self.assertEqual(topup.status, WalletTopUp.SUCCESS)
                self.assertTrue(topup.fulfilled)

                self.client.get(reverse('wallet-paystack-callback'), {'reference': topup.reference})
                customer_profile.refresh_from_db()
                self.assertEqual(customer_profile.wallet_credits, 62)

    def test_error_alerts_render_with_bootstrap_danger_class(self):
        user = User.objects.create_user(
            username='wallet-owner',
            password='pass12345',
            email='wallet-owner@example.com',
        )
        self.client.login(username='wallet-owner', password='pass12345')

        response = self.client.get(reverse('wallet-paystack-callback'), follow=True)

        self.assertContains(response, 'alert alert-danger')
        self.assertContains(response, 'Missing Paystack transaction reference.')

    def test_success_alerts_render_after_registration(self):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'worker03',
                'first_name': 'Sade',
                'last_name': 'Fixer',
                'email': 'sade@example.com',
                'role': 'worker',
                'phone': '08000000001',
                'city': 'Lagos',
                'address': 'Surulere',
                'latitude': '6.509500',
                'longitude': '3.367600',
                'bio': 'Careful and punctual',
                'skills': 'Cleaning, Painting',
                'hourly_rate': '12000',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
            follow=True,
        )

        self.assertContains(response, 'alert alert-success')
        self.assertContains(
            response,
            'Your ProxiFix account is live. We added 50 welcome FixPoints to your wallet, and you can top up anytime.',
        )

    def test_worker_job_detail_hides_other_workers_applications(self):
        customer = User.objects.create_user(username='customer03', password='pass12345')
        viewer = User.objects.create_user(username='worker-viewer', password='pass12345')
        competitor = User.objects.create_user(username='worker-competitor', password='pass12345')

        customer_profile = customer.profile
        customer_profile.city = 'Lagos'
        customer_profile.save()

        viewer_profile = viewer.profile
        viewer_profile.role = Profile.WORKER
        viewer_profile.city = 'Lagos'
        viewer_profile.skills = 'Cleaning'
        viewer_profile.save()

        competitor_profile = competitor.profile
        competitor_profile.role = Profile.WORKER
        competitor_profile.city = 'Lagos'
        competitor_profile.skills = 'Cleaning'
        competitor_profile.save()

        job = Job.objects.create(
            customer=customer_profile,
            category='Cleaning',
            title='Deep clean apartment',
            description='Need a cleaner for a weekend job',
            location_label='Lagos',
            budget_min=15000,
            budget_max=25000,
        )
        JobApplication.objects.create(
            job=job,
            worker=competitor_profile,
            pitch='I can handle this job tomorrow morning.',
            proposed_price=18000,
            estimated_days=1,
        )

        self.client.login(username='worker-viewer', password='pass12345')
        response = self.client.get(reverse('job-detail', args=[job.pk]))

        self.assertContains(response, 'Apply To This Job')
        self.assertNotContains(response, 'Applications')
        self.assertNotContains(response, 'Recommended workers')
        self.assertNotContains(response, 'I can handle this job tomorrow morning.')

    def test_customer_profile_form_hides_worker_only_fields(self):
        user = User.objects.create_user(username='customer-profile', password='pass12345')
        self.client.login(username='customer-profile', password='pass12345')

        response = self.client.get(reverse('profile-edit'))

        self.assertNotContains(response, 'name="skills"')
        self.assertNotContains(response, 'name="hourly_rate"')
        self.assertNotContains(response, 'name="response_time_hours"')
        self.assertNotContains(response, 'name="is_verified"')

    def test_about_page_renders_with_navigation_links(self):
        response = self.client.get(reverse('about'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'marketplace/about.html')
        self.assertContains(response, reverse('about'))
        self.assertContains(response, reverse('pricing'))

    def test_pricing_page_renders_real_fixpoint_packages(self):
        response = self.client.get(reverse('pricing'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'marketplace/pricing.html')
        self.assertContains(response, 'Starter Pack')
        self.assertContains(response, 'Value Pack')
        self.assertContains(response, 'Pro Pack')
        self.assertContains(response, '&#8358;500')
        self.assertContains(response, '&#8358;1000')
        self.assertContains(response, '&#8358;2000')
        self.assertContains(response, '50 FixPoints')
        self.assertContains(response, '110 FixPoints')
        self.assertContains(response, '250 FixPoints')

    def test_logged_out_pricing_page_uses_register_cta(self):
        response = self.client.get(reverse('pricing'))

        self.assertContains(response, 'Create account to buy FixPoints')
        self.assertContains(response, f'href="{reverse("register")}"')

    def test_logged_in_pricing_page_uses_wallet_cta(self):
        user = User.objects.create_user(username='pricing-user', password='pass12345')
        self.client.login(username='pricing-user', password='pass12345')

        response = self.client.get(reverse('pricing'))

        self.assertContains(response, 'Buy FixPoints')
        self.assertContains(response, f'href="{reverse("wallet")}"')
