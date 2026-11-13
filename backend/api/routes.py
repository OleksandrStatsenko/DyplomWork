import csv
from datetime import date
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import Delivery, Product, Supplier
from backend.database.session import get_db
from backend.schemas import (
    DeliveryCreate,
    DeliveryRead,
    ProductCreate,
    ProductRead,
    SupplierCreate,
    SupplierRead,
)

router = APIRouter(prefix="/api")


@router.post("/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED, tags=["suppliers"])
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/suppliers", response_model=list[SupplierRead], tags=["suppliers"])
def list_suppliers(search: str | None = Query(default=None, max_length=200), db: Session = Depends(get_db)):
    stmt = select(Supplier).order_by(Supplier.name)
    if search:
        stmt = stmt.where(Supplier.name.ilike(f"%{search}%"))
    return db.scalars(stmt).all()


@router.get("/suppliers/{supplier_id}", response_model=SupplierRead, tags=["suppliers"])
def get_supplier(supplier_id: int, db: Session = Depends(get_db)):
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Постачальника не знайдено")
    return supplier


@router.put("/suppliers/{supplier_id}", response_model=SupplierRead, tags=["suppliers"])
def update_supplier(supplier_id: int, payload: SupplierCreate, db: Session = Depends(get_db)):
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Постачальника не знайдено")
    for field, value in payload.model_dump().items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["suppliers"])
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Постачальника не знайдено")
    if supplier.deliveries:
        raise HTTPException(status_code=409, detail="Не можна видалити постачальника, який має поставки")
    db.delete(supplier)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED, tags=["products"])
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/products", response_model=list[ProductRead], tags=["products"])
def list_products(search: str | None = Query(default=None, max_length=200), db: Session = Depends(get_db)):
    stmt = select(Product).order_by(Product.name)
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%"))
    return db.scalars(stmt).all()


@router.put("/products/{product_id}", response_model=ProductRead, tags=["products"])
def update_product(product_id: int, payload: ProductCreate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не знайдено")
    for field, value in payload.model_dump().items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["products"])
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не знайдено")
    if product.deliveries:
        raise HTTPException(status_code=409, detail="Не можна видалити товар, який є у поставках")
    db.delete(product)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/deliveries", response_model=DeliveryRead, status_code=status.HTTP_201_CREATED, tags=["deliveries"])
def create_delivery(payload: DeliveryCreate, db: Session = Depends(get_db)):
    if db.get(Supplier, payload.supplier_id) is None:
        raise HTTPException(status_code=404, detail="Постачальника не знайдено")
    if db.get(Product, payload.product_id) is None:
        raise HTTPException(status_code=404, detail="Товар не знайдено")
    delivery = Delivery(**payload.model_dump())
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


@router.get("/deliveries", response_model=list[DeliveryRead], tags=["deliveries"])
def list_deliveries(
    date_from: date | None = None,
    date_to: date | None = None,
    product_id: int | None = Query(default=None, gt=0),
    supplier_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="Початкова дата не може бути пізнішою за кінцеву")
    stmt = select(Delivery).order_by(Delivery.delivery_date.desc(), Delivery.id.desc())
    if date_from:
        stmt = stmt.where(Delivery.delivery_date >= date_from)
    if date_to:
        stmt = stmt.where(Delivery.delivery_date <= date_to)
    if product_id:
        stmt = stmt.where(Delivery.product_id == product_id)
    if supplier_id:
        stmt = stmt.where(Delivery.supplier_id == supplier_id)
    return db.scalars(stmt).all()


@router.put("/deliveries/{delivery_id}", response_model=DeliveryRead, tags=["deliveries"])
def update_delivery(delivery_id: int, payload: DeliveryCreate, db: Session = Depends(get_db)):
    delivery = db.get(Delivery, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Поставку не знайдено")
    if db.get(Supplier, payload.supplier_id) is None:
        raise HTTPException(status_code=404, detail="Постачальника не знайдено")
    if db.get(Product, payload.product_id) is None:
        raise HTTPException(status_code=404, detail="Товар не знайдено")
    for field, value in payload.model_dump().items():
        setattr(delivery, field, value)
    db.commit()
    db.refresh(delivery)
    return delivery


@router.delete("/deliveries/{delivery_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["deliveries"])
def delete_delivery(delivery_id: int, db: Session = Depends(get_db)):
    delivery = db.get(Delivery, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Поставку не знайдено")
    db.delete(delivery)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/deliveries/export.csv", tags=["deliveries"])
def export_deliveries_csv(db: Session = Depends(get_db)):
    deliveries = db.scalars(
        select(Delivery).order_by(Delivery.delivery_date.desc(), Delivery.id.desc())
    ).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "ID постачальника", "ID товару", "Кількість", "Дата поставки", "Ціна за одиницю", "Примітки"])
    for item in deliveries:
        writer.writerow([
            item.id,
            item.supplier_id,
            item.product_id,
            item.quantity,
            item.delivery_date.isoformat(),
            item.unit_price if item.unit_price is not None else "",
            item.notes or "",
        ])
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="deliveries.csv"'},
    )
