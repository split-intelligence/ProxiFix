# Push Notifications Architecture Diagram

## High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CUSTOMER BROWSER                                 │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Service Worker (sw.js)                                          │    │
│  │  - Listens: push, notificationclick events                      │    │
│  │  - Shows browser notification to user                           │    │
│  │  - Opens job URL on notification click                          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                            ▲                                             │
│                            │ (push event)                                │
│                            │                                             │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Page (base.html)                                                │    │
│  │  - Registers service worker on page load                        │    │
│  │  - Requests notification permission (Notification API)         │    │
│  │  - Subscribes to push via PushManager.subscribe()              │    │
│  │  - Sends subscription to server via POST /push/subscribe/      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                    subscription payload (json)
                                  │
                                  ▼
        ┌─────────────────────────────────────────────┐
        │           DJANGO SERVER                     │
        │                                             │
        │  1. POST /push/subscribe/                   │
        │     - Validates CSRF                        │
        │     - Saves endpoint + keys to DB           │
        │     ├─ endpoint: "https://push..."          │
        │     ├─ p256dh: "...encryption key..."       │
        │     └─ auth: "...auth token..."             │
        │                                             │
        │  2. Worker applies for job:                 │
        │     apply_to_job() view                    │
        │     → send_push_notification_to_profile()   │
        │       └─ send_web_push() via pywebpush     │
        │                                             │
        │  3. Customer accepts bid:                   │
        │     accept_application() view              │
        │     → send_push_notification_to_profile()   │
        │       └─ send_web_push() via pywebpush     │
        │                                             │
        │  Database: PushSubscription table           │
        │  ├─ id, profile_id, endpoint, p256dh, auth│
        │  └─ created_at, updated_at                 │
        └─────────────────────────────────────────────┘
                           │
            VAPID-signed push payload
                           │
                           ▼
        ┌─────────────────────────────────────────────┐
        │        PUSH SERVICE (Browser Vendor)        │
        │     (Google FCM, Firefox, Apple, etc.)      │
        │                                             │
        │  - Receives signed payload                  │
        │  - Validates VAPID signature                │
        │  - Routes to recipient device               │
        │  - Encrypts with user's subscription keys   │
        └─────────────────────────────────────────────┘
                           │
                  encrypted payload
                           │
                           ▼
        ┌─────────────────────────────────────────────┐
        │        USER'S DEVICE (Recipient)            │
        │                                             │
        │  - Receives push message                    │
        │  - Decrypts with local subscription keys    │
        │  - Wakes up service worker                  │
        │  - Dispatches 'push' event                  │
        └─────────────────────────────────────────────┘
```

## Bid Submission Flow (Customer Notification)

```
WORKER SIDE                          SERVER                    CUSTOMER SIDE
═════════════════════════════════════════════════════════════════════════════

  User clicks
  "Submit Bid"
       │
       ▼
  apply_to_job()
  view called
       │
       ├─ Validate job is OPEN
       ├─ Create JobApplication record
       ├─ Deduct credits
       │
       ├─ Award XP (worker)
       │
       └─ send_push_notification_to_profile(job.customer)
           │
           ├─ Get all subscriptions for customer
           │
           ├─ For each subscription:
           │   │
           │   └─ send_web_push()
           │       │
           │       ├─ _subscription_info()
           │       ├─ _vapid_claims()
           │       │
           │       └─ webpush.webpush()
           │           │
           │           └─ Sign with VAPID private key
           │
           └─ Send to push service (FCM/etc)
                                            │
                                            ▼
                                   Push service routes
                                   to customer device
                                            │
                                            ▼
                                   Service worker receives
                                   'push' event
                                            │
                                            ▼
                                   sw.js push listener:
                                   - Parse payload
                                   - Call showNotification()
                                   - User sees:
                                     "New proposal received
                                      [Worker] bid on [Job]"
                                            │
                                            ▼
                                   User clicks notification
                                            │
                                            ▼
                                   notificationclick handler:
                                   - opens job URL
                                   - shows bid details
```

## Bid Acceptance Flow (Worker Notification)

```
CUSTOMER SIDE                       SERVER                     WORKER SIDE
═════════════════════════════════════════════════════════════════════════════

  User reviews bid,
  clicks "Accept"
       │
       ▼
  accept_application()
  view called
       │
       ├─ Verify customer owns job
       ├─ Update Job.selected_worker
       ├─ Update Job.status → IN_PROGRESS
       ├─ Mark application.status → ACCEPTED
       ├─ Reject all other bids
       │
       ├─ Award XP (worker)
       │
       └─ send_push_notification_to_profile(application.worker)
           │
           ├─ Get all subscriptions for worker
           │
           ├─ For each subscription:
           │   │
           │   └─ send_web_push()
           │       │
           │       ├─ _subscription_info()
           │       ├─ _vapid_claims()
           │       │
           │       └─ webpush.webpush()
           │           │
           │           └─ Sign with VAPID private key
           │
           └─ Send to push service (FCM/etc)
                                            │
                                            ▼
                                   Push service routes
                                   to worker device
                                            │
                                            ▼
                                   Service worker receives
                                   'push' event
                                            │
                                            ▼
                                   sw.js push listener:
                                   - Parse payload
                                   - Call showNotification()
                                   - User sees:
                                     "Bid accepted
                                      [Customer] accepted [Job]"
                                            │
                                            ▼
                                   User clicks notification
                                            │
                                            ▼
                                   notificationclick handler:
                                   - opens job URL
                                   - shows customer contact info
```

## Database Schema (PushSubscription)

```
┌──────────────────────────────────────────────────────────┐
│                    PushSubscription                       │
├──────────────────────────────────────────────────────────┤
│ id (BigAutoField, PK)                                    │
│ profile_id (FK → Profile.id)                             │
│ endpoint (URLField, max 500 chars)                       │
│   Example: "https://fcm.googleapis.com/fcm/send/..."     │
│ p256dh (CharField, max 255 chars)                        │
│   Purpose: Encryption key for client → server            │
│ auth (CharField, max 255 chars)                          │
│   Purpose: Authentication token for subscription         │
│ created_at (DateTimeField, auto_now_add)                 │
│ updated_at (DateTimeField, auto_now)                     │
├──────────────────────────────────────────────────────────┤
│ Constraints:                                             │
│  - Unique together: (profile_id, endpoint)               │
│  - One subscription per device per user                  │
│  - Ordering: -updated_at (most recent first)             │
└──────────────────────────────────────────────────────────┘
```

## Settings Configuration

```python
# proxifix/settings.py

PUSH_VAPID_PUBLIC_KEY = config(
    'PUSH_VAPID_PUBLIC_KEY',
    default=''
)
# Shared with frontend; allows browser to create subscription
# Example: "BCabc+123def/456ghi="

PUSH_VAPID_PRIVATE_KEY = config(
    'PUSH_VAPID_PRIVATE_KEY',
    default=''
)
# Secret! Used to sign push payloads
# Example: "XYZ789abc+def/ghi="

PUSH_VAPID_CLAIMS_SUBJECT = config(
    'PUSH_VAPID_CLAIMS_SUBJECT',
    default='mailto:no-reply@proxifix.com'
)
# Required for VAPID signature; email or URL of service operator
```

## URL Routing

```
GET  /push/public-key/
     └─ Returns: {"publicKey": "BCabc+123..."}
     └─ Used by: Browser during service worker registration
     └─ Auth: login_required

POST /push/subscribe/
     ├─ Body: {
     │   "endpoint": "https://push-service.example/send/...",
     │   "keys": {
     │     "p256dh": "...base64 encryption key...",
     │     "auth": "...base64 auth token..."
     │   }
     │ }
     ├─ Response: {"success": true}
     ├─ Action: Saves/updates PushSubscription in database
     └─ Auth: login_required, CSRF protected
```

## Error Handling & Recovery

```
send_web_push() flow:
  │
  ├─ Check if webpush available
  │   └─ If not → return False (silent fail)
  │
  ├─ Check if VAPID_PRIVATE_KEY set
  │   └─ If not → return False (silent fail)
  │
  ├─ Call webpush.webpush()
  │   │
  │   └─ WebPushException caught:
  │       │
  │       ├─ If HTTP 410 (Gone) or 404 (Not Found)
  │       │   └─ Delete subscription (auto-cleanup)
  │       │   └─ User will re-subscribe on next visit
  │       │
  │       └─ All other errors → return False
  │
  └─ Return True on success
```

## Service Worker Event Handlers (sw.js)

```javascript
self.addEventListener('push', event => {
  // 1. Decode push payload
  // 2. Parse JSON
  // 3. Extract title, body, url
  // 4. Show showNotification()
})

self.addEventListener('notificationclick', event => {
  // 1. Prevent default behavior
  // 2. Close notification
  // 3. Extract URL from notification.data
  // 4. Open URL in new/existing window
  // 5. Focus if already open
})
```

## Client-Side Flow (base.html)

```javascript
1. urlBase64ToUint8Array()    // Helper: decode VAPID pubkey
2. getCookie()                 // Helper: read CSRF token
3. registerPushSubscription()   // Main function
   │
   ├─ Check browser support
   ├─ Request notification permission
   ├─ Fetch public key from /push/public-key/
   ├─ Call PushManager.subscribe()
   ├─ POST subscription to /push/subscribe/
   └─ Handle success/error
```

---

This architecture ensures:
- ✅ **End-to-end encryption** (subscription keys)
- ✅ **Vendor independence** (works with any push service)
- ✅ **Graceful degradation** (works without push configured)
- ✅ **Auto-recovery** (re-subscribes on expired endpoints)
- ✅ **CSRF protected** (all POST endpoints)
- ✅ **Async & non-blocking** (doesn't delay bid acceptance)
