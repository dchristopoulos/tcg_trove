# TCG Trove 10-Agent Knowledge Base

Consolidated findings from a 10-lane audit pass.  
Date: 2026-04-15

## Agent 1: Authentication and Session Security

Findings:
- Session validation is centralized and consistent in API deps.
- Remaining gap is explicit coverage for session absolute-timeout expiration behavior.

Implemented:
- Authenticated listing creation and seller-spoof prevention.
- Production preflight bounds checks for session/login/body/upload limits.

Next:
- Add integration test for absolute timeout expiry + forced re-auth.

## Agent 2: Authorization Boundaries (Critical)

Findings:
- Permission model (`permission_grants` / `permission_revokes`) is bypassed in several service-level checks that use `actor_role == "admin"`:
  - `app/services/inquiry_service.py:44,64`
  - `app/services/viewing_service.py:59`
  - `app/services/reservation_service.py:90,109`
  - `app/services/payment_service.py:26`
  - `app/api/v1/routers/users.py:134`
- Recommendations endpoint allows unauthenticated cross-user access by `user_id`:
  - `app/api/v1/routers/listings.py:219-220`
  - downstream personalization reads favorites/inquiries in `app/services/listing_service.py:193+`.

Impact:
- Revoked admin permissions may still be effectively privileged.
- Possible user-behavior/privacy leakage through recommendations.

Next:
- Replace role-string checks with permission-aware checks (`has_permission`/`require_permission`) plus sellership checks.
- Require auth on `/api/v1/listings/recommendations` and restrict `user_id` to self (or privileged roles only).

## Agent 3: Input Validation and Error Handling

Findings:
- Core validation paths are improved and tested.
- Optional hardening: add warning thresholds for extreme but positive numeric values.

Implemented:
- Type + positivity checks for bounded env ints.
- Cross-field check `UPLOAD_MAX_BYTES <= MAX_BODY_SIZE_BYTES`.

Next:
- Add warning-level checks for outlier values (very large lockout/body/rate values).

## Agent 4: Database and Migrations

Findings:
- Production preflight blocks SQLite correctly.
- Migration-first approach is documented, but runtime compatibility mutation fallback should be sunset.

Next:
- Add runtime flag to disable schema compatibility mutation logic after migration rollout stabilization.

## Agent 5: Testing and Regression Coverage

Findings:
- New authz regression tests were added, but privileged endpoint matrix is incomplete.

Implemented:
- Added tests for `search/logs` permission gate.
- Added tests for listing-viewings seller/admin boundary.

Next:
- Add matrix tests for all privileged endpoints (admin/supervisor/seller/regular).
- Add tests for recommendations self-only enforcement once fixed.

## Agent 6: Deployment and Operations

Findings:
- Docs are now preflight-driven and clearer.

Implemented:
- README includes concrete preflight checks and minimum deployment sequence.
- `docs/PRODUCTION_READINESS.md` has mandatory blocking preflight section.

Next:
- Add one-command deployment gate script for local + CI parity.

## Agent 7: Frontend/Static/Uploads Reliability

Findings:
- Runtime uploads were previously at risk of accidental tracking.

Implemented:
- Upload directory now tracks sentinel file only:
  - `app/static/uploads/.gitkeep`
  - ignore pattern: `app/static/uploads/*` with exception for `.gitkeep`.

Next:
- Add cleanup/retention job for stale uploads.

## Agent 8: Dependency and Config Hygiene

Findings:
- Ignore rules now cover key local/runtime artifacts.

Implemented:
- `.gitignore` includes `tmp/`, `temp/`, `.cache/`, `.serena/`, `*.log`, `node_modules/`.

Next:
- Add `clean` script target for safe local artifact cleanup.

## Agent 9: Observability and Diagnostics

Findings:
- Baseline observability is present, but alerting verification is not automated.

Implemented:
- Preflight warns when `SENTRY_DSN` is empty.
- Health/readiness/metrics endpoints documented for ops.

Next:
- Add alert-rule checklist + smoke test for request-id propagation.

## Agent 10: Repo Hygiene and CI Guardrails

Findings:
- Repo hygiene docs and ignore rules improved.
- CI still lacks explicit artifact-policy enforcement.

Implemented:
- Added repository hygiene section in README.
- Production readiness docs tightened.

Next:
- Add CI guard that fails on committed runtime artifacts (`uploads`, logs, temp/cache outputs).

## Priority Backlog (Recommended Order)

1. Fix permission bypass by removing role-string admin checks in services/routes and enforcing permission-aware authz consistently.
2. Lock down `/api/v1/listings/recommendations` to authenticated self (or privileged actor).
3. Add privileged endpoint access matrix tests and recommendation auth tests.
4. Add one-command production gate script and CI artifact-policy check.
5. Add upload retention/cleanup routine.
