# ProxiFix Push Notifications Implementation Summary

## What Was Added

### 1. **Database Model (`PushSubscription`)**
   - Stores browser push subscription details per user
   - Fields: `profile`, `endpoint`, `p256dh`, `auth`
   - Unique constraint: one subscription per profile/endpoint pair
   - Located in: [marketplace/models.py](marketplace/models.py#L196)

### 2. **Service Layer Functions** (`marketplace/services.py`)
   - `send_web_push(subscription, payload)` — Low-level push delivery via pywebpush
   - `send_push_notification_to_profile(profile, payload)` — Sends to all user subscriptions
   - `_vapid_claims()` — VAPID signing claims
   - `_subscription_info()` — Formats subscription for WebPush API
   - Handles invalid subscriptions (auto-deletes 404/410 responses)
   - Optional dependency: `pywebpush >= 2.0.0`

### 3. **REST Endpoints** (`marketplace/views.py`)
   - `push_public_key()` — GET `/push/public-key/` — Returns VAPID public key for browser registration
   - `push_subscribe()` — POST `/push/subscribe/` — Stores browser subscription payload
   - Integrated into job workflow:
     - **apply_to_job()** — Sends notification to customer when bid received
     - **accept_application()** — Sends notification to worker when bid accepted

### 4. **Service Worker** (`marketplace/templates/sw.js`)
   - `push` event listener — Receives payloads, displays notifications
   - `notificationclick` event listener — Opens job URL on notification click
   - Integrates with existing cache-first strategy

### 5. **Client-Side Registration** (`marketplace/templates/marketplace/base.html`)
   - Enhanced service worker registration with push subscription flow:
     - Requests notification permission (if authenticated)
     - Fetches public VAPID key
     - Subscribes via `PushManager.subscribe()`
     - Sends subscription endpoint & keys to server
   - Graceful degradation if push unsupported

### 6. **Admin Panel** (`marketplace/admin.py`)
   - PushSubscriptionAdmin: View/manage subscriptions per user
   - Readonly fields: endpoint, p256dh, auth (encryption keys)
   - Searchable by profile/username

### 7. **Configuration** (`proxifix/settings.py`)
   - `PUSH_VAPID_PUBLIC_KEY` — Public key for browser (env var)
   - `PUSH_VAPID_PRIVATE_KEY` — Private key for signing (env var, keep secure)
   - `PUSH_VAPID_CLAIMS_SUBJECT` — VAPID subject claim (default: mailto:no-reply@proxifix.com)

### 8. **Migration**
   - `0004_pushsubscription.py` — Creates PushSubscription table

### 9. **Dependencies**
   - Updated: `requirements.txt` with `pywebpush==2.0.0`
   - Optional in dev; production requires it for push delivery

---

## Notification Flow

### **When Worker Submits a Bid**

1. Worker fills form and submits → **`apply_to_job()` view**
2. JobApplication created, credits deducted
3. `send_push_notification_to_profile(customer, {...})` called
4. For each stored subscription:
   - `send_web_push()` sends via pywebpush
   - Browser receives and triggers service worker `push` event
   - `sw.js` displays: **"New proposal received — [Worker Name] submitted a bid on [Job Title]"**
5. Click notification → Opens job detail page

### **When Customer Accepts a Bid**

1. Customer views job and accepts bid → **`accept_application()` view**
2. Job marked as IN_PROGRESS, worker awarded XP
3. `send_push_notification_to_profile(worker, {...})` called
4. Same flow, notification: **"Bid accepted — Your bid for [Job Title] has been accepted."**
5. Click notification → Opens job detail page

---

## Setup Instructions (Developer)

### Quick Start

```bash
# 1. Install dependencies
pip install pywebpush==2.0.0

# 2. Generate VAPID keys (one-time)
python -m webpush --generate-keys

# 3. Add to .env
PUSH_VAPID_PUBLIC_KEY=<public_key_from_above>
PUSH_VAPID_PRIVATE_KEY=<private_key_from_above>

# 4. Apply migration
python manage.py migrate

# 5. Run server
python manage.py runserver
```

### Testing Locally

- Log in as customer
- Create a job
- Log in as worker (different browser tab/incognito)
- View job and submit bid
- Switch back to customer tab → Should see push notification

### Production Deployment

1. Set PUSH_VAPID keys in environment (secrets manager)
2. Ensure HTTPS enabled: `SECURE_SSL_REDIRECT = True`
3. Run migration: `python manage.py migrate`
4. Collect static: `python manage.py collectstatic`
5. Restart Django/ASGI server

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Optional pywebpush** | Allows graceful degradation if not installed; push disabled but core app works |
| **Per-subscription loop** | User may have multiple devices; each gets notified independently |
| **Auto-delete stale subs** | Reduces DB bloat; push service endpoints expire naturally |
| **URL in payload data** | Allows service worker to navigate on click without hardcoding |
| **VAPID claims subject** | Configurable for different deployment scenarios; defaults to safe value |
| **No user-visible errors** | Network/push failures logged silently; doesn't block bid acceptance flow |

---

## Files Modified

- **Models**: [marketplace/models.py](marketplace/models.py#L196) — Added PushSubscription
- **Services**: [marketplace/services.py](marketplace/services.py#L343) — Added push helpers
- **Views**: [marketplace/views.py](marketplace/views.py#L20-L30, #L477-L502, #L553-L563) — Added endpoints & hooks
- **URLs**: [marketplace/urls.py](marketplace/urls.py#L15-L17) — Added /push/ routes
- **Admin**: [marketplace/admin.py](marketplace/admin.py#L43-L46) — Registered model
- **Frontend**: [marketplace/templates/marketplace/base.html](marketplace/templates/marketplace/base.html#L189-L242) — Enhanced SW registration
- **Service Worker**: [marketplace/templates/sw.js](marketplace/templates/sw.js#L24-L55) — Added push/notification listeners
- **Settings**: [proxifix/settings.py](proxifix/settings.py#L137-L141) — Added config keys
- **Requirements**: [requirements.txt](requirements.txt#L7) — Added pywebpush
- **Migration**: [marketplace/migrations/0004_pushsubscription.py](marketplace/migrations/0004_pushsubscription.py) — Schema change
- **Docs**: [docs/PUSH_NOTIFICATIONS.md](docs/PUSH_NOTIFICATIONS.md) — Full setup & troubleshooting guide

---

## Next Steps (Optional Enhancements)

1. **Push Notification History** — Store sent notifications for audit/replay
2. **User Preferences** — Allow users to opt-in/out of specific notification types
3. **Batch Notifications** — Coalesce multiple bids into single notification
4. **Analytics** — Track open/click rates per notification
5. **Rate Limiting** — Prevent notification spam (e.g., max 1 per job per hour)
6. **Fallback Email** — Send email if push fails or user hasn't subscribed
7. **In-App Bell Icon** — Show unread badge linked to notification center

---

## Security & GDPR Notes

- **PushSubscription data** is non-personal (endpoint is opaque, no user IDs stored in keys)
- **Encryption keys** (p256dh, auth) are specific to subscription; push service handles encryption
- **VAPID private key** must be kept secure; consider rotating periodically in production
- **User consent** is required (notification permission); complies with web standards
- **Right to delete** — Subscriptions auto-clean on 410; users can revoke via browser settings

---

## Support & Debugging

See [docs/PUSH_NOTIFICATIONS.md](docs/PUSH_NOTIFICATIONS.md) for:
- Detailed troubleshooting
- Browser compatibility matrix
- DevTools inspection steps
- Common error codes and solutions
