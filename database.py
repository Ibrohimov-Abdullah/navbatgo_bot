import sqlite3
from datetime import datetime


def init_database():
    """Initialize the database with all required tables"""
    conn = sqlite3.connect('barbershop.db')
    cursor = conn.cursor()

    # Users (Clients)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        full_name TEXT,
        username TEXT,
        phone TEXT,
        language TEXT DEFAULT 'uz',
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Cities
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name_uz TEXT,
        name_ru TEXT,
        name_en TEXT,
        is_active BOOLEAN DEFAULT 1
    )
    ''')

    # Districts
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS districts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id INTEGER,
        name_uz TEXT,
        name_ru TEXT,
        name_en TEXT,
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY (city_id) REFERENCES cities (id)
    )
    ''')

    # Barbershops
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS barbershops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        name TEXT,
        city_id INTEGER,
        district_id INTEGER,
        address TEXT,
        phone TEXT,
        description TEXT,
        latitude REAL,
        longitude REAL,
        rating REAL DEFAULT 0,
        is_active BOOLEAN DEFAULT 0, -- 0 = pending approval, 1 = active
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (city_id) REFERENCES cities (id),
        FOREIGN KEY (district_id) REFERENCES districts (id),
        FOREIGN KEY (owner_id) REFERENCES users (telegram_id)
    )
    ''')

    # Barbershop Photos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS barbershop_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barbershop_id INTEGER,
        photo_id TEXT,
        caption TEXT,
        is_main BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (barbershop_id) REFERENCES barbershops (id)
    )
    ''')

    # Barbers
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS barbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barbershop_id INTEGER,
        full_name TEXT,
        experience_years INTEGER DEFAULT 0,
        specialty TEXT,
        description TEXT,
        rating REAL DEFAULT 0,
        is_active BOOLEAN DEFAULT 1,
        work_schedule TEXT DEFAULT '09:00-19:00',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (barbershop_id) REFERENCES barbershops (id)
    )
    ''')

    # Barber Photos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS barber_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barber_id INTEGER,
        photo_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (barber_id) REFERENCES barbers (id)
    )
    ''')

    # Services
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barbershop_id INTEGER,
        name_uz TEXT,
        name_ru TEXT,
        name_en TEXT,
        price INTEGER,
        duration_minutes INTEGER DEFAULT 30,
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY (barbershop_id) REFERENCES barbershops (id)
    )
    ''')

    # Bookings
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        barber_id INTEGER,
        barbershop_id INTEGER,
        service_id INTEGER,
        booking_date DATE,
        booking_time TIME,
        status TEXT DEFAULT 'pending', -- pending, confirmed, cancelled, completed
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES users (telegram_id),
        FOREIGN KEY (barber_id) REFERENCES barbers (id),
        FOREIGN KEY (barbershop_id) REFERENCES barbershops (id),
        FOREIGN KEY (service_id) REFERENCES services (id)
    )
    ''')

    # Reviews
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER UNIQUE,
        rating INTEGER CHECK(rating >= 1 AND rating <= 5),
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES bookings (id)
    )
    ''')

    # Insert default cities
    cursor.execute("SELECT COUNT(*) FROM cities")
    if cursor.fetchone()[0] == 0:
        default_cities = [
            ('Toshkent', 'Ташкент', 'Tashkent'),
            ('Andijon', 'Андижан', 'Andijan'),
            ('Samarqand', 'Самарканд', 'Samarkand'),
            ('Buxoro', 'Бухара', 'Bukhara'),
            ('Namangan', 'Наманган', 'Namangan'),
            ('Farg\'ona', 'Фергана', 'Fergana'),
            ('Jizzax', 'Джизак', 'Jizzakh'),
            ('Navoiy', 'Навои', 'Navoi'),
            ('Qarshi', 'Карши', 'Karshi'),
            ('Nukus', 'Нукус', 'Nukus')
        ]
        cursor.executemany(
            "INSERT INTO cities (name_uz, name_ru, name_en) VALUES (?, ?, ?)",
            default_cities
        )

    # Insert default districts for Tashkent
    cursor.execute("SELECT id FROM cities WHERE name_uz = 'Toshkent'")
    tashkent_id = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM districts WHERE city_id = ?", (tashkent_id,))
    if cursor.fetchone()[0] == 0:
        tashkent_districts = [
            (tashkent_id, 'Yunusobod', 'Юнусабад', 'Yunusabad'),
            (tashkent_id, 'Mirzo Ulug\'bek', 'Мирзо Улугбек', 'Mirzo Ulugbek'),
            (tashkent_id, 'Shayxontoxur', 'Шайхонтохур', 'Shaykhantakhur'),
            (tashkent_id, 'Chilonzor', 'Чиланзар', 'Chilanzar'),
            (tashkent_id, 'Olmazor', 'Олмазор', 'Olmazor'),
            (tashkent_id, 'Yakkasaroy', 'Яккасарай', 'Yakkasaray'),
            (tashkent_id, 'Mirobod', 'Миробод', 'Mirobod'),
            (tashkent_id, 'Sergeli', 'Сергели', 'Sergeli'),
            (tashkent_id, 'Bektemir', 'Бектемир', 'Bektemir'),
            (tashkent_id, 'Uchtepa', 'Учтепа', 'Uchtepa')
        ]
        cursor.executemany(
            "INSERT INTO districts (city_id, name_uz, name_ru, name_en) VALUES (?, ?, ?, ?)",
            tashkent_districts
        )

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")


def get_db_connection():
    """Get database connection"""
    return sqlite3.connect('barbershop.db')


# Initialize database when module is imported
init_database()
