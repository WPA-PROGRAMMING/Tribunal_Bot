# backend/scraper.py
import requests
from bs4 import BeautifulSoup
from config.settings import TRIBUNAL_URL
import time
from datetime import datetime

URL_JUZGADOS = "http://siisej-dttos.tsjtlaxcala.gob.mx/busqueda/busqueda-expedientes/juzgados-activos"

# ---------------- Distritos y Juzgados ----------------

def obtener_distritos():
    """
    Obtiene todos los distritos disponibles.
    Retorna: dict con formato {id: nombre_distrito}
    """
    try:
        print("📡 Consultando distritos...")
        resp = requests.get(URL_JUZGADOS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        print(f"🔍 Respuesta API: {data}")
        
        distritos = {}
        for key, val in data.items():
            if isinstance(val, dict):
                for nombre_distrito in val.keys():
                    distritos[key] = nombre_distrito.strip()
                    
        print(f"📍 Distritos procesados: {distritos}")
        return distritos
        
    except requests.RequestException as e:
        print(f"❌ Error de conexión obteniendo distritos: {e}")
        return {}
    except Exception as e:
        print(f"❌ Error procesando distritos: {e}")
        return {}

def obtener_juzgados_por_distrito(distrito_id):
    """
    Obtiene juzgados activos de un distrito específico.
    Retorna: lista de dict con formato [{'id': str, 'nombre_juzgado': str}]
    """
    try:
        print(f"📡 Consultando juzgados para distrito {distrito_id}...")
        resp = requests.get(URL_JUZGADOS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        print(f"🔍 Datos del distrito {distrito_id}: {data.get(str(distrito_id))}")
        
        juzgados_lista = []
        distrito_data = data.get(str(distrito_id))
        
        if not distrito_data:
            print(f"⚠️ No se encontró el distrito {distrito_id}")
            return []
        
        for nombre_distrito, juzgados in distrito_data.items():
            print(f"🏛️ Procesando distrito: {nombre_distrito}")
            print(f"⚖️ Juzgados encontrados: {len(juzgados) if juzgados else 0}")
            
            if not isinstance(juzgados, list):
                print(f"⚠️ Los juzgados no son una lista: {type(juzgados)}")
                continue
                
            for juzgado in juzgados:
                if isinstance(juzgado, dict) and juzgado.get('activo') == '1':
                    juzgados_lista.append({
                        'id': juzgado.get('id', ''),
                        'nombre_juzgado': juzgado.get('nombre_juzgado', 'Sin nombre')
                    })
                    
        print(f"✅ Juzgados activos encontrados: {len(juzgados_lista)}")
        return juzgados_lista
        
    except requests.RequestException as e:
        print(f"❌ Error de conexión obteniendo juzgados: {e}")
        return []
    except Exception as e:
        print(f"❌ Error procesando juzgados: {e}")
        return []

# ---------------- Consultar expediente ----------------

def obtener_expediente(distrito, juzgado, numero, ano):
    """
    Consulta la página del tribunal y devuelve información básica del expediente.
    
    Args:
        distrito (str): ID del distrito
        juzgado (str): ID del juzgado  
        numero (str): Número del expediente
        ano (str): Año del expediente
        
    Returns:
        list: Lista de diccionarios con datos del expediente o None si no existe
    """
    payload = {
        "distrito": distrito,
        "juzgado": juzgado,
        "numeroExpediente": numero,
        "ano": ano
    }
    
    try:
        print(f"📡 Consultando expediente: {payload}")
        response = requests.get(TRIBUNAL_URL, params=payload, timeout=15)
        response.raise_for_status()
        
        # Agregar un pequeño delay para no sobrecargar el servidor
        time.sleep(1)
        
    except requests.RequestException as e:
        print(f"❌ Error al consultar expediente: {e}")
        return None
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Buscar diferentes tipos de tablas que puedan contener los datos
    tabla = soup.find("table")
    if not tabla:
        # Buscar tablas con clases específicas si es necesario
        tabla = soup.find("table", class_="table") or soup.find("table", id="expedientes")
        
    # Verificar primero si hay mensaje de error específico del tribunal
    error_box = soup.find("div", {"id": "error_box", "class": ["alert", "alert-danger"]})
    if error_box and not error_box.has_attr("d-none"):
        # Si el error_box no tiene la clase d-none, significa que está visible
        error_text = error_box.get_text().strip()
        print(f"❌ Error del tribunal: {error_text}")
        
        if "no esta ingresado en la base de datos" in error_text.lower():
            print("📄 Expediente no existe en la base de datos")
            return []  # Expediente no existe
        else:
            print(f"⚠️ Error desconocido: {error_text}")
            return None  # Error desconocido
    
    # También verificar si el error_box existe pero puede estar oculto inicialmente
    error_box_hidden = soup.find("div", id="error_box")
    if error_box_hidden:
        error_text = error_box_hidden.get_text().strip()
        if error_text and "no esta ingresado en la base de datos" in error_text.lower():
            print("📄 Expediente no existe en la base de datos (detectado en div oculto)")
            return []
    
    if not tabla:
        print("⚠️ No se encontró tabla en la respuesta")
        # Verificar otros posibles mensajes de error
        error_msgs = soup.find_all(["div", "p", "span"], class_=["alert", "error", "warning", "mensaje"])
        
        for msg in error_msgs:
            texto_msg = msg.get_text().strip()
            if texto_msg:
                print(f"🔍 Mensaje en página: {texto_msg}")
                
                # Verificar diferentes variantes del mensaje de error
                if any(keyword in texto_msg.lower() for keyword in [
                    "no esta ingresado", 
                    "no se encontr", 
                    "sin resultados", 
                    "no existe",
                    "expediente no válido"
                ]):
                    print("📄 La página indica que no se encontraron resultados")
                    return []
        
        return None
    
    # Extraer datos de la tabla
    expedientes = []
    filas = tabla.find_all("tr")
    
    # Identificar encabezados
    encabezados = []
    primera_fila = filas[0] if filas else None
    if primera_fila:
        celdas_encabezado = primera_fila.find_all(["th", "td"])
        encabezados = [celda.get_text().strip().lower() for celda in celdas_encabezado]
        print(f"📋 Encabezados encontrados: {encabezados}")
    
    # Procesar filas de datos (saltar la primera si contiene encabezados)
    inicio = 1 if encabezados else 0
    
    for fila in filas[inicio:]:
        celdas = fila.find_all(["td", "th"])
        if len(celdas) == 0:
            continue
            
        # Extraer texto de cada celda
        valores = [celda.get_text().strip() for celda in celdas]
        
        # Si tenemos encabezados, crear un diccionario
        if encabezados and len(valores) >= len(encabezados):
            expediente_data = {}
            for i, encabezado in enumerate(encabezados):
                if i < len(valores):
                    expediente_data[encabezado] = valores[i]
            expedientes.append(expediente_data)
        else:
            # Si no hay encabezados claros, usar índices genéricos
            expediente_data = {
                'columna_' + str(i): valor 
                for i, valor in enumerate(valores) if valor
            }
            if expediente_data:  # Solo agregar si hay datos
                expedientes.append(expediente_data)
    
    print(f"✅ Expedientes procesados: {len(expedientes)}")
    for i, exp in enumerate(expedientes[:3]):  # Mostrar solo los primeros 3
        print(f"📄 Expediente {i+1}: {exp}")
    
    return expedientes if expedientes else []

def buscar_expedientes_avanzado(parametros):
    """
    Búsqueda avanzada de expedientes con múltiples criterios.
    
    Args:
        parametros (dict): Diccionario con criterios de búsqueda
                          Puede incluir: nombre_actor, nombre_demandado, materia, etc.
    
    Returns:
        list: Lista de expedientes encontrados
    """
    try:
        print(f"🔍 Búsqueda avanzada con parámetros: {parametros}")
        
        # Construir URL de búsqueda avanzada si existe
        url_avanzada = TRIBUNAL_URL.replace("/consulta", "/busqueda-avanzada")
        
        response = requests.get(url_avanzada, params=parametros, timeout=15)
        response.raise_for_status()
        
        time.sleep(1)  # Delay para no sobrecargar
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Procesar resultados similares a obtener_expediente
        return _procesar_resultados_tabla(soup)
        
    except requests.RequestException as e:
        print(f"❌ Error en búsqueda avanzada: {e}")
        return []

def _procesar_resultados_tabla(soup):
    """
    Función auxiliar para procesar tablas de resultados.
    
    Args:
        soup: Objeto BeautifulSoup con el HTML parseado
        
    Returns:
        list: Lista de diccionarios con los datos extraídos
    """
    tabla = soup.find("table") or soup.find("table", class_="table")
    
    if not tabla:
        return []
    
    resultados = []
    filas = tabla.find_all("tr")
    
    if not filas:
        return []
    
    # Obtener encabezados
    encabezados = []
    primera_fila = filas[0]
    celdas_encabezado = primera_fila.find_all(["th", "td"])
    encabezados = [celda.get_text().strip() for celda in celdas_encabezado]
    
    # Procesar datos
    for fila in filas[1:]:
        celdas = fila.find_all(["td", "th"])
        if not celdas:
            continue
            
        valores = [celda.get_text().strip() for celda in celdas]
        
        if len(valores) >= len(encabezados):
            resultado = {}
            for i, encabezado in enumerate(encabezados):
                if i < len(valores):
                    resultado[encabezado] = valores[i]
            
            # Solo agregar si tiene contenido útil
            if any(valor for valor in resultado.values()):
                resultados.append(resultado)
    
    return resultados

def validar_expediente_existe(distrito, juzgado, numero, ano):
    """
    Valida si un expediente existe detectando el div de error específico del tribunal.
    
    Args:
        distrito (str): ID del distrito
        juzgado (str): ID del juzgado
        numero (str): Número del expediente  
        ano (str): Año del expediente
        
    Returns:
        dict: {'existe': bool, 'mensaje': str, 'datos': list}
    """
    payload = {
        "distrito": distrito,
        "juzgado": juzgado,
        "numeroExpediente": numero,
        "ano": ano
    }
    
    try:
        print(f"🔍 Validando existencia del expediente: {payload}")
        response = requests.get(TRIBUNAL_URL, params=payload, timeout=15)
        response.raise_for_status()
        time.sleep(1)
        
    except requests.RequestException as e:
        print(f"❌ Error al validar expediente: {e}")
        return {'existe': None, 'mensaje': f'Error de conexión: {e}', 'datos': []}
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Detectar el div de error específico del tribunal
    error_box = soup.find("div", id="error_box")
    
    if error_box:
        error_text = error_box.get_text().strip()
        
        # Verificar si el mensaje de error está presente
        if "no esta ingresado en la base de datos" in error_text.lower():
            # Verificar si el div está visible (no tiene clase d-none)
            classes = error_box.get('class', [])
            if 'd-none' not in classes:
                print("❌ Expediente NO existe - div de error visible")
                return {
                    'existe': False, 
                    'mensaje': error_text, 
                    'datos': []
                }
            else:
                print("✅ Expediente existe - div de error oculto")
                # Intentar obtener los datos
                datos = obtener_expediente(distrito, juzgado, numero, ano)
                return {
                    'existe': True, 
                    'mensaje': 'Expediente encontrado', 
                    'datos': datos or []
                }
    
    # Si no hay div de error o está oculto, verificar si hay tabla con datos
    tabla = soup.find("table")
    if tabla:
        filas = tabla.find_all("tr")
        if len(filas) > 1:  # Más de una fila indica datos
            print("✅ Expediente existe - tabla con datos encontrada")
            datos = obtener_expediente(distrito, juzgado, numero, ano)
            return {
                'existe': True, 
                'mensaje': 'Expediente encontrado con datos', 
                'datos': datos or []
            }
    
    # Caso ambiguo - no hay error claro ni datos claros
    print("⚠️ Estado ambiguo del expediente")
    return {
        'existe': None, 
        'mensaje': 'No se pudo determinar si el expediente existe', 
        'datos': []
    }

def _detectar_error_expediente(soup):
    """
    Detecta si la página muestra el mensaje de error específico del tribunal.
    
    Args:
        soup: Objeto BeautifulSoup con el HTML parseado
        
    Returns:
        dict: {'hay_error': bool, 'mensaje': str, 'tipo': str}
    """
    # Buscar el div específico del tribunal
    error_box = soup.find("div", id="error_box")
    
    if error_box:
        classes = error_box.get('class', [])
        error_text = error_box.get_text().strip()
        
        # Si el div no tiene la clase d-none, está visible (hay error)
        if 'd-none' not in classes and error_text:
            print(f"🚨 Div de error visible: {error_text}")
            return {
                'hay_error': True, 
                'mensaje': error_text, 
                'tipo': 'expediente_no_existe'
            }
        elif error_text and "no esta ingresado en la base de datos" in error_text.lower():
            # El div existe pero está oculto, probablemente se muestre con JavaScript
            print(f"⚠️ Div de error presente (oculto): {error_text}")
            return {
                'hay_error': False, 
                'mensaje': error_text, 
                'tipo': 'error_potencial'
            }
    
    # Buscar otros posibles indicadores de error
    error_indicators = soup.find_all(["div", "p", "span"], class_=["alert-danger", "error", "warning"])
    
    for indicator in error_indicators:
        texto = indicator.get_text().strip().lower()
        if any(keyword in texto for keyword in [
            "no esta ingresado", 
            "expediente no válido",
            "no se encontr",
            "sin resultados"
        ]):
            return {
                'hay_error': True, 
                'mensaje': indicator.get_text().strip(), 
                'tipo': 'error_general'
            }
    
    return {'hay_error': False, 'mensaje': '', 'tipo': 'sin_error'}

def obtener_estadisticas_juzgado(distrito_id, juzgado_id, fecha_inicio=None, fecha_fin=None):
    """
    Obtiene estadísticas básicas de un juzgado en un período determinado.
    
    Args:
        distrito_id (str): ID del distrito
        juzgado_id (str): ID del juzgado
        fecha_inicio (str): Fecha de inicio en formato YYYY-MM-DD
        fecha_fin (str): Fecha de fin en formato YYYY-MM-DD
        
    Returns:
        dict: Diccionario con estadísticas básicas
    """
    # Esta función dependería de que el sistema del tribunal tenga endpoints específicos
    # Por ahora retorna un placeholder
    
    estadisticas = {
        'distrito_id': distrito_id,
        'juzgado_id': juzgado_id,
        'periodo': {
            'inicio': fecha_inicio,
            'fin': fecha_fin
        },
        'total_expedientes': 0,
        'expedientes_activos': 0,
        'expedientes_concluidos': 0,
        'fecha_consulta': datetime.now().isoformat()
    }
    
    print(f"📊 Estadísticas placeholder generadas para juzgado {juzgado_id}")
    return estadisticas