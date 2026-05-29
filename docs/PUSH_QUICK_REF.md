# Push Notifications Quick Reference

## Generate & Configure Keys (First Time)

```bash
# Generate VAPID keys
python -m webpush --generate-keys

# Add to .env
PUSH_VAPID_PUBLIC_KEY=public_key_here
PUSH_VAPID_PRIVATE_KEY=private_key_here
```

## Run Migrations

```bash
python manage.py migrate
```

## Test Locally

1. **As Customer**
   - Log in, create a job
   - Grant notification permission when prompted

2. **As Worker** (separate browser/incognito)
   - Log in, find the job
   - Click "Apply" / "Submit Bid"
   - **Expect notification on customer's browser**: "New proposal received"

3. **As Customer** (back to main browser)
   - View job, accept the bid
   - **Expect notification on worker's browser**: "Bid accepted"

## Admin Panel

View stored subscriptions:
```
http://localhost:8000/admin/marketplace/pushsubscription/
```

## Code Locations

| Component | File | Lines |
|-----------|------|-------|
| Model | `marketplace/models.py` | 196–207 |
| Service functions | `marketplace/services.py` | 343–388 |
| Endpoints | `marketplace/views.py` | 475–502 |
| URL routes | `marketplace/urls.py` | 15–17 |
| Service worker | `marketplace/templates/sw.js` | 24–55 |
| Client registration | `marketplace/templates/marketplace/base.html` | 189–242 |

## Common Issues

| Issue | Solution |
|-------|----------|
| "Push notifications not configured" | Set VAPID keys in .env |
| Notification not showing | Check: (1) permission granted, (2) HTTPS/localhost, (3) subscription stored in admin |
| Service Worker fails registration | Hard refresh (Ctrl+Shift+R), check DevTools → Application tab |
| pywebpush ImportError | Run `pip install pywebpush==2.0.0` |
| Old subscriptions sending 410 | Automatic; they're deleted and user re-subscribes on next visit |

## Integration Points (Where Notifications Sent)

**`apply_to_job()` view** (line ~510)
```python
send_push_notification_to_profile(
    job.customer,
    {
        'title': 'New proposal received',
        'body': f'{profile.display_name} submitted a bid on your job: {job.title}',
        'url': job.get_absolute_url(),
    },
)
```

**`accept_application()` view** (line ~563)
```python
send_push_notification_to_profile(
    application.worker,
    {
        'title': 'Bid accepted',
        'body': f'Your bid for {job.title} has been accepted.',
        'url': job.get_absolute_url(),
    },
)
```

## Payload Shape

```python
{
    'title': str,        # Notification headline
    'body': str,         # Notification message
    'url': str,          # URL to open on click (relative or absolute)
}
```

## Browser Support

| Browser | Desktop | Mobile |
|---------|---------|--------|
| Chrome | ✅ | ✅ (Android) |
| Firefox | ✅ | ✅ (Android) |
| Safari | ✅ (16+) | ✅ (16+) |
| Edge | ✅ | ✅ |

## Environment Variables Required

```bash
PUSH_VAPID_PUBLIC_KEY=...      # Share with frontend (public)
PUSH_VAPID_PRIVATE_KEY=...     # Keep secret! (server only)
PUSH_VAPID_CLAIMS_SUBJECT=mailto:no-reply@proxifix.com  # Optional
```

## Useful Django Commands

```bash
# Check migration status
python manage.py showmigrations marketplace

# Apply migrations
python manage.py migrate

# Drop & recreate (dev only!)
python manage.py migrate marketplace zero
python manage.py migrate marketplace

# Access admin
http://localhost:8000/admin/
```

## Key Functions

```python
# Send to a single profile (all their subscriptions)
send_push_notification_to_profile(profile, payload)

# Send to a single subscription (low-level)
send_web_push(subscription, payload)
```

## Settings to Know

```python
PUSH_VAPID_PUBLIC_KEY        # From environment
PUSH_VAPID_PRIVATE_KEY       # From environment (secret!)
PUSH_VAPID_CLAIMS_SUBJECT    # From environment (default provided)
```

## DevTools Tips

1. **Service Workers & Manifest**: Application → Service Workers
2. **Test Notification**: Application → Service Workers → Send notification
3. **Push Subscriptions**: Open IndexedDB → pushManager → subscriptions
4. **Network: Logs all push deliveries and errors
5. **Console**: Check for JS errors during registration

---

**For full docs, see**: [PUSH_NOTIFICATIONS.md](PUSH_NOTIFICATIONS.md) & [PUSH_IMPLEMENTATION.md](PUSH_IMPLEMENTATION.md)
