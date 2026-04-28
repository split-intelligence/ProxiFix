from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Job, Profile, WalletTopUp
from .services import complete_job, get_level_metadata, recommend_workers


class MarketplaceSmokeTests(TestCase):
    def test_registration_creates_profile_without_free_fixpoints(self):
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
        self.assertEqual(profile.wallet_credits, 0)
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

    def test_wallet_balance_only_changes_after_verified_topup(self):
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
