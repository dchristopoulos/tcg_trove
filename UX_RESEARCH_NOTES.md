# TCG Trove UX Research Notes

Date: 2026-05-04

## Sources Reviewed

- Baymard Institute, Product Page UX 2026: `https://baymard.com/blog/current-state-ecommerce-product-page-ux`
- Baymard Institute, Product Lists & Filtering UX: `https://baymard.com/research/ecommerce-product-lists`
- Nielsen Norman Group, Ecommerce Search, Filters, and Routing Pages: `https://www.nngroup.com/reports/ecommerce-ux-search-including-faceted-search/`
- Nielsen Norman Group, Ecommerce Product Pages: `https://www.nngroup.com/articles/ecommerce-product-pages/`
- WCAG 2.2 Quick Reference: `https://www.w3.org/WAI/WCAG22/quickref/`
- FastAPI templates: `https://fastapi.tiangolo.com/advanced/templates/`
- FastAPI testing: `https://fastapi.tiangolo.com/tutorial/testing/`
- Playwright accessibility testing: `https://playwright.dev/docs/accessibility-testing`
- Playwright MCP docs: `https://playwright.dev/docs/getting-started-mcp`
- Microsoft Playwright MCP repository: `https://github.com/microsoft/playwright-mcp`
- Chart.js documentation: `https://www.chartjs.org/docs/latest/`
- Scryfall API/image docs: `https://scryfall.com/docs/api` and `https://scryfall.com/docs/api/images`
- YGOPRODeck API guide: `https://ygoprodeck.com/api-guide/`
- TCGplayer marketplace/seller pages: `https://www.tcgplayer.com/`, `https://seller.tcgplayer.com/`
- Cardmarket and new user guide: `https://www.cardmarket.com/en`, `https://help.cardmarket.com/en/new-user-guide`

## Useful Patterns Found

### Ecommerce Product Lists / Search

Baymard and NN/g both emphasize that users need to quickly find and compare products. For TCG Trove this means:

- Search should be prominent and tolerant of names, franchise terms, rarity, condition, and price phrasing.
- Product/listing cards should show consistent comparable data: image, name, game, rarity, condition, stock, seller/price, and action.
- Filters should show result count, active state, reset path, and no-result recovery.
- Quick actions such as wishlist and add-to-cart should provide immediate feedback.

### Product Detail Pages

NN/g states product pages need recognizable images, descriptive names, price, availability, options, cart feedback, and concise product information. Baymard highlights product-page weaknesses around hidden options, weak images, save/wishlist friction, total cost clarity, and unclear policy/support information.

For TCG Trove this means:

- The detail page should look like a card product page, not just a generic listing.
- Card image, card number, game, set/rarity/condition, stock, seller, and price need to be easy to scan.
- Related cards should include images.
- Wishlist/add-to-cart should be async where possible.
- Simulated wallet/checkout limitations should be clear near purchase surfaces.

### Cart / Checkout / Wallet

Ecommerce checkout UX favors clear totals, no hidden costs, persistent cart feedback, and understandable error states. For TCG Trove:

- Cart subtotal and wallet balance should be close together.
- Empty cart, insufficient funds, stock unavailable, and own-listing purchase errors should be visible.
- Wallet deposit should be clearly simulated.
- Withdraw should remain unsupported and explained, not pretended.

### Dashboards / Reports

Dashboard/reporting UI should prioritize KPIs, trends, top lists, and recent logs. For TCG Trove:

- Supervisor reports should lead with revenue, orders, cards sold, average order, active sellers.
- Tables need headings/captions and clear empty states.
- CSS bars or simple charts are enough; Chart.js is optional.

### Accessibility / WCAG 2.2

WCAG 2.2 quick reference reinforces:

- Text alternatives for non-text content.
- Keyboard accessible controls.
- Visible focus.
- Labels or instructions for form inputs.
- Error identification.
- Sufficient contrast.
- No color-only meaning.
- Semantic headings and tables.

For this project, focus should be on labels, focus states, alt text, table captions, contrast, and clear form errors rather than adding a new accessibility dependency.

### FastAPI + Jinja2

FastAPI’s template guidance supports the existing architecture: use `Jinja2Templates`, pass `request` to templates, and keep server-rendered pages simple. FastAPI’s testing guidance supports the existing `TestClient` approach.

### Playwright / Browser Testing

Playwright accessibility docs recommend automated scans using Axe where configured. This project already has Playwright-related dev dependencies in `package.json`, including `@axe-core/playwright`, but the Python pytest suite is currently the stable baseline. Use the in-app browser for smoke testing and avoid making fragile browser tests mandatory unless the existing Node setup is verified.

### Chart.js

Chart.js is a good option for simple report charts, but adding a runtime dependency or CDN is unnecessary if CSS bars/tables are already understandable. For a university demo, local CSS bars are lower-risk.

### Trading-Card Marketplace Inspiration

TCGplayer and Cardmarket suggest common marketplace concepts:

- Product/card identity and set/game context.
- Seller offers attached to a card.
- Condition and language matter.
- Trust and marketplace flow matter.
- Seller tools should focus on inventory and orders.

Do not scrape these sites or depend on their APIs. Use only as flow inspiration.

## What Applies To TCG Trove

- Make route flows obvious for graders.
- Improve homepage, browse/search, detail, cart/wallet, reports, and admin as the main grading surfaces.
- Use consistent badges for game, rarity, condition, stock, and simulated wallet states.
- Ensure active filters and no-result recovery are visible.
- Keep card images stable, lazy-loaded, alt-texted, and fallback-safe.
- Make role navigation clearer without adding dead links.
- Keep existing TestClient tests and add focused tests for the safer improvements.

## What Should Not Be Implemented

- Real payment processing.
- Live price APIs at runtime.
- Scraping TCGplayer/Cardmarket.
- Full schema rename from inherited listing fields to card fields; this would be high-risk and test-heavy.
- React/Next/Tailwind/Vite rebuild.
- Complex product review/rating systems.
- Guest wishlist/cart persistence overhaul.
- Heavy visual regression setup unless the existing Playwright setup proves already stable.

## Specific UI Improvements To Make

1. Create reusable CSS classes for page heads, badges, product/card grids, metric cards, empty states, and tables.
2. Clean the base navigation by role and remove dead/noisy links where possible.
3. Improve homepage with stats, featured cards, popular games, role explanation, and simulation disclaimer.
4. Improve browse page with active filter chips, min/max price, sorting, better card actions, and clearer empty state.
5. Improve detail page with a seller-offer area, card metadata, related image cards, and async cart feedback.
6. Improve cart/wallet with clear steps, simulated-payment disclaimer, and transaction/order summary.
7. Improve supervisor reports with KPI cards and CSS revenue bars.
8. Improve admin dashboard with high-signal summaries and role distribution.
9. Add `loading="lazy"` and dimensions/aspect rules to card images.
10. Improve form labels/helper text and visible focus states.

## Specific Tests To Add

- Browse page handles weird characters and no results.
- Detail page includes image fallback and card number/listing ID.
- Async add-to-cart returns JSON for fetch requests.
- Wallet deposit rejects invalid amounts.
- Withdraw stays unsupported.
- Buyer cannot access reports/admin.
- Supervisor can access reports.
- Admin can access admin.
- Report page loads with seeded/demo order data.
- Core pages have no obvious real-estate terms in visible HTML.

## Dependencies / MCPs Considered

Accepted:

- Existing Python/FastAPI/Jinja/pytest stack.
- Existing in-app browser tooling for smoke checks.
- Existing external card image URLs with fallback behavior.

Rejected for now:

- New frontend framework: too large and risky.
- New payment libraries: out of scope and unsafe for a simulation.
- Runtime card APIs: would make the demo network-dependent.
- Chart.js dependency/CDN: useful but not necessary; CSS bars and tables are safer.
- Additional MCP installation: current browser/search/filesystem tooling is enough.
- Mandatory Playwright/Axe test expansion: package scripts exist, but pytest is the stable grading command.

## Implementation Priorities

1. Low-risk UI polish and copy cleanup.
2. Role navigation and grading path clarity.
3. Browse/detail/cart/wallet/report/admin improvements.
4. Seed/report data quality if needed.
5. Focused tests.
6. Documentation package.
