from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.models.audit_log import AuditLog  # noqa: F401
from app.db.models.email_outbox import EmailOutbox  # noqa: F401
from app.db.models.favorite import Favorite  # noqa: F401
from app.db.models.inquiry import Inquiry  # noqa: F401
from app.db.models.inquiry_message import InquiryMessage  # noqa: F401
from app.db.base import Base
from app.db.models.listing import Listing  # noqa: F401
from app.db.models.order import Order  # noqa: F401
from app.db.models.payment_log import PaymentLog  # noqa: F401
from app.db.models.rate_limit_event import RateLimitEvent  # noqa: F401
from app.db.models.reservation import Reservation  # noqa: F401
from app.db.models.search_log import SearchLog  # noqa: F401
from app.db.models.two_factor_challenge import TwoFactorChallenge  # noqa: F401
from app.db.models.user import User  # noqa: F401
from app.db.models.viewing import Viewing  # noqa: F401
from app.db.session import SessionLocal, engine
from app.web.auth import hash_password


def _seed_default_admin() -> None:
    if not settings.seed_default_admin:
        return
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == "admin").first()
        if existing is None:
            existing = db.query(User).filter(User.email == "admin@tcgtrove.com").first()
        if existing is not None:
            existing.role = "admin"
            existing.email_verified = True
            existing.must_reset_password = False
            if "@" not in str(existing.email) or str(existing.email).endswith(".local"):
                existing.email = "admin@tcgtrove.com"
            db.add(existing)
            db.commit()
            return
        admin_user = User(
            email="admin@tcgtrove.com",
            username="admin",
            password=hash_password("admin"),
            role="admin",
            email_verified=True,
            must_reset_password=False,
        )
        db.add(admin_user)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(User).filter(User.username == "admin").first()
        if existing is not None:
            existing.role = "admin"
            existing.email_verified = True
            existing.must_reset_password = False
            db.add(existing)
            db.commit()
    finally:
        db.close()


def _seed_demo_marketplace() -> None:
    if "test_tcg_trove_" in settings.database_url:
        return
    db = SessionLocal()
    try:
        def upsert_demo_user(
            *,
            email: str,
            username: str,
            password: str,
            role: str,
            balance: int = 0,
        ) -> User:
            user = db.query(User).filter(User.username == username).first()
            if user is None:
                user = db.query(User).filter(User.email == email).first()
            if user is None:
                user = User(
                    email=email,
                    username=username,
                    password=hash_password(password),
                    role=role,
                    email_verified=True,
                    must_reset_password=False,
                    balance=balance,
                )
            else:
                user.email = email
                user.role = role
                user.email_verified = True
                user.must_reset_password = False
                if user.balance is None:
                    user.balance = balance
            db.add(user)
            db.flush()
            return user

        seller = db.query(User).filter(User.username == "seller").first()
        if seller is None:
            seller = User(
                email="seller@tcgtrove.com",
                username="seller",
                password=hash_password("seller123"),
                role="seller",
                email_verified=True,
                must_reset_password=False,
                balance=0,
            )
            db.add(seller)
            db.commit()
            db.refresh(seller)

        buyer = db.query(User).filter(User.username == "buyer").first()
        if buyer is None:
            buyer = User(
                email="buyer@tcgtrove.com",
                username="buyer",
                password=hash_password("buyer123"),
                role="buyer",
                email_verified=True,
                must_reset_password=False,
                balance=25000,
            )
            db.add(buyer)

        supervisor = db.query(User).filter(User.username == "supervisor").first()
        if supervisor is None:
            supervisor = User(
                email="supervisor@tcgtrove.com",
                username="supervisor",
                password=hash_password("supervisor123"),
                role="supervisor",
                email_verified=True,
                must_reset_password=False,
                balance=0,
            )
            db.add(supervisor)
        db.commit()

        dummy_users = [
            {
                "email": "maria.seller@tcgtrove.com",
                "username": "maria_seller",
                "password": "demo123",
                "role": "seller",
                "balance": 4200,
            },
            {
                "email": "nikos.cards@tcgtrove.com",
                "username": "nikos_seller",
                "password": "demo123",
                "role": "seller",
                "balance": 7800,
            },
            {
                "email": "eleni.buyer@tcgtrove.com",
                "username": "eleni_buyer",
                "password": "demo123",
                "role": "buyer",
                "balance": 850,
            },
            {
                "email": "george.collector@tcgtrove.com",
                "username": "george_buyer",
                "password": "demo123",
                "role": "buyer",
                "balance": 1600,
            },
            {
                "email": "sofia.deckbuilder@tcgtrove.com",
                "username": "sofia_buyer",
                "password": "demo123",
                "role": "buyer",
                "balance": 2400,
            },
            {
                "email": "reports@tcgtrove.com",
                "username": "reports_supervisor",
                "password": "demo123",
                "role": "supervisor",
                "balance": 0,
            },
        ]
        extra_sellers: list[User] = []
        for user_data in dummy_users:
            seeded_user = upsert_demo_user(**user_data)
            if seeded_user.role == "seller":
                extra_sellers.append(seeded_user)
        db.commit()

        if db.query(Listing).count() > 0:
            return

        seller_pool = [seller, *extra_sellers]
        sample_cards = [
            {
                "title": "Charizard ex 228/197 - Obsidian Flames",
                "price": 30,
                "location": "Pokemon",
                "size": 2,
                "bedrooms": 2023,
                "bathrooms": 5,
                "property_type": "hyper_rare",
                "furnished": "near_mint",
                "description": "Real Pokemon TCG card data: Charizard ex 228/197 from Scarlet & Violet: Obsidian Flames. Hyper Rare demo listing, sleeved and binder stored.",
                "image_url": "https://images.pokemontcg.io/sv3/228_hires.png",
                "seller_id": seller.id,
            },
            {
                "title": "Charizard ex 125/197 - Obsidian Flames",
                "price": 8,
                "location": "Pokemon",
                "size": 6,
                "bedrooms": 2023,
                "bathrooms": 4,
                "property_type": "double_rare",
                "furnished": "lightly_played",
                "description": "Real Pokemon TCG card data: Charizard ex 125/197 from Scarlet & Violet: Obsidian Flames. Double Rare version for a lower-price buyer demo.",
                "image_url": "https://images.pokemontcg.io/sv3/125_hires.png",
                "seller_id": seller.id,
            },
            {
                "title": "Umbreon VMAX 215/203 - Evolving Skies",
                "price": 950,
                "location": "Pokemon",
                "size": 1,
                "bedrooms": 2021,
                "bathrooms": 5,
                "property_type": "secret_rare",
                "furnished": "near_mint",
                "description": "Real Pokemon TCG card data: Umbreon VMAX 215/203 from Sword & Shield: Evolving Skies. High-end Secret Rare sample for marketplace filtering.",
                "image_url": "https://images.pokemontcg.io/swsh7/215_hires.png",
                "seller_id": seller.id,
            },
            {
                "title": "Blue-Eyes White Dragon SDK-001 - Starter Deck Kaiba",
                "price": 120,
                "location": "Yu-Gi-Oh!",
                "size": 1,
                "bedrooms": 2002,
                "bathrooms": 4,
                "property_type": "ultra_rare",
                "furnished": "lightly_played",
                "description": "Real Yu-Gi-Oh! card data: Blue-Eyes White Dragon SDK-001 from Starter Deck: Kaiba. Ultra Rare classic with light edge wear.",
                "image_url": "https://images.ygoprodeck.com/images/cards/89631139.jpg",
                "seller_id": seller.id,
            },
            {
                "title": "Dark Magician SDY-006 - Starter Deck Yugi",
                "price": 75,
                "location": "Yu-Gi-Oh!",
                "size": 2,
                "bedrooms": 2002,
                "bathrooms": 4,
                "property_type": "ultra_rare",
                "furnished": "moderately_played",
                "description": "Real Yu-Gi-Oh! card data: Dark Magician SDY-006 from Starter Deck: Yugi. A recognizable Ultra Rare listing for seller and search demos.",
                "image_url": "https://images.ygoprodeck.com/images/cards/46986414.jpg",
                "seller_id": seller.id,
            },
            {
                "title": "Exodia the Forbidden One LOB-124 - Legend of Blue Eyes",
                "price": 180,
                "location": "Yu-Gi-Oh!",
                "size": 1,
                "bedrooms": 2002,
                "bathrooms": 5,
                "property_type": "ultra_rare",
                "furnished": "lightly_played",
                "description": "Real Yu-Gi-Oh! card data: Exodia the Forbidden One LOB-124 from Legend of Blue Eyes White Dragon. Collectible Ultra Rare demo listing.",
                "image_url": "https://images.ygoprodeck.com/images/cards/33396948.jpg",
                "seller_id": seller.id,
            },
            {
                "title": "Black Lotus - Limited Edition Alpha",
                "price": 500000,
                "location": "Magic: The Gathering",
                "size": 1,
                "bedrooms": 1993,
                "bathrooms": 5,
                "property_type": "rare",
                "furnished": "moderately_played",
                "description": "Real Magic: The Gathering card data: Black Lotus from Limited Edition Alpha, released in 1993. Premium showcase listing with simulated pricing.",
                "image_url": "https://cards.scryfall.io/normal/front/b/0/b0faa7f2-b547-42c4-a810-839da50dadfe.jpg?1559591477",
                "seller_id": seller.id,
            },
            {
                "title": "Mox Sapphire - Limited Edition Alpha",
                "price": 180000,
                "location": "Magic: The Gathering",
                "size": 1,
                "bedrooms": 1993,
                "bathrooms": 5,
                "property_type": "rare",
                "furnished": "near_mint",
                "description": "Real Magic: The Gathering card data: Mox Sapphire from Limited Edition Alpha. Rare Power Nine card included as a high-value marketplace example.",
                "image_url": "https://cards.scryfall.io/normal/front/8/2/82da0972-b17b-4600-9efd-e9430a0db04b.jpg?1559591414",
                "seller_id": seller.id,
            },
            {
                "title": "Shivan Dragon - Limited Edition Alpha",
                "price": 2500,
                "location": "Magic: The Gathering",
                "size": 1,
                "bedrooms": 1993,
                "bathrooms": 4,
                "property_type": "rare",
                "furnished": "lightly_played",
                "description": "Real Magic: The Gathering card data: Shivan Dragon from Limited Edition Alpha. Classic Rare creature card for collectible inventory demos.",
                "image_url": "https://cards.scryfall.io/normal/front/f/e/fefbf149-f988-4f8b-9f53-56f5878116a6.jpg?1559591401",
                "seller_id": seller.id,
            },
            {
                "title": "Monkey.D.Luffy OP01-003 - Romance Dawn",
                "price": 6,
                "location": "One Piece Card Game",
                "size": 8,
                "bedrooms": 2022,
                "bathrooms": 3,
                "property_type": "leader",
                "furnished": "near_mint",
                "description": "Real One Piece Card Game data: Monkey.D.Luffy OP01-003 from OP-01 Romance Dawn. Leader card listing with multiple demo-stock copies.",
                "image_url": "https://devilfruittcg.gg/api/card-image?id=OP01-003",
                "seller_id": seller.id,
            },
            {
                "title": "Nami OP01-016 - Romance Dawn",
                "price": 5,
                "location": "One Piece Card Game",
                "size": 5,
                "bedrooms": 2022,
                "bathrooms": 3,
                "property_type": "rare",
                "furnished": "near_mint",
                "description": "Real One Piece Card Game data: Nami OP01-016 from OP-01 Romance Dawn. Rare Straw Hat Crew card used for affordable checkout demos.",
                "image_url": "https://devilfruittcg.gg/api/card-image?id=OP01-016",
                "seller_id": seller.id,
            },
            {
                "title": "Roronoa Zoro OP01-001 - Romance Dawn",
                "price": 12,
                "location": "One Piece Card Game",
                "size": 3,
                "bedrooms": 2022,
                "bathrooms": 4,
                "property_type": "leader",
                "furnished": "near_mint",
                "description": "Real One Piece Card Game data: Roronoa Zoro OP01-001 from OP-01 Romance Dawn. Leader card listing for same-franchise discovery.",
                "image_url": "https://devilfruittcg.gg/api/card-image?id=OP01-001",
                "seller_id": seller.id,
            },
            {
                "title": "Elsa - Spirit of Winter 42/204 - The First Chapter",
                "price": 110,
                "location": "Disney Lorcana",
                "size": 2,
                "bedrooms": 2023,
                "bathrooms": 5,
                "property_type": "legendary",
                "furnished": "near_mint",
                "description": "Real Disney Lorcana card data: Elsa - Spirit of Winter 42/204 from The First Chapter. Legendary card listing with clean demo metadata.",
                "image_url": "https://cards.lorcast.io/card/digital/normal/crd_04bca46a8e2d4e9ba0fbdbfc6c99e51e.avif?1709690747",
                "seller_id": seller.id,
            },
            {
                "title": "Stitch - Rock Star 23/204 - The First Chapter",
                "price": 35,
                "location": "Disney Lorcana",
                "size": 4,
                "bedrooms": 2023,
                "bathrooms": 4,
                "property_type": "super_rare",
                "furnished": "lightly_played",
                "description": "Real Disney Lorcana card data: Stitch - Rock Star 23/204 from The First Chapter. Super Rare listing for Lorcana search demos.",
                "image_url": "https://cards.lorcast.io/card/digital/normal/crd_c32945ecfd3d44859d3af3841977a737.avif?1709690747",
                "seller_id": seller.id,
            },
            {
                "title": "Mickey Mouse - Brave Little Tailor 115/204",
                "price": 2,
                "location": "Disney Lorcana",
                "size": 10,
                "bedrooms": 2023,
                "bathrooms": 2,
                "property_type": "legendary",
                "furnished": "near_mint",
                "description": "Real Disney Lorcana card data: Mickey Mouse - Brave Little Tailor 115/204 from The First Chapter. Low-cost listing for cart demos.",
                "image_url": "https://cards.lorcast.io/card/digital/normal/crd_e74ef94562b9440e8dd95ada098728d6.avif?1709690747",
                "seller_id": seller.id,
            },
            {
                "title": "Pikachu GG30/GG70 - Crown Zenith Galarian Gallery",
                "price": 12,
                "location": "Pokemon",
                "size": 5,
                "bedrooms": 2023,
                "bathrooms": 4,
                "property_type": "trainer_gallery_rare_holo",
                "furnished": "near_mint",
                "description": "Real Pokemon TCG card data: Pikachu GG30/GG70 from Crown Zenith Galarian Gallery. Affordable popular card for search and checkout demos.",
                "image_url": "https://images.pokemontcg.io/swsh12pt5gg/GG30_hires.png",
                "seller_id": seller.id,
            },
            {
                "title": "Mewtwo VSTAR GG44/GG70 - Crown Zenith Galarian Gallery",
                "price": 65,
                "location": "Pokemon",
                "size": 2,
                "bedrooms": 2023,
                "bathrooms": 5,
                "property_type": "rare_holo_vstar",
                "furnished": "near_mint",
                "description": "Real Pokemon TCG card data: Mewtwo VSTAR GG44/GG70 from Crown Zenith Galarian Gallery. Rare Holo VSTAR sample listing with real card artwork.",
                "image_url": "https://images.pokemontcg.io/swsh12pt5gg/GG44_hires.png",
                "seller_id": seller.id,
            },
            {
                "title": "Lugia V 186/195 - Silver Tempest",
                "price": 150,
                "location": "Pokemon",
                "size": 1,
                "bedrooms": 2022,
                "bathrooms": 5,
                "property_type": "rare_ultra",
                "furnished": "lightly_played",
                "description": "Real Pokemon TCG card data: Lugia V 186/195 from Sword & Shield: Silver Tempest. Rare Ultra card listing for premium Pokemon filtering.",
                "image_url": "https://images.pokemontcg.io/swsh12/186_hires.png",
                "seller_id": seller.id,
            },
            {
                "title": "Giratina V 186/196 - Lost Origin",
                "price": 290,
                "location": "Pokemon",
                "size": 1,
                "bedrooms": 2022,
                "bathrooms": 5,
                "property_type": "rare_ultra",
                "furnished": "near_mint",
                "description": "Real Pokemon TCG card data: Giratina V 186/196 from Sword & Shield: Lost Origin. High-value Rare Ultra listing for demo analytics.",
                "image_url": "https://images.pokemontcg.io/swsh11/186_hires.png",
                "seller_id": seller.id,
            },
            {
                "title": "Gengar VMAX 271/264 - Fusion Strike",
                "price": 80,
                "location": "Pokemon",
                "size": 2,
                "bedrooms": 2021,
                "bathrooms": 5,
                "property_type": "rare_rainbow",
                "furnished": "near_mint",
                "description": "Real Pokemon TCG card data: Gengar VMAX 271/264 from Sword & Shield: Fusion Strike. Rare Rainbow listing for Pokemon collection browsing.",
                "image_url": "https://images.pokemontcg.io/swsh8/271_hires.png",
                "seller_id": seller.id,
            },
            {
                "title": "Shanks OP01-120 - Romance Dawn",
                "price": 60,
                "location": "One Piece Card Game",
                "size": 2,
                "bedrooms": 2022,
                "bathrooms": 5,
                "property_type": "secret_rare",
                "furnished": "near_mint",
                "description": "Real One Piece Card Game data: Shanks OP01-120 from OP-01 Romance Dawn. Secret Rare listing with official card artwork.",
                "image_url": "https://devilfruittcg.gg/api/card-image?id=OP01-120",
                "seller_id": seller.id,
            },
            {
                "title": "Trafalgar Law OP01-002 - Romance Dawn",
                "price": 9,
                "location": "One Piece Card Game",
                "size": 6,
                "bedrooms": 2022,
                "bathrooms": 4,
                "property_type": "leader",
                "furnished": "near_mint",
                "description": "Real One Piece Card Game data: Trafalgar Law OP01-002 from OP-01 Romance Dawn. Leader card listing for same-game discovery.",
                "image_url": "https://devilfruittcg.gg/api/card-image?id=OP01-002",
                "seller_id": seller.id,
            },
            {
                "title": "Roronoa Zoro OP01-025 - Romance Dawn",
                "price": 20,
                "location": "One Piece Card Game",
                "size": 4,
                "bedrooms": 2022,
                "bathrooms": 4,
                "property_type": "super_rare",
                "furnished": "lightly_played",
                "description": "Real One Piece Card Game data: Roronoa Zoro OP01-025 from OP-01 Romance Dawn. Super Rare card for One Piece search demos.",
                "image_url": "https://devilfruittcg.gg/api/card-image?id=OP01-025",
                "seller_id": seller.id,
            },
            {
                "title": "Portgas.D.Ace OP02-013 - Paramount War",
                "price": 18,
                "location": "One Piece Card Game",
                "size": 4,
                "bedrooms": 2023,
                "bathrooms": 4,
                "property_type": "super_rare",
                "furnished": "near_mint",
                "description": "Real One Piece Card Game data: Portgas.D.Ace OP02-013 from OP-02 Paramount War. Super Rare listing with real card image.",
                "image_url": "https://devilfruittcg.gg/api/card-image?id=OP02-013",
                "seller_id": seller.id,
            },
            {
                "title": "Yamato OP01-121 - Romance Dawn",
                "price": 35,
                "location": "One Piece Card Game",
                "size": 3,
                "bedrooms": 2022,
                "bathrooms": 5,
                "property_type": "secret_rare",
                "furnished": "near_mint",
                "description": "Real One Piece Card Game data: Yamato OP01-121 from OP-01 Romance Dawn. Secret Rare listing for higher-value One Piece filtering.",
                "image_url": "https://devilfruittcg.gg/api/card-image?id=OP01-121",
                "seller_id": seller.id,
            },
            {
                "title": "Rayquaza VMAX 218/203 - Evolving Skies",
                "price": 315,
                "location": "Pokemon",
                "size": 1,
                "bedrooms": 2021,
                "bathrooms": 5,
                "property_type": "secret_rare",
                "furnished": "near_mint",
                "description": "Real Pokemon TCG card data: Rayquaza VMAX 218/203 from Sword & Shield: Evolving Skies. Premium Secret Rare listing with verified external artwork.",
                "image_url": "https://images.pokemontcg.io/swsh7/218_hires.png",
                "seller_id": seller.id,
            },
            {
                "title": "Mew ex 232/091 - Paldean Fates",
                "price": 92,
                "location": "Pokemon",
                "size": 2,
                "bedrooms": 2024,
                "bathrooms": 5,
                "property_type": "special_illustration_rare",
                "furnished": "near_mint",
                "description": "Real Pokemon TCG card data: Mew ex 232/091 from Scarlet & Violet: Paldean Fates. Special Illustration Rare listing for modern Pokemon discovery.",
                "image_url": "https://images.pokemontcg.io/sv4pt5/232_hires.png",
                "seller_id": seller.id,
            },
            {
                "title": "Dark Magician Girl MFC-000 - Magician's Force",
                "price": 140,
                "location": "Yu-Gi-Oh!",
                "size": 1,
                "bedrooms": 2003,
                "bathrooms": 5,
                "property_type": "secret_rare",
                "furnished": "near_mint",
                "description": "Real Yu-Gi-Oh! card data: Dark Magician Girl from Magician's Force. Secret Rare classic with verified YGOPRODeck artwork.",
                "image_url": "https://images.ygoprodeck.com/images/cards/38033121.jpg",
                "seller_id": seller.id,
            },
        ]
        for index, item in enumerate(sample_cards):
            item["seller_id"] = seller_pool[index % len(seller_pool)].id
            listing = Listing(**item)
            db.add(listing)
            db.flush()
            from app.db.models.listing import ListingPriceHistory

            db.add(ListingPriceHistory(listing_id=listing.id, price=listing.price))
        db.commit()
    finally:
        db.close()


def init_db() -> None:
    """Create local tables and seed demo users/card listings for the university project."""
    Base.metadata.create_all(bind=engine)
    _seed_default_admin()
    _seed_demo_marketplace()
