# Push Notifications Setup for ProxiFix

## Overview
ProxiFix now sends browser push notifications to alert:
- **Customers** when a worker submits a bid on their job
- **Workers** when their bid is accepted by a customer

Push notifications leverage the PWA service worker and require VAPID keys for signing payloads.

## Prerequisites

1. **HTTPS in Production** — Push notifications require HTTPS (HTTP only works on localhost).
2. **Browser Support** — Push API is supported on:
   - Chrome/Edge (desktop & Android)
   - Firefox (desktop & Android)
   - Safari 16+
   - Opera
3. **User Permission** — Users must grant notification permission before subscriptions are stored.

## Installation

### 1. Install pywebpush

```bash
pip install pywebpush==2.0.0
```

Or update your existing installation:
```bash
pip install -r requirements.txt
```

### 2. Generate VAPID Keys

Generate a pair of public-private VAPID keys (one-time setup):

```bash
python -m webpush --generate-keys
```

Output will look like:
```
Public Key: ABC123...
Private Key: XYZ789...
```

### 3. Configure Environment Variables

Add the keys to your `.env` file:

```
PUSH_VAPID_PUBLIC_KEY=ABC123...xyz=
PUSH_VAPID_PRIVATE_KEY=XYZ789...
PUSH_VAPID_CLAIMS_SUBJECT=mailto:no-reply@proxifix.com
```

The public key is exposed to browsers; keep the private key secure.

### 4. Apply Database Migration

```bash
python manage.py migrate
```

This creates the `PushSubscription` table to store browser subscription details.

### 5. Restart Development Server

```bash
python manage.py runserver
```

## How It Works

### Client Side (Browser)

1. Service worker registers when the user logs in.
2. Browser requests notification permission.
3. If granted, client fetches the public VAPID key from `/push/public-key/`.
4. Browser subscribes to push via `PushManager.subscribe()`.
5. Subscription endpoint and keys are sent to `/push/subscribe/` (POST).
6. Server stores the subscription in the database.

### Server Side (Django)

1. When a worker submits an application (`apply_to_job`):
   - Customer's push subscription is retrieved.
   - Push notification is sent via `send_push_notification_to_profile()`.
   - Payload: `{ title: "New proposal", body: "...", url: "/jobs/123" }`

2. When a customer accepts a bid (`accept_application`):
   - Worker's push subscription is retrieved.
   - Push notification is sent.
   - Payload: `{ title: "Bid accepted", body: "...", url: "/jobs/123" }`

### Service Worker (Client-side Notification)

1. Service worker receives push event from browser.
2. Parses notification payload.
3. Shows system notification to user.
4. On click, opens the related job URL.

## Testing

### 1. Local Development (Localhost)

Since service workers work on localhost with HTTP, test locally:

```bash
python manage.py runserver
```

- Create a customer account and a worker account.
- Log in as worker, visit a job, and submit a bid.
- Check browser console → Application → Service Workers for any errors.
- If notification permission is granted, you should see a notification.

### 2. DevTools Inspection

- Open DevTools → Application → Service Workers.
- Check the "Notifications" tab to manually trigger test notifications.
- Verify the PushSubscription is stored in the admin panel: `/admin/marketplace/pushsubscription/`.

### 3. Production Testing

Deploy with HTTPS and test the full flow:

```bash
SECURE_SSL_REDIRECT=true python manage.py runserver
```

## Troubleshooting

### "Push notifications are not configured"
- Check `.env` for `PUSH_VAPID_PUBLIC_KEY` and `PUSH_VAPID_PRIVATE_KEY`.
- Ensure settings are loaded correctly.

### Notification not showing
- Verify notification permission is granted (check browser settings → Notifications).
- Check browser console for errors.
- Ensure HTTPS is enabled in production.
- Check admin panel → PushSubscription for stored subscriptions.

### Old subscriptions returning 410/404 errors
- Service automatically deletes invalid subscriptions.
- User will be re-subscribed on next visit.

### pywebpush ImportError
- Ensure `pip install pywebpush==2.0.0` completed successfully.
- Verify Python version supports the package (3.8+).

## Implementation Details

### Models
- `PushSubscription` (profile, endpoint, p256dh, auth) — stores browser subscription info.

### Views
- `push_public_key` (GET) — returns VAPID public key.
- `push_subscribe` (POST) — saves browser subscription.

### Services
- `send_push_notification_to_profile(profile, payload)` — sends notifications to all subscriptions.
- `send_web_push(subscription, payload)` — low-level WebPush API call.

### URLs
- `/push/public-key/` → GET public VAPID key.
- `/push/subscribe/` → POST browser subscription.

### Service Worker (sw.js)
- `push` event listener — receives and displays notifications.
- `notificationclick` event — handles notification clicks.

## Security Notes

1. **VAPID Private Key** — Keep secure; never expose in frontend.
2. **Endpoint URLs** — Subscription endpoints are unique and time-limited by the push service.
3. **Data Encryption** — Push payloads are encrypted in transit using the user's key.
4. **Permission Model** — Users explicitly grant notification permission per site per browser.

## Production Deployment Checklist

- [ ] HTTPS enabled with valid certificate.
- [ ] `PUSH_VAPID_PUBLIC_KEY` and `PUSH_VAPID_PRIVATE_KEY` set in environment.
- [ ] `SECURE_SSL_REDIRECT = True` in `settings.py`.
- [ ] Database migration applied: `python manage.py migrate`.
- [ ] Static files collected: `python manage.py collectstatic`.
- [ ] Test subscription and notification flow end-to-end.
- [ ] Monitor push delivery logs (optional: integrate with Sentry or similar).

## Further Reading

- [MDN: Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [Web.dev: Push Notifications](https://web.dev/web-platform/push-notifications/)
- [pywebpush Documentation](https://github.com/web-push-libs/pywebpush)
- [VAPID Specification](https://datatracker.ietf.org/doc/html/draft-thomson-webpush-vapid)
