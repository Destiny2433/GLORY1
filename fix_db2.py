import sqlite3

def fix_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Create gallery table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT NOT NULL
        )
    ''')

    # Images to insert
    images = [
        'pr.jpg', 'logo.jpg', 'gloryt.jpg', 'gtr.jpg', 'Gallery/ecw.jpg',
        'Gallery/glo.jpg', 'Gallery/gltr.jpg', 'Gallery/hyt.jpg', 'Gallery/yt.jpg',
        'Gallery/logo.png', 'Gallery/585040828_17901420666303431_2278276743714763226_n.jpg',
        'Gallery/DE.jpg', 'Gallery/F.jpg', 'Gallery/FRANK.jpg', 'Gallery/glortyh.jpg',
        'Gallery/GRE.jpg', 'Gallery/IY.jpg', 'Gallery/LA.jpg', 'Gallery/PEACE.jpg',
        'Gallery/PIC.jpg', 'Gallery/PICT.jpg', 'Gallery/YUOP.jpg', 'Gallery/YUT.jpg',
        'g.jpg', 'pic.jpg', 'GL.jpg', 'Gallery/DE.jpg', 'Gallery/fds.jpg',
        'Gallery/fdse.jpg', 'Gallery/gfd.jpg', 'Gallery/gfr.jpg', 'Gallery/gr.jpg',
        'Gallery/ref.jpg', 'Gallery/trf.jpg', 'Gallery/guy.jpg', 'g.jpg',
        'Screenshot 2025-11-20 210745.png'
    ]

    # Insert only if table is empty
    cursor.execute('SELECT COUNT(*) FROM gallery')
    count = cursor.fetchone()[0]
    
    if count == 0:
        cursor.executemany('''
            INSERT INTO gallery (image_path) VALUES (?)
        ''', [(img,) for img in images])
        print(f"Inserted {len(images)} images into gallery.")
    else:
        print("Gallery table already populated.")

    conn.commit()
    conn.close()
    print("Database updated successfully.")

if __name__ == '__main__':
    fix_db()
