# OAuth Configuration Guide: Staging vs Production

This guide explains how to set up separate OAuth applications for staging and production environments.

## Why Separate OAuth Apps?

| Benefit | Description |
|---------|-------------|
| **Security isolation** | Tokens from staging can't affect production |
| **Independent rate limits** | Testing won't exhaust production quotas |
| **Safe revocation** | Can reset staging credentials without downtime |
| **Clear audit trails** | Know which environment made each API call |
| **Redirect URL clarity** | No conflicts between environment URLs |

---

## Google OAuth (Gmail/Calendar)

### Step 1: Create Staging App

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a **new project** named `YourApp-Staging`
3. Navigate to **APIs & Services > Credentials**
4. Click **Create Credentials > OAuth client ID**
5. Configure:
   - Application type: **Web application**
   - Name: `YourApp Staging`
   - Authorized redirect URIs:
     ```
     https://staging.yourdomain.com/api/integrations/gmail/callback
     http://localhost:8000/api/integrations/gmail/callback  (for local dev)
     ```
6. Copy the **Client ID** and **Client Secret**

### Step 2: Create Production App

1. Create a **new project** named `YourApp-Production`
2. Repeat the same steps with production URLs:
   - Authorized redirect URIs:
     ```
     https://app.yourdomain.com/api/integrations/gmail/callback
     ```

### Step 3: Enable Required APIs (both projects)

- Gmail API
- Google Calendar API
- Google People API (optional, for contacts)

---

## Zoom OAuth

### Step 1: Create Staging App

1. Go to [Zoom App Marketplace](https://marketplace.zoom.us/develop/create)
2. Click **Develop > Build App**
3. Choose **OAuth** app type
4. Configure:
   - App Name: `YourApp Staging`
   - Redirect URL: `https://staging.yourdomain.com/api/integrations/zoom/callback`
   - Add scopes: `meeting:write`, `meeting:read`
5. Copy credentials

### Step 2: Create Production App

1. Create another OAuth app
2. Configure with production URLs
3. **Important**: Production apps require Zoom review for public use

---

## Meta (Facebook/Instagram)

### Step 1: Create Staging App

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Click **My Apps > Create App**
3. Choose **Business** type
4. Configure:
   - App Name: `YourApp Staging`
   - Add **Facebook Login** product
   - Valid OAuth Redirect URIs:
     ```
     https://staging.yourdomain.com/api/integrations/meta/callback
     ```
5. Add required permissions (in App Review):
   - `leads_retrieval`
   - `pages_read_engagement`
   - `pages_manage_metadata`

### Step 2: Create Production App

1. Create separate app for production
2. **Note**: Production Meta apps require App Review before going live

---

## Environment Configuration

### Backend `.env` Files

```bash
# .env.development (local)
GOOGLE_CLIENT_ID=staging_client_id_here
GOOGLE_CLIENT_SECRET=staging_client_secret_here
ZOOM_CLIENT_ID=staging_zoom_id
ZOOM_CLIENT_SECRET=staging_zoom_secret
META_APP_ID=staging_meta_app_id
META_APP_SECRET=staging_meta_app_secret

# .env.staging
GOOGLE_CLIENT_ID=staging_client_id_here
GOOGLE_CLIENT_SECRET=staging_client_secret_here
ZOOM_CLIENT_ID=staging_zoom_id
ZOOM_CLIENT_SECRET=staging_zoom_secret
META_APP_ID=staging_meta_app_id
META_APP_SECRET=staging_meta_app_secret

# .env.production
GOOGLE_CLIENT_ID=prod_client_id_here
GOOGLE_CLIENT_SECRET=prod_client_secret_here
ZOOM_CLIENT_ID=prod_zoom_id
ZOOM_CLIENT_SECRET=prod_zoom_secret
META_APP_ID=prod_meta_app_id
META_APP_SECRET=prod_meta_app_secret
```

### Redirect URL Configuration

Update your backend config to use environment-aware redirect URLs:

```python
# app/core/config.py
import os

class Settings:
    # Base URL for callbacks (set per environment)
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
    
    # OAuth credentials (different per environment)
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    
    @property
    def google_redirect_uri(self) -> str:
        return f"{self.BASE_URL}/api/integrations/gmail/callback"
```

---

## Deployment Checklist

### Staging Environment
- [ ] Google Cloud project created (`YourApp-Staging`)
- [ ] Google OAuth client configured with staging URLs
- [ ] Gmail + Calendar APIs enabled
- [ ] Zoom OAuth app created (staging)
- [ ] Meta app created (staging, development mode OK)
- [ ] `.env.staging` configured with staging credentials
- [ ] `BASE_URL` set to `https://staging.yourdomain.com`

### Production Environment
- [ ] Google Cloud project created (`YourApp-Production`)
- [ ] Google OAuth client configured with production URLs
- [ ] Gmail + Calendar APIs enabled
- [ ] OAuth consent screen verified (if > 100 users)
- [ ] Zoom OAuth app created + reviewed for marketplace
- [ ] Meta app created + App Review completed
- [ ] `.env.production` configured with production credentials
- [ ] `BASE_URL` set to `https://app.yourdomain.com`

---

## Security Notes

1. **Never commit `.env` files** - Use secrets management (GitHub Secrets, AWS Secrets Manager, etc.)
2. **Rotate secrets periodically** - Especially after team changes
3. **Monitor OAuth usage** - Check Google Cloud Console / Zoom Dashboard for unusual activity
4. **Use least-privilege scopes** - Only request permissions you actually need
5. **Set up alerts** - Get notified of quota exhaustion or auth failures

---

## Troubleshooting

### "redirect_uri_mismatch" error
- Ensure the redirect URI in your code **exactly matches** what's registered in the OAuth provider
- Check for trailing slashes, http vs https, port numbers

### "invalid_client" error
- Wrong client ID/secret for the environment
- Check `.env` is loaded correctly

### Tokens from staging appearing in production
- This indicates shared credentials - create separate OAuth apps as described above
