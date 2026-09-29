import re
import os
from io import BytesIO
from PIL import Image

try:
    import winocr
except ImportError:
    winocr = None

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

# Blacklist of common header/legal words found on ID documents that are NOT personal names
NON_NAME_WORDS = {
    "REPUBLICA", "BOLIVARIANA", "ARGENTINA", "COLOMBIA", "CHILE", "MEXICO", "ESPANA",
    "VENEZUELA", "PERU", "URUGUAY", "PARAGUAY", "ECUADOR", "DOMINICANA", "PANAMA",
    "CEDULA", "IDENTIDAD", "PERSONAL", "CIVIL", "NACIONAL", "ELECTORAL", "CIUDADANIA",
    "DOCUMENTO", "DNI", "PASAPORTE", "PASSPORT", "LICENCIA", "CONDUCIR", "REGISTRO",
    "MINISTERIO", "GOBIERNO", "INSTITUTO", "DIRECCION", "GENERAL", "ESTADO",
    "APELLIDOS", "NOMBRES", "APELLIDO", "NOMBRE", "SURNAME", "GIVEN", "NAMES",
    "FECHA", "NACIMIENTO", "EXPEDICION", "VENCIMIENTO", "EXPIRACION", "EMISION",
    "SEXO", "LUGAR", "NACIONALIDAD", "TITULAR", "FIRMA", "SIGNATURE", "DATE", "BIRTH",
    "VALIDO", "HASTA", "CODIGO", "DONANTE", "ORGANOS", "CLASE", "CATEGORIA", "NUMERO",
    "CIUDADANO", "CIUDADANA", "DELEGACION", "SECCION", "SERIE"
}

def load_image_from_file_or_bytes(file_path_or_bytes, is_pdf=False):
    """
    Returns a PIL Image object from a file path, bytes, or first page of a PDF.
    """
    if is_pdf or (isinstance(file_path_or_bytes, str) and file_path_or_bytes.lower().endswith(".pdf")):
        if fitz is None:
            raise RuntimeError("PyMuPDF (pymupdf) no está disponible para procesar PDF.")
        doc = fitz.open(file_path_or_bytes)
        if len(doc) == 0:
            raise ValueError("El archivo PDF está vacío.")
        page = doc[0]
        # Render at 2x resolution for high accuracy
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img
    
    if isinstance(file_path_or_bytes, (bytes, bytearray)):
        return Image.open(BytesIO(file_path_or_bytes)).convert("RGB")
    
    return Image.open(file_path_or_bytes).convert("RGB")

def run_native_ocr(image):
    """
    Executes Windows Native OCR on a PIL Image.
    """
    if winocr is None:
        return ""
    try:
        res = winocr.recognize_pil_sync(image, "es")
        if not res or not res.get("text"):
            res = winocr.recognize_pil_sync(image)
        return res.get("text", "") if res else ""
    except Exception as e:
        print(f"[OCR Warning] winocr error: {e}")
        try:
            res = winocr.recognize_pil_sync(image)
            return res.get("text", "") if res else ""
        except Exception as e2:
            print(f"[OCR Error] Fallback failed: {e2}")
            return ""

def clean_ocr_text(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

def detect_document_type(text):
    text_upper = text.upper()
    if "PASAPORTE" in text_upper or "PASSPORT" in text_upper or "P<" in text_upper:
        return "Pasaporte"
    if "LICENCIA" in text_upper or "CONDUCCION" in text_upper or "CONDUCIR" in text_upper:
        return "Licencia de Conducir"
    if "DNI" in text_upper or "DOCUMENTO NACIONAL" in text_upper:
        return "DNI"
    if "EXTRANJERIA" in text_upper or "RESIDENCIA" in text_upper:
        return "Cédula de Extranjería"
    return "Cédula de Identidad"

def extract_document_number(text):
    text_clean = text.replace(",", ".")
    
    # 1. Venezuelan style with prefix V-, E-, J-
    v_match = re.search(r'\b([VEJGvejg][-\s]?\d{6,9})\b', text)
    if v_match:
        return v_match.group(1).upper().replace(" ", "")

    # 2. Explicit keywords: "NUMERO:", "NO.", "N°", "C.I.", "CEDULA", "DNI"
    keyword_match = re.search(r'(?:CEDULA|DNI|DOCUMENTO|NUMERO|N[°º\.]|NO\.|PASAPORTE|PASSPORT)[\s:]*([A-Z0-9\.\-]{6,15})\b', text_clean, re.IGNORECASE)
    if keyword_match:
        candidate = keyword_match.group(1).strip()
        candidate = re.sub(r'[\.\-]+$', '', candidate)
        if any(c.isdigit() for c in candidate) and len(re.sub(r'\D', '', candidate)) >= 5:
            return candidate

    # 3. Formatted with dots: 12.345.678 or 12.345.678-9
    dot_match = re.search(r'\b(\d{1,3}(?:\.\d{3}){2}(?:[-\s]?[0-9kK])?)\b', text_clean)
    if dot_match:
        return dot_match.group(1)

    # 4. Continuous numbers 6 to 10 digits
    numbers = re.findall(r'\b(\d{6,10})\b', text)
    if numbers:
        valid_numbers = [n for n in numbers if not (n.startswith("19") or n.startswith("20")) or len(n) > 4]
        if valid_numbers:
            return valid_numbers[0]
        return numbers[0]

    return ""

def extract_name_and_surname(text):
    """
    Extracts name and surname using multi-strategy parser.
    """
    text_clean = text.replace("\r", " ").replace("\n", " ")
    
    # Strategy 1: Explicit labels (NOMBRES: ... APELLIDOS: ...)
    boundary = r'(?=\b(?:APELLI\w*|NOMBRES?|NACIONALIDAD|FECHA|SEXO|ESTADO|CEDULA|NUMERO|FIRMA|LUGAR|EMISION|$)\b)'
    
    m_nom = re.search(r'NOMBRES?[\s:]+([A-Za-zÁÉÍÓÚáéíóúÑñ\s]+?)' + boundary, text_clean, re.IGNORECASE)
    m_ape = re.search(r'APELLI\w*[\s:]+([A-Za-zÁÉÍÓÚáéíóúÑñ\s]+?)' + boundary, text_clean, re.IGNORECASE)

    if m_nom and m_ape:
        nombres = m_nom.group(1).strip()
        apellidos = m_ape.group(1).strip()
        full = f"{nombres} {apellidos}".strip()
        cleaned_words = [w for w in full.split() if w.upper() not in NON_NAME_WORDS]
        if cleaned_words:
            return " ".join(cleaned_words).title()

    if m_nom:
        cleaned_words = [w for w in m_nom.group(1).strip().split() if w.upper() not in NON_NAME_WORDS]
        if cleaned_words:
            return " ".join(cleaned_words).title()

    if m_ape:
        cleaned_words = [w for w in m_ape.group(1).strip().split() if w.upper() not in NON_NAME_WORDS]
        if cleaned_words:
            return " ".join(cleaned_words).title()

    # Strategy 2: Passport MRZ format (e.g. P<URYPEREZ<<JUAN<CARLOS)
    mrz_name_match = re.search(r'P<[A-Z]{3}([A-Z]+)<<([A-Z<]+)', text.upper())
    if mrz_name_match:
        surname_mrz = mrz_name_match.group(1).replace("<", " ").strip()
        names_mrz = mrz_name_match.group(2).replace("<", " ").strip()
        return f"{names_mrz} {surname_mrz}".title()

    # Strategy 3: Multi-line analysis looking for clean capitalized name candidate lines
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    candidates = []
    for line in lines:
        cleaned_line = re.sub(r'[^A-Za-zÁÉÍÓÚáéíóúÑñ\s]', ' ', line).strip()
        words = cleaned_line.split()
        if 2 <= len(words) <= 4:
            blacklisted_count = sum(1 for w in words if w.upper() in NON_NAME_WORDS)
            if blacklisted_count == 0 and all(len(w) >= 2 for w in words):
                candidates.append(cleaned_line)

    if candidates:
        return " ".join(candidates[0].split()).title()

    return ""

def process_identity_document(file_path_or_bytes, is_pdf=False, client_ocr_text=""):
    """
    Main extraction pipeline:
    Loads image/PDF -> Native OCR (or client OCR fallback for Linux cloud) -> Extracts fields -> Returns structured result.
    """
    img = load_image_from_file_or_bytes(file_path_or_bytes, is_pdf=is_pdf)
    raw_text = run_native_ocr(img)
    if not raw_text and client_ocr_text:
        raw_text = client_ocr_text
        
    clean_text = clean_ocr_text(raw_text)
    
    doc_type = detect_document_type(clean_text)
    doc_num = extract_document_number(clean_text)
    full_name = extract_name_and_surname(clean_text)
    
    return {
        "success": True,
        "tipo_documento": doc_type,
        "documento_numero": doc_num,
        "nombre_apellido": full_name,
        "raw_text": clean_text
    }
