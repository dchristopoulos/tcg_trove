# TCG Trove Testing Report

## Commands Run

```powershell
cd C:\Users\dimit\Desktop\computer_science\pythonprojects\tcgtrove
python -m compileall app
python -m pytest -q
```

## Latest Result

- `python -m compileall app`: passed
- `python -m pytest -q`: passed; one browser E2E test remains skipped by default unless `RUN_E2E=1` is set

## Automated Coverage Summary

The existing pytest suite covers:

- API health and core web pages
- Register/login/session behavior
- Role redirects and access controls
- Listing creation and validation
- Search/filter behavior, including card marketplace query parsing
- Wishlist/favorites behavior
- Cart, wallet top-up, checkout, insufficient balance, and order creation
- Seller ownership protections
- Supervisor report access
- Supervisor dashboard access and safe Buyer/Seller permission assignment
- Admin dashboard and management behaviors
- Image fallback presence on listing pages
- Seller listing creation through external image URL without local upload

## Edge Cases Checked

- Empty search does not crash
- Special card names such as `Blue-Eyes` remain searchable
- Natural queries such as `Pokemon under 50` map to franchise and max-price filtering
- Franchise-only searches work for Pokemon, Yu-Gi-Oh!, Magic, One Piece, Lorcana, and Digimon seed data
- Invalid wallet deposit amounts are rejected
- Checkout rejects empty cart, own listings, out-of-stock cards, and insufficient wallet balance
- Buyer cannot access supervisor/admin-only pages
- Seller cannot remove another seller's listing

## Manual Browser Smoke Plan

Use the local server at `http://127.0.0.1:8000` and click through:

- Homepage
- Login/register
- Buyer browse/search/detail/wishlist/cart/wallet/checkout
- Seller create listing and seller inbox
- Supervisor report
- Admin dashboard

## Manual Route Smoke Result

After restarting the stale port `8000` server, the following real local routes returned `200 OK`:

- Public: `/`, `/login`, `/users/register`, `/listings`, `/permissions`
- Buyer: `/dashboard`, `/listings?q=Pokemon+under+50`, `/listings/2`, `/wallet`, `/cart`, `/messages/my`
- Seller: `/dashboard`, `/listings/new`, `/messages/inbox`, `/wallet`
- Supervisor: `/dashboard`, `/reports`, `/listings`
- Supervisor permission dashboard: `/supervisor`
- Admin: `/dashboard`, `/admin`, `/reports`, `/listings`

Playwright is configured in `package.json`, but `node_modules` was not installed during this pass to avoid changing the local dependency state. The safe smoke check used the running FastAPI server and authenticated web sessions.

## Known Testing Limitations

- Browser visual tests are smoke-level only; the primary reliable test suite is pytest.
- Wallet payments are simulated, so tests validate database balance/order behavior rather than real payment processor calls.
- External image URLs are not downloaded during tests; templates verify fallback behavior and layout references.
