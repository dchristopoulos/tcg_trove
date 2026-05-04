# TCG Trove Project Audit

Date: 2026-05-04

## 1. Architecture Summary

TCG Trove is a FastAPI application using SQLAlchemy ORM, SQLite for local demo data, Jinja2 templates for server-rendered HTML, and a small plain JavaScript/CSS frontend layer. The project has both HTML routes under `app/web/routers/` and JSON API routes under `app/api/v1/routers/`.

The marketplace was adapted from a HomeFinder-style listing architecture. The UI now presents card marketplace concepts, but several inherited internal column names remain, especially:

- `location` = game/franchise
- `size` = stock
- `bedrooms` = release year
- `bathrooms` = rarity score
- `property_type` = rarity
- `furnished` = condition

This mapping is workable for a university demo but remains the largest technical clarity risk.

## 2. Folder Structure Summary

- `app/api/v1/routers/`: JSON API endpoints for users, listings, favorites, inquiries/messages, reports, payments, search, reservations, and viewings.
- `app/core/`: settings, logging, metrics, utility functions, production preflight checks.
- `app/db/models/`: SQLAlchemy models.
- `app/db/init_db.py`: demo seed data and table initialization.
- `app/managers/`: database access helpers.
- `app/schemas/`: Pydantic schemas.
- `app/services/`: business/use-case layer.
- `app/static/`: CSS, JavaScript, favicon, placeholder SVG, uploads.
- `app/templates/`: Jinja2 pages.
- `app/web/routers/`: HTML page routes.
- `scripts/`: local server, reset, backup, restore, production preflight, maintenance helpers.
- `tests/`: pytest integration and smoke tests.
- `frontend/`: inherited separate frontend folder; not the primary demo surface.

## 3. Database Models

Detected SQLAlchemy model classes:

- `AuditLog`
- `EmailOutbox`
- `Favorite`
- `Inquiry`
- `InquiryMessage`
- `Listing`
- `ListingPriceHistory`
- `Order`
- `PaymentLog`
- `RateLimitEvent`
- `Reservation`
- `SearchLog`
- `TwoFactorChallenge`
- `User`
- `Viewing`

Core demo-relevant models are `User`, `Listing`, `ListingPriceHistory`, `Favorite`, `Inquiry`, `InquiryMessage`, `Order`, `PaymentLog`, and `SearchLog`.

Models still present from inherited architecture include `Reservation` and `Viewing`; they are not central to the TCG marketplace demo and create naming noise.

## 4. Main Routes / Pages

Important HTML routes:

- `/`: homepage
- `/users/register`: register
- `/login`: login
- `/logout`: logout POST
- `/dashboard`: role dashboard
- `/listings`: browse/search/filter cards
- `/listings/new`: create card listing
- `/listings/{listing_id}`: card detail
- `/listings/{listing_id}/save`: wishlist add POST
- `/listings/{listing_id}/unsave`: wishlist remove POST
- `/listings/compare`: comparison flow
- `/listings/decision-lab`: inherited decision helper
- `/cart`: cart/order history
- `/cart/add/{listing_id}`: add to cart POST
- `/cart/remove/{listing_id}`: remove from cart POST
- `/wallet`: wallet
- `/wallet/add`: virtual deposit POST
- `/wallet/withdraw`: unsupported withdrawal POST
- `/checkout`: simulated checkout POST
- `/permissions`: role permissions matrix
- `/messages/my`: buyer messages
- `/messages/inbox`: seller inbox
- `/reports`: supervisor reports
- `/admin`: admin dashboard
- `/account`: account settings

Important JSON API route groups:

- `/api/v1/listings`
- `/api/v1/search`
- `/api/v1/users`
- `/api/v1/favorites`
- `/api/v1/inquiries`
- `/api/v1/payments`
- `/api/v1/reports`
- `/api/v1/gdpr`

## 5. Templates List

Templates detected:

- `404.html`
- `500.html`
- `account.html`
- `admin.html`
- `base.html`
- `cart.html`
- `change_password.html`
- `create_listing.html`
- `dashboard.html`
- `decision_lab.html`
- `forgot_password.html`
- `home.html`
- `listing_detail.html`
- `listings_compare.html`
- `listings.html`
- `login.html`
- `messages_contact.html`
- `messages_inbox.html`
- `messages_my.html`
- `permissions.html`
- `register.html`
- `reports.html`
- `reset_password.html`
- `user_profile.html`
- `wallet.html`

Most templates currently use inline `<style>` blocks. That makes quick iteration easy, but it fragments the design system and makes long-term polish harder.

## 6. Static Assets List

Static files detected:

- `app.js` around 19 KB
- `styles.css` around 24.5 KB
- `styles.min.css` around 24.5 KB
- `ux-metrics.js` around 3.4 KB
- `favicon.svg`
- `listing-placeholder.svg`
- upload images under `app/static/uploads/`

Card listing images are mostly external curated URLs with `onerror` fallback to the local placeholder.

## 7. Auth / Session / Role System Summary

Auth is implemented with server sessions and CSRF-protected forms. Demo roles are:

- Buyer
- Seller
- Supervisor
- Admin

The account system includes login, registration, password reset/change pages, email outbox support, permission grants/revokes, and two-factor challenge model/service support. Role checks exist in both HTML and API layers. The `/permissions` page explains role capabilities.

Current visible demo accounts:

- `buyer` / `buyer123`
- `seller` / `seller123`
- `supervisor` / `supervisor123`
- `admin` / `admin`

## 8. Existing Tests Summary

Baseline command results:

- `python -m compileall app`: passed
- `python -m pytest -q`: `75 passed, 1 skipped`

Test files and approximate test counts:

- `tests/test_api.py`: 56 tests
- `tests/test_config.py`: 5 tests
- `tests/test_load_smoke.py`: 1 test
- `tests/test_production_preflight.py`: 7 tests
- `tests/test_ux_events.py`: 2 tests
- `tests/e2e/test_web_e2e.py`: 1 test

Coverage appears strongest around API behavior, auth/permissions, listing flows, messages, and production checks. Browser/UI tests are present but limited.

## 9. Current UI/UX Weaknesses

Ranked observations:

1. Design styles are split across global CSS and many inline template blocks.
2. Role navigation is present but can be clearer and more role-specific.
3. Browse/search is functional but could better expose active filters, sorting, result counts, and direct cart/wishlist actions.
4. Card detail page is improved but still represents one listing more than a true product page with multiple seller offers.
5. Cart/wallet is usable but could better show checkout steps, transaction states, and simulated-payment disclaimers.
6. Seller dashboard/create listing flow could be more clearly card-specific.
7. Supervisor/admin pages exist but should visually emphasize KPIs, tables, and grading-relevant reports.
8. Some buttons and helper text still feel generic.
9. Mobile layout should be smoke-tested across the main role pages.
10. External images need lazy loading and consistent fallback behavior everywhere.

## 10. Current Technical Risks

1. Inherited database field names are semantically mismatched with card marketplace concepts.
2. Inherited `viewings` and `reservations` routes/models may confuse graders if exposed in API docs.
3. Tests still contain real-estate sample data and expected strings.
4. Some API schemas still expose `bedrooms`, `bathrooms`, `property_type`, and `furnished`.
5. There are existing Node/Playwright/a11y scripts in `package.json`, but they may need verification before relying on them.
6. `styles.min.css` appears similar in size to `styles.css`; minification may not be currently meaningful.
7. External images depend on third-party availability; fallback is present but should be documented.

## 11. Remaining Real-Estate / HomeFinder Leftovers

User-facing docs still mention HomeFinder intentionally as the reference architecture. Internal and test leftovers include:

- `Reservation` / `Viewing` models and API routes.
- Query parameters such as `min_bedrooms`, `max_bathrooms`, `furnished`.
- Tests using apartment/house/studio examples.
- Text like "Any furnishing", "properties", "viewing", and "property seller" in tests and some compatibility messages.
- Internal schema fields `property_type`, `bedrooms`, `bathrooms`, `size`, `location`, and `furnished`.

Risk recommendation: avoid a full schema rename because it is high-risk and would touch many tests/routes. Prefer user-facing copy cleanup, docs honesty, and adapter/helper naming where safe.

## 12. Accessibility Issues Likely Present

Likely issues to review:

- Inline focus styling consistency across buttons/links/forms.
- Tables may need captions or clearer headings on admin/report pages.
- Some icon-only or visual state controls may need accessible names.
- Error messages may not always be programmatically associated with fields.
- External card images have alt text in key templates, but all image placements should be checked.
- Color contrast needs browser inspection, especially badges and muted text.
- Dynamic toast messages exist; the toast stack has live-region attributes, which is good.
- Mobile menu and keyboard navigation need smoke verification.

## 13. Highest-Value Improvements Ranked By Impact / Risk

1. Clean navigation and page-level copy so each role flow is obvious. Low risk, high grading value.
2. Move repeated UI patterns toward a small design system: buttons, badges, cards, metric panels, empty states. Medium risk, high value.
3. Polish homepage, browse/search, card detail, cart/wallet, reports, and admin pages. Medium risk, very high value.
4. Add active filter chips, sorting, and better empty states on browse. Medium risk, high value.
5. Improve seller dashboard/create listing labels and validation copy. Low-medium risk, high value.
6. Improve supervisor reports and seed demo orders if needed. Medium risk, high grading value.
7. Add focused tests for new UI/user flows and edge cases. Low-medium risk, high confidence value.
8. Browser smoke and accessibility review with existing Playwright tooling if available. Medium setup risk, useful if stable.
9. Internal schema rename from real-estate names to card names. High risk; reject for this polish pass unless absolutely necessary.

## 14. Baseline Test Results

Commands run before code changes:

```powershell
python -m compileall app
python -m pytest -q
```

Results:

- Compile: passed
- Tests: `75 passed, 1 skipped`

Manual checkpoint:

- No git repository found.
- Created `checkpoints\2026-05-04-baseline-checkpoint.md`.
