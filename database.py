import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kyc_database.db")

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Configuración de los 3 usuarios del sistema:
# 1 Propietario (con permisos totales de eliminación) + Manuel Mursuli + Iosef Bavo
DEFAULT_USERS = [
    {
        "username": "admin",
        "password": "Admin2026*",
        "full_name": "Propietario (Tú)",
        "role": "Propietario"
    },
    {
        "username": "mmursuli",
        "password": "Manuel2026*",
        "full_name": "Manuel Mursuli",
        "role": "Operador KYC"
    },
    {
        "username": "ibavo",
        "password": "Iosef2026*",
        "full_name": "Iosef Bavo",
        "role": "Operador KYC"
    }
]

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # KYC records table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kyc_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento_numero TEXT NOT NULL,
            nombre_apellido TEXT NOT NULL,
            tipo_documento TEXT DEFAULT 'Cédula de Identidad',
            fecha_hora TEXT NOT NULL,
            file_url TEXT NOT NULL,
            file_name TEXT,
            file_cloud_provider TEXT DEFAULT 'local',
            file_public_id TEXT,
            ocr_raw_text TEXT,
            estado TEXT DEFAULT 'Registrado',
            notas TEXT,
            uploaded_by TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    try:
        cursor.execute("ALTER TABLE kyc_records ADD COLUMN uploaded_by TEXT DEFAULT 'admin'")
    except sqlite3.OperationalError:
        pass
    
    # Settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kyc_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kyc_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'Operador KYC',
            is_active INTEGER DEFAULT 1,
            last_login TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Ensure default users exist and have correct roles
    for u in DEFAULT_USERS:
        cursor.execute("SELECT id, role FROM kyc_users WHERE LOWER(username) = ?", (u["username"].lower(),))
        existing = cursor.fetchone()
        pwd_hash = generate_password_hash(u["password"])
        
        if not existing:
            cursor.execute("""
                INSERT INTO kyc_users (username, password_hash, full_name, role)
                VALUES (?, ?, ?, ?)
            """, (u["username"].lower(), pwd_hash, u["full_name"], u["role"]))
        else:
            # Update role and full name to guarantee Propietario, Manuel Mursuli and Iosef Bavo
            cursor.execute("""
                UPDATE kyc_users 
                SET role = ?, full_name = ?
                WHERE id = ?
            """, (u["role"], u["full_name"], existing["id"]))
    
    # Clean up older dummy users if any exist (operador1, supervisor)
    cursor.execute("DELETE FROM kyc_users WHERE username IN ('operador1', 'supervisor')")
    
    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc ON kyc_records (documento_numero)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nombre ON kyc_records (nombre_apellido)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON kyc_users (username)")
    
    conn.commit()
    conn.close()

# User Management Functions
def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM kyc_users WHERE LOWER(username) = ?", (username.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def verify_user(username, password):
    user = get_user_by_username(username)
    if not user:
        return None
    if not user.get("is_active", 1):
        return None
    if check_password_hash(user["password_hash"], password):
        update_last_login(user["id"])
        return user
    return None

def create_user(username, password, full_name, role="Operador KYC"):
    username = username.lower().strip()
    if get_user_by_username(username):
        return False, f"El usuario '{username}' ya existe."
    
    pwd_hash = generate_password_hash(password)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO kyc_users (username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?)
        """, (username, pwd_hash, full_name.strip(), role))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return True, user_id
    except Exception as e:
        conn.close()
        return False, str(e)

def delete_user(user_id):
    """
    Deletes a user account.
    Prohibits deleting the Propietario account.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM kyc_users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return False, "Usuario no encontrado."
    
    if user["role"] == "Propietario":
        conn.close()
        return False, "No se puede eliminar la cuenta del Propietario."
    
    cursor.execute("DELETE FROM kyc_users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True, f"Usuario '{user['username']}' eliminado exitosamente."

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, full_name, role, is_active, last_login, created_at FROM kyc_users ORDER BY id ASC")
    users = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return users

def update_last_login(user_id):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE kyc_users SET last_login = ? WHERE id = ?", (now_str, user_id))
    conn.commit()
    conn.close()

# KYC Records Functions
def save_record(documento_numero, nombre_apellido, tipo_documento, fecha_hora, 
                file_url, file_name="", file_cloud_provider="local", file_public_id="", 
                ocr_raw_text="", estado="Registrado", notas="", uploaded_by="admin"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO kyc_records (
            documento_numero, nombre_apellido, tipo_documento, fecha_hora,
            file_url, file_name, file_cloud_provider, file_public_id,
            ocr_raw_text, estado, notas, uploaded_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        documento_numero.strip(),
        nombre_apellido.strip().upper(),
        tipo_documento.strip(),
        fecha_hora,
        file_url,
        file_name,
        file_cloud_provider,
        file_public_id,
        ocr_raw_text,
        estado,
        notas,
        uploaded_by
    ))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id

def delete_record(record_id):
    """
    Deletes a KYC document record by its ID.
    Returns the record dict for cleanup of local files if needed.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM kyc_records WHERE id = ?", (record_id,))
    record = cursor.fetchone()
    if not record:
        conn.close()
        return False, "Registro no encontrado."
    
    rec_dict = dict(record)
    cursor.execute("DELETE FROM kyc_records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    return True, rec_dict

def count_records(documento_numero=None, nombre_apellido=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    clean_doc = (documento_numero or "").strip()
    clean_nom = (nombre_apellido or "").strip()
    
    if not clean_doc and not clean_nom:
        conn.close()
        return 0, []
        
    if clean_doc and clean_nom:
        cursor.execute("""
            SELECT * FROM kyc_records 
            WHERE documento_numero = ? AND UPPER(nombre_apellido) LIKE ?
            ORDER BY id DESC
        """, (clean_doc, f"%{clean_nom.upper()}%"))
        rows = [dict(r) for r in cursor.fetchall()]
        if rows:
            conn.close()
            return len(rows), rows

        cursor.execute("SELECT * FROM kyc_records WHERE documento_numero = ? ORDER BY id DESC", (clean_doc,))
        rows = [dict(r) for r in cursor.fetchall()]
        if rows:
            conn.close()
            return len(rows), rows

        cursor.execute("SELECT * FROM kyc_records WHERE UPPER(nombre_apellido) LIKE ? ORDER BY id DESC", (f"%{clean_nom.upper()}%",))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return len(rows), rows

    if clean_doc:
        cursor.execute("SELECT * FROM kyc_records WHERE documento_numero = ? ORDER BY id DESC", (clean_doc,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return len(rows), rows

    if clean_nom:
        cursor.execute("SELECT * FROM kyc_records WHERE UPPER(nombre_apellido) LIKE ? ORDER BY id DESC", (f"%{clean_nom.upper()}%",))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return len(rows), rows

    conn.close()
    return 0, []

def search_records(query="", limit=100):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = (query or "").strip()
    if query:
        search_param = f"%{query.upper()}%"
        cursor.execute("""
            SELECT * FROM kyc_records 
            WHERE documento_numero LIKE ? OR UPPER(nombre_apellido) LIKE ? OR tipo_documento LIKE ?
            ORDER BY id DESC LIMIT ?
        """, (search_param, search_param, search_param, limit))
    else:
        cursor.execute("SELECT * FROM kyc_records ORDER BY id DESC LIMIT ?", (limit,))
        
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total_records FROM kyc_records")
    total_records = cursor.fetchone()["total_records"]
    
    cursor.execute("SELECT COUNT(DISTINCT documento_numero) as unique_clients FROM kyc_records")
    unique_clients = cursor.fetchone()["unique_clients"]
    
    cursor.execute("""
        SELECT documento_numero, nombre_apellido, COUNT(*) as count 
        FROM kyc_records 
        GROUP BY documento_numero 
        HAVING count > 1 
        ORDER BY count DESC 
        LIMIT 5
    """)
    duplicates = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return {
        "total_records": total_records,
        "unique_clients": unique_clients,
        "frequent_clients": duplicates
    }

def get_setting(key, default=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM kyc_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO kyc_settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()
