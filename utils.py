import sqlite3
import json
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from config import LANGUAGES, get_translation


def get_user_language(user_id):
    """Get user's language preference"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT language FROM users WHERE telegram_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'uz'


def get_text(user_id, key):
    """Get translated text for user"""
    lang = get_user_language(user_id)
    return get_translation(lang, key)


def register_user(telegram_id, full_name, username, phone, language='uz'):
    """Register a new user"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO users (telegram_id, full_name, username, phone, language)
            VALUES (?, ?, ?, ?, ?)
        ''', (telegram_id, full_name, username, phone, language))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error registering user: {e}")
        return False
    finally:
        conn.close()


def get_cities(language='uz'):
    """Get list of cities"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    if language == 'uz':
        cursor.execute(
            "SELECT id, name_uz FROM cities WHERE is_active = 1 ORDER BY name_uz")
    elif language == 'ru':
        cursor.execute(
            "SELECT id, name_ru FROM cities WHERE is_active = 1 ORDER BY name_ru")
    else:
        cursor.execute(
            "SELECT id, name_en FROM cities WHERE is_active = 1 ORDER BY name_en")

    cities = cursor.fetchall()
    conn.close()
    return cities


def get_districts(city_id, language='uz'):
    """Get districts for a city"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    if language == 'uz':
        cursor.execute('''
            SELECT id, name_uz FROM districts 
            WHERE city_id = ? AND is_active = 1 
            ORDER BY name_uz
        ''', (city_id,))
    elif language == 'ru':
        cursor.execute('''
            SELECT id, name_ru FROM districts 
            WHERE city_id = ? AND is_active = 1 
            ORDER BY name_ru
        ''', (city_id,))
    else:
        cursor.execute('''
            SELECT id, name_en FROM districts 
            WHERE city_id = ? AND is_active = 1 
            ORDER BY name_en
        ''', (city_id,))

    districts = cursor.fetchall()
    conn.close()
    return districts


def get_barbershops_by_location(city_id, district_id=None, language='uz'):
    """Get barbershops by location"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    query = '''
        SELECT id, name, address, phone, rating, description 
        FROM barbershops 
        WHERE city_id = ? AND is_active = 1
    '''
    params = [city_id]

    if district_id:
        query += ' AND district_id = ?'
        params.append(district_id)

    query += ' ORDER BY rating DESC, name'

    cursor.execute(query, params)
    barbershops = cursor.fetchall()
    conn.close()

    return barbershops


def get_barbershop_details(barbershop_id, language='uz'):
    """Get detailed information about a barbershop"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT b.name, b.address, b.phone, b.description, b.rating,
               c.name_uz, c.name_ru, c.name_en,
               d.name_uz, d.name_ru, d.name_en,
               b.latitude, b.longitude
        FROM barbershops b
        JOIN cities c ON b.city_id = c.id
        LEFT JOIN districts d ON b.district_id = d.id
        WHERE b.id = ?
    ''', (barbershop_id,))

    result = cursor.fetchone()

    # Get photos
    cursor.execute('''
        SELECT photo_id, caption, is_main 
        FROM barbershop_photos 
        WHERE barbershop_id = ? 
        ORDER BY is_main DESC
    ''', (barbershop_id,))
    photos = cursor.fetchall()

    # Get barbers
    cursor.execute('''
        SELECT id, full_name, experience_years, specialty, rating, description
        FROM barbers 
        WHERE barbershop_id = ? AND is_active = 1
        ORDER BY rating DESC
    ''', (barbershop_id,))
    barbers = cursor.fetchall()

    # Get services
    cursor.execute('''
        SELECT id, 
               CASE WHEN ? = 'uz' THEN name_uz 
                    WHEN ? = 'ru' THEN name_ru 
                    ELSE name_en END as name,
               price, duration_minutes
        FROM services 
        WHERE barbershop_id = ? AND is_active = 1
        ORDER BY price
    ''', (language, language, barbershop_id))
    services = cursor.fetchall()

    conn.close()

    if result:
        details = {
            'name': result[0],
            'address': result[1],
            'phone': result[2],
            'description': result[3],
            'rating': result[4],
            'city': result[5] if language == 'uz' else (result[6] if language == 'ru' else result[7]),
            'district': result[8] if language == 'uz' else (result[9] if language == 'ru' else result[10]) if result[8] else None,
            'latitude': result[11],
            'longitude': result[12],
            'photos': photos,
            'barbers': barbers,
            'services': services
        }
        return details
    return None


def create_booking(client_id, barber_id, barbershop_id, service_id, date, time, notes=''):
    """Create a new booking"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO bookings 
            (client_id, barber_id, barbershop_id, service_id, booking_date, booking_time, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        ''', (client_id, barber_id, barbershop_id, service_id, date, time, notes))

        booking_id = cursor.lastrowid
        conn.commit()

        # Get booking details for notification
        cursor.execute('''
            SELECT u.full_name, u.phone, b.name, br.full_name, s.name_uz, bk.booking_date, bk.booking_time
            FROM bookings bk
            JOIN users u ON bk.client_id = u.telegram_id
            JOIN barbershops b ON bk.barbershop_id = b.id
            JOIN barbers br ON bk.barber_id = br.id
            JOIN services s ON bk.service_id = s.id
            WHERE bk.id = ?
        ''', (booking_id,))

        booking_info = cursor.fetchone()
        conn.close()

        return booking_id, booking_info
    except Exception as e:
        conn.close()
        print(f"Error creating booking: {e}")
        return None, None


def get_user_bookings(user_id):
    """Get all bookings for a user"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT bk.id, b.name, br.full_name, bk.booking_date, bk.booking_time, bk.status,
               s.name_uz, s.price
        FROM bookings bk
        JOIN barbershops b ON bk.barbershop_id = b.id
        JOIN barbers br ON bk.barber_id = br.id
        LEFT JOIN services s ON bk.service_id = s.id
        WHERE bk.client_id = ?
        ORDER BY bk.booking_date DESC, bk.booking_time DESC
    ''', (user_id,))

    bookings = cursor.fetchall()
    conn.close()
    return bookings


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in kilometers"""
    if not all([lat1, lon1, lat2, lon2]):
        return None

    R = 6371  # Earth's radius in km

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    distance = R * c
    return round(distance, 2)


def get_nearby_barbershops(user_lat, user_lon, radius_km=5, language='uz'):
    """Get barbershops within specified radius"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, name, address, phone, rating, latitude, longitude
        FROM barbershops 
        WHERE is_active = 1 AND latitude IS NOT NULL AND longitude IS NOT NULL
    ''')

    all_shops = cursor.fetchall()
    conn.close()

    nearby_shops = []
    for shop in all_shops:
        shop_id, name, address, phone, rating, lat, lon = shop
        distance = calculate_distance(user_lat, user_lon, lat, lon)

        if distance and distance <= radius_km:
            nearby_shops.append({
                'id': shop_id,
                'name': name,
                'address': address,
                'phone': phone,
                'rating': rating,
                'distance': distance
            })

    # Sort by distance
    nearby_shops.sort(key=lambda x: x['distance'])
    return nearby_shops


def format_booking_details(booking_info, language='uz'):
    """Format booking details for display"""
    if not booking_info:
        return ""

    client_name, client_phone, shop_name, barber_name, service_name, date, time = booking_info

    details = f"📋 *{get_translation(language, 'booking_details')}*\n\n"
    details += f"👤 {get_translation(language, 'name')}: {client_name}\n"
    details += f"📞 {get_translation(language, 'phone')}: {client_phone}\n"
    details += f"🏢 {get_translation(language, 'name')}: {shop_name}\n"
    details += f"💇 {get_translation(language, 'barber')}: {barber_name}\n"
    if service_name:
        details += f"💈 {get_translation(language, 'services')}: {service_name}\n"
    details += f"📅 {get_translation(language, 'date')}: {date}\n"
    details += f"⏰ {get_translation(language, 'time')}: {time}\n"

    return details


def get_available_time_slots(barber_id, date):
    """Get available time slots for a barber on specific date"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    # Get barber's work schedule
    cursor.execute(
        "SELECT work_schedule FROM barbers WHERE id = ?", (barber_id,))
    result = cursor.fetchone()
    work_schedule = result[0] if result else "09:00-19:00"

    # Parse work schedule
    try:
        start_str, end_str = work_schedule.split('-')
        start_hour = int(start_str.split(':')[0])
        end_hour = int(end_str.split(':')[0])
    except:
        start_hour, end_hour = 9, 19

    # Get booked slots
    cursor.execute('''
        SELECT booking_time FROM bookings 
        WHERE barber_id = ? AND booking_date = ? AND status IN ('confirmed', 'pending')
    ''', (barber_id, date))

    booked_times = [row[0] for row in cursor.fetchall()]
    conn.close()

    # Generate time slots (every 30 minutes)
    available_slots = []
    for hour in range(start_hour, end_hour):
        for minute in [0, 30]:
            time_str = f"{hour:02d}:{minute:02d}"
            if time_str not in booked_times:
                available_slots.append(time_str)

    return available_slots


def send_booking_notifications(booking_id, bot):
    """Send notifications about new booking"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    # Get booking details
    cursor.execute('''
        SELECT b.owner_id, br.full_name, bk.booking_date, bk.booking_time,
               bs.name, u.full_name as client_name
        FROM bookings bk
        JOIN barbershops b ON bk.barbershop_id = b.id
        JOIN barbers br ON bk.barber_id = br.id
        JOIN users u ON bk.client_id = u.telegram_id
        WHERE bk.id = ?
    ''', (booking_id,))

    result = cursor.fetchone()
    if not result:
        conn.close()
        return

    owner_id, barber_name, date, time, shop_name, client_name = result

    # Send to barber owner
    notification = f"🆕 *Yangi bron!*\n\n"
    notification += f"🏢 Sartaroshxona: {shop_name}\n"
    notification += f"💇 Sartarosh: {barber_name}\n"
    notification += f"👤 Mijoz: {client_name}\n"
    notification += f"📅 Sana: {date}\n"
    notification += f"⏰ Vaqt: {time}\n"

    try:
        bot.send_message(owner_id, notification, parse_mode='Markdown')
    except:
        pass

    # Send to barber if different from owner
    cursor.execute(
        'SELECT telegram_id FROM barbers WHERE id = ?', (barber_user_id,))
    barber_user_id = cursor.fetchone()
    if barber_user_id and barber_user_id[0] != owner_id:
        try:
            bot.send_message(
                barber_user_id[0], notification, parse_mode='Markdown')
        except:
            pass

    conn.close()
