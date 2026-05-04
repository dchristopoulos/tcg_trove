# TCG Trove Demo Script

Use this as a 5-8 minute presentation path.

## Before the Demo

```powershell
cd C:\Users\dimit\Desktop\computer_science\pythonprojects\tcgtrove
python scripts\reset_demo_db.py
python scripts\dev_server.py --reload
```

Open http://127.0.0.1:8000.

If the reset command says the database is open, stop the running server and run the reset command again.

Main demo accounts:

- Buyer: `buyer` / `buyer123`
- Seller: `seller` / `seller123`
- Supervisor: `supervisor` / `supervisor123`
- Admin: `admin` / `admin`

Extra dummy users for admin/supervisor role demos: `eleni_buyer`, `george_buyer`, `sofia_buyer`, `maria_seller`, `nikos_seller`, and `reports_supervisor` all use password `demo123`.

## Demo Flow

1. Homepage
   - Show the TCG Trove homepage and point out that this is a trading-card marketplace.
   - Point out the live marketplace stats, featured card images, popular games, and role overview.

2. Register/Login
   - Open `/users/register` briefly to show account creation.
   - Go to `/login`.

3. Buyer Flow
   - Login as `buyer` / `buyer123`.
   - Open `/listings`.
   - Search/filter by a franchise such as `Pokemon`, `One Piece Card Game`, `Digimon Card Game`, `Yu-Gi-Oh!`, or `Magic`.
   - Try natural searches like `Pokemon under 50`, `secret rare one piece`, or `near mint under 10`.
   - Open a card detail page.
   - Show the real card image, card number, listing ID, game, rarity, condition, stock, seller offer table, and price history.
   - Open `/permissions` to show the role permissions matrix.
   - Click `Add to Wishlist`.
   - Click `Add to Cart`.
   - Open `/wallet`.
   - Show the top-right wallet link, wallet balance, deposit form, and unsupported withdraw request.
   - Add virtual funds if needed.
   - Open `/cart`.
   - Checkout.
   - Show order history and the generated transaction reference.
   - Logout.

4. Seller Flow
   - Login as `seller` / `seller123`.
   - Open `/listings/new`.
   - Show the quick-fill presets, image URL field, optional upload field, and image preview.
   - Click a preset, adjust the price/stock if desired, and explain that this makes new listings easy during a demo.
   - Mention sellers can create listings and view seller messages/inbox.
   - Open `/dashboard` or `/messages/inbox` to show seller-facing information.
   - Logout.

5. Supervisor Flow
   - Login as `supervisor` / `supervisor123`.
   - Open `/supervisor`.
   - Show marketplace user counts and the User Permissions table.
   - Explain that supervisors can safely switch regular users between Buyer and Seller, while Admin/Supervisor accounts are locked.
   - Open `/reports`.
   - Show total sales, cards sold, order count, revenue by month, top cards, top sellers, and payment log summary.
   - Point out average order value, active sellers, and the simple monthly revenue chart bars.
   - Logout.

6. Admin Flow
   - Login as `admin` / `admin`.
   - Open `/admin`.
   - Show user roles, listing thumbnails, listing management, marketplace metrics, operational alerts, and admin-level controls.

7. Tests
   - In PowerShell, run or show:

```powershell
python -m compileall app
python -m pytest -q
```

   - Mention the verified result: `75 passed, 1 skipped`.

## Short Closing Line

TCG Trove adapts the original HomeFinder architecture into a trading-card marketplace with authentication, roles, search, listings, wishlist, cart, wallet checkout, reports, admin tools, and a repeatable seeded demo state.
