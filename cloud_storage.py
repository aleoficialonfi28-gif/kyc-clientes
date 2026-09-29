import os
import uuid
import datetime
from pathlib import Path

# Base upload directory for local storage & backup
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

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

from database import get_setting

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
    
    return {
        "provider": provider,
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
    Saves the file to local backup and uploads it to the configured cloud provider (Cloudinary, S3, or Local).
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
    
    # 1. Try Cloudinary if configured
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
            
    # 2. Try AWS S3 / Supabase / B2 if configured
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
            
    # 3. Default: Local Served Storage (Always 100% reliable)
    return {
        "file_url": f"/uploads/{safe_filename}",
        "file_name": safe_filename,
        "provider": "local",
        "public_id": safe_filename,
        "local_path": local_path
    }

def test_cloud_connection(provider, credentials):
    """
    Tests credentials for the selected cloud provider.
    """
    if provider == "cloudinary":
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
            # Test ping
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
