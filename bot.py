import asyncio
import json
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

BASE = Path(__file__).parent
MENU_FILE = BASE / "menu.json"

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# Кошики зберігаються в пам'яті, поки бот працює.
carts = {}


def load_menu():
    return json.loads(MENU_FILE.read_text(encoding="utf-8"))


def save_menu(data):
    MENU_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍢 Welcome-закуски", callback_data="cat:Welcome")],
            [InlineKeyboardButton(text="🔥 BBQ", callback_data="cat:BBQ")],
            [InlineKeyboardButton(text="🍓 Десерти / фрукти", callback_data="cat:Десерти / фрукти")],
            [InlineKeyboardButton(text="🛒 Кошик", callback_data="cart")],
        ]
    )


def product_kb(pid: str, category: str, qty: int):
    """Клавіатура товару з актуальною кількістю."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➖", callback_data=f"minus:{pid}"),
                InlineKeyboardButton(text=f"{qty} шт.", callback_data="noop"),
                InlineKeyboardButton(text="➕", callback_data=f"plus:{pid}"),
            ],
            [
                InlineKeyboardButton(text="🛒 Кошик", callback_data="cart"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat:{category}"),
            ],
        ]
    )


def cart_text(uid):
    cart = carts.get(uid, {})
    menu = {x["id"]: x for x in load_menu()}

    if not cart:
        return "🛒 Ваш кошик порожній."

    lines = ["🛒 <b>Ваше замовлення</b>\n"]
    total = 0

    for pid, qty in cart.items():
        if pid not in menu:
            continue

        p = menu[pid]
        subtotal = p["price"] * qty
        total += subtotal
        lines.append(f"• {p['name']} × {qty} = {subtotal} грн")

    lines.append(f"\n<b>Разом: {total} грн</b>")
    return "\n".join(lines)


@dp.message(CommandStart())
async def start(m: Message):
    await m.answer(
        "Вітаємо у <b>GASTRO Catering</b>!\nОберіть категорію:",
        reply_markup=main_kb(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("cat:"))
async def category(c: CallbackQuery):
    cat = c.data.split(":", 1)[1]

    products = [
        x
        for x in load_menu()
        if x["category"] == cat and x.get("active", True)
    ]

    rows = [
        [
            InlineKeyboardButton(
                text=f"{p['name']} — {p['price']} грн",
                callback_data=f"item:{p['id']}",
            )
        ]
        for p in products
    ]
    rows.append(
        [InlineKeyboardButton(text="⬅️ Головне меню", callback_data="home")]
    )

    await c.message.edit_text(
        f"<b>{cat}</b>\nОберіть позицію:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await c.answer()


@dp.callback_query(F.data.startswith("item:"))
async def item(c: CallbackQuery):
    pid = c.data.split(":", 1)[1]
    p = next(x for x in load_menu() if x["id"] == pid)

    qty = carts.get(c.from_user.id, {}).get(pid, 0)

    await c.message.edit_text(
        f"<b>{p['name']}</b>\n"
        f"Вихід: {p['weight']}\n"
        f"Ціна: <b>{p['price']} грн</b>",
        reply_markup=product_kb(pid, p["category"], qty),
        parse_mode="HTML",
    )
    await c.answer()


@dp.callback_query(F.data.startswith(("plus:", "minus:")))
async def change_qty(c: CallbackQuery):
    """
    Змінюємо кількість у кошику і ОКРЕМО оновлюємо клавіатуру.
    Саме це виправляє ситуацію, коли в кошику кількість змінювалась,
    але на кнопці залишалось "0 шт.".
    """
    action, pid = c.data.split(":", 1)

    p = next((x for x in load_menu() if x["id"] == pid), None)
    if p is None:
        await c.answer("Позицію не знайдено", show_alert=True)
        return

    cart = carts.setdefault(c.from_user.id, {})
    current = cart.get(pid, 0)

    if action == "plus":
        new_qty = current + 1
    else:
        new_qty = max(0, current - 1)

    if new_qty == 0:
        cart.pop(pid, None)
    else:
        cart[pid] = new_qty

    # Важливо: не викликаємо item(c) повторно.
    # Оновлюємо саме inline-клавіатуру, щоб число змінювалось одразу.
    await c.message.edit_reply_markup(
        reply_markup=product_kb(pid, p["category"], new_qty)
    )
    await c.answer(f"Кількість: {new_qty}")


@dp.callback_query(F.data == "cart")
async def cart(c: CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оформити", callback_data="checkout")],
            [InlineKeyboardButton(text="🗑 Очистити", callback_data="clear")],
            [InlineKeyboardButton(text="⬅️ Меню", callback_data="home")],
        ]
    )

    await c.message.edit_text(
        cart_text(c.from_user.id),
        reply_markup=kb,
        parse_mode="HTML",
    )
    await c.answer()


@dp.callback_query(F.data == "clear")
async def clear(c: CallbackQuery):
    carts[c.from_user.id] = {}

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оформити", callback_data="checkout")],
            [InlineKeyboardButton(text="🗑 Очистити", callback_data="clear")],
            [InlineKeyboardButton(text="⬅️ Меню", callback_data="home")],
        ]
    )

    await c.message.edit_text(
        "🛒 Ваш кошик порожній.",
        reply_markup=kb,
    )
    await c.answer("Кошик очищено")


@dp.callback_query(F.data == "home")
async def home(c: CallbackQuery):
    await c.message.edit_text(
        "Оберіть категорію:",
        reply_markup=main_kb(),
    )
    await c.answer()


@dp.callback_query(F.data == "noop")
async def noop(c: CallbackQuery):
    await c.answer()


class Order(StatesGroup):
    name = State()
    phone = State()
    date = State()
    address = State()
    comment = State()


@dp.callback_query(F.data == "checkout")
async def checkout(c: CallbackQuery, state: FSMContext):
    if not carts.get(c.from_user.id):
        await c.answer("Кошик порожній", show_alert=True)
        return

    await state.set_state(Order.name)
    await c.message.answer("Як вас звати?")
    await c.answer()


@dp.message(Order.name)
async def order_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await state.set_state(Order.phone)
    await m.answer("Ваш номер телефону?")


@dp.message(Order.phone)
async def order_phone(m: Message, state: FSMContext):
    await state.update_data(phone=m.text)
    await state.set_state(Order.date)
    await m.answer("На яку дату та час потрібне замовлення?")


@dp.message(Order.date)
async def order_date(m: Message, state: FSMContext):
    await state.update_data(date=m.text)
    await state.set_state(Order.address)
    await m.answer("Адреса доставки / місце проведення?")


@dp.message(Order.address)
async def order_address(m: Message, state: FSMContext):
    await state.update_data(address=m.text)
    await state.set_state(Order.comment)
    await m.answer("Коментар до замовлення? Якщо немає — напишіть «-».")


@dp.message(Order.comment)
async def finish_order(m: Message, state: FSMContext):
    await state.update_data(comment=m.text)
    d = await state.get_data()

    order = cart_text(m.from_user.id)

    text = (
        f"🔔 <b>НОВЕ ЗАМОВЛЕННЯ</b>\n\n"
        f"{order}\n\n"
        f"👤 {d['name']}\n"
        f"📞 {d['phone']}\n"
        f"📅 {d['date']}\n"
        f"📍 {d['address']}\n"
        f"💬 {d['comment']}\n"
        f"Telegram: @{m.from_user.username or 'немає username'} | ID {m.from_user.id}"
    )

    await bot.send_message(ADMIN_ID, text, parse_mode="HTML")

    carts[m.from_user.id] = {}
    await state.clear()

    await m.answer(
        "✅ Дякуємо! Замовлення передано менеджеру GASTRO Catering.",
        reply_markup=main_kb(),
    )


@dp.message(Command("admin"))
async def admin(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    await m.answer(
        "Адмін-команди:\n"
        "/price ID ЦІНА — змінити ціну\n"
        "/toggle ID — увімкнути/вимкнути позицію\n"
        "/items — список ID товарів"
    )


@dp.message(Command("items"))
async def items(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    await m.answer(
        "\n".join(
            f"{x['id']} — {x['name']} — {x['price']} грн — "
            f"{'ON' if x.get('active', True) else 'OFF'}"
            for x in load_menu()
        )
    )


@dp.message(Command("price"))
async def price(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    try:
        _, pid, value = m.text.split(maxsplit=2)
        value = int(value)

        data = load_menu()
        p = next(x for x in data if x["id"] == pid)
        p["price"] = value
        save_menu(data)

        await m.answer(f"✅ {p['name']}: {value} грн")
    except Exception:
        await m.answer(
            "Формат: /price ID ЦІНА\n"
            "Наприклад: /price salmon 280"
        )


@dp.message(Command("toggle"))
async def toggle(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    try:
        _, pid = m.text.split(maxsplit=1)

        data = load_menu()
        p = next(x for x in data if x["id"] == pid)
        p["active"] = not p.get("active", True)
        save_menu(data)

        await m.answer(
            f"✅ {p['name']}: "
            f"{'увімкнено' if p['active'] else 'вимкнено'}"
        )
    except Exception:
        await m.answer("Формат: /toggle ID")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
