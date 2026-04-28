from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile_edit, name='profile-edit'),
    path('jobs/', views.job_list, name='job-list'),
    path('jobs/new/', views.job_create, name='job-create'),
    path('jobs/<int:pk>/', views.job_detail, name='job-detail'),
    path('jobs/<int:pk>/apply/', views.apply_to_job, name='job-apply'),
    path('jobs/<int:pk>/boost/', views.boost_job, name='job-boost'),
    path('jobs/<int:job_pk>/applications/<int:application_pk>/accept/', views.accept_application, name='application-accept'),
    path('jobs/<int:pk>/status/<slug:status>/', views.update_job_status, name='job-status'),
    path('jobs/<int:pk>/review/', views.submit_review, name='job-review'),
    path('workers/', views.worker_directory, name='worker-directory'),
    path('wallet/', views.wallet, name='wallet'),
    path('wallet/paystack/callback/', views.wallet_paystack_callback, name='wallet-paystack-callback'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
]
