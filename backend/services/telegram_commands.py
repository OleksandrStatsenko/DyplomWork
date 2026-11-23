from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import Delivery, Product, Supplier


HELP_TEXT = """Команди обліку (поля розділяйте символом |):

Перегляд:
 /suppliers [пошук] — список постачальників
 /products [пошук] — список товарів
 /deliveries — останні поставки

Постачальники:
 /supplier_add Назва|Контакт|Телефон|Email
 /supplier_edit ID|Назва|Контакт|Телефон|Email
 /supplier_delete ID ПІДТВЕРДЖУЮ

Товари:
 /product_add Назва|Одиниця|Опис|Ціна за м³
 /product_edit ID|Назва|Одиниця|Опис|Ціна за м³
 /product_delete ID ПІДТВЕРДЖУЮ

Поставки:
 /delivery_add ID_постачальника|ID_товару|Кількість|РРРР-ММ-ДД|Ціна|Примітки
 /delivery_edit ID|ID_постачальника|ID_товару|Кількість|РРРР-ММ-ДД|Ціна|Примітки
 /delivery_delete ID ПІДТВЕРДЖУЮ

Для необов'язкових полів можна залишити порожнє місце між |.
Видалення виконується лише з точним підтвердженням ПІДТВЕРДЖУЮ.
Голосом можна просити показати списки або диктувати команду додавання
у форматі: «додай постачальника: Назва | Контакт | Телефон | Email».
"""


def _parts(argument: str, expected: int) -> list[str]:
    values = [part.strip() for part in argument.split("|")]
    if len(values) != expected:
        raise ValueError(f"Потрібно вказати {expected} поля, розділивши їх символом |.")
    return values


def _optional(value: str) -> str | None:
    return value or None


def _decimal(value: str, label: str, *, required: bool = False) -> Decimal | None:
    if not value:
        if required:
            raise ValueError(f"Не заповнено поле «{label}».")
        return None
    try:
        result = Decimal(value.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Поле «{label}» має бути числом.") from exc
    if not result.is_finite() or result < 0 or (required and result == 0):
        raise ValueError(f"Поле «{label}» має бути додатним числом.")
    return result


def _positive_id(value: str, label: str = "ID") -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise ValueError(f"{label} має бути цілим числом.") from exc
    if result <= 0:
        raise ValueError(f"{label} має бути більшим за нуль.")
    return result


def _confirmed(argument: str) -> int:
    values = argument.rsplit(maxsplit=1)
    if len(values) != 2 or values[1] != "ПІДТВЕРДЖУЮ":
        raise ValueError("Для видалення повторіть команду та додайте в кінці: ПІДТВЕРДЖУЮ.")
    return _positive_id(values[0])


def _supplier_line(item: Supplier) -> str:
    return f"#{item.id} {item.name} | контакт: {item.contact or '—'} | тел.: {item.phone or '—'} | email: {item.email or '—'}"


def _product_line(item: Product) -> str:
    price = f"{item.price_per_cubic_meter:.2f}" if item.price_per_cubic_meter is not None else "—"
    return f"#{item.id} {item.name} | одиниця: {item.unit or '—'} | ціна/м³: {price}"


def _delivery_line(item: Delivery) -> str:
    return (
        f"#{item.id} {item.delivery_date.isoformat()} | "
        f"{item.supplier.name} → {item.product.name} | "
        f"{item.quantity} {item.product.unit or ''} | "
        f"ціна: {item.unit_price if item.unit_price is not None else '—'}"
    )


def handle_accounting_command(message: str, db: Session) -> str | None:
    """Execute explicit, validated Telegram accounting commands.

    Returns None when the message is not an accounting command, so it can be
    passed to the conversational assistant.
    """
    text = message.strip()
    lowered = text.casefold()

    # Friendly read-only phrases also work with speech transcription.
    aliases = {
        "покажи постачальників": "/suppliers",
        "список постачальників": "/suppliers",
        "покажи товари": "/products",
        "список товарів": "/products",
        "покажи поставки": "/deliveries",
        "список поставок": "/deliveries",
        "допомога": "/help",
        "команди": "/help",
    }
    if lowered in aliases:
        text = aliases[lowered]

    # Natural spoken creation phrase with a strict pipe-delimited payload.
    spoken_prefixes = {
        "додай постачальника:": "/supplier_add",
        "створи постачальника:": "/supplier_add",
        "додай товар:": "/product_add",
        "створи товар:": "/product_add",
        "зареєструй поставку:": "/delivery_add",
        "додай поставку:": "/delivery_add",
    }
    for prefix, command in spoken_prefixes.items():
        if lowered.startswith(prefix):
            text = command + " " + text[len(prefix):].strip()
            break

    if not text.startswith("/"):
        return None

    command, _, argument = text.partition(" ")
    command = command.split("@", 1)[0].lower()
    argument = argument.strip()

    if command in {"/help", "/start"}:
        return HELP_TEXT

    if command == "/suppliers":
        stmt = select(Supplier).order_by(Supplier.name)
        if argument:
            stmt = stmt.where(Supplier.name.ilike(f"%{argument}%"))
        rows = db.scalars(stmt.limit(15)).all()
        return "Постачальники:\n" + ("\n".join(_supplier_line(x) for x in rows) if rows else "Записів поки немає.")

    if command == "/products":
        stmt = select(Product).order_by(Product.name)
        if argument:
            stmt = stmt.where(Product.name.ilike(f"%{argument}%"))
        rows = db.scalars(stmt.limit(15)).all()
        return "Товари:\n" + ("\n".join(_product_line(x) for x in rows) if rows else "Записів поки немає.")

    if command == "/deliveries":
        rows = db.scalars(
            select(Delivery).order_by(Delivery.delivery_date.desc(), Delivery.id.desc()).limit(15)
        ).all()
        return "Останні поставки:\n" + ("\n".join(_delivery_line(x) for x in rows) if rows else "Поставок поки немає.")

    if command == "/supplier_add":
        name, contact, phone, email = _parts(argument, 4)
        if not name:
            raise ValueError("Назва постачальника обов'язкова.")
        item = Supplier(name=name, contact=_optional(contact), phone=_optional(phone), email=_optional(email))
        db.add(item)
        db.commit()
        db.refresh(item)
        return "Постачальника додано:\n" + _supplier_line(item)

    if command == "/supplier_edit":
        values = _parts(argument, 5)
        item_id = _positive_id(values[0])
        item = db.get(Supplier, item_id)
        if item is None:
            return "Постачальника з таким ID не знайдено."
        if not values[1]:
            raise ValueError("Назва постачальника обов'язкова.")
        item.name, item.contact, item.phone, item.email = (
            values[1], _optional(values[2]), _optional(values[3]), _optional(values[4])
        )
        db.commit()
        db.refresh(item)
        return "Дані постачальника оновлено:\n" + _supplier_line(item)

    if command == "/supplier_delete":
        item_id = _confirmed(argument)
        item = db.get(Supplier, item_id)
        if item is None:
            return "Постачальника з таким ID не знайдено."
        if item.deliveries:
            return "Не можна видалити постачальника, поки з ним пов'язані поставки."
        db.delete(item)
        db.commit()
        return f"Постачальника #{item_id} видалено."

    if command == "/product_add":
        name, unit, description, price = _parts(argument, 4)
        if not name:
            raise ValueError("Назва товару обов'язкова.")
        item = Product(
            name=name, unit=_optional(unit), description=_optional(description),
            price_per_cubic_meter=_decimal(price, "ціна за м³"),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return "Товар додано:\n" + _product_line(item)

    if command == "/product_edit":
        values = _parts(argument, 5)
        item_id = _positive_id(values[0])
        item = db.get(Product, item_id)
        if item is None:
            return "Товар з таким ID не знайдено."
        if not values[1]:
            raise ValueError("Назва товару обов'язкова.")
        item.name = values[1]
        item.unit = _optional(values[2])
        item.description = _optional(values[3])
        item.price_per_cubic_meter = _decimal(values[4], "ціна за м³")
        db.commit()
        db.refresh(item)
        return "Дані товару оновлено:\n" + _product_line(item)

    if command == "/product_delete":
        item_id = _confirmed(argument)
        item = db.get(Product, item_id)
        if item is None:
            return "Товар з таким ID не знайдено."
        if item.deliveries:
            return "Не можна видалити товар, який уже використовується в поставках."
        db.delete(item)
        db.commit()
        return f"Товар #{item_id} видалено."

    if command in {"/delivery_add", "/delivery_edit"}:
        expected = 6 if command == "/delivery_add" else 7
        values = _parts(argument, expected)
        if command == "/delivery_edit":
            delivery_id = _positive_id(values.pop(0))
            item = db.get(Delivery, delivery_id)
            if item is None:
                return "Поставку з таким ID не знайдено."
        else:
            item = Delivery()

        supplier_id = _positive_id(values[0], "ID постачальника")
        product_id = _positive_id(values[1], "ID товару")
        supplier = db.get(Supplier, supplier_id)
        product = db.get(Product, product_id)
        if supplier is None:
            return "Постачальника з таким ID не знайдено. Перевірте /suppliers."
        if product is None:
            return "Товар з таким ID не знайдено. Перевірте /products."
        quantity = _decimal(values[2], "кількість", required=True)
        try:
            delivery_date = date.fromisoformat(values[3])
        except ValueError as exc:
            raise ValueError("Дата має бути у форматі РРРР-ММ-ДД.") from exc
        unit_price = _decimal(values[4], "ціна")
        item.supplier_id = supplier_id
        item.product_id = product_id
        item.quantity = quantity
        item.delivery_date = delivery_date
        item.unit_price = unit_price
        item.notes = _optional(values[5])
        db.add(item)
        db.commit()
        db.refresh(item)
        return ("Поставку оновлено:\n" if command == "/delivery_edit" else "Поставку зареєстровано:\n") + _delivery_line(item)

    if command == "/delivery_delete":
        item_id = _confirmed(argument)
        item = db.get(Delivery, item_id)
        if item is None:
            return "Поставку з таким ID не знайдено."
        db.delete(item)
        db.commit()
        return f"Поставку #{item_id} видалено."

    return None
