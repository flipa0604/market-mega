from datetime import datetime

from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    id: int
    sender: str
    text: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class CategoryOut(BaseModel):
    id: int
    name: str
    image: str | None = None

    class Config:
        from_attributes = True


class ProductOut(BaseModel):
    id: int
    category_id: int
    name: str
    description: str | None = None
    price: float
    image: str | None = None

    class Config:
        from_attributes = True


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=999)


class OrderCreate(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1)


class OrderCreateResponse(BaseModel):
    order_id: int
    total_price: float
    message: str = "Buyurtma qabul qilindi. Botga qaytib, lokatsiya yuboring."
