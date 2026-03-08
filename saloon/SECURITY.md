# Saloon Security Hardening

## Runtime Security Checklist
- Set `DJANGO_DEBUG=0` in production.
- Set a long random `DJANGO_SECRET_KEY` (50+ chars).
- Set `DJANGO_ALLOWED_HOSTS` to your real domains (comma-separated).
- Set `DJANGO_CSRF_TRUSTED_ORIGINS` with full HTTPS origins.
- Set `SALOON_SECURE_SSL_REDIRECT=1`.
- Keep `SALOON_HSTS_SECONDS=31536000` (or higher if policy allows).
- Tune brute-force controls with:
  - `SALOON_LOGIN_MAX_ATTEMPTS` (default `5`)
  - `SALOON_LOGIN_LOCKOUT_SECONDS` (default `900`)

## TLS and Cipher Suites
Django does not terminate TLS directly in production; TLS versions and cipher suites are enforced in the reverse proxy/load balancer.

- Use `deploy/nginx_tls.conf` as the baseline hardened TLS config.
- Keep only TLS 1.2/1.3 enabled.
- Keep strong AEAD cipher suites and disable legacy protocols/ciphers.

## Validation Command
Run this in production-like env before go-live:

```powershell
$env:DJANGO_DEBUG='0'
$env:DJANGO_SECRET_KEY='replace-with-strong-random-secret'
$env:DJANGO_ALLOWED_HOSTS='your-domain.example'
$env:DJANGO_CSRF_TRUSTED_ORIGINS='https://your-domain.example'
$env:SALOON_SECURE_SSL_REDIRECT='1'
python manage.py check --deploy
```
