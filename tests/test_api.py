from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.base import Base
from backend.database import models  # noqa: F401
from backend.database.session import get_db
from backend.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_supplier_product_and_delivery_lifecycle(client: TestClient) -> None:
    supplier_response = client.post(
        "/api/suppliers",
        json={"name": "ТОВ Постачальник", "contact": "Іван", "phone": "+380000000000"},
    )
    assert supplier_response.status_code == 201
    supplier_id = supplier_response.json()["id"]

    product_response = client.post(
        "/api/products",
        json={"name": "Пісок", "unit": "м³", "price_per_cubic_meter": "450.00"},
    )
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]

    delivery_response = client.post(
        "/api/deliveries",
        json={
            "supplier_id": supplier_id,
            "product_id": product_id,
            "quantity": "3.500",
            "delivery_date": "2026-11-13",
            "unit_price": "450.00",
        },
    )
    assert delivery_response.status_code == 201
    delivery_id = delivery_response.json()["id"]

    listed = client.get("/api/deliveries", params={"supplier_id": supplier_id})
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == delivery_id

    exported = client.get("/api/deliveries/export.csv")
    assert exported.status_code == 200
    assert "Пісок" in exported.text
    assert "ТОВ Постачальник" in exported.text

    deleted = client.delete(f"/api/deliveries/{delivery_id}")
    assert deleted.status_code == 204


def test_delivery_rejects_unknown_references(client: TestClient) -> None:
    response = client.post(
        "/api/deliveries",
        json={
            "supplier_id": 999,
            "product_id": 999,
            "quantity": "1",
            "delivery_date": "2026-11-13",
        },
    )
    assert response.status_code == 404


def test_telegram_webhook_requires_secret(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.config import settings

    monkeypatch.setattr(settings, "telegram_webhook_secret", "test-secret")
    response = client.post("/api/telegram/webhook", json={"update_id": 1})
    assert response.status_code == 403

    response = client.post(
        "/api/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        json={"update_id": 1},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_telegram_commands_create_and_list_records(client: TestClient) -> None:
    from backend.services.telegram_commands import handle_accounting_command

    db = TestingSessionLocal()
    try:
        supplier_reply = handle_accounting_command(
            "/supplier_add ТОВ Альфа|Іван|+380501112233|alpha@example.com", db
        )
        assert supplier_reply is not None and "ТОВ Альфа" in supplier_reply

        product_reply = handle_accounting_command("/product_add Пісок|м³|Кар'єрний пісок|450", db)
        assert product_reply is not None and "Пісок" in product_reply

        suppliers = handle_accounting_command("/suppliers", db)
        products = handle_accounting_command("покажи товари", db)
        assert suppliers is not None and "ТОВ Альфа" in suppliers
        assert products is not None and "Пісок" in products
    finally:
        db.close()


def test_telegram_delivery_command_and_safe_delete(client: TestClient) -> None:
    from backend.services.telegram_commands import handle_accounting_command

    db = TestingSessionLocal()
    try:
        handle_accounting_command("/supplier_add ТОВ Бета|||", db)
        handle_accounting_command("/product_add Цемент|т|Мішки|200", db)

        delivery_reply = handle_accounting_command(
            "/delivery_add 1|1|2,5|2026-11-20|200|Тестова поставка", db
        )
        assert delivery_reply is not None and "Поставку зареєстровано" in delivery_reply

        blocked = handle_accounting_command("/supplier_delete 1 ПІДТВЕРДЖУЮ", db)
        assert blocked is not None and "Не можна видалити" in blocked

        deleted = handle_accounting_command("/delivery_delete 1 ПІДТВЕРДЖУЮ", db)
        assert deleted == "Поставку #1 видалено."
    finally:
        db.close()


def test_telegram_delete_requires_explicit_confirmation(client: TestClient) -> None:
    from backend.services.telegram_commands import handle_accounting_command

    db = TestingSessionLocal()
    try:
        handle_accounting_command("/supplier_add ТОВ Гамма|||", db)
        with pytest.raises(ValueError, match="ПІДТВЕРДЖУЮ"):
            handle_accounting_command("/supplier_delete 1", db)
        assert db.get(models.Supplier, 1) is not None
    finally:
        db.close()
