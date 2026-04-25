"""
Admin panel routerlari.

Barcha sahifalar `require_admin`'dan himoyalangan.
/admin/login va /admin/logout — ochiq.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models import (
    Category,
    Message,
    MessageSender,
    Order,
    OrderStatus,
    Product,
    User,
)
from app.utils.deps import require_admin
from app.utils.security import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    check_credentials,
    create_session_token,
    current_admin,
)

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


async def _save_upload(upload: UploadFile | None) -> str | None:
    if not upload or not upload.filename:
        return None
    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Rasm kengaytmasi ruxsat etilmagan: {ext}",
        )
    name = f"{uuid.uuid4().hex}{ext}"
    dest = settings.uploads_dir / name
    content = await upload.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB
        raise HTTPException(status_code=400, detail="Rasm 10 MB dan katta")
    dest.write_bytes(content)
    return f"/static/uploads/{name}"


# ============================================================
# Login / Logout
# ============================================================


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    if current_admin(request):
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse(
        request, "login.html", {"error": None}
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if not check_credentials(username, password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Login yoki parol xato"},
            status_code=401,
        )
    token = create_session_token(username)
    resp = RedirectResponse(url="/admin", status_code=302)
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
    )
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse(url="/admin/login", status_code=302)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# ============================================================
# Dashboard
# ============================================================


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    total_categories = (await db.execute(select(func.count(Category.id)))).scalar() or 0
    total_products = (await db.execute(select(func.count(Product.id)))).scalar() or 0
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_orders = (await db.execute(select(func.count(Order.id)))).scalar() or 0
    pending_orders = (
        await db.execute(
            select(func.count(Order.id)).where(Order.status == OrderStatus.new)
        )
    ).scalar() or 0

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "admin": admin,
            "stats": {
                "categories": total_categories,
                "products": total_products,
                "users": total_users,
                "orders": total_orders,
                "pending": pending_orders,
            },
        },
    )


# ============================================================
# Categories
# ============================================================


@router.get("/categories", response_class=HTMLResponse)
async def categories_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    result = await db.execute(select(Category).order_by(Category.sort_order, Category.name))
    categories = list(result.scalars().all())
    return templates.TemplateResponse(
        request,
        "categories.html",
        {"admin": admin, "categories": categories},
    )


@router.post("/categories")
async def category_create(
    name: str = Form(...),
    sort_order: int = Form(0),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    image_path = await _save_upload(image)
    db.add(Category(name=name.strip(), sort_order=sort_order, image=image_path))
    await db.commit()
    return RedirectResponse(url="/admin/categories", status_code=302)


@router.post("/categories/{category_id}/update")
async def category_update(
    category_id: int,
    name: str = Form(...),
    sort_order: int = Form(0),
    is_active: str | None = Form(None),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    cat = await db.get(Category, category_id)
    if not cat:
        raise HTTPException(404)
    cat.name = name.strip()
    cat.sort_order = sort_order
    cat.is_active = bool(is_active)
    new_image = await _save_upload(image)
    if new_image:
        cat.image = new_image
    await db.commit()
    return RedirectResponse(url="/admin/categories", status_code=302)


@router.post("/categories/{category_id}/delete")
async def category_delete(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    cat = await db.get(Category, category_id)
    if cat:
        await db.delete(cat)
        await db.commit()
    return RedirectResponse(url="/admin/categories", status_code=302)


# ============================================================
# Products
# ============================================================


@router.get("/products", response_class=HTMLResponse)
async def products_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    result = await db.execute(
        select(Product).options(selectinload(Product.category)).order_by(Product.id.desc())
    )
    products = list(result.scalars().all())
    cats_result = await db.execute(select(Category).order_by(Category.name))
    categories = list(cats_result.scalars().all())
    return templates.TemplateResponse(
        request,
        "products.html",
        {
            "admin": admin,
            "products": products,
            "categories": categories,
        },
    )


@router.post("/products")
async def product_create(
    name: str = Form(...),
    category_id: int = Form(...),
    price: float = Form(...),
    description: str = Form(""),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    image_path = await _save_upload(image)
    db.add(
        Product(
            name=name.strip(),
            category_id=category_id,
            price=price,
            description=description.strip() or None,
            image=image_path,
        )
    )
    await db.commit()
    return RedirectResponse(url="/admin/products", status_code=302)


@router.post("/products/{product_id}/update")
async def product_update(
    product_id: int,
    name: str = Form(...),
    category_id: int = Form(...),
    price: float = Form(...),
    description: str = Form(""),
    is_active: str | None = Form(None),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    p = await db.get(Product, product_id)
    if not p:
        raise HTTPException(404)
    p.name = name.strip()
    p.category_id = category_id
    p.price = price
    p.description = description.strip() or None
    p.is_active = bool(is_active)
    new_image = await _save_upload(image)
    if new_image:
        p.image = new_image
    await db.commit()
    return RedirectResponse(url="/admin/products", status_code=302)


@router.post("/products/{product_id}/delete")
async def product_delete(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    p = await db.get(Product, product_id)
    if p:
        await db.delete(p)
        await db.commit()
    return RedirectResponse(url="/admin/products", status_code=302)


# ============================================================
# Orders
# ============================================================


@router.get("/orders", response_class=HTMLResponse)
async def orders_list(
    request: Request,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.user))
        .order_by(Order.id.desc())
    )
    if status_filter:
        try:
            stmt = stmt.where(Order.status == OrderStatus(status_filter))
        except ValueError:
            pass
    result = await db.execute(stmt)
    orders = list(result.scalars().all())
    return templates.TemplateResponse(
        request,
        "orders.html",
        {
            "admin": admin,
            "orders": orders,
            "statuses": list(OrderStatus),
            "status_filter": status_filter,
        },
    )


# ============================================================
# Chat
# ============================================================


@router.get("/chat", response_class=HTMLResponse)
async def chat_users_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    # Har bir userning oxirgi xabari + o'qilmaganlar soni
    last_msg_subq = (
        select(
            Message.user_id,
            func.max(Message.created_at).label("last_at"),
        )
        .group_by(Message.user_id)
        .subquery()
    )
    unread_subq = (
        select(
            Message.user_id,
            func.count(Message.id).label("unread"),
        )
        .where(
            Message.sender == MessageSender.user,
            Message.is_read.is_(False),
        )
        .group_by(Message.user_id)
        .subquery()
    )
    stmt = (
        select(
            User,
            last_msg_subq.c.last_at,
            unread_subq.c.unread,
        )
        .join(last_msg_subq, User.id == last_msg_subq.c.user_id)
        .outerjoin(unread_subq, User.id == unread_subq.c.user_id)
        .order_by(last_msg_subq.c.last_at.desc())
    )
    result = await db.execute(stmt)
    rows = [
        {"user": u, "last_at": last_at, "unread": unread or 0}
        for u, last_at, unread in result.all()
    ]
    return templates.TemplateResponse(
        request,
        "chat_users.html",
        {"admin": admin, "rows": rows},
    )


@router.get("/chat/{user_id}", response_class=HTMLResponse)
async def chat_with_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404)
    msgs_result = await db.execute(
        select(Message)
        .where(Message.user_id == user_id)
        .order_by(Message.created_at.asc())
        .limit(500)
    )
    messages = list(msgs_result.scalars().all())
    # User'ning xabarlarini "o'qildi" deb belgilash
    await db.execute(
        Message.__table__.update()
        .where(
            Message.user_id == user_id,
            Message.sender == MessageSender.user,
            Message.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.commit()
    return templates.TemplateResponse(
        request,
        "chat_room.html",
        {"admin": admin, "u": user, "messages": messages},
    )


@router.post("/chat/{user_id}/send")
async def chat_send(
    user_id: int,
    text: str = Form(...),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404)
    text = text.strip()
    if not text:
        return RedirectResponse(url=f"/admin/chat/{user_id}", status_code=302)

    msg = Message(
        user_id=user_id,
        sender=MessageSender.admin,
        text=text,
        is_read=False,
    )
    db.add(msg)
    await db.commit()

    # Telegram orqali user'ga yetkazish
    try:
        from app.bot.bot import bot

        await bot.send_message(
            user.telegram_id,
            f"💬 <b>Admin javobi:</b>\n\n{text}",
        )
    except Exception:  # noqa: BLE001
        pass

    return RedirectResponse(url=f"/admin/chat/{user_id}", status_code=302)


@router.get("/chat/{user_id}/messages.json")
async def chat_messages_json(
    user_id: int,
    after_id: int = 0,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
) -> dict:
    """Auto-refresh uchun JSON endpoint."""
    result = await db.execute(
        select(Message)
        .where(Message.user_id == user_id, Message.id > after_id)
        .order_by(Message.created_at.asc())
        .limit(100)
    )
    msgs = list(result.scalars().all())
    if msgs:
        await db.execute(
            Message.__table__.update()
            .where(
                Message.user_id == user_id,
                Message.sender == MessageSender.user,
                Message.is_read.is_(False),
            )
            .values(is_read=True)
        )
        await db.commit()
    return {
        "messages": [
            {
                "id": m.id,
                "sender": m.sender.value,
                "text": m.text,
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ]
    }


# ============================================================
# Orders (continued)
# ============================================================


@router.post("/orders/{order_id}/status")
async def order_update_status(
    order_id: int,
    status_value: str = Form(...),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(404)
    try:
        order.status = OrderStatus(status_value)
    except ValueError as exc:
        raise HTTPException(400, f"Noto'g'ri status: {status_value}") from exc
    await db.commit()
    return RedirectResponse(url="/admin/orders", status_code=302)
