import sqlite3

DB_FILE = 'musics.db'

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Таблица лайков пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            video_id TEXT,
            title TEXT,
            file_id TEXT,
            UNIQUE(user_id, video_id)
        )
    ''')
    # Таблица всех пользователей бота (для рассылки и статистики)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            language TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_like(user_id: int, video_id: str, title: str, file_id: str = ""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Записываем или обновляем
    c.execute('''
        INSERT OR REPLACE INTO likes (user_id, video_id, title, file_id) 
        VALUES (?, ?, ?, ?)
    ''', (user_id, video_id, title, file_id))
    conn.commit()
    conn.close()

def remove_like(user_id: int, video_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM likes WHERE user_id = ? AND video_id = ?', (user_id, video_id))
    conn.commit()
    conn.close()

def has_like(user_id: int, video_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM likes WHERE user_id = ? AND video_id = ?', (user_id, video_id))
    result = c.fetchone()
    conn.close()
    return bool(result)

def get_likes(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Возвращаем все сохраненные песни для пользователя
    c.execute('SELECT video_id, title, file_id FROM likes WHERE user_id = ?', (user_id,))
    results = c.fetchall()
    conn.close()
    return results

# Инициализируем базу данных при первом импорте файла
init_db()

# ===================== USERS & ADMIN =====================

def add_user(user_id: int, username: str, first_name: str):
    """Добавляет или обновляет пользователя в базе."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name) 
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                username = excluded.username,
                first_name = excluded.first_name
        ''', (user_id, username, first_name))
        conn.commit()
    except Exception as e:
        print(f"Ошибка при сохранении пользователя: {e}")
    finally:
        conn.close()

def get_user_language(user_id: int):
    """Возвращает язык пользователя или None."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except:
        return None
    finally:
        conn.close()

def set_user_language(user_id: int, lang: str):
    """Устанавливает язык пользователя."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
        conn.commit()
    except Exception as e:
        print(f"Ошибка сохранения языка: {e}")
    finally:
        conn.close()

def get_users_by_language(lang: str = None):
    """Возвращает список ID пользователей по языку (или всех)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if lang:
            cursor.execute("SELECT user_id FROM users WHERE language = ?", (lang,))
        else:
            cursor.execute("SELECT user_id FROM users")
        results = cursor.fetchall()
        return [row[0] for row in results]
    except Exception as e:
        print(f"Ошибка при получении списка пользователей: {e}")
        return []
    finally:
        conn.close()

def get_stats():
    """Возвращает расширенную статистику."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users")
        u_total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE language = 'ru'")
        u_ru = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE language = 'en'")
        u_en = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE language = 'uz'")
        u_uz = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE language IS NULL")
        u_none = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM likes")
        likes = cursor.fetchone()[0]
        return {
            'total': u_total,
            'ru': u_ru,
            'en': u_en,
            'uz': u_uz,
            'none': u_none,
            'likes': likes
        }
    except Exception as e:
        print(f"Ошибка статистики: {e}")
        return {}
    finally:
        conn.close()
