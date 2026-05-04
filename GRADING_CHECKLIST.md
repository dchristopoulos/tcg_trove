# TCG Trove Grading Checklist

| Requirement | Status | Where to Demo | Test Coverage / Notes |
| --- | --- | --- | --- |
| Register | Done | `/users/register` | Covered by web/auth tests |
| Login/logout | Done | `/login`, navbar logout | Covered by web/auth tests |
| Email confirmation | Partial/simulated | Auth/account flow | Local email/outbox style flow; no real SMTP required |
| 2FA | Partial/inherited | Auth services/models | Not part of main demo path |
| Buyer role | Done | `buyer` / `buyer123` | Role tests cover buyer restrictions |
| Seller role | Done | `seller` / `seller123` | Seller create/ownership tests |
| Supervisor role | Done | `supervisor` / `supervisor123`, `/reports` | Report access tests |
| Supervisor dashboard | Done | `/supervisor` | Supervisor page and permission update tests |
| Supervisor selects permissions | Done for Buyer/Seller | `/supervisor` User Permissions table | Test verifies Buyer-to-Seller update and blocks Admin assignment |
| Admin role | Done | `admin` / `admin`, `/admin` | Admin access tests |
| Browse cards | Done | `/listings` | Web page tests |
| Search cards | Done | `/listings?q=Pokemon+under+50` | Search/filter tests |
| Filter cards | Done | Browse filter panel | Filter edge cases covered |
| Same-game discovery | Done | Card detail page | Manual/browser smoke target |
| Wishlist/favorites | Done | Save button on listing/detail pages | Favorite tests |
| Card detail page | Done | `/listings/{id}` | Page-load tests |
| Seller listings embedded on card page | Done | Seller Offer table on detail page | Manual/browser smoke target |
| Seller contact | Done | Detail page contact form/messages | Inquiry/message tests |
| Price history | Done | Detail page price history area | Database price history support |
| Cart | Done | `/cart` | Cart tests |
| Wallet balance | Done | `/wallet`, top-right wallet nav | Wallet tests |
| Deposit | Done/simulated | `/wallet` | Valid/invalid amount tests |
| Withdraw | Shown as unsupported | `/wallet` | Documented limitation |
| Checkout simulation | Done | `/cart` checkout | Checkout success/failure tests |
| Payment/order logs | Done | `/cart`, `/wallet`, `/reports` | Order/payment behavior tests |
| Order history | Done | `/cart`, `/wallet` | Checkout/order tests |
| Seller create listing | Done | `/listings/new` | Listing validation plus image-URL listing test |
| Seller edit/remove own listings | Partial | Dashboard/inherited flows, admin full management | Ownership protection covered |
| Supervisor monthly report | Done | `/reports` | Report access tests |
| Top cards/top sellers | Done | `/reports` | Uses actual order data |
| Admin dashboard | Done | `/admin` | Admin tests |
| Permissions tab | Done | `/permissions` | Page available to all users |
| Real card data/images | Done | Homepage, browse, detail, admin | Seeded fixed data; fallback image behavior |
| Documentation | Done | README, DEMO_SCRIPT, SCREENSHOT_CHECKLIST, PROJECT_AUDIT, UX_RESEARCH_NOTES, TESTING_REPORT | Honest limitations documented |

## Notes for Marking

TCG Trove intentionally keeps the original FastAPI/Jinja/SQLAlchemy architecture. Some internal database column names are inherited, but user-facing pages present card marketplace concepts: cards, listings, sellers, wallet, cart, order history, reports, and admin controls.
