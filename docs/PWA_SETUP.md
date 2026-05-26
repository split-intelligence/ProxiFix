# HandiGO PWA Setup & Production Guide

## Overview
HandiGO is now a Progressive Web App (PWA) with service worker support, offline caching, install prompts, and iOS splash screens.

## Development

### Running Locally
```bash
python manage.py runserver
```
Visit `http://localhost:8000` in your browser.

### Testing PWA Features
- **Manifest & Service Worker**: Open DevTools → Application → Manifest and Service Workers tabs.
- **Install Prompt**: On Chrome/Edge, the browser may show "Install app" or you can simulate it in Console:
  ```js
  window.dispatchEvent(new Event('beforeinstallprompt'));
  ```
- **Offline Mode**: In DevTools → Network, throttle to offline and navigate to cached pages.
- **iOS**: Test on an iOS device or simulator by visiting the site and tapping "Add to Home Screen" (or using Simulator's Share → Add to Home Screen).

## Production

### Critical: HTTPS Requirement
**Service Workers require HTTPS in production.** HTTP is only allowed for localhost during development.

Ensure your domain has a valid SSL/TLS certificate (via Let's Encrypt, AWS ACM, or your host provider).

### Deployment Checklist

1. **HTTPS Setup**
   - Verify your server serves HTTPS on port 443.
   - Redirect all HTTP traffic to HTTPS.
   - Use HTTP/2 if possible for faster asset loading.

2. **Django Settings**
   ```python
   # proxifix/settings.py
   SECURE_SSL_REDIRECT = True  # Redirect HTTP → HTTPS
   SESSION_COOKIE_SECURE = True
   CSRF_COOKIE_SECURE = True
   SECURE_HSTS_SECONDS = 31536000  # 1 year
   SECURE_HSTS_INCLUDE_SUBDOMAINS = True
   SECURE_HSTS_PRELOAD = True
   ```

3. **Static Files**
   - Serve static files (manifest, service worker, icons, CSS, JS) with long cache headers (`Cache-Control: public, max-age=31536000`) or no-cache for index/HTML.
   - Use a CDN (e.g., CloudFront, Cloudflare) to reduce latency and improve performance.

4. **Service Worker Cache Management**
   - The service worker is versioned as `handigo-pwa-v2`.
   - When you deploy updates, increment `CACHE_NAME` in `marketplace/templates/sw.js` to force clients to re-cache.
   - Example:
     ```javascript
     const CACHE_NAME = 'handigo-pwa-v3';  // increment on update
     ```

5. **Domain & SEO**
   - Ensure your manifest references correct start_url (e.g., `"start_url": "/"` or your production root).
   - Add your domain to Google Search Console and Bing Webmaster Tools.
   - Consider adding a sitemap.xml and robots.txt.

### Performance Tips

- **Lazy Load Images**: Images are not all pre-cached; use lazy loading to reduce initial payload.
- **Compression**: Enable gzip/brotli compression at the server level (Django + nginx/Apache).
- **Service Worker Updates**: The current SW uses a cache-first strategy for assets and network-first for navigations. Update when deploying new assets.
- **Monitor**: Use lighthouse, web.dev, or similar tools to monitor PWA score and performance.

## File Structure

```
marketplace/
├── static/marketplace/
│   ├── css/app.css
│   ├── manifest.json             # PWA manifest
│   ├── offline.html              # Offline fallback page
│   ├── images/
│   │   ├── handigo-logo.png      # 192x192 + 512x512 (used in manifest)
│   │   ├── proxifix-logo.png     # Apple touch icon
│   │   └── ios-splash-*.png      # iOS splash screens (6 sizes)
├── templates/
│   ├── marketplace/base.html     # PWA meta tags, install banner, SW registration
│   └── sw.js                     # Service worker (cache strategy, offline handling)
```

## Key Features

### 1. Service Worker
- **Location**: Served at `/sw.js` and precached in `PRECACHE_URLS`.
- **Strategy**: 
  - Navigations: network-first with offline fallback.
  - Same-origin assets: cache-first, updates cache on fetch.
- **Cache Name**: `handigo-pwa-v2` (increment to force update on deploy).

### 2. Manifest
- **Location**: `/static/marketplace/manifest.json`
- **Includes**: app name, colors, icons (192/512 + maskable), start URL, offline page reference.

### 3. Install Banner
- Small fixed banner at bottom-left of screen (dismissible).
- Shows on `beforeinstallprompt` event (Chrome, Edge, Firefox).
- Does not block iOS users (Apple uses "Add to Home Screen" instead).

### 4. Offline Capability
- Core assets cached on first visit.
- Navigation requests fall back to `/static/marketplace/offline.html` if offline.
- Users can navigate cached pages while offline.

### 5. iOS Support
- Apple touch icon (180×180).
- Splash screens (6 sizes for iPhone/iPad).
- Web app title and status bar color.

## Updating the PWA

### When Deploying New Code
1. Increment `CACHE_NAME` in `marketplace/templates/sw.js`:
   ```javascript
   const CACHE_NAME = 'handigo-pwa-v3';  // was v2
   ```
2. Update `PRECACHE_URLS` if static files change.
3. Deploy and monitor Service Worker registration in DevTools → Application.

### Icons & Splash Screens
- Replace or regenerate PNG files in `marketplace/static/marketplace/images/`.
- Splash images are referenced by media queries in `marketplace/templates/marketplace/base.html`.

## Debugging

### Common Issues

**Service Worker not updating**
- Hard refresh (Ctrl+Shift+R or Cmd+Shift+R on Mac).
- Check DevTools → Application → Service Workers for errors.
- Verify HTTPS is enabled in production.

**Manifest not found**
- Ensure `DEBUG = False` or serve static files correctly (use `collectstatic`).
- Check `STATIC_URL` and `STATIC_ROOT` in `proxifix/settings.py`.

**Splash screens not showing on iOS**
- Confirm PNGs are at the correct sizes and paths.
- Test on actual device or Simulator.
- Check Console for 404 errors.

**Install banner not showing**
- Chrome/Edge: Manifest criteria must be met (icon, title, etc.); DevTools → Application shows criteria.
- iOS: Doesn't show install banner; users tap Share → Add to Home Screen instead.

## Resources

- [MDN: Progressive Web Apps](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps)
- [Google: Building PWAs](https://web.dev/progressive-web-apps/)
- [Apple: Configuring Web Apps](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariWebContent/ConfiguringWebApplications/ConfiguringWebApplications.html)
- [Manifest Spec](https://www.w3.org/TR/appmanifest/)

## Support

For any issues or questions about the PWA setup, refer to the code comments in:
- `marketplace/templates/sw.js`
- `marketplace/templates/marketplace/base.html`
- `marketplace/static/marketplace/manifest.json`
