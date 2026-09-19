# IRIS Etel IAM Demo

A FastAPI web application that demonstrates ZITADEL-powered identity and access management. The landing page is styled after a U.S. government portal (IRS.gov-style) and is branded as **IRIS Etel Demo**.

## Features

- **ZITADEL OIDC sign-in** using Authlib with PKCE
- **Role-aware access**: success page displays project roles from `urn:zitadel:iam:org:projects:roles`
- **No-access handling**: users without roles see a friendly, informative message
- **Single logout** via the OIDC `end_session_endpoint`
- **Production-aligned deployment** on EC2 behind your existing nginx setup

## ZITADEL application settings

In your ZITADEL project, create an application with these values:

| Setting               | Value                                                 |
| --------------------- | ----------------------------------------------------- |
| Application type      | Web                                                   |
| Authentication method | PKCE / Code                                           |
| Redirect URIs         | `https://etelligent-group.dev/iam-demo/auth/callback` |
| Post Logout URIs      | `https://etelligent-group.dev/iam-demo/auth/callback` |
| Development mode      | Off (redirect URIs must use `https://`)               |

Make sure the application requests these scopes:

```text
openid
profile
email
offline_access
urn:zitadel:iam:org:projects:roles
urn:zitadel:iam:user:resourceowner
```

Assign at least one project role to test users in ZITADEL; otherwise they will land on the no-access page.

## Local development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy .env.example to .env and fill in OIDC_CLIENT_ID + SESSION_SECRET
cp .env.example .env

python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8088
```

Open http://127.0.0.1:8088/iam-demo/.

> Local testing of the callback requires the redirect URI `https://etelligent-group.dev/iam-demo/auth/callback` to resolve to your machine, or you can temporarily add a development-mode redirect URI in ZITADEL.

## EC2 deployment

1. SSH into the EC2 instance and clone or upload this repository.
2. Generate a session secret:

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

3. Export the required variables and run the deploy script:

   ```bash
   export OIDC_CLIENT_ID="YOUR_ZITADEL_CLIENT_ID"
   export SESSION_SECRET="YOUR_GENERATED_SECRET"
   chmod +x deploy.sh
   ./deploy.sh
   ```

4. Ensure DNS for `etelligent-group.dev` points to the EC2 instance's public IP.
5. Configure your existing nginx reverse proxy to forward `/iam-demo/` to `127.0.0.1:8088`.

After deployment:

- Demo app: `https://etelligent-group.dev/iam-demo/`
- ZITADEL: `https://etelligent-group.dev:8083/zitadel`

## Project structure

```text
├── app/
│   ├── __init__.py
│   ├── auth.py          # OIDC helpers, PKCE, token validation
│   ├── config.py        # Environment-based configuration
│   └── main.py          # FastAPI routes
├── static/
│   ├── css/styles.css
│   └── js/app.js
├── templates/
│   ├── base.html
│   ├── index.html       # IRS.gov-style landing page
│   ├── success.html
│   ├── no_access.html
│   └── error.html
├── .env.example
├── deploy.sh
├── requirements.txt
└── README.md
```

## Troubleshooting

- **Callback fails with "Invalid OIDC state parameter"**: check that sessions are persisted across requests. Ensure `SESSION_SECRET` is stable and cookies are accepted by the browser.
- **HTTPS redirect issues**: verify your nginx proxy sends `X-Forwarded-Proto: https` and uvicorn runs with `--proxy-headers`.
- **No roles shown**: confirm the ZITADEL application requests `urn:zitadel:iam:org:projects:roles` and that the user has roles assigned in the project.
- **CORS or issuer errors**: ensure `OIDC_ISSUER` exactly matches the `issuer` value returned by `https://etelligent-group.dev:8083/.well-known/openid-configuration`.
