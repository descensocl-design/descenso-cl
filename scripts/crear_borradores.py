    return json.loads(ruta.read_text(encoding='utf-8'))


def valor_yaml(texto):
    return json.dumps(str(texto), ensure_ascii=False)


def identificar_categoria(noticia):
    texto = (noticia.get('titulo', '') + ' ' + noticia.get('descripcion', '')).lower()
    if any(p in texto for p in ('freeride', 'line of the year', 'rampage', 'slopestyle', 'dirt jump')):
        return 'Freeride'
    if any(p in texto for p in ('cross country', 'cross-country', 'xco', 'xc race')):
        return 'XC'
    if any(p in texto for p in ('enduro', 'emtb', 'e-mtb', 'decoy', 'trail bike')):
        return 'Enduro'
    if any(p in texto for p in ('downhill', 'world cup dh', 'dh race')):
        return 'Downhill'
    return 'Downhill'


def enlaces_existentes():
    enlaces = set()
    for carpeta in (CARPETA_BORRADORES, CARPETA_PUBLICADAS):
        if not carpeta.exists():
            continue
        for archivo in carpeta.glob('*.md'):
            contenido = archivo.read_text(encoding='utf-8-sig')
            coincidencia = re.search(r'^source_url:\s*["\']?([^"\'\n]+)', contenido, re.MULTILINE)
            if coincidencia:
                enlaces.add(normalizar_url(coincidencia.group(1)))
    return enlaces


def contar_borradores_hoy():
    hoy = datetime.now(timezone.utc).date()
    cantidad = 0
    if not CARPETA_BORRADORES.exists():
        return 0
    for archivo in CARPETA_BORRADORES.glob('*.md'):
        try:
            contenido = archivo.read_text(encoding='utf-8-sig')
            coincidencia = re.search(r'^draft_created_at:\s*["\']?(\d{4}-\d{2}-\d{2})', contenido, re.MULTILINE)
            if coincidencia and date.fromisoformat(coincidencia.group(1)) == hoy:
                cantidad += 1
        except (OSError, ValueError):
            continue
    return cantidad


def contexto_de(noticia):
    contexto = noticia.get('contexto_rss') or noticia.get('descripcion') or ''
    return str(contexto).strip()[:8000]


def redactar_con_gemini(noticia):
    clave = os.getenv('GEMINI_API_KEY', '').strip()
    if not clave:
        return None, 'Sin GEMINI_API_KEY; se conserva ficha de revisión'

    contexto = contexto_de(noticia)
    titulo = str(noticia.get('titulo', '')).strip()
    if not titulo or not contexto:
        return None, 'No hay título o descripción suficiente'

    hechos = {
        'titulo_original': titulo,
        'fuente': noticia.get('fuente', ''),
        'fecha_fuente': noticia.get('fecha', ''),
        'texto_disponible': contexto,
        'url_fuente': noticia.get('url', ''),
    }
    instrucciones = (
        'Eres editor de Descenso.cl, medio de ciclismo de montaña. '
        'Redacta un BORRADOR periodístico ORIGINAL en español de Chile, claro y preciso. '
        'Usa EXCLUSIVAMENTE los hechos contenidos en los datos JSON proporcionados. '
        'No inventes citas, resultados, fechas, lugares, especificaciones técnicas, biografías, '
        'opiniones de protagonistas ni contexto adicional. '
        'No asumas que el título o la descripción del RSS son hechos corroborados por otra fuente. '
        'No finjas haber leído el artículo enlazado: la URL es solo referencia. '
        'Si hay poca información, escribe únicamente 1 o 2 párrafos breves y termina con '
        '"Información pendiente de verificación editorial." '
        'No incluyas encabezados YAML, imágenes, créditos, ni título en la respuesta. '
        'No copies frases largas del texto de origen; parafrasea. '
        'No uses Markdown salvo párrafos simples.\n\n'
        'DATOS DE LA NOTICIA:\n' + json.dumps(hechos, ensure_ascii=False)
    )
    endpoint = ('https://generativelanguage.googleapis.com/v1beta/models/'
                + MODELO_GEMINI + ':generateContent')
    payload = {
        'contents': [{'parts': [{'text': instrucciones}]}],
        'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 650},
    }
    peticion = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': clave},
        method='POST',
    )
    for intento in range(3):
        try:
            with urllib.request.urlopen(peticion, timeout=35) as respuesta:
                datos = json.loads(respuesta.read().decode('utf-8'))
            partes = datos.get('candidates', [{}])[0].get('content', {}).get('parts', [])
            texto = '\n'.join(p.get('text', '') for p in partes).strip()
            if len(texto) < 40:
                return None, 'Respuesta de Gemini vacía o demasiado corta'
            return texto[:4500], None
        except urllib.error.HTTPError as error:
            if error.code in (429, 500, 502, 503, 504) and intento < 2:
                time.sleep(2 * (intento + 1))
                continue
            return None, f'Gemini HTTP {error.code}'
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError) as error:
            return None, f'Error de Gemini: {type(error).__name__}'
    return None, 'Gemini no disponible'


def crear_borrador(noticia):
    url = normalizar_url(noticia['url'])
    identificador = hashlib.sha256(url.encode('utf-8')).hexdigest()[:12]
    fecha_creacion = datetime.now(timezone.utc)
    fecha_noticia = noticia.get('fecha') or fecha_creacion.isoformat()
    titulo = noticia.get('titulo', 'Noticia MTB')
    categoria = identificar_categoria(noticia)
    imagen = noticia.get('imagen') or ''
    fotografo = noticia.get('fotografo') or ''
    credito = noticia.get('credito') or ''
    pendiente = bool(noticia.get('imagen_pendiente_revision', True))
    contexto = contexto_de(noticia)
    calidad = noticia.get('calidad_contexto') or ('insuficiente' if len(contexto.split()) < 80 else 'parcial')

    nombre_archivo = fecha_creacion.strftime('%Y-%m-%d') + '-' + identificador + '.md'
    ruta = CARPETA_BORRADORES / nombre_archivo
    redaccion, error = redactar_con_gemini(noticia)
    estado = 'redactado_pendiente_revision' if redaccion else 'ficha_pendiente_redaccion'

    lineas = [
        '---',
        f'title: {valor_yaml(titulo)}',
        f'date: {valor_yaml(fecha_noticia)}',
        f'category: {valor_yaml(categoria)}',
        f'source_url: {valor_yaml(url)}',
        f'image: {valor_yaml(imagen)}',
        f'image_credit: {valor_yaml(credito)}',
        f'photographer: {valor_yaml(fotografo)}',
        f'image_pending_review: {str(pendiente).lower()}',
        f'draft_created_at: {valor_yaml(fecha_creacion.isoformat())}',
        '---', '',
        '**BORRADOR AUTOMÁTICO — PENDIENTE DE VERIFICACIÓN Y APROBACIÓN**', '',
    ]
    if redaccion:
        lineas.extend([redaccion, ''])
    else:
        lineas.extend([
            'No se generó redacción automática. Esta ficha requiere revisión.', '',
            f'**Motivo:** {error}', '',
        ])
    lineas.extend([
        f'**Estado interno:** {estado}', '',
        f'**Calidad del contexto:** {calidad}', '',
