"""
Seed Script — Initializes the $1M Shadow Portfolio in MongoDB.

Run with: cd finvibe && python -m scripts.seed_portfolio
"""
from datetime import datetime, timezone
from backend.deps import get_portfolios_col
from backend.config import settings


def seed_shadow_portfolio():
    """Insert the initial $1M shadow portfolio if it doesn't exist."""

    existing = get_portfolios_col().find_one({
        "user_id": "finvibe-agent",
        "portfolio_type": "shadow",
    })

    if existing:
        print(f"[Seed] Shadow portfolio already exists (cash=${existing.get('cash_balance', 0):,.2f})")
        return

    portfolio_doc = {
        "user_id": "finvibe-agent",
        "portfolio_type": "shadow",
        "holdings": [],
        "cash_balance": settings.shadow_portfolio_cash,
        "total_value": settings.shadow_portfolio_cash,
        "inception_date": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    result = get_portfolios_col().insert_one(portfolio_doc)
    print(f"[Seed] Created shadow portfolio:")
    print(f"  ID: {result.inserted_id}")
    print(f"  Cash: ${settings.shadow_portfolio_cash:,.2f}")
    print(f"  Type: shadow")


def seed_demo_user_portfolio():
    """Insert a demo user portfolio with some sample holdings."""

    existing = get_portfolios_col().find_one({
        "user_id": "demo",
        "portfolio_type": "user",
    })

    if existing:
        print(f"[Seed] Demo user portfolio already exists")
        return

    portfolio_doc = {
        "user_id": "demo",
        "portfolio_type": "user",
        "holdings": [
            {"ticker": "AAPL", "shares": 50, "avg_cost": 178.50, "current_price": 0},
            {"ticker": "MSFT", "shares": 30, "avg_cost": 380.00, "current_price": 0},
            {"ticker": "GOOGL", "shares": 20, "avg_cost": 140.00, "current_price": 0},
            {"ticker": "NVDA", "shares": 25, "avg_cost": 720.00, "current_price": 0},
            {"ticker": "TSLA", "shares": 15, "avg_cost": 245.00, "current_price": 0},
        ],
        "cash_balance": 50000.00,
        "total_value": 50000.00,  # Will be recalculated when prices are fetched
        "inception_date": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    result = get_portfolios_col().insert_one(portfolio_doc)
    print(f"[Seed] Created demo user portfolio:")
    print(f"  ID: {result.inserted_id}")
    print(f"  Holdings: AAPL, MSFT, GOOGL, NVDA, TSLA")
    print(f"  Cash: $50,000")


if __name__ == "__main__":
    print("\n🌱 Seeding FinVibe Database...\n")
    seed_shadow_portfolio()
    seed_demo_user_portfolio()
    print("\n✅ Seeding complete!\n")
