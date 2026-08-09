# Ubiquitous Language

## Push Notifications

- **Browser-safe VAPID public key**: The URL-safe, uncompressed public key sent to the browser for `PushManager.subscribe()`. It is 65 bytes before base64url encoding.
- **PEM public key body**: The base64 body inside a `-----BEGIN PUBLIC KEY-----` file. This is useful for server tooling, but browsers cannot subscribe with it directly.
- **Push subscription**: A browser-created endpoint plus its `p256dh` and `auth` keys. ProxiFix stores it against a `Profile`.
- **Subscribed profile**: A customer or worker profile with at least one stored push subscription.
- **Push payload**: The JSON message sent through Web Push. It carries a title, body, and target URL.
- **Delivery attempt**: A server-side call to the browser's push service through `pywebpush`.
- **Stale subscription**: A saved subscription that the push service rejects as gone. The app deletes these when the push service returns `404` or `410`.
