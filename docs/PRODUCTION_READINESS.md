# Production Readiness Checklist

Use this checklist before promoting to production.

## 1. Mandatory Production Preflight (Blocking Gate)

- [ ] Run `python scripts/prod_preflight.py --env-file .env` and require `PASS` before deploy.
- [ ] Confirm `APP_ENV=production`.
- [ ] Confirm `SESSION_SECRET` is at least 32 chars and not a default/placeholder.
- [ ] Confirm `DATABASE_URL` is set and is not SQLite.
- [ ] Confirm `ALLOWED_ORIGINS` is explicit and not `*`.
- [ ] Confirm `PUBLIC_BASE_URL` is set and starts with `https://`.
- [ ] Confirm `SEED_DEFAULT_ADMIN=false`.
- [ ] Confirm positive integer limits:
  `LOGIN_RATE_LIMIT_PER_MINUTE`, `API_RATE_LIMIT_PER_MINUTE`,
  `SESSION_MAX_AGE_SECONDS`, `SESSION_ABSOLUTE_TIMEOUT_SECONDS`,
  `MAX_BODY_SIZE_BYTES`, `UPLOAD_MAX_BYTES`,
  `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_SECONDS`.
- [ ] Confirm `UPLOAD_MAX_BYTES <= MAX_BODY_SIZE_BYTES`.
- [ ] If `SMTP_ENABLED=true`, confirm `SMTP_USERNAME`, `SMTP_PASSWORD`, and valid `SMTP_FROM_EMAIL`.

## 2. Database and Migrations

- [ ] Apply migrations with `alembic upgrade head` in staging and production.
- [ ] Remove reliance on runtime compatibility `ALTER TABLE` paths once migration rollout is complete.
- [ ] Verify backup + restore procedure with a timed recovery drill.

## 3. Environment and Secrets

- [ ] Set `APP_ENV=production`.
- [ ] Set a strong `SESSION_SECRET`.
- [ ] Set explicit `ALLOWED_ORIGINS` (no wildcard in production).
- [ ] Configure SMTP credentials for real email delivery.
- [ ] Store secrets in a vault/provider, not committed `.env` files.

## 4. Reliability and Health

- [ ] Wire liveness probe to `GET /health/live`.
- [ ] Wire readiness probe to `GET /health/ready`.
- [ ] Monitor `GET /health` for environment and database status.

## 5. Security

- [ ] Run dependency scanning (`pip-audit` or equivalent).
- [ ] Run static security scan (`bandit`) in CI.
- [ ] Confirm CSRF/session/rate-limit controls are enabled in production config.
- [ ] Confirm rate-limit state is persisted in shared storage (DB/Redis) for multi-instance deployments.
- [ ] Review admin permissions and audit log coverage.

## 6. Observability

- [ ] Centralize app logs with request IDs.
- [ ] Export and scrape `/metrics` from the deployment environment.
- [ ] Add error tracking (for example, Sentry) in production.
- [ ] Alert on availability, elevated 5xx rates, and auth failures.

## 7. Quality Gates

- [ ] CI must pass lint, migration smoke check, tests, and security scan.
- [ ] Maintain minimum test coverage threshold.
- [ ] Add browser UX/accessibility checks for critical pages.

## 8. Deployment

- [ ] Build immutable artifact/container.
- [ ] Run zero-downtime migration/deploy procedure.
- [ ] Validate smoke tests post-deploy (`/health`, login flow, listings search).
