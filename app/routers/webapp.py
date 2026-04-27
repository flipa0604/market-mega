"""
Mini App uchun JSON API.

Frontend barcha so'rovlarga `X-Telegram-Init-Data` sarlavhasini qo'shadi.
Autentifikatsiya `get_webapp_user` dependency ichida bajariladi.
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    CartItem,
    Category,
    Message,
    MessageSender,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    User,
)
from app.schemas.webapp import (
    CartItemIn,
    CartItemOut,
    CategoryOut,
    MessageCreate,
    MessageOut,
    OrderCreate,
    OrderCreateResponse,
    ProductOut,
)
from app.utils.admin_lookup import get_admin_chat_ids
from app.utils.deps import get_webapp_user

router = APIRouter(prefix="/api", tags=["webapp"])


@router.get("/me")
async def me(user: User = Depends(get_webapp_user)) -> dict:
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "full_name": user.full_name,
        "phone": user.phone,
    }


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_webapp_user),
) -> list[Category]:
    result = await db.execute(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.sort_order, Category.name)
    )
    return list(result.scalars().all())


@router.get("/categories/{category_id}/products", response_model=list[ProductOut])
async def list_products(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_webapp_user),
) -> list[Product]:
    result = await db.execute(
        select(Product)
        .where(Product.category_id == category_id, Product.is_active.is_(True))
        .order_by(Product.name)
    )
    return list(result.scalars().all())


@router.get("/products/search", response_model=list[ProductOut])
async def search_products(
    q: str = "",
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_webapp_user),
) -> list[Product]:
    """Mahsulotlarni nomi yoki izohi bo'yicha qidirish."""
    q = q.strip()
    if len(q) < 2:
        return []
    pattern = f"%{q}%"
    result = await db.execute(
        select(Product)
        .where(
            Product.is_active.is_(True),
            (Product.name.ilike(pattern)) | (Product.description.ilike(pattern)),
        )
        .order_by(Product.name)
        .limit(50)
    )
    return list(result.scalars().all())


@router.post("/orders", response_model=OrderCreateResponse)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_webapp_user),
) -> OrderCreateResponse:
    # Mahsulotlarni bazadan olamiz (narxni mijozga ishonmaymiz)
    product_ids = [item.product_id for item in payload.items]
    result = await db.execute(
        select(Product).where(Product.id.in_(product_ids), Product.is_active.is_(True))
    )
    products = {p.id: p for p in result.scalars().all()}

    missing = [pid for pid in product_ids if pid not in products]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Mahsulotlar topilmadi yoki nofaol: {missing}",
        )

    order = Order(
        user_id=user.id,
        status=OrderStatus.pending_location,
        customer_name=user.full_name,
        customer_phone=user.phone,
        total_price=0,
    )
    db.add(order)
    await db.flush()  # order.id olish uchun

    total = Decimal("0")
    for item in payload.items:
        product = products[item.product_id]
        unit_price = Decimal(str(product.price))
        total += unit_price * item.quantity
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                unit_price=unit_price,
                quantity=item.quantity,
            )
        )

    order.total_price = float(total)
    await db.commit()
    await db.refresh(order)

    return OrderCreateResponse(
        order_id=order.id,
        total_price=float(order.total_price),
    )


@router.get("/cart", response_model=list[CartItemOut])
async def get_cart(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_webapp_user),
) -> list[dict]:
    """Foydalanuvchining savat ichidagi mahsulotlari."""
    result = await db.execute(
        select(CartItem)
        .where(CartItem.user_id == user.id)
        .options(selectinload(CartItem.product))
        .order_by(CartItem.id)
    )
    items = list(result.scalars().all())
    return [
        {
            "product_id": ci.product_id,
            "quantity": ci.quantity,
            "product": {
                "id": ci.product.id,
                "category_id": ci.product.category_id,
                "name": ci.product.name,
                "description": ci.product.description,
                "price": float(ci.product.price),
                "image": ci.product.image,
            },
        }
        for ci in items
        if ci.product and ci.product.is_active
    ]


@router.post("/cart")
async def upsert_cart_item(
    payload: CartItemIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_webapp_user),
) -> dict:
    """Savatga mahsulot qo'shish/yangilash. quantity=0 -> o'chirish."""
    # Mahsulot mavjudligini tekshirish
    product = await db.get(Product, payload.product_id)
    if not product or not product.is_active:
        raise HTTPException(404, "Mahsulot topilmadi yoki nofaol")

    if payload.quantity <= 0:
        await db.execute(
            delete(CartItem).where(
                CartItem.user_id == user.id,
                CartItem.product_id == payload.product_id,
            )
        )
    else:
        # PostgreSQL UPSERT
        stmt = (
            pg_insert(CartItem)
            .values(
                user_id=user.id,
                product_id=payload.product_id,
                quantity=payload.quantity,
            )
            .on_conflict_do_update(
                constraint="uq_cart_user_product",
                set_={"quantity": payload.quantity},
            )
        )
        await db.execute(stmt)

    await db.commit()
    return {"ok": True, "quantity": payload.quantity}


@router.delete("/cart")
async def clear_cart(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_webapp_user),
) -> dict:
    await db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    await db.commit()
    return {"ok": True}


@router.get("/messages", response_model=list[MessageOut])
async def list_messages(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_webapp_user),
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.user_id == user.id)
        .order_by(Message.created_at.asc())
        .limit(200)
    )
    msgs = list(result.scalars().all())
    # User chat ochganda admin xabarlarini "o'qildi" deb belgilash
    await db.execute(
        Message.__table__.update()
        .where(
            Message.user_id == user.id,
            Message.sender == MessageSender.admin,
            Message.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.commit()
    return msgs


@router.post("/messages", response_model=MessageOut)
async def send_message(
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_webapp_user),
) -> Message:
    msg = Message(
        user_id=user.id,
        sender=MessageSender.user,
        text=payload.text.strip(),
        is_read=False,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    # Barcha admin'larga Telegram orqali notification
    admin_ids = await get_admin_chat_ids(db)
    if admin_ids:
        from app.bot.bot import bot

        text = (
            f"💬 <b>{user.full_name}</b> "
            f"({'@' + user.username if user.username else user.phone or ''}):\n\n"
            f"{payload.text}\n\n"
            f"<i>Javob berish: Admin paneldan «Chat» bo'limini oching</i>"
        )
        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, text)
            except Exception:  # noqa: BLE001
                pass

    return msg


@router.get("/orders/{order_id}")
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_webapp_user),
) -> dict:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user.id)
        .options(selectinload(Order.items))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    return {
        "id": order.id,
        "status": order.status.value,
        "total_price": float(order.total_price),
        "items": [
            {
                "product_name": it.product_name,
                "quantity": it.quantity,
                "unit_price": float(it.unit_price),
            }
            for it in order.items
        ],
    }
