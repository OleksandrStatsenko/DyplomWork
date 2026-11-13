from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)


class SupplierRead(ORMModel):
    id: int
    name: str
    contact: str | None
    phone: str | None
    email: str | None
    created_at: datetime


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    unit: str | None = Field(default=None, max_length=40)
    description: str | None = None
    price_per_cubic_meter: Decimal | None = Field(default=None, ge=0)


class ProductRead(ORMModel):
    id: int
    name: str
    unit: str | None
    description: str | None
    price_per_cubic_meter: Decimal | None
    created_at: datetime


class DeliveryCreate(BaseModel):
    supplier_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    delivery_date: date
    unit_price: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class DeliveryRead(ORMModel):
    id: int
    supplier_id: int
    product_id: int
    quantity: Decimal
    delivery_date: date
    unit_price: Decimal | None
    notes: str | None
    created_at: datetime


class AssistantMessage(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class AssistantReply(BaseModel):
    reply: str
    intent: str = "chat"


class VoiceReply(BaseModel):
    transcript: str
    reply: str
    audio_base64: str | None = None
    audio_media_type: str | None = None
