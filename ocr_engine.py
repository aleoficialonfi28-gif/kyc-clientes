import re
import os
from io import BytesIO
from PIL import Image, ImageEnhance, ImageOps

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
    "REPUBLICA", "BOLIVARIANA", "ARGENTINA", "COLOMBIA", "CHILE", "MEXICO", "MÉXICO", "ESPANA", "ESPAÑA",
    "VENEZUELA", "PERU", "PERÚ", "URUGUAY", "PARAGUAY", "ECUADOR", "DOMINICANA", "PANAMA", "PANAMÁ",
    "BOLIVIA", "BRASIL", "BRAZIL", "CEDULA", "IDENTIDAD", "PERSONAL", "CIVIL", "NACIONAL", "ELECTORAL",
    "CIUDADANIA", "CIUDADANÍA", "DOCUMENTO", "DNI", "PASAPORTE", "PASSPORT", "LICENCIA", "CONDUCIR", "CONDUCCION",
    "REGISTRO", "MINISTERIO", "GOBIERNO", "INSTITUTO", "DIRECCION", "DIRECCIÓN", "GENERAL", "ESTADO",
    "APELLIDOS", "NOMBRES", "APELLIDO", "NOMBRE", "SURNAME", "SURNAMES", "GIVEN", "NAMES", "FORENAME",
    "PATERNO", "MATERNO", "PRIMER", "SEGUNDO", "PRENOMBRES", "FULL", "NAME",
    "FECHA", "NACIMIENTO", "EXPEDICION", "EXPEDICIÓN", "VENCIMIENTO", "EXPIRACION", "EXPIRACIÓN", "EMISION", "EMISIÓN",
    "SEXO", "LUGAR", "NACIONALIDAD", "TITULAR", "FIRMA", "SIGNATURE", "DATE", "BIRTH",
    "VALIDO", "HASTA", "CODIGO", "CÓDIGO", "DONANTE", "ORGANOS", "ÓRGANOS", "CLASE", "CATEGORIA", "CATEGORÍA", "NUMERO", "NÚMERO",
    "CIUDADANO", "CIUDADANA", "DELEGACION", "DELEGACIÓN", "SECCION", "SECCIÓN", "SERIE", "FOTO", "FOLIO",
    "CURP", "RUT", "RUN", "MERCOSUR", "CONSULAR", "POLICIA", "POLICÍA", "DOMICILIO", "DIRECCION",
    "VIGENCIA", "CLAVE", "ELECTOR", "DISTRITO", "MUNICIPIO", "LOCALIDAD", "CREDENCIAL", "VOTAR", "ESTUDIANTE"
}

# Country & Nationality mapping patterns
COUNTRY_PATTERNS = [
    ("Venezuela", [r'\bVENEZUELA\b', r'\bBOLIVARIANA\b', r'\bVENEZOLAN[AO]\b', r'\bNACIONALIDAD[\s:]+V\b', r'P<VEN']),
    ("Colombia", [r'\bCOLOMBIA\b', r'\bCOLOMBIAN[AO]\b', r'P<COL']),
    ("Argentina", [r'\bARGENTINA\b', r'\bARGENTIN[AO]\b', r'P<ARG']),
    ("Chile", [r'\bCHILE\b', r'\bCHILEN[AO]\b', r'P<CHL']),
    ("Perú", [r'\bPERU\b', r'\bPERÚ\b', r'\bPERUAN[AO]\b', r'P<PER']),
    ("Uruguay", [r'\bURUGUAY\b', r'\bURUGUAY[AO]\b', r'\bORIENTAL\b', r'P<URY']),
    ("Ecuador", [r'\bECUADOR\b', r'\bECUATORIAN[AO]\b', r'P<ECU']),
    ("México", [r'\bMEXICO\b', r'\bMÉXICO\b', r'\bMEXICAN[AO]\b', r'\bESTADOS UNIDOS MEXICANOS\b', r'\bINSTITUTO NACIONAL ELECTORAL\b', r'\bCREDENCIAL PARA VOTAR\b', r'P<MEX']),
    ("Bolivia", [r'\bBOLIVIA\b', r'\bBOLIVIAN[AO]\b', r'\bPLURINACIONAL\b', r'P<BOL']),
    ("Paraguay", [r'\bPARAGUAY\b', r'\bPARAGUAY[AO]\b', r'P<PRY']),
    ("España", [r'\bESPA[ÑN]A\b', r'\bESPA[ÑN]OL[A]?\b', r'\bREINO DE ESPA[ÑN]A\b', r'P<ESP']),
    ("República Dominicana", [r'\bDOMINICANA\b', r'\bDOMINICAN[AO]\b', r'P<DOM']),
    ("Panamá", [r'\bPANAM[AÁ]\b', r'\bPANAME[ÑN][AO]\b', r'P<PAN']),
    ("Costa Rica", [r'\bCOSTA RICA\b', r'\bCOSTARRICENSE\b', r'P<CRI']),
    ("Guatemala", [r'\bGUATEMALA\b', r'\bGUATEMALTEC[AO]\b', r'P<GTM']),
    ("Honduras", [r'\bHONDURAS\b', r'\bHONDURE[ÑN][AO]\b', r'P<HND']),
    ("El Salvador", [r'\bEL SALVADOR\b', r'\bSALVADORE[ÑN][AO]\b', r'P<SLV']),
    ("Nicaragua", [r'\bNICARAGUA\b', r'\bNICARAG[UÜ]ENSE\b', r'P<NIC']),
    ("Cuba", [r'\bCUBA\b', r'\bCUBAN[AO]\b', r'P<CUB']),
    ("Brasil", [r'\bBRASIL\b', r'\bBRAZIL\b', r'\bBRASILE[ÑN][AO]\b', r'\bBRASILEIR[AO]\b', r'P<BRA']),
    ("Estados Unidos", [r'\bESTADOS UNIDOS\b', r'\bUNITED STATES\b', r'\bUSA\b', r'\bESTADOUNIDENSE\b', r'P<USA']),
    ("Canadá", [r'\bCANADA\b', r'\bCANADÁ\b', r'\bCANADIENSE\b', r'P<CAN']),
    ("Italia", [r'\bITALIA\b', r'\bITALIAN[AO]\b', r'P<ITA']),
    ("Francia", [r'\bFRANCIA\b', r'\bFRANCE\b', r'\bFRANCES[A]?\b', r'P<FRA']),
    ("Alemania", [r'\bALEMANIA\b', r'\bGERMANY\b', r'\bALEMAN[A]?\b', r'P<DEU']),
]

def preprocess_image_for_ocr(pil_img):
    """
    Enhances image for OCR: corrects orientation, upscales low-res cards, enhances contrast and sharpness.
    """
    try:
        img = ImageOps.exif_transpose(pil_img)
    except Exception:
        img = pil_img

    if img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    min_dim = min(w, h)
    if min_dim < 1200:
        scale = 1200.0 / min_dim
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    try:
        img = ImageEnhance.Contrast(img).enhance(1.35)
        img = ImageEnhance.Sharpness(img).enhance(1.3)
    except Exception:
        pass

    return img

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
        # Render at 2.5x resolution for high accuracy
        zoom = 2.5
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return preprocess_image_for_ocr(img)
    
    if isinstance(file_path_or_bytes, (bytes, bytearray)):
        img = Image.open(BytesIO(file_path_or_bytes))
        return preprocess_image_for_ocr(img)
    
    img = Image.open(file_path_or_bytes)
    return preprocess_image_for_ocr(img)

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
    if "EXTRANJERIA" in text_upper or "EXTRANJERÍA" in text_upper or "RESIDENCIA" in text_upper:
        return "Cédula de Extranjería"
    return "Cédula de Identidad"

def extract_document_number(text):
    text_clean = text.replace(",", ".")
    
    # 1. Venezuelan style with prefix V-, E-, J-
    v_match = re.search(r'\b([VEJGvejg][-\s]?\d{6,9})\b', text)
    if v_match:
        return v_match.group(1).upper().replace(" ", "")

    # 2. Explicit keywords: "NUMERO:", "NO.", "N°", "C.I.", "CEDULA", "DNI"
    keyword_match = re.search(r'(?:CEDULA|C\.I\.|DNI|DOCUMENTO|NUMERO|N[°º\.]|NO\.|PASAPORTE|PASSPORT)[\s:]*([A-Z0-9\.\-]{6,15})\b', text_clean, re.IGNORECASE)
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

def clean_name_tokens(text):
    """Cleans punctuation and stopwords from candidate name string."""
    clean = re.sub(r'[^A-Za-zÁÉÍÓÚáéíóúÑñ\s]', ' ', text)
    words = [w for w in clean.split() if w.upper() not in NON_NAME_WORDS and (len(w) >= 2 or w.upper() == 'Y')]
    return " ".join(words)

def extract_name_and_surname(text):
    """
    Extracts name and surname using an advanced multi-strategy parser:
    1. Machine Readable Zone (MRZ for Passports TD3, and National IDs TD1 / TD2)
    2. Single-line detection containing both Apellidos and Nombres
    3. Multi-line and dual surname detection (APELLIDOS, 1er/2do APELLIDO, PRENOMBRES, SURNAME)
    4. Mexican INE / IFE multi-line structure
    5. Combined label detection (APELLIDOS Y NOMBRES)
    6. Heuristic candidate line analysis
    """
    text_up = text.upper()
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # 1. MRZ (Passports and modern Latin American IDs TD1/TD2)
    for line in lines:
        line_clean = line.replace(" ", "")
        if "<<" in line_clean and "<" in line_clean:
            cleaned_mrz = re.sub(r'^[A-Z0-9<]{5}', '', line_clean) if (line_clean.startswith("P<") or line_clean.startswith("ID") or line_clean.startswith("I<")) else line_clean
            parts = cleaned_mrz.split("<<")
            if len(parts) >= 2:
                surnames = parts[0].replace("<", " ").strip()
                names = parts[1].replace("<", " ").strip()
                surnames_clean = clean_name_tokens(surnames)
                names_clean = clean_name_tokens(names)
                if surnames_clean and names_clean:
                    return f"{names_clean} {surnames_clean}".title()

    # 2. Check for single line containing BOTH Apellidos and Nombres
    for line in lines:
        m_inline1 = re.search(r'(?:APELLIDO\w*|SURNAME)[\s:]+(.*?)(?:NOMBRES?|GIVEN|FORENAME)[\s:]+(.*)', line, re.IGNORECASE)
        if m_inline1:
            ape = clean_name_tokens(m_inline1.group(1))
            nom = clean_name_tokens(m_inline1.group(2))
            if ape and nom:
                return f"{nom} {ape}".title()

        m_inline2 = re.search(r'(?:NOMBRES?|GIVEN|FORENAME)[\s:]+(.*?)(?:APELLIDO\w*|SURNAME)[\s:]+(.*)', line, re.IGNORECASE)
        if m_inline2:
            nom = clean_name_tokens(m_inline2.group(1))
            ape = clean_name_tokens(m_inline2.group(2))
            if ape and nom:
                return f"{nom} {ape}".title()

    # Helper to find next non-empty, non-label line
    def find_next_valid_line(start_idx):
        for offset in range(1, 4):
            if start_idx + offset < len(lines):
                candidate = lines[start_idx + offset].strip()
                candidate_up = candidate.upper()
                if any(lbl in candidate_up for lbl in ["NOMBRE", "APELLIDO", "SEXO", "FECHA", "CEDULA", "NACIONALIDAD", "FIRMA", "ESTADO", "LUGAR", "VENCIMIENTO"]):
                    return ""
                cleaned = clean_name_tokens(candidate)
                if cleaned:
                    return cleaned
        return ""

    # 3. Mexican INE format: Single line 'NOMBRE' followed by 3 lines (Paterno, Materno, Nombres)
    for idx, line in enumerate(lines):
        if line.strip().upper() in ["NOMBRE", "NOMBRE:", "NOMBRE / NAME"]:
            sub_lines = []
            for off in range(1, 4):
                if idx + off < len(lines):
                    nxt = lines[idx + off].strip()
                    if not any(k in nxt.upper() for k in ["EDAD", "SEXO", "DOMICILIO", "CLAVE", "CURP", "FECHA", "REGISTRO", "NACIONALIDAD"]):
                        toks = clean_name_tokens(nxt)
                        if toks:
                            sub_lines.append(toks)
            if len(sub_lines) == 3:
                return f"{sub_lines[2]} {sub_lines[0]} {sub_lines[1]}".title()
            elif len(sub_lines) == 2:
                return f"{sub_lines[1]} {sub_lines[0]}".title()

    # 4. Multi-line Label Scanning
    apellidos_found = []
    nombres_found = []
    combo_found = ""

    re_ape_label = re.compile(
        r'(?:^|[\s_\|\-\*\.\:0-9])(?:(?:1ER\.?|2DO\.?|PRIMER|SEGUNDO)\s+)?(?:APELLIDOS?|APELLIDO\s*\(\s*S\s*\)|APELLIDO\s+PATERNO|APELLIDO\s+MATERNO|SURNAME|SURNAMES|LAST\s*NAME)(?:[\s/]+(?:SURNAME|SURNAMES))?[\s:]*(.*)$',
        re.IGNORECASE
    )
    re_nom_label = re.compile(
        r'(?:^|[\s_\|\-\*\.\:0-9])(?:PRENOMBRES?|NOMBRES?|NOMBRE\s*\(\s*S\s*\)|NOMBRE\s+DE\s+PILA|GIVEN\s*NAMES?|FIRST\s*NAME)(?:[\s/]+(?:GIVEN\s*NAMES?|FORENAMES?))?[\s:]*(.*)$',
        re.IGNORECASE
    )
    re_combo_label = re.compile(
        r'(?:^|[\s_\|\-\*\.\:0-9])(?:APELLIDOS?\s+Y\s+NOMBRES?|NOMBRES?\s+Y\s+APELLIDOS?|NOMBRE\s+COMPLETO|FULL\s+NAME)[\s:]*(.*)$',
        re.IGNORECASE
    )

    for idx, line in enumerate(lines):
        # Combo (Apellidos y Nombres)
        m_c = re_combo_label.search(line)
        if m_c:
            inline = clean_name_tokens(m_c.group(1))
            if inline:
                combo_found = inline
            else:
                next_l = find_next_valid_line(idx)
                if next_l:
                    combo_found = next_l
            continue

        # Apellidos
        m_a = re_ape_label.search(line)
        if m_a:
            inline = clean_name_tokens(m_a.group(1))
            if inline:
                apellidos_found.append(inline)
            else:
                next_l = find_next_valid_line(idx)
                if next_l:
                    apellidos_found.append(next_l)
            continue

        # Nombres
        m_n = re_nom_label.search(line)
        if m_n:
            inline = clean_name_tokens(m_n.group(1))
            if inline:
                nombres_found.append(inline)
            else:
                next_l = find_next_valid_line(idx)
                if next_l:
                    nombres_found.append(next_l)
            continue

    if nombres_found or apellidos_found:
        nombres_str = " ".join(nombres_found).strip()
        apellidos_str = " ".join(apellidos_found).strip()
        if nombres_str and apellidos_str:
            return f"{nombres_str} {apellidos_str}".title()
        elif nombres_str:
            return nombres_str.title()
        else:
            return apellidos_str.title()

    if combo_found:
        return combo_found.title()

    # 5. Fallback: Search for cleanest 2-4 word line
    for line in lines:
        cleaned = clean_name_tokens(line)
        words = cleaned.split()
        if 2 <= len(words) <= 4 and not any(c.isdigit() for c in line):
            return cleaned.title()

    return ""

def extract_country_and_nationality(text):
    """
    Extracts the country and nationality from ID documents or Passports.
    Prioritizes:
    1. Explicit 'NACIONALIDAD:' or 'PAIS:' labels
    2. Passport MRZ country codes (e.g. P<VEN, P<COL, P<ARG)
    3. Document headers / Government titles (e.g. REPUBLICA DE COLOMBIA)
    """
    text_up = text.upper()

    # 1. Check explicit label
    m_nac = re.search(r'(?:NACIONALIDAD|PAIS|PAÍS|ORIGEN|NACIONALIDAD\s*[/]\s*NATIONALITY)[\s:/]+([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+)', text_up)
    if m_nac:
        val = m_nac.group(1).strip()
        # Single-letter Venezuelan indicator (V = Venezolana, E = Extranjero)
        if val.startswith("V"):
            return "Venezuela"
        if val.startswith("E") and len(val) == 1:
            return "Extranjero"
        for country, patterns in COUNTRY_PATTERNS:
            for p in patterns:
                if re.search(p, val):
                    return country

    # 2. Check Passport MRZ
    for country, patterns in COUNTRY_PATTERNS:
        for p in patterns:
            if p.startswith("P<") and p in text_up:
                return country

    # 3. Check General Document Headers and Body
    for country, patterns in COUNTRY_PATTERNS:
        for p in patterns:
            if not p.startswith("P<") and re.search(p, text_up):
                return country

    return "Desconocido"

def process_identity_document(file_path_or_bytes, is_pdf=False, client_ocr_text=""):
    """
    Main extraction pipeline:
    Loads image/PDF -> Preprocesses -> Native OCR -> Extracts fields -> Returns structured result.
    """
    img = load_image_from_file_or_bytes(file_path_or_bytes, is_pdf=is_pdf)
    raw_text = run_native_ocr(img)
    if not raw_text and client_ocr_text:
        raw_text = client_ocr_text
        
    clean_text = clean_ocr_text(raw_text)
    
    doc_type = detect_document_type(clean_text)
    doc_num = extract_document_number(clean_text)
    full_name = extract_name_and_surname(clean_text)
    country = extract_country_and_nationality(clean_text)
    
    return {
        "success": True,
        "tipo_documento": doc_type,
        "documento_numero": doc_num,
        "nombre_apellido": full_name,
        "pais_nacionalidad": country,
        "raw_text": clean_text
    }
