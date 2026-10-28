import os
import uuid
import datetime
import json
import sqlite3
import zipfile
import shutil
from pathlib import Path

# Base upload directory for local storage & backup
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Google Drive default account
DEFAULT_GDRIVE_EMAIL = "contabilidadalejandro3@gmail.com"

# Optional cloud drivers
try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    cloudinary = None

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None

try:
    import requests
except ImportError:
    requests = None

from database import get_setting, DB_FILE

def get_cloud_config():
    """
    Retrieves cloud configuration from environment or database settings.
    """
    provider = os.getenv("CLOUD_PROVIDER") or get_setting("cloud_provider", "local")
    
    # Cloudinary config
    c_name = os.getenv("CLOUDINARY_CLOUD_NAME") or get_setting("cloudinary_cloud_name", "")
    c_key = os.getenv("CLOUDINARY_API_KEY") or get_setting("cloudinary_api_key", "")
    c_secret = os.getenv("CLOUDINARY_API_SECRET") or get_setting("cloudinary_api_secret", "")
    c_url = os.getenv("CLOUDINARY_URL") or get_setting("cloudinary_url", "")
    
    # S3 / Supabase config
    s3_bucket = os.getenv("AWS_BUCKET_NAME") or get_setting("s3_bucket", "")
    s3_key = os.getenv("AWS_ACCESS_KEY_ID") or get_setting("s3_access_key", "")
    s3_secret = os.getenv("AWS_SECRET_ACCESS_KEY") or get_setting("s3_secret_key", "")
    s3_region = os.getenv("AWS_REGION") or get_setting("s3_region", "us-east-1")
    s3_endpoint = os.getenv("AWS_ENDPOINT_URL") or get_setting("s3_endpoint", "")
    
    # Google Drive config for contabilidadalejandro3@gmail.com
    gd_email = os.getenv("GDRIVE_ACCOUNT_EMAIL") or get_setting("gdrive_account_email", DEFAULT_GDRIVE_EMAIL)
    gd_token = os.getenv("GDRIVE_ACCESS_TOKEN") or get_setting("gdrive_access_token", "")
    gd_folder_id = os.getenv("GDRIVE_FOLDER_ID") or get_setting("gdrive_folder_id", "")
    
    return {
        "provider": provider,
        "gdrive": {
            "email": gd_email,
            "token": gd_token,
            "folder_id": gd_folder_id,
            "configured": bool(gd_token)
        },
        "cloudinary": {
            "cloud_name": c_name,
            "api_key": c_key,
            "api_secret": c_secret,
            "url": c_url,
            "configured": bool(c_url or (c_name and c_key and c_secret))
        },
        "s3": {
            "bucket": s3_bucket,
            "access_key": s3_key,
            "secret_key": s3_secret,
            "region": s3_region,
            "endpoint": s3_endpoint,
            "configured": bool(s3_bucket and s3_key and s3_secret)
        }
    }

def upload_file_to_cloud(file_storage, custom_filename=None):
    """
    Saves the file to local backup and uploads it to the configured cloud provider (Google Drive, Cloudinary, S3, or Local).
    Returns dict: {
        "file_url": str,
        "file_name": str,
        "provider": str,
        "public_id": str,
        "local_path": str
    }
    """
    config = get_cloud_config()
    
    # Generate unique safe filename
    original_name = getattr(file_storage, "filename", "document.jpg")
    ext = os.path.splitext(original_name)[1].lower() or ".jpg"
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"kyc_{timestamp}_{unique_id}{ext}"
    
    local_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    # Save a local copy first for OCR processing and local access
    file_storage.seek(0)
    file_storage.save(local_path)
    file_storage.seek(0)
    
    # 1. Try Google Drive if configured
    if config["provider"] == "gdrive" and config["gdrive"]["token"] and requests:
        try:
            gd_conf = config["gdrive"]
            headers = {"Authorization": f"Bearer {gd_conf['token']}"}
            metadata = {"name": safe_filename}
            if gd_conf["folder_id"]:
                metadata["parents"] = [gd_conf["folder_id"]]
                
            files = {
                'data': ('metadata', json.dumps(metadata), 'application/json; charset=UTF-8'),
                'file': open(local_path, 'rb')
            }
            
            resp = requests.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                headers=headers,
                files=files,
                timeout=15
            )
            files['file'].close()
            
            if resp.status_code in (200, 201):
                data = resp.json()
                file_id = data.get("id", "")
                cloud_url = f"https://drive.google.com/file/d/{file_id}/view"
                return {
                    "file_url": cloud_url,
                    "file_name": safe_filename,
                    "provider": "gdrive",
                    "public_id": file_id,
                    "local_path": local_path
                }
            else:
                print(f"[Google Drive Upload Error] HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[Google Drive Upload Exception] {e}. Falling back to local storage.")

    # 2. Try Cloudinary if configured
    if (config["provider"] == "cloudinary" or config["cloudinary"]["configured"]) and cloudinary:
        try:
            c_conf = config["cloudinary"]
            if c_conf["url"]:
                cloudinary.config(cloudinary_url=c_conf["url"])
            else:
                cloudinary.config(
                    cloud_name=c_conf["cloud_name"],
                    api_key=c_conf["api_key"],
                    api_secret=c_conf["api_secret"],
                    secure=True
                )
            
            upload_result = cloudinary.uploader.upload(
                local_path,
                folder="kyc_clientes",
                resource_type="auto"
            )
            
            cloud_url = upload_result.get("secure_url") or upload_result.get("url")
            public_id = upload_result.get("public_id", "")
            
            return {
                "file_url": cloud_url,
                "file_name": safe_filename,
                "provider": "cloudinary",
                "public_id": public_id,
                "local_path": local_path
            }
        except Exception as e:
            print(f"[Cloudinary Upload Error] {e}. Falling back to local storage.")
            
    # 3. Try AWS S3 / Supabase / B2 if configured
    if config["provider"] == "s3" and config["s3"]["configured"] and boto3:
        try:
            s_conf = config["s3"]
            client_kwargs = {
                "service_name": "s3",
                "aws_access_key_id": s_conf["access_key"],
                "aws_secret_access_key": s_conf["secret_key"],
                "region_name": s_conf["region"]
            }
            if s_conf["endpoint"]:
                client_kwargs["endpoint_url"] = s_conf["endpoint"]
                
            s3_client = boto3.client(**client_kwargs)
            s3_key = f"kyc_docs/{safe_filename}"
            
            s3_client.upload_file(local_path, s_conf["bucket"], s3_key)
            
            if s_conf["endpoint"]:
                s3_url = f"{s_conf['endpoint']}/{s_conf['bucket']}/{s3_key}"
            else:
                s3_url = f"https://{s_conf['bucket']}.s3.{s_conf['region']}.amazonaws.com/{s3_key}"
                
            return {
                "file_url": s3_url,
                "file_name": safe_filename,
                "provider": "s3",
                "public_id": s3_key,
                "local_path": local_path
            }
        except Exception as e:
            print(f"[S3 Upload Error] {e}. Falling back to local storage.")
            
    # 4. Default: Local Storage
    return {
        "file_url": f"/uploads/{safe_filename}",
        "file_name": safe_filename,
        "provider": "local",
        "public_id": safe_filename,
        "local_path": local_path
    }

def create_full_backup_zip():
    """
    Creates a full backup zip containing:
    - kyc_database.db (full SQLite database)
    - All document scans and photos in uploads/
    - manifest.json with backup metadata for contabilidadalejandro3@gmail.com
    - Excel report (if pandas and openpyxl available)
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"KYC_RESPALDO_GOOGLE_DRIVE_{timestamp}.zip"
    backup_path = os.path.join(UPLOAD_DIR, backup_filename)
    
    # Checkpoint SQLite WAL mode to ensure DB is 100% up-to-date
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA wal_checkpoint(FULL);")
        conn.close()
    except Exception as e:
        print(f"[Backup WAL Checkpoint] Warning: {e}")
        
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 1. Add database
        if os.path.exists(DB_FILE):
            zipf.write(DB_FILE, arcname="kyc_database.db")
            
        # 2. Add uploaded document images/PDFs
        if os.path.exists(UPLOAD_DIR):
            for fname in os.listdir(UPLOAD_DIR):
                fpath = os.path.join(UPLOAD_DIR, fname)
                # Don't recurse other zip backups
                if os.path.isfile(fpath) and not fname.endswith(".zip") and not fname.startswith("."):
                    zipf.write(fpath, arcname=f"documentos/{fname}")
                    
        # 3. Add manifest metadata for contabilidadalejandro3@gmail.com
        manifest = {
            "app": "KYC CLIENTES",
            "account": DEFAULT_GDRIVE_EMAIL,
            "backup_date": datetime.datetime.now().isoformat(),
            "description": "Copia de seguridad completa para la nube de Google Drive de contabilidadalejandro3@gmail.com",
            "database_file": "kyc_database.db",
            "provider": "Google Drive Sync"
        }
        zipf.writestr("manifest_google_drive.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    return backup_path, backup_filename

def upload_backup_to_gdrive():
    """
    Creates the backup ZIP and pushes it to Google Drive for contabilidadalejandro3@gmail.com if token is configured.
    """
    backup_path, backup_filename = create_full_backup_zip()
    config = get_cloud_config()
    gd_conf = config.get("gdrive", {})
    
    if gd_conf.get("token") and requests:
        try:
            headers = {"Authorization": f"Bearer {gd_conf['token']}"}
            metadata = {
                "name": backup_filename,
                "description": f"Respaldo automático KYC CLIENTES - {DEFAULT_GDRIVE_EMAIL}"
            }
            if gd_conf.get("folder_id"):
                metadata["parents"] = [gd_conf["folder_id"]]
                
            with open(backup_path, 'rb') as f:
                files = {
                    'data': ('metadata', json.dumps(metadata), 'application/json; charset=UTF-8'),
                    'file': f
                }
                resp = requests.post(
                    "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                    headers=headers,
                    files=files,
                    timeout=30
                )
                
            if resp.status_code in (200, 201):
                file_id = resp.json().get("id")
                return {
                    "success": True,
                    "message": f"Respaldo subido a Google Drive ({DEFAULT_GDRIVE_EMAIL}) con éxito.",
                    "drive_url": f"https://drive.google.com/file/d/{file_id}/view",
                    "filename": backup_filename,
                    "local_download_url": f"/uploads/{backup_filename}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Error de Google Drive API (HTTP {resp.status_code}): {resp.text}",
                    "local_download_url": f"/uploads/{backup_filename}",
                    "filename": backup_filename
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Excepción conectando con Google Drive: {str(e)}",
                "local_download_url": f"/uploads/{backup_filename}",
                "filename": backup_filename
            }
            
    # If no active token, the backup was successfully prepared locally and is ready for download/Drive sync
    return {
        "success": True,
        "message": f"Paquete de respaldo consolidado generado con éxito para {DEFAULT_GDRIVE_EMAIL}.",
        "local_download_url": f"/uploads/{backup_filename}",
        "filename": backup_filename,
        "email": DEFAULT_GDRIVE_EMAIL
    }

def test_cloud_connection(provider, credentials):
    """
    Tests credentials for the selected cloud provider.
    """
    if provider == "gdrive":
        email = credentials.get("email", DEFAULT_GDRIVE_EMAIL)
        token = credentials.get("token", "").strip()
        if not token:
            # Informative confirmation that target account is set
            return True, f"Cuenta de Google Drive configurada para: {email}. (Listo para sincronización de respaldos)"
            
        if not requests:
            return False, "La librería requests no está disponible."
            
        try:
            headers = {"Authorization": f"Bearer {token}"}
            res = requests.get("https://www.googleapis.com/drive/v3/about?fields=user", headers=headers, timeout=10)
            if res.status_code == 200:
                user_info = res.json().get("user", {})
                user_email = user_info.get("emailAddress", email)
                return True, f"Conexión exitosa con Google Drive ({user_email})."
            else:
                return False, f"Token de Google Drive inválido o expirado (HTTP {res.status_code})."
        except Exception as e:
            return False, f"Error conectando a Google Drive: {str(e)}"

    elif provider == "cloudinary":
        if not cloudinary:
            return False, "La librería cloudinary no está instalada."
        try:
            if credentials.get("url"):
                cloudinary.config(cloudinary_url=credentials["url"])
            else:
                cloudinary.config(
                    cloud_name=credentials.get("cloud_name"),
                    api_key=credentials.get("api_key"),
                    api_secret=credentials.get("api_secret"),
                    secure=True
                )
            res = cloudinary.api.ping()
            return True, "Conexión a Cloudinary establecida con éxito."
        except Exception as e:
            return False, f"Error conectando a Cloudinary: {str(e)}"
            
    elif provider == "s3":
        if not boto3:
            return False, "La librería boto3 no está instalada."
        try:
            client_kwargs = {
                "service_name": "s3",
                "aws_access_key_id": credentials.get("access_key"),
                "aws_secret_access_key": credentials.get("secret_key"),
                "region_name": credentials.get("region", "us-east-1")
            }
            if credentials.get("endpoint"):
                client_kwargs["endpoint_url"] = credentials["endpoint"]
            s3_client = boto3.client(**client_kwargs)
            s3_client.head_bucket(Bucket=credentials.get("bucket"))
            return True, f"Bucket '{credentials.get('bucket')}' accesible correctamente."
        except Exception as e:
            return False, f"Error conectando a S3: {str(e)}"
            
    return True, "Modo local activo y listo para almacenar archivos."
