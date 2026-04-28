from django.contrib import admin

from .models import CreditTransaction, Job, JobApplication, Profile, Review, WalletTopUp, XPEvent


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'role', 'city', 'wallet_credits', 'xp', 'completed_jobs', 'is_verified')
    list_filter = ('role', 'city', 'is_verified')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'city', 'skills')


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'customer', 'category', 'status', 'urgency', 'is_boosted', 'budget_min', 'budget_max', 'created_at')
    list_filter = ('status', 'urgency', 'category', 'is_boosted')
    search_fields = ('title', 'description', 'location_label', 'location_address', 'customer__user__username')


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('job', 'worker', 'status', 'proposed_price', 'estimated_days', 'match_score_snapshot', 'created_at')
    list_filter = ('status',)
    search_fields = ('job__title', 'worker__user__username')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('job', 'reviewer', 'reviewee', 'rating', 'created_at')
    list_filter = ('rating',)


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = ('profile', 'delta', 'balance_after', 'reason', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('profile__user__username', 'reason')


@admin.register(XPEvent)
class XPEventAdmin(admin.ModelAdmin):
    list_display = ('profile', 'amount', 'reason', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('profile__user__username', 'reason')


@admin.register(WalletTopUp)
class WalletTopUpAdmin(admin.ModelAdmin):
    list_display = ('profile', 'package_name', 'naira_amount', 'credits', 'status', 'fulfilled', 'created_at')
    list_filter = ('status', 'fulfilled', 'created_at')
    search_fields = ('profile__user__username', 'reference', 'package_name')
