import os
import io
import socket
import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, redirect, url_for, session
from werkzeug.utils import secure_filename
import pandas as pd

from database import (
    init_db, save_record, delete_record, count_records, search_records, get_stats, 
    set_setting, get_setting, verify_user, create_user, delete_user, get_all_users
)
from ocr_engine import process_identity_document
from cloud_storage import upload_file_to_cloud, get_cloud_config, test_cloud_connection, UPLOAD_DIR

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'kyc_clientes_security_secret_2026_x89a')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max upload

# Initialize database
init_db()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_local_ip():
    """Returns local network IPv4 address for sharing link."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def get_public_url():
    """Returns public HTTPS tunnel URL if active."""
    public_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public_url.txt")
    if os.path.exists(public_file):
        try:
            with open(public_file, "r", encoding="utf-8") as f:
                url = f.read().strip()
                if url.startswith("https://"):
                    return url
        except Exception:
            pass
    db_url = get_setting("public_tunnel_url", "")
    if db_url and db_url.startswith("https://"):
        return db_url
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "error": "Sesión expirada. Debe iniciar sesión."}), 401
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def owner_required(f):
    """Requires the logged-in user to be the Propietario (Owner)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"success": False, "error": "Debe iniciar sesión."}), 401
        if session.get('role') != 'Propietario':
            return jsonify({"success": False, "error": "Acceso denegado. Solo el Propietario tiene permisos para esta acción."}), 403
        return f(*args, **kwargs)
    return decorated_function

# ================= AUTHENTICATION ROUTES =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    port = int(os.environ.get('PORT', 5000))
    local_ip = get_local_ip()
    local_network_url = f"http://{local_ip}:{port}/login"
    public_base = get_public_url()
    public_url = f"{public_base}/login" if public_base else None
    share_url = public_url if public_url else local_network_url

    if 'user_id' in session:
        return redirect(url_for('index'))

    error = None

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = verify_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            next_url = request.args.get('next') or url_for('index')
            return redirect(next_url)
        else:
            error = "Usuario o contraseña incorrectos. Verifique sus credenciales autorizadas."

    return render_template('login.html', error=error, network_url=share_url, public_url=public_url, local_network_url=local_network_url)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ================= MAIN APPLICATION =================

@app.route('/')
@login_required
def index():
    cloud_info = get_cloud_config()
    stats = get_stats()
    port = int(os.environ.get('PORT', 5000))
    local_ip = get_local_ip()
    local_network_url = f"http://{local_ip}:{port}/login"
    public_base = get_public_url()
    public_url = f"{public_base}/login" if public_base else None
    share_url = public_url if public_url else local_network_url
    is_owner = (session.get('role') == 'Propietario')
    return render_template('index.html', cloud_info=cloud_info, stats=stats, 
                           network_url=share_url, public_url=public_url, local_network_url=local_network_url,
                           is_owner=is_owner)

@app.route('/uploads/<path:filename>')
@login_required
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)

# ================= API ENDPOINTS =================

@app.route('/api/users', methods=['GET'])
@login_required
def get_users_list():
    users = get_all_users()
    is_owner = (session.get('role') == 'Propietario')
    return jsonify({"success": True, "users": users, "is_owner": is_owner})

@app.route('/api/users', methods=['POST'])
@owner_required
def handle_create_user():
    data = request.json or {}
    full_name = data.get("full_name", "").strip()
    username = data.get("username", "").strip()
    role = data.get("role", "Operador KYC").strip()
    password = data.get("password", "").strip()

    if not full_name or not username or not password:
        return jsonify({"success": False, "error": "Todos los campos son requeridos."}), 400

    ok, res = create_user(username, password, full_name, role)
    if ok:
        return jsonify({"success": True, "message": f"Usuario '{username}' creado exitosamente."})
    else:
        return jsonify({"success": False, "error": res}), 400

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@owner_required
def handle_delete_user(user_id):
    """Only Propietario can delete other user accounts."""
    ok, msg = delete_user(user_id)
    if ok:
        return jsonify({"success": True, "message": msg})
    else:
        return jsonify({"success": False, "error": msg}), 400

@app.route('/api/records/<int:record_id>', methods=['DELETE'])
@owner_required
def handle_delete_record(record_id):
    """Only Propietario can delete uploaded records and documents."""
    ok, res = delete_record(record_id)
    if not ok:
        return jsonify({"success": False, "error": res}), 400

    # Clean local file if stored locally
    try:
        if res.get("file_cloud_provider") == "local" and res.get("file_name"):
            local_file = os.path.join(UPLOAD_DIR, res["file_name"])
            if os.path.exists(local_file):
                os.remove(local_file)
    except Exception as e:
        print(f"[File cleanup warning] {e}")

    return jsonify({"success": True, "message": f"Registro #{record_id} eliminado exitosamente."})

@app.route('/api/scan-and-upload', methods=['POST'])
@login_required
def scan_and_upload():
    """
    Receives an ID document (image or PDF).
    1. Uploads to Cloud Storage (Cloudinary / S3 / Local).
    2. Runs OCR to automatically extract document number and name.
    3. Queries how many times this client/doc was previously registered.
    4. Automatically records or returns data for client verification.
    """
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No se seleccionó ningún archivo."}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "El archivo está vacío."}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": "Formato no permitido. Suba JPG, PNG, WEBP o PDF."}), 400

    auto_save = request.form.get("auto_save", "true").lower() == "true"
    tipo_doc_override = request.form.get("tipo_documento", "").strip()
    notas = request.form.get("notas", "").strip()
    client_ocr = request.form.get("client_ocr_text", "").strip()

    # Step 1: Upload to Cloud / Local Storage
    cloud_result = upload_file_to_cloud(file)
    local_path = cloud_result["local_path"]
    is_pdf = local_path.lower().endswith(".pdf")

    # Step 2: OCR Extraction
    try:
        ocr_result = process_identity_document(local_path, is_pdf=is_pdf, client_ocr_text=client_ocr)
    except Exception as e:
        ocr_result = {
            "success": False,
            "tipo_documento": "Cédula de Identidad",
            "documento_numero": "",
            "nombre_apellido": "",
            "raw_text": f"Error procesando OCR: {str(e)}"
        }

    tipo_doc = tipo_doc_override or ocr_result.get("tipo_documento") or "Cédula de Identidad"
    doc_num = ocr_result.get("documento_numero", "").strip()
    nombre = ocr_result.get("nombre_apellido", "").strip()
    pais = request.form.get("pais_nacionalidad", "").strip() or ocr_result.get("pais_nacionalidad", "Desconocido").strip()
    raw_ocr = ocr_result.get("raw_text", "")

    # Exact upload timestamp (format: YYYY-MM-DD HH:MM:SS)
    now = datetime.datetime.now()
    fecha_hora_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Query how many times registered so far
    prev_count = 0
    if doc_num or nombre:
        prev_count, _ = count_records(documento_numero=doc_num, nombre_apellido=nombre)

    current_user = session.get('username', 'admin')

    record_id = None
    if auto_save and (doc_num or nombre):
        record_id = save_record(
            documento_numero=doc_num if doc_num else "S/N",
            nombre_apellido=nombre if nombre else "DESCONOCIDO",
            tipo_documento=tipo_doc,
            pais_nacionalidad=pais,
            fecha_hora=fecha_hora_str,
            file_url=cloud_result["file_url"],
            file_name=cloud_result["file_name"],
            file_cloud_provider=cloud_result["provider"],
            file_public_id=cloud_result["public_id"],
            ocr_raw_text=raw_ocr,
            estado="Registrado",
            notas=notas,
            uploaded_by=current_user
        )
        total_times_registered = prev_count + 1
    else:
        total_times_registered = prev_count

    return jsonify({
        "success": True,
        "record_id": record_id,
        "documento_numero": doc_num,
        "nombre_apellido": nombre,
        "pais_nacionalidad": pais,
        "tipo_documento": tipo_doc,
        "fecha_hora": fecha_hora_str,
        "file_url": cloud_result["file_url"],
        "file_name": cloud_result["file_name"],
        "cloud_provider": cloud_result["provider"],
        "ocr_raw_text": raw_ocr,
        "times_registered": total_times_registered,
        "is_repeat": total_times_registered > 1
    })

@app.route('/api/confirm-save', methods=['POST'])
@login_required
def confirm_save():
    """
    Saves or updates manual corrections made by the user to the scanned document.
    """
    data = request.json or {}
    doc_num = data.get("documento_numero", "").strip()
    nombre = data.get("nombre_apellido", "").strip()
    pais = data.get("pais_nacionalidad", "Desconocido").strip()
    tipo_doc = data.get("tipo_documento", "Cédula de Identidad").strip()
    file_url = data.get("file_url", "").strip()
    file_name = data.get("file_name", "").strip()
    cloud_provider = data.get("cloud_provider", "local").strip()
    public_id = data.get("public_id", "").strip()
    raw_ocr = data.get("ocr_raw_text", "").strip()
    notas = data.get("notas", "").strip()
    
    if not doc_num and not nombre:
        return jsonify({"success": False, "error": "Debe especificar número de documento o nombre."}), 400

    now = datetime.datetime.now()
    fecha_hora_str = now.strftime("%Y-%m-%d %H:%M:%S")

    prev_count, _ = count_records(documento_numero=doc_num, nombre_apellido=nombre)
    current_user = session.get('username', 'admin')

    record_id = save_record(
        documento_numero=doc_num if doc_num else "S/N",
        nombre_apellido=nombre if nombre else "DESCONOCIDO",
        tipo_documento=tipo_doc,
        pais_nacionalidad=pais,
        fecha_hora=fecha_hora_str,
        file_url=file_url,
        file_name=file_name,
        file_cloud_provider=cloud_provider,
        file_public_id=public_id,
        ocr_raw_text=raw_ocr,
        estado="Registrado",
        notas=notas,
        uploaded_by=current_user
    )

    total_times = prev_count + 1

    return jsonify({
        "success": True,
        "record_id": record_id,
        "documento_numero": doc_num,
        "nombre_apellido": nombre,
        "pais_nacionalidad": pais,
        "fecha_hora": fecha_hora_str,
        "times_registered": total_times,
        "is_repeat": total_times > 1
    })

@app.route('/api/check-client', methods=['GET'])
@login_required
def check_client():
    """
    Core requirement:
    'AL PONER SU CEDULA Y NOMBRE ME APAREZCA CUANTAS VECES FUE REGISTRADO'
    """
    doc_num = request.args.get("cedula", "").strip()
    nombre = request.args.get("nombre", "").strip()

    if not doc_num and not nombre:
        return jsonify({
            "success": False,
            "error": "Ingrese al menos la cédula o el nombre para consultar."
        }), 400

    count, records = count_records(documento_numero=doc_num, nombre_apellido=nombre)
    
    first_seen = records[-1]["fecha_hora"] if records else None
    last_seen = records[0]["fecha_hora"] if records else None

    return jsonify({
        "success": True,
        "search_cedula": doc_num,
        "search_nombre": nombre,
        "times_registered": count,
        "is_registered": count > 0,
        "is_repeat": count > 1,
        "first_registered": first_seen,
        "last_registered": last_seen,
        "history": records
    })

@app.route('/api/records', methods=['GET'])
@login_required
def get_all_records():
    query = request.args.get("q", "")
    limit = int(request.args.get("limit", 100))
    records = search_records(query=query, limit=limit)
    is_owner = (session.get('role') == 'Propietario')
    return jsonify({
        "success": True,
        "count": len(records),
        "records": records,
        "is_owner": is_owner
    })

@app.route('/api/stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    return jsonify({
        "success": True,
        "stats": get_stats(),
        "cloud": get_cloud_config(),
        "is_owner": (session.get('role') == 'Propietario')
    })

@app.route('/api/config/cloud', methods=['POST'])
@owner_required
def save_cloud_configuration():
    """Only Propietario can configure cloud credentials."""
    data = request.json or {}
    provider = data.get("provider", "local")
    
    if provider == "cloudinary":
        c_name = data.get("cloud_name", "").strip()
        c_key = data.get("api_key", "").strip()
        c_secret = data.get("api_secret", "").strip()
        c_url = data.get("url", "").strip()
        
        ok, msg = test_cloud_connection("cloudinary", {
            "cloud_name": c_name,
            "api_key": c_key,
            "api_secret": c_secret,
            "url": c_url
        })
        if not ok:
            return jsonify({"success": False, "error": msg}), 400
            
        set_setting("cloud_provider", "cloudinary")
        set_setting("cloudinary_cloud_name", c_name)
        set_setting("cloudinary_api_key", c_key)
        set_setting("cloudinary_api_secret", c_secret)
        set_setting("cloudinary_url", c_url)
        return jsonify({"success": True, "message": "Cloudinary configurado exitosamente."})
        
    elif provider == "s3":
        bucket = data.get("bucket", "").strip()
        key = data.get("access_key", "").strip()
        secret = data.get("secret_key", "").strip()
        region = data.get("region", "us-east-1").strip()
        endpoint = data.get("endpoint", "").strip()
        
        ok, msg = test_cloud_connection("s3", {
            "bucket": bucket,
            "access_key": key,
            "secret_key": secret,
            "region": region,
            "endpoint": endpoint
        })
        if not ok:
            return jsonify({"success": False, "error": msg}), 400
            
        set_setting("cloud_provider", "s3")
        set_setting("s3_bucket", bucket)
        set_setting("s3_access_key", key)
        set_setting("s3_secret_key", secret)
        set_setting("s3_region", region)
        set_setting("s3_endpoint", endpoint)
        return jsonify({"success": True, "message": "AWS S3 / Supabase configurado exitosamente."})
        
    else:
        set_setting("cloud_provider", "local")
        return jsonify({"success": True, "message": "Modo de almacenamiento local activado."})

@app.route('/api/export/excel', methods=['GET'])
@login_required
def export_excel():
    records = search_records(query="", limit=10000)
    if not records:
        return "No hay registros para exportar.", 400
        
    df = pd.DataFrame(records)
    columns_map = {
        "id": "ID",
        "documento_numero": "Cédula / Documento",
        "nombre_apellido": "Nombre y Apellido",
        "pais_nacionalidad": "País / Nacionalidad",
        "tipo_documento": "Tipo de Documento",
        "fecha_hora": "Fecha y Hora de Subida",
        "file_url": "Enlace del Documento (Nube)",
        "file_cloud_provider": "Almacenamiento",
        "uploaded_by": "Registrado Por",
        "estado": "Estado KYC",
        "notas": "Notas"
    }
    
    existing_cols = [c for c in columns_map.keys() if c in df.columns]
    df = df[existing_cols].rename(columns=columns_map)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='KYC_CLIENTES')
    output.seek(0)
    
    filename = f"KYC_CLIENTES_EXPORT_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    local_ip = get_local_ip()
    print("=" * 60)
    print(">> KYC CLIENTES iniciado con exito!")
    print(f"[*] Acceso local (esta maquina):          http://localhost:{port}/login")
    print(f"[*] Link para otras personas (LAN/Wi-Fi): http://{local_ip}:{port}/login")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=True)
