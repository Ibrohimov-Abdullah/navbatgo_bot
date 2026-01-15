import re
import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
from datetime import datetime, timedelta
import os

from config import BARBER_BOT_TOKEN, LANGUAGES, get_translation
from utils import get_user_language, get_text

# Initialize bot
bot = telebot.TeleBot(BARBER_BOT_TOKEN)

# Barber session storage
barber_sessions = {}


class BarberSession:
    """Store barber session data during registration"""

    def __init__(self, user_id):
        self.user_id = user_id
        self.step = None
        self.shop_data = {
            'name': None,
            'city_id': None,
            'district_id': None,
            'address': None,
            'phone': None,
            'description': None,
            'latitude': None,
            'longitude': None,
            'photos': [],
            'barbers': []
        }
        self.current_barber = None
        self.current_photo = None


def get_barber_session(user_id):
    """Get or create barber session"""
    if user_id not in barber_sessions:
        barber_sessions[user_id] = BarberSession(user_id)
    return barber_sessions[user_id]


def clear_barber_session(user_id):
    """Clear barber session"""
    if user_id in barber_sessions:
        del barber_sessions[user_id]

# -------------------- COMMAND HANDLERS --------------------


@bot.message_handler(commands=['start'])
def start_command(message):
    """Handle /start command"""
    user_id = message.from_user.id
    full_name = message.from_user.full_name

    # Check if user has barbershop
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT b.id, b.name, b.is_active 
        FROM barbershops b
        WHERE b.owner_id = ?
    ''', (user_id,))

    barbershop = cursor.fetchone()
    conn.close()

    if barbershop:
        # User has barbershop - show management panel
        shop_id, shop_name, is_active = barbershop
        show_barber_panel(message, user_id, shop_id, shop_name, is_active)
    else:
        # User doesn't have barbershop - offer registration
        show_welcome_message(message, user_id)


def show_welcome_message(message, user_id):
    """Show welcome message for new barbers"""
    text = f"✂️ *Добро пожаловать в панель управления барбершопом!*\n\n"
    text += f"Привет, {message.from_user.first_name}! 👋\n\n"
    text += "Я помогу вам управлять вашим барбершопом:\n"
    text += "• Добавить новый барбершоп\n"
    text += "• Управлять бронированиями\n"
    text += "• Редактировать информацию\n"
    text += "• Добавлять мастеров и услуги\n\n"
    text += "Для начала работы добавьте ваш барбершоп:"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        "➕ Добавить барбершоп", callback_data="register_shop"))
    markup.add(InlineKeyboardButton("ℹ️ Подробнее", callback_data="info"))

    bot.send_message(
        message.chat.id,
        text,
        parse_mode='Markdown',
        reply_markup=markup
    )


def show_barber_panel(message, user_id, shop_id, shop_name, is_active):
    """Show barber management panel"""
    status_text = "🟢 Активен" if is_active == 1 else "🟡 На модерации" if is_active == 0 else "🔴 Заблокирован"

    text = f"🏢 *Управление барбершопом*\n\n"
    text += f"*Название:* {shop_name}\n"
    text += f"*Статус:* {status_text}\n\n"
    text += "Выберите раздел управления:"

    markup = InlineKeyboardMarkup(row_width=2)

    markup.add(
        InlineKeyboardButton(
            "📋 Бронирования", callback_data=f"bookings_{shop_id}"),
        InlineKeyboardButton("👥 Мастера", callback_data=f"barbers_{shop_id}")
    )

    markup.add(
        InlineKeyboardButton("💈 Услуги", callback_data=f"services_{shop_id}"),
        InlineKeyboardButton("📸 Фото", callback_data=f"photos_{shop_id}")
    )

    markup.add(
        InlineKeyboardButton(
            "⚙️ Настройки", callback_data=f"settings_{shop_id}"),
        InlineKeyboardButton("📊 Статистика", callback_data=f"stats_{shop_id}")
    )

    if isinstance(message, types.Message):
        bot.send_message(
            message.chat.id,
            text,
            parse_mode='Markdown',
            reply_markup=markup
        )
    else:
        bot.edit_message_text(
            text,
            message.chat.id,
            message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )

# -------------------- SHOP REGISTRATION --------------------


@bot.callback_query_handler(func=lambda call: call.data == 'register_shop')
def start_shop_registration(call):
    """Start shop registration process"""
    user_id = call.from_user.id
    session = get_barber_session(user_id)
    session.step = 'waiting_shop_name'

    bot.send_message(
        call.message.chat.id,
        "🏢 *Добавление нового барбершопа*\n\n"
        "Шаг 1 из 8\n\n"
        "Введите название вашего барбершопа:",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_shop_name')
def handle_shop_name(message):
    """Handle shop name input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    if len(message.text) < 3:
        bot.send_message(
            message.chat.id, "❌ Название должно содержать минимум 3 символа")
        return

    session.shop_data['name'] = message.text.strip()
    session.step = 'waiting_city'

    # Show city selection
    show_city_selection(message, user_id)


def show_city_selection(message, user_id):
    """Show city selection for registration"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name_ru FROM cities WHERE is_active = 1 ORDER BY name_ru")
    cities = cursor.fetchall()
    conn.close()

    markup = InlineKeyboardMarkup(row_width=2)

    for city_id, city_name in cities:
        markup.add(InlineKeyboardButton(
            city_name, callback_data=f"reg_city_{city_id}"))

    bot.send_message(
        message.chat.id,
        "🏙 *Выберите город:*",
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('reg_city_'))
def handle_reg_city_selection(call):
    """Handle city selection during registration"""
    user_id = call.from_user.id
    session = barber_sessions[user_id]
    city_id = int(call.data.split('_')[2])

    session.shop_data['city_id'] = city_id
    session.step = 'waiting_district'

    # Show district selection
    show_district_selection(call.message, user_id, city_id)


def show_district_selection(message, user_id, city_id):
    """Show district selection for registration"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name_ru FROM districts 
        WHERE city_id = ? AND is_active = 1 
        ORDER BY name_ru
    ''', (city_id,))

    districts = cursor.fetchall()
    conn.close()

    if not districts:
        # Skip district selection if no districts
        session = barber_sessions[user_id]
        session.shop_data['district_id'] = None
        session.step = 'waiting_address'

        bot.send_message(
            message.chat.id,
            "📍 *Введите адрес барбершопа:*\n\n"
            "Пример: ул. Навои, 45, этаж 2",
            parse_mode='Markdown'
        )
        return

    markup = InlineKeyboardMarkup(row_width=2)

    for district_id, district_name in districts:
        markup.add(InlineKeyboardButton(district_name,
                   callback_data=f"reg_district_{district_id}"))

    bot.edit_message_text(
        "📍 *Выберите район:*",
        message.chat.id,
        message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('reg_district_'))
def handle_reg_district_selection(call):
    """Handle district selection during registration"""
    user_id = call.from_user.id
    session = barber_sessions[user_id]
    district_id = int(call.data.split('_')[2])

    session.shop_data['district_id'] = district_id
    session.step = 'waiting_address'

    bot.edit_message_text(
        "📍 *Введите адрес барбершопа:*\n\n"
        "Пример: ул. Навои, 45, этаж 2",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_address')
def handle_address(message):
    """Handle address input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    if len(message.text) < 5:
        bot.send_message(
            message.chat.id, "❌ Адрес должен содержать минимум 5 символов")
        return

    session.shop_data['address'] = message.text.strip()
    session.step = 'waiting_phone'

    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📱 Поделиться номером", request_contact=True))

    bot.send_message(
        message.chat.id,
        "📞 *Введите телефонный номер для связи:*\n\n"
        "Можно отправить контакт или ввести вручную\n"
        "Пример: +998901234567",
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_phone',
                     content_types=['text', 'contact'])
def handle_phone(message):
    """Handle phone input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()
        # Validate phone number
        if not re.match(r'^\+?[1-9]\d{9,14}$', phone.replace(' ', '')):
            bot.send_message(
                message.chat.id, "❌ Введите корректный номер телефона")
            return

    session.shop_data['phone'] = phone
    session.step = 'waiting_description'

    bot.send_message(
        message.chat.id,
        "📝 *Введите описание барбершопа:*\n\n"
        "Расскажите о вашем заведении, услугах, атмосфере.\n"
        "Можно добавить хештеги: #барбершоп #стрижка #бр"),


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_description')
def handle_description(message):
    """Handle description input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    session.shop_data['description'] = message.text.strip()
    session.step = 'waiting_location'

    # Ask for location
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton(
        "📍 Отправить местоположение", request_location=True))
    markup.add(KeyboardButton("🚫 Пропустить"))

    bot.send_message(
        message.chat.id,
        "📍 *Отправьте местоположение барбершопа:*\n\n"
        "Это поможет клиентам найти вас быстрее.\n"
        "Если не хотите указывать, нажмите 'Пропустить'",
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_location',
                     content_types=['location', 'text'])
def handle_location(message):
    """Handle location input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    if message.location:
        session.shop_data['latitude'] = message.location.latitude
        session.shop_data['longitude'] = message.location.longitude
    else:
        session.shop_data['latitude'] = None
        session.shop_data['longitude'] = None

    session.step = 'waiting_photos'

    bot.send_message(
        message.chat.id,
        "📸 *Добавьте фотографии барбершопа:*\n\n"
        "Рекомендуется добавить 3-5 фотографий:\n"
        "• Фасад\n"
        "• Интерьер\n"
        "• Рабочие места\n"
        "• Примеры работ\n\n"
        "Отправьте фотографии по одной.\n"
        "После отправки всех фото нажмите 'Готово'",
        parse_mode='Markdown',
        reply_markup=types.ReplyKeyboardRemove()
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_photos',
                     content_types=['photo'])
def handle_photos(message):
    """Handle photo upload"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    # Get the best quality photo
    photo = message.photo[-1]
    photo_id = photo.file_id

    # Store photo
    session.shop_data['photos'].append(photo_id)

    # Show current photos count
    count = len(session.shop_data['photos'])

    if count < 5:
        bot.send_message(
            message.chat.id,
            f"✅ Фото {count} добавлено. Можно добавить еще {5-count} фото.\n"
            f"Отправьте следующее фото или нажмите 'Готово'",
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        session.step = 'waiting_barbers'
        show_barber_info_input(message, user_id)


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_photos' and
                     message.text and message.text.lower() == 'готово')
def finish_photos(message):
    """Finish photo upload"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    if not session.shop_data['photos']:
        bot.send_message(
            message.chat.id, "❌ Пожалуйста, добавьте хотя бы одну фотографию")
        return

    session.step = 'waiting_barbers'
    show_barber_info_input(message, user_id)


def show_barber_info_input(message, user_id):
    """Show barber information input form"""
    session = barber_sessions[user_id]

    text = "👤 *Добавление мастеров*\n\n"
    text += "Теперь добавьте информацию о мастерах.\n\n"
    text += "Введите полное имя мастера:"

    session.current_barber = {
        'name': None,
        'experience': None,
        'specialty': None,
        'description': None,
        'photos': []
    }

    bot.send_message(
        message.chat.id,
        text,
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_barbers' and
                     barber_sessions[message.from_user.id].current_barber['name'] is None)
def handle_barber_name(message):
    """Handle barber name input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    if len(message.text.strip()) < 2:
        bot.send_message(
            message.chat.id, "❌ Имя должно содержать минимум 2 символа")
        return

    session.current_barber['name'] = message.text.strip()

    bot.send_message(
        message.chat.id,
        "💼 *Сколько лет опыта у мастера?*\n\n"
        "Введите число (например: 3):",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_barbers' and
                     barber_sessions[message.from_user.id].current_barber['name'] and
                     barber_sessions[message.from_user.id].current_barber['experience'] is None)
def handle_barber_experience(message):
    """Handle barber experience input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    try:
        experience = int(message.text.strip())
        if experience < 0 or experience > 50:
            bot.send_message(
                message.chat.id, "❌ Введите корректное число лет опыта (0-50)")
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите число")
        return

    session.current_barber['experience'] = experience

    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(
        "Мужские стрижки",
        "Женские стрижки",
        "Барбер",
        "Колорист",
        "Универсал",
        "Другое"
    )

    bot.send_message(
        message.chat.id,
        "🎯 *Специализация мастера:*\n\n"
        "Выберите из списка или введите свою:",
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_barbers' and
                     barber_sessions[message.from_user.id].current_barber['experience'] is not None and
                     barber_sessions[message.from_user.id].current_barber['specialty'] is None)
def handle_barber_specialty(message):
    """Handle barber specialty input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    session.current_barber['specialty'] = message.text.strip()

    bot.send_message(
        message.chat.id,
        "📝 *Краткое описание мастера:*\n\n"
        "Расскажите о мастере, его стиле, подходе к работе.\n"
        "Можно пропустить, отправив '0'",
        parse_mode='Markdown',
        reply_markup=types.ReplyKeyboardRemove()
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_barbers' and
                     barber_sessions[message.from_user.id].current_barber['specialty'] and
                     barber_sessions[message.from_user.id].current_barber['description'] is None)
def handle_barber_description(message):
    """Handle barber description input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    if message.text.strip() == '0':
        session.current_barber['description'] = None
    else:
        session.current_barber['description'] = message.text.strip()

    session.step = 'waiting_barber_photos'

    bot.send_message(
        message.chat.id,
        "📸 *Добавьте фото мастера (опционально):*\n\n"
        "Отправьте фото мастера или его работ.\n"
        "Можно добавить несколько фото.\n"
        "Когда закончите, нажмите 'Пропустить'",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_barber_photos',
                     content_types=['photo'])
def handle_barber_photo(message):
    """Handle barber photo upload"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    # Get the best quality photo
    photo = message.photo[-1]
    photo_id = photo.file_id

    session.current_barber['photos'].append(photo_id)

    bot.send_message(
        message.chat.id,
        "✅ Фото добавлено. Можно добавить еще или нажать 'Пропустить'",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'waiting_barber_photos' and
                     message.text and message.text.lower() in ['пропустить', 'готово'])
def finish_barber_photos(message):
    """Finish barber photo upload"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    # Add current barber to shop data
    session.shop_data['barbers'].append(session.current_barber.copy())

    # Ask if want to add more barbers
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("✅ Добавить еще мастера", "🚫 Завершить добавление")

    bot.send_message(
        message.chat.id,
        f"✅ Мастер '{session.current_barber['name']}' добавлен!\n\n"
        f"Всего мастеров: {len(session.shop_data['barbers'])}\n\n"
        "Добавить еще мастера?",
        parse_mode='Markdown',
        reply_markup=markup
    )

    # Reset current barber
    session.current_barber = {
        'name': None,
        'experience': None,
        'specialty': None,
        'description': None,
        'photos': []
    }

    session.step = 'asking_more_barbers'


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'asking_more_barbers')
def handle_more_barbers_choice(message):
    """Handle choice to add more barbers"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    if message.text == "✅ Добавить еще мастера":
        show_barber_info_input(message, user_id)
    else:
        # Finish registration and save to database
        save_barbershop_to_db(message, user_id)


def save_barbershop_to_db(message, user_id):
    """Save barbershop data to database"""
    session = barber_sessions[user_id]

    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    try:
        # Insert barbershop
        cursor.execute('''
            INSERT INTO barbershops 
            (owner_id, name, city_id, district_id, address, phone, description, latitude, longitude, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (
            user_id,
            session.shop_data['name'],
            session.shop_data['city_id'],
            session.shop_data['district_id'],
            session.shop_data['address'],
            session.shop_data['phone'],
            session.shop_data['description'],
            session.shop_data['latitude'],
            session.shop_data['longitude']
        ))

        shop_id = cursor.lastrowid

        # Insert photos
        for i, photo_id in enumerate(session.shop_data['photos']):
            is_main = 1 if i == 0 else 0
            cursor.execute('''
                INSERT INTO barbershop_photos (barbershop_id, photo_id, is_main)
                VALUES (?, ?, ?)
            ''', (shop_id, photo_id, is_main))

        # Insert barbers
        for barber_data in session.shop_data['barbers']:
            cursor.execute('''
                INSERT INTO barbers 
                (barbershop_id, full_name, experience_years, specialty, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                shop_id,
                barber_data['name'],
                barber_data['experience'],
                barber_data['specialty'],
                barber_data['description']
            ))

            barber_id = cursor.lastrowid

            # Insert barber photos
            for photo_id in barber_data['photos']:
                cursor.execute('''
                    INSERT INTO barber_photos (barber_id, photo_id)
                    VALUES (?, ?)
                ''', (barber_id, photo_id))

        conn.commit()

        # Add default services
        default_services = [
            (shop_id, "Мужская стрижка", "Мужская стрижка",
             "Men's haircut", 50000, 45),
            (shop_id, "Стрижка машинкой",
             "Стрижка машинкой", "Clipper cut", 30000, 30),
            (shop_id, "Стрижка + борода", "Стрижка + борода",
             "Haircut + beard", 70000, 60),
            (shop_id, "Королевское бритье",
             "Королевское бритье", "Royal shave", 40000, 40),
            (shop_id, "Укладка", "Укладка", "Styling", 25000, 20)
        ]

        cursor.executemany('''
            INSERT INTO services 
            (barbershop_id, name_uz, name_ru, name_en, price, duration_minutes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', default_services)

        conn.commit()

        # Send success message
        success_text = f"🎉 *Поздравляем! Ваш барбершоп зарегистрирован!*\n\n"
        success_text += f"🏢 *Название:* {session.shop_data['name']}\n"
        success_text += f"📍 *Адрес:* {session.shop_data['address']}\n"
        success_text += f"👥 *Мастера:* {len(session.shop_data['barbers'])}\n"
        success_text += f"📸 *Фото:* {len(session.shop_data['photos'])}\n\n"
        success_text += "⏳ *Статус:* На модерации\n\n"
        success_text += "Ваша заявка отправлена на проверку администратору.\n"
        success_text += "Обычно проверка занимает 1-2 часа.\n"
        success_text += "Вы получите уведомление, когда барбершоп будет активирован.\n\n"
        success_text += "А пока вы можете:\n"
        success_text += "• Добавить дополнительные услуги\n"
        success_text += "• Настроить расписание работы\n"
        success_text += "• Добавить больше фото\n\n"
        success_text += "Спасибо за регистрацию в NavbatGo! ✨"

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(
            "🏠 Перейти в панель управления", callback_data="go_to_panel"))

        bot.send_message(
            message.chat.id,
            success_text,
            parse_mode='Markdown',
            reply_markup=markup
        )

        # Clear session
        clear_barber_session(user_id)

        # Notify admin about new registration
        notify_admin_about_new_shop(shop_id, session.shop_data['name'])

    except Exception as e:
        conn.rollback()
        print(f"Error saving barbershop: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при сохранении данных. Пожалуйста, попробуйте снова."
        )
    finally:
        conn.close()


def notify_admin_about_new_shop(shop_id, shop_name):
    """Notify admin about new barbershop registration"""
    # Get admin IDs from config
    from config import ADMIN_IDS

    for admin_id in ADMIN_IDS:
        try:
            text = f"🆕 *Новая заявка на регистрацию барбершопа!*\n\n"
            text += f"🏢 *Название:* {shop_name}\n"
            text += f"🆔 *ID:* {shop_id}\n"
            text += f"📅 *Дата:* {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            text += "Для проверки перейдите в админ-панель."

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("👨‍💼 Перейти в админку",
                       callback_data=f"admin_review_{shop_id}"))

            bot.send_message(
                admin_id,
                text,
                parse_mode='Markdown',
                reply_markup=markup
            )
        except:
            pass

# -------------------- BOOKINGS MANAGEMENT --------------------


@bot.callback_query_handler(func=lambda call: call.data.startswith('bookings_'))
def handle_bookings_menu(call):
    """Handle bookings menu"""
    user_id = call.from_user.id
    shop_id = int(call.data.split('_')[1])

    show_bookings_menu(call.message, user_id, shop_id)


def show_bookings_menu(message, user_id, shop_id):
    """Show bookings management menu"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    # Get shop name
    cursor.execute("SELECT name FROM barbershops WHERE id = ?", (shop_id,))
    shop_name = cursor.fetchone()[0]

    # Get today's bookings count
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT COUNT(*) FROM bookings 
        WHERE barbershop_id = ? AND booking_date = ? AND status IN ('pending', 'confirmed')
    ''', (shop_id, today))

    today_count = cursor.fetchone()[0]

    # Get pending bookings count
    cursor.execute('''
        SELECT COUNT(*) FROM bookings 
        WHERE barbershop_id = ? AND status = 'pending'
    ''', (shop_id,))

    pending_count = cursor.fetchone()[0]

    conn.close()

    text = f"📋 *Управление бронированиями*\n\n"
    text += f"🏢 *Барбершоп:* {shop_name}\n\n"
    text += f"📊 *Статистика:*\n"
    text += f"• Сегодня: {today_count} записей\n"
    text += f"• Ожидают подтверждения: {pending_count}\n\n"
    text += "Выберите действие:"

    markup = InlineKeyboardMarkup(row_width=2)

    markup.add(
        InlineKeyboardButton(
            "📅 Сегодня", callback_data=f"today_bookings_{shop_id}"),
        InlineKeyboardButton("⏳ На подтверждение",
                             callback_data=f"pending_bookings_{shop_id}")
    )

    markup.add(
        InlineKeyboardButton(
            "📆 На эту неделю", callback_data=f"week_bookings_{shop_id}"),
        InlineKeyboardButton(
            "🔍 Поиск брони", callback_data=f"search_booking_{shop_id}")
    )

    markup.add(InlineKeyboardButton(
        "🔙 Назад", callback_data=f"back_to_panel_{shop_id}"))

    if isinstance(message, types.Message):
        bot.send_message(
            message.chat.id,
            text,
            parse_mode='Markdown',
            reply_markup=markup
        )
    else:
        bot.edit_message_text(
            text,
            message.chat.id,
            message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith('today_bookings_'))
def show_today_bookings(call):
    """Show today's bookings"""
    user_id = call.from_user.id
    shop_id = int(call.data.split('_')[2])

    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT bk.id, br.full_name, u.full_name, bk.booking_time, bk.status, s.name_ru
        FROM bookings bk
        JOIN barbers br ON bk.barber_id = br.id
        JOIN users u ON bk.client_id = u.telegram_id
        LEFT JOIN services s ON bk.service_id = s.id
        WHERE bk.barbershop_id = ? AND bk.booking_date = ?
        ORDER BY bk.booking_time
    ''', (shop_id, today))

    bookings = cursor.fetchall()
    conn.close()

    if not bookings:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(
            "🔙 Назад", callback_data=f"bookings_{shop_id}"))

        bot.edit_message_text(
            "📭 *На сегодня нет записей*",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
        return

    text = f"📅 *Записи на сегодня ({today})*\n\n"

    for i, booking in enumerate(bookings, 1):
        booking_id, barber_name, client_name, time, status, service_name = booking

        status_emoji = {
            'pending': '⏳',
            'confirmed': '✅',
            'cancelled': '❌',
            'completed': '🏁'
        }.get(status, '❓')

        time_str = time[:5] if len(time) >= 5 else time

        text += f"{i}. {status_emoji} *{time_str}*\n"
        text += f"   💇 {barber_name}\n"
        text += f"   👤 {client_name}\n"
        if service_name:
            text += f"   💈 {service_name}\n"
        text += f"   [ID: {booking_id}]\n\n"

    markup = InlineKeyboardMarkup(row_width=2)

    # Add buttons for each booking
    for booking in bookings[:5]:  # Show first 5 bookings
        booking_id, barber_name, client_name, time, status, service_name = booking
        time_str = time[:5] if len(time) >= 5 else time
        btn_text = f"{time_str} - {client_name}"

        if len(btn_text) > 15:
            btn_text = btn_text[:15] + "..."

        markup.add(InlineKeyboardButton(
            btn_text, callback_data=f"view_booking_{booking_id}"))

    markup.add(InlineKeyboardButton(
        "🔙 Назад", callback_data=f"bookings_{shop_id}"))

    bot.edit_message_text(
        text[:4000],
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('view_booking_'))
def view_booking_details(call):
    """View booking details"""
    user_id = call.from_user.id
    booking_id = int(call.data.split('_')[2])

    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT bk.booking_date, bk.booking_time, bk.status, bk.notes,
               u.full_name, u.phone,
               br.full_name, b.name,
               s.name_ru, s.price
        FROM bookings bk
        JOIN users u ON bk.client_id = u.telegram_id
        JOIN barbers br ON bk.barber_id = br.id
        JOIN barbershops b ON bk.barbershop_id = b.id
        LEFT JOIN services s ON bk.service_id = s.id
        WHERE bk.id = ?
    ''', (booking_id,))

    booking = cursor.fetchone()
    conn.close()

    if not booking:
        bot.answer_callback_query(call.id, "❌ Бронь не найдена")
        return

    (date, time, status, notes, client_name, client_phone,
     barber_name, shop_name, service_name, price) = booking

    # Format status
    status_texts = {
        'pending': '⏳ Ожидает подтверждения',
        'confirmed': '✅ Подтверждена',
        'cancelled': '❌ Отменена',
        'completed': '🏁 Завершена'
    }

    status_display = status_texts.get(status, status)

    # Format details
    text = f"📋 *Детали бронирования*\n\n"
    text += f"🆔 *ID:* {booking_id}\n"
    text += f"📅 *Дата:* {date}\n"
    text += f"⏰ *Время:* {time}\n"
    text += f"📊 *Статус:* {status_display}\n\n"

    text += f"👤 *Клиент:*\n"
    text += f"• Имя: {client_name}\n"
    text += f"• Телефон: {client_phone or 'Не указан'}\n\n"

    text += f"💇 *Мастер:* {barber_name}\n"

    if service_name:
        text += f"💈 *Услуга:* {service_name}"
        if price:
            text += f" ({price} сум)"
        text += "\n"

    if notes:
        text += f"\n📝 *Заметки:* {notes}\n"

    markup = InlineKeyboardMarkup(row_width=2)

    # Add action buttons based on status
    if status == 'pending':
        markup.add(
            InlineKeyboardButton(
                "✅ Подтвердить", callback_data=f"confirm_booking_{booking_id}"),
            InlineKeyboardButton(
                "❌ Отклонить", callback_data=f"reject_booking_{booking_id}")
        )
    elif status == 'confirmed':
        markup.add(
            InlineKeyboardButton(
                "🏁 Завершить", callback_data=f"complete_booking_{booking_id}"),
            InlineKeyboardButton(
                "📞 Позвонить", callback_data=f"call_client_{booking_id}")
        )
    elif status == 'completed':
        markup.add(
            InlineKeyboardButton(
                "⭐ Оценить", callback_data=f"rate_booking_{booking_id}"),
            InlineKeyboardButton(
                "📞 Позвонить", callback_data=f"call_client_{booking_id}")
        )

    # Get shop_id for back button
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT barbershop_id FROM bookings WHERE id = ?", (booking_id,))
    shop_id = cursor.fetchone()[0]
    conn.close()

    markup.add(
        InlineKeyboardButton(
            "📋 К списку", callback_data=f"today_bookings_{shop_id}"),
        InlineKeyboardButton(
            "🏠 В панель", callback_data=f"back_to_panel_{shop_id}")
    )

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_booking_'))
def confirm_booking(call):
    """Confirm booking"""
    booking_id = int(call.data.split('_')[2])

    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE bookings SET status = 'confirmed' WHERE id = ?", (booking_id,))
    conn.commit()

    # Get booking info for notification
    cursor.execute('''
        SELECT u.telegram_id, b.name, br.full_name, bk.booking_date, bk.booking_time
        FROM bookings bk
        JOIN users u ON bk.client_id = u.telegram_id
        JOIN barbershops b ON bk.barbershop_id = b.id
        JOIN barbers br ON bk.barber_id = br.id
        WHERE bk.id = ?
    ''', (booking_id,))

    booking_info = cursor.fetchone()
    conn.close()

    if booking_info:
        client_id, shop_name, barber_name, date, time = booking_info

        # Notify client
        try:
            notification = f"✅ *Ваша бронь подтверждена!*\n\n"
            notification += f"🏢 *Барбершоп:* {shop_name}\n"
            notification += f"💇 *Мастер:* {barber_name}\n"
            notification += f"📅 *Дата:* {date}\n"
            notification += f"⏰ *Время:* {time}\n\n"
            notification += "📍 Пожалуйста, приходите вовремя!"

            bot.send_message(client_id, notification, parse_mode='Markdown')
        except:
            pass

    bot.answer_callback_query(call.id, "✅ Бронь подтверждена")

    # Refresh view
    view_booking_details(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_booking_'))
def reject_booking(call):
    """Reject booking"""
    booking_id = int(call.data.split('_')[2])

    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
    conn.commit()

    # Get booking info for notification
    cursor.execute('''
        SELECT u.telegram_id, b.name, br.full_name, bk.booking_date, bk.booking_time
        FROM bookings bk
        JOIN users u ON bk.client_id = u.telegram_id
        JOIN barbershops b ON bk.barbershop_id = b.id
        JOIN barbers br ON bk.barber_id = br.id
        WHERE bk.id = ?
    ''', (booking_id,))

    booking_info = cursor.fetchone()
    conn.close()

    if booking_info:
        client_id, shop_name, barber_name, date, time = booking_info

        # Notify client
        try:
            notification = f"❌ *Ваша бронь отклонена*\n\n"
            notification += f"🏢 *Барбершоп:* {shop_name}\n"
            notification += f"📅 *Дата:* {date}\n"
            notification += f"⏰ *Время:* {time}\n\n"
            notification += "Пожалуйста, выберите другое время или свяжитесь с барбершопом."

            bot.send_message(client_id, notification, parse_mode='Markdown')
        except:
            pass

    bot.answer_callback_query(call.id, "❌ Бронь отклонена")

    # Refresh view
    view_booking_details(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith('complete_booking_'))
def complete_booking(call):
    """Complete booking"""
    booking_id = int(call.data.split('_')[2])

    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE bookings SET status = 'completed' WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "🏁 Бронь завершена")

    # Refresh view
    view_booking_details(call)

# -------------------- BARBERS MANAGEMENT --------------------


@bot.callback_query_handler(func=lambda call: call.data.startswith('barbers_'))
def handle_barbers_menu(call):
    """Handle barbers management menu"""
    user_id = call.from_user.id
    shop_id = int(call.data.split('_')[1])

    show_barbers_management(call.message, user_id, shop_id)


def show_barbers_management(message, user_id, shop_id):
    """Show barbers management interface"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    # Get barbers
    cursor.execute('''
        SELECT id, full_name, experience_years, specialty, rating, is_active
        FROM barbers 
        WHERE barbershop_id = ?
        ORDER BY full_name
    ''', (shop_id,))

    barbers = cursor.fetchall()
    conn.close()

    text = f"👥 *Управление мастерами*\n\n"
    text += f"Всего мастеров: {len(barbers)}\n\n"

    for i, barber in enumerate(barbers, 1):
        barber_id, name, experience, specialty, rating, is_active = barber

        status = "🟢" if is_active == 1 else "🔴"
        exp_text = f" ({experience} лет)" if experience else ""
        spec_text = f" - {specialty}" if specialty else ""
        rating_text = f" ⭐{rating}" if rating else ""

        text += f"{i}. {status} *{name}*{exp_text}{spec_text}{rating_text}\n"

    text += "\nВыберите действие:"

    markup = InlineKeyboardMarkup(row_width=2)

    markup.add(
        InlineKeyboardButton("➕ Добавить мастера",
                             callback_data=f"add_barber_{shop_id}"),
        InlineKeyboardButton("✏️ Редактировать",
                             callback_data=f"edit_barbers_{shop_id}")
    )

    # Add buttons for each barber
    for barber in barbers[:5]:
        barber_id, name, experience, specialty, rating, is_active = barber
        btn_text = f"👤 {name}"
        if len(btn_text) > 15:
            btn_text = btn_text[:15] + "..."

        markup.add(InlineKeyboardButton(
            btn_text, callback_data=f"view_barber_{barber_id}"))

    markup.add(InlineKeyboardButton(
        "🔙 Назад", callback_data=f"back_to_panel_{shop_id}"))

    if isinstance(message, types.Message):
        bot.send_message(
            message.chat.id,
            text,
            parse_mode='Markdown',
            reply_markup=markup
        )
    else:
        bot.edit_message_text(
            text,
            message.chat.id,
            message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith('add_barber_'))
def add_new_barber(call):
    """Start adding new barber"""
    user_id = call.from_user.id
    shop_id = int(call.data.split('_')[2])

    # Store shop_id in session
    if user_id not in barber_sessions:
        barber_sessions[user_id] = BarberSession(user_id)

    session = barber_sessions[user_id]
    session.shop_data['shop_id'] = shop_id
    session.step = 'adding_barber_name'

    bot.send_message(
        call.message.chat.id,
        "👤 *Добавление нового мастера*\n\n"
        "Введите полное имя мастера:",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'adding_barber_name')
def handle_new_barber_name(message):
    """Handle new barber name input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    if len(message.text.strip()) < 2:
        bot.send_message(
            message.chat.id, "❌ Имя должно содержать минимум 2 символа")
        return

    session.current_barber = {
        'name': message.text.strip(),
        'experience': None,
        'specialty': None,
        'description': None,
        'photos': []
    }

    session.step = 'adding_barber_experience'

    bot.send_message(
        message.chat.id,
        "💼 *Сколько лет опыта у мастера?*\n\n"
        "Введите число (например: 3):",
        parse_mode='Markdown'
    )

# Continue with barber adding flow similar to registration...
# For brevity, I'll skip to the save function


def save_barber_to_db(message, user_id):
    """Save new barber to database"""
    session = barber_sessions[user_id]
    shop_id = session.shop_data.get('shop_id')

    if not shop_id or not session.current_barber['name']:
        bot.send_message(message.chat.id, "❌ Ошибка данных")
        return

    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO barbers 
            (barbershop_id, full_name, experience_years, specialty, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            shop_id,
            session.current_barber['name'],
            session.current_barber['experience'],
            session.current_barber['specialty'],
            session.current_barber['description']
        ))

        barber_id = cursor.lastrowid

        # Insert barber photos
        for photo_id in session.current_barber['photos']:
            cursor.execute('''
                INSERT INTO barber_photos (barber_id, photo_id)
                VALUES (?, ?)
            ''', (barber_id, photo_id))

        conn.commit()

        bot.send_message(
            message.chat.id,
            f"✅ Мастер '{session.current_barber['name']}' успешно добавлен!",
            parse_mode='Markdown'
        )

        # Clear current barber data
        session.current_barber = None
        session.step = None

        # Show barbers management again
        show_barbers_management(message, user_id, shop_id)

    except Exception as e:
        conn.rollback()
        print(f"Error saving barber: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при сохранении мастера."
        )
    finally:
        conn.close()

# -------------------- SERVICES MANAGEMENT --------------------


@bot.callback_query_handler(func=lambda call: call.data.startswith('services_'))
def handle_services_menu(call):
    """Handle services management menu"""
    user_id = call.from_user.id
    shop_id = int(call.data.split('_')[1])

    show_services_management(call.message, user_id, shop_id)


def show_services_management(message, user_id, shop_id):
    """Show services management interface"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    # Get services
    cursor.execute('''
        SELECT id, name_ru, price, duration_minutes, is_active
        FROM services 
        WHERE barbershop_id = ?
        ORDER BY price
    ''', (shop_id,))

    services = cursor.fetchall()
    conn.close()

    text = f"💈 *Управление услугами*\n\n"
    text += f"Всего услуг: {len(services)}\n\n"

    total_income = 0
    for i, service in enumerate(services, 1):
        service_id, name, price, duration, is_active = service

        status = "🟢" if is_active == 1 else "🔴"
        duration_text = f" ({duration} мин)" if duration else ""

        text += f"{i}. {status} *{name}*\n"
        text += f"   💰 {price} сум{duration_text}\n"

        total_income += price

    text += f"\n💰 *Общая стоимость услуг:* {total_income} сум\n\n"
    text += "Выберите действие:"

    markup = InlineKeyboardMarkup(row_width=2)

    markup.add(
        InlineKeyboardButton("➕ Добавить услугу",
                             callback_data=f"add_service_{shop_id}"),
        InlineKeyboardButton("✏️ Редактировать",
                             callback_data=f"edit_services_{shop_id}")
    )

    # Add buttons for each service
    for service in services[:5]:
        service_id, name, price, duration, is_active = service
        btn_text = f"💈 {name[:15]}..."

        markup.add(InlineKeyboardButton(
            btn_text, callback_data=f"view_service_{service_id}"))

    markup.add(InlineKeyboardButton(
        "🔙 Назад", callback_data=f"back_to_panel_{shop_id}"))

    if isinstance(message, types.Message):
        bot.send_message(
            message.chat.id,
            text,
            parse_mode='Markdown',
            reply_markup=markup
        )
    else:
        bot.edit_message_text(
            text,
            message.chat.id,
            message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith('add_service_'))
def add_new_service(call):
    """Start adding new service"""
    user_id = call.from_user.id
    shop_id = int(call.data.split('_')[2])

    # Store shop_id in session
    if user_id not in barber_sessions:
        barber_sessions[user_id] = BarberSession(user_id)

    session = barber_sessions[user_id]
    session.shop_data['shop_id'] = shop_id
    session.step = 'adding_service_name'

    bot.send_message(
        call.message.chat.id,
        "💈 *Добавление новой услуги*\n\n"
        "Введите название услуги на русском:",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'adding_service_name')
def handle_new_service_name(message):
    """Handle new service name input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    if len(message.text.strip()) < 2:
        bot.send_message(
            message.chat.id, "❌ Название должно содержать минимум 2 символа")
        return

    session.shop_data['new_service'] = {
        'name_ru': message.text.strip(),
        'name_uz': None,
        'name_en': None,
        'price': None,
        'duration': None
    }

    session.step = 'adding_service_price'

    bot.send_message(
        message.chat.id,
        "💰 *Введите цену услуги (в сумах):*\n\n"
        "Пример: 50000",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'adding_service_price')
def handle_new_service_price(message):
    """Handle new service price input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    try:
        price = int(message.text.strip())
        if price <= 0 or price > 1000000:
            bot.send_message(
                message.chat.id, "❌ Введите корректную цену (1-1,000,000 сум)")
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите число")
        return

    session.shop_data['new_service']['price'] = price
    session.step = 'adding_service_duration'

    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(
        "30 минут",
        "45 минут",
        "60 минут",
        "90 минут",
        "120 минут"
    )

    bot.send_message(
        message.chat.id,
        "⏱ *Выберите продолжительность услуги:*",
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.message_handler(func=lambda message:
                     message.from_user.id in barber_sessions and
                     barber_sessions[message.from_user.id].step == 'adding_service_duration')
def handle_new_service_duration(message):
    """Handle new service duration input"""
    user_id = message.from_user.id
    session = barber_sessions[user_id]

    duration_map = {
        "30 минут": 30,
        "45 минут": 45,
        "60 минут": 60,
        "90 минут": 90,
        "120 минут": 120
    }

    if message.text in duration_map:
        duration = duration_map[message.text]
    else:
        try:
            duration = int(message.text.strip().split()[0])
            if duration <= 0 or duration > 240:
                bot.send_message(
                    message.chat.id, "❌ Введите корректную продолжительность (1-240 минут)")
                return
        except:
            bot.send_message(
                message.chat.id, "❌ Пожалуйста, введите число минут")
            return

    session.shop_data['new_service']['duration'] = duration

    # Save service to database
    save_service_to_db(message, user_id)


def save_service_to_db(message, user_id):
    """Save new service to database"""
    session = barber_sessions[user_id]
    shop_id = session.shop_data.get('shop_id')
    service_data = session.shop_data.get('new_service')

    if not shop_id or not service_data:
        bot.send_message(message.chat.id, "❌ Ошибка данных")
        return

    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO services 
            (barbershop_id, name_uz, name_ru, name_en, price, duration_minutes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            shop_id,
            service_data['name_uz'] or service_data['name_ru'],
            service_data['name_ru'],
            service_data['name_en'] or service_data['name_ru'],
            service_data['price'],
            service_data['duration']
        ))

        conn.commit()

        bot.send_message(
            message.chat.id,
            f"✅ Услуга '{service_data['name_ru']}' успешно добавлена!\n"
            f"💰 Цена: {service_data['price']} сум\n"
            f"⏱ Продолжительность: {service_data['duration']} минут",
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()
        )

        # Clear service data
        session.shop_data['new_service'] = None
        session.step = None

        # Show services management again
        show_services_management(message, user_id, shop_id)

    except Exception as e:
        conn.rollback()
        print(f"Error saving service: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при сохранении услуги.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    finally:
        conn.close()

# -------------------- STATISTICS --------------------


@bot.callback_query_handler(func=lambda call: call.data.startswith('stats_'))
def handle_statistics(call):
    """Handle statistics menu"""
    user_id = call.from_user.id
    shop_id = int(call.data.split('_')[1])

    show_statistics(call.message, user_id, shop_id)


def show_statistics(message, user_id, shop_id):
    """Show barbershop statistics"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    # Get shop info
    cursor.execute("SELECT name FROM barbershops WHERE id = ?", (shop_id,))
    shop_name = cursor.fetchone()[0]

    # Get total bookings
    cursor.execute('''
        SELECT COUNT(*) as total_bookings,
               SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_bookings,
               SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_bookings,
               SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_bookings
        FROM bookings 
        WHERE barbershop_id = ?
    ''', (shop_id,))

    stats = cursor.fetchone()
    total_bookings, completed, confirmed, cancelled = stats

    # Get today's bookings
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT COUNT(*) FROM bookings 
        WHERE barbershop_id = ? AND booking_date = ?
    ''', (shop_id, today))

    today_bookings = cursor.fetchone()[0]

    # Get this month's bookings
    month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT COUNT(*) FROM bookings 
        WHERE barbershop_id = ? AND booking_date >= ?
    ''', (shop_id, month_start))

    month_bookings = cursor.fetchone()[0]

    # Get revenue from completed bookings
    cursor.execute('''
        SELECT SUM(s.price) as total_revenue
        FROM bookings bk
        JOIN services s ON bk.service_id = s.id
        WHERE bk.barbershop_id = ? AND bk.status = 'completed'
    ''', (shop_id,))

    revenue_result = cursor.fetchone()
    total_revenue = revenue_result[0] if revenue_result[0] else 0

    # Get barber stats
    cursor.execute('''
        SELECT br.full_name, COUNT(bk.id) as booking_count
        FROM bookings bk
        JOIN barbers br ON bk.barber_id = br.id
        WHERE bk.barbershop_id = ? AND bk.status = 'completed'
        GROUP BY br.id
        ORDER BY booking_count DESC
        LIMIT 5
    ''', (shop_id,))

    top_barbers = cursor.fetchall()

    # Get popular services
    cursor.execute('''
        SELECT s.name_ru, COUNT(bk.id) as service_count
        FROM bookings bk
        JOIN services s ON bk.service_id = s.id
        WHERE bk.barbershop_id = ? AND bk.status = 'completed'
        GROUP BY s.id
        ORDER BY service_count DESC
        LIMIT 5
    ''', (shop_id,))

    popular_services = cursor.fetchall()

    conn.close()

    # Format statistics
    text = f"📊 *Статистика барбершопа*\n\n"
    text += f"🏢 *{shop_name}*\n\n"

    text += f"📈 *Общая статистика:*\n"
    text += f"• Всего бронирований: {total_bookings}\n"
    text += f"• Завершено: {completed}\n"
    text += f"• Подтверждено: {confirmed}\n"
    text += f"• Отменено: {cancelled}\n"
    text += f"• Сегодня: {today_bookings}\n"
    text += f"• Этот месяц: {month_bookings}\n"
    text += f"💰 Общий доход: {total_revenue:,} сум\n\n"

    if top_barbers:
        text += f"🏆 *Топ мастеров:*\n"
        for i, (barber_name, count) in enumerate(top_barbers, 1):
            text += f"{i}. {barber_name}: {count} заказов\n"
        text += "\n"

    if popular_services:
        text += f"🔥 *Популярные услуги:*\n"
        for i, (service_name, count) in enumerate(popular_services, 1):
            text += f"{i}. {service_name}: {count}\n"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        "🔄 Обновить", callback_data=f"stats_{shop_id}"))
    markup.add(InlineKeyboardButton(
        "🔙 Назад", callback_data=f"back_to_panel_{shop_id}"))

    if isinstance(message, types.Message):
        bot.send_message(
            message.chat.id,
            text,
            parse_mode='Markdown',
            reply_markup=markup
        )
    else:
        bot.edit_message_text(
            text,
            message.chat.id,
            message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )

# -------------------- BACK BUTTONS --------------------


@bot.callback_query_handler(func=lambda call: call.data.startswith('back_to_panel_'))
def back_to_panel(call):
    """Go back to main panel"""
    user_id = call.from_user.id
    shop_id = int(call.data.split('_')[3])

    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, is_active FROM barbershops WHERE id = ?", (shop_id,))
    shop_info = cursor.fetchone()
    conn.close()

    if shop_info:
        shop_name, is_active = shop_info
        show_barber_panel(call.message, user_id, shop_id, shop_name, is_active)


@bot.callback_query_handler(func=lambda call: call.data == 'go_to_panel')
def go_to_panel(call):
    """Go to panel after registration"""
    user_id = call.from_user.id

    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, is_active FROM barbershops WHERE owner_id = ?", (user_id,))
    barbershop = cursor.fetchone()
    conn.close()

    if barbershop:
        shop_id, shop_name, is_active = barbershop
        show_barber_panel(call.message, user_id, shop_id, shop_name, is_active)
    else:
        bot.send_message(
            call.message.chat.id,
            "❌ Барбершоп не найден. Пожалуйста, зарегистрируйте барбершоп."
        )

# -------------------- MAIN --------------------


def startbarber():
    """Main function to start the bot"""
    print("💈 Barber bot is starting...")
    print("✅ Barber bot is running. Press Ctrl+C to stop.")
    bot.infinity_polling()


if __name__ == '__main__':
    startbarber()
