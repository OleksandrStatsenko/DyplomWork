# Database design

The initial cloud database is PostgreSQL. Both the website and Telegram bot will use the same FastAPI services and the same database.

## Tables

- `users`: web identity and optional Telegram account identifier. Passwords are stored only as password hashes.
- `suppliers`: supplier name, contact person, phone, and email.
- `products`: material/product name, unit, description, and optional price per cubic metre.
- `deliveries`: normalized foreign keys to supplier and product, quantity, date, optional unit price and notes.
- `conversation_history`: text messages associated with a user and the channel (`web` or `telegram`).

## Mapping from the old application

The previous desktop program used `suppliers(name, contact, phone, email)`, `products(name, unit, description, price_per_cubic_meter)`, and `deliveries(supplier_id, product_id, delivery_date)`.

The Telegram script used inconsistent table/column naming in different handlers (for example `SupplierID` versus `id`, and `ProductName` versus `product_id`). The new schema standardizes names to lowercase snake_case and stores a delivery's product by `product_id`. The Telegram delivery flow will therefore be updated to select an existing product rather than writing a free-text product name.

## Setup

1. Create an empty PostgreSQL database named `voice_assistant`.
2. Copy `.env.example` to `.env` and set `DATABASE_URL`.
3. Install the dependencies from the repository root.
4. Run `python -m backend.database.init_db` for a local prototype, or execute `backend/database/schema.sql` in the PostgreSQL database console.

The SQL file and SQLAlchemy models describe the same initial schema. For a production deployment, introduce Alembic migrations before making further schema changes.

## Important

This is a new schema; no legacy SQL Server data has been migrated because a database export was not available. The legacy scripts also contain exposed API and bot credentials. Revoke/rotate those credentials and remove them from Git history before deploying.
