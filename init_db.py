import sqlite3

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Drop existing tables if re-initializing
    cursor.execute('DROP TABLE IF EXISTS events')
    cursor.execute('DROP TABLE IF EXISTS ministers')
    cursor.execute('DROP TABLE IF EXISTS hero')
    cursor.execute('DROP TABLE IF EXISTS gallery')
    cursor.execute('DROP TABLE IF EXISTS contact_messages')
    cursor.execute('DROP TABLE IF EXISTS volunteer_applications')
    cursor.execute('DROP TABLE IF EXISTS newsletter_subscribers')

    # Create tables
    cursor.execute('''
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            flyer_image TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE ministers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            image TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE hero (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            main_title TEXT NOT NULL,
            subtitle TEXT NOT NULL,
            media_path TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT,
            message TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE volunteer_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            age TEXT,
            team TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE newsletter_subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Insert default data
    cursor.execute('''
        INSERT INTO events (title, event_date, flyer_image)
        VALUES ('Mid Year Praise', 'Friday 19th June 2026', '705365290_17926303863303431_278754292481268159_n.jpg')
    ''')

    ministers = [
        ('Rev. Dr. David Aya', 'Guest Minister', 'frank.png'),
        ('Min. Pelumi Deborah', 'Gospel Minister', 'glory.jpeg'),
        ('Rev. Francis Arowolo', 'DCC Secretary', 'segun.png'),
        ('Rev. Moses Ayando', 'DCC Chairman', 'ayando.png'),
        ('ECWA LWDCC Praise Team', 'Praise Team', 'gtr.jpg')
    ]
    cursor.executemany('''
        INSERT INTO ministers (name, role, image)
        VALUES (?, ?, ?)
    ''', ministers)

    cursor.execute('''
        INSERT INTO hero (main_title, subtitle, media_path)
        VALUES (
            'ECWA GLORY CONCERT', 
            '"For I know the plans I have for you," declares the Lord, "plans to prosper you and not to harm you, plans to give you hope and a future." - Jeremiah 29:11', 
            'VID.mp4'
        )
    ''')

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == '__main__':
    init_db()
