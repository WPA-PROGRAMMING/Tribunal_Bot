# backend/db.py
from pymongo import MongoClient
from config.settings import MONGO_URI
from datetime import datetime, timedelta

client = MongoClient(MONGO_URI)
db = client["tribunal_bot"]
usuarios = db["usuarios"]

def save_user_if_not_exists(user_id, username, first_name):
    """Guarda un usuario nuevo con prueba gratuita de 10 días"""
    if not usuarios.find_one({"user_id": user_id}):
        fecha_registro = datetime.utcnow()
        fecha_expiracion = fecha_registro + timedelta(days=10)

        usuarios.insert_one({
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "fecha_registro": fecha_registro,
            "fecha_expiracion": fecha_expiracion,
            "activo": True
        })
        return True
    return False

def get_user(user_id):
    return usuarios.find_one({"user_id": user_id})

def is_subscription_active(user_id):
    user = get_user(user_id)
    if not user:
        return False
    return user["activo"] and datetime.utcnow() <= user["fecha_expiracion"]

def deactivate_user(user_id):
    usuarios.update_one({"user_id": user_id}, {"$set": {"activo": False}})

def get_expired_users():
    """Obtiene todos los usuarios cuya suscripción ya expiró y sigue activa."""
    now = datetime.utcnow()
    return list(usuarios.find({
        "activo": True,
        "fecha_expiracion": {"$lt": now}
    }))

expedientes = db["expedientes"]

def save_expediente(usuario_id, distrito, juzgado, numero, ano, identificador):
    """Guarda un expediente nuevo si no existe"""
    if not expedientes.find_one({"usuario_id": usuario_id, "identificador": identificador}):
        expedientes.insert_one({
            "usuario_id": usuario_id,
            "distrito": distrito,
            "juzgado": juzgado,
            "numero": numero,
            "ano": ano,
            "identificador": identificador,
            "ultimo_chequeo": None,
            "ultima_actualizacion": None,
            "historial": []
        })
        return True
    return False

def get_user_expedientes(usuario_id):
    return list(expedientes.find({"usuario_id": usuario_id}))

def eliminar_expediente(usuario_id, identificador):
    """
    Elimina un expediente del seguimiento de un usuario.

    Args:
        usuario_id (int): ID del usuario en Telegram
        identificador (str): Identificador único del expediente

    Returns:
        bool: True si se eliminó, False si no se encontró
    """
    resultado = expedientes.delete_one({
        "usuario_id": usuario_id,
        "identificador": identificador
    })

    if resultado.deleted_count > 0:
        print(f"✅ Expediente {identificador} eliminado para usuario {usuario_id}")
        return True
    else:
        print(f"⚠️ No se encontró expediente {identificador} para usuario {usuario_id}")
        return False

def update_expediente_historial(usuario_id, identificador, datos_actuales):
    """
    Actualiza el historial de un expediente específico.
    
    Args:
        usuario_id (int): ID del usuario en Telegram
        identificador (str): Identificador único del expediente
        datos_actuales (list): Lista con los datos actuales del expediente
        
    Returns:
        bool: True si se actualizó, False si hubo error
    """
    try:
        if not datos_actuales:
            print(f"⚠️ No hay datos para actualizar en expediente {identificador}")
            return False
        
        # Buscar el expediente
        expediente = expedientes.find_one({
            "usuario_id": usuario_id,
            "identificador": identificador
        })
        
        if not expediente:
            print(f"⚠️ No se encontró expediente {identificador} para usuario {usuario_id}")
            return False
        
        # Preparar la nueva entrada del historial
        nueva_entrada = {
            "fecha_chequeo": datetime.utcnow(),
            "datos": datos_actuales
        }
        
        # Obtener la última actualización
        ultima_actualizacion = str(datos_actuales[-1]) if datos_actuales else ""
        
        # Obtener el historial actual
        historial_actual = expediente.get("historial", [])
        
        # Verificar si hay cambios comparando con la última entrada
        hay_cambios = True
        if historial_actual:
            ultimo_registro = historial_actual[-1]
            if ultimo_registro.get("datos") == datos_actuales:
                hay_cambios = False
                print(f"📄 Sin cambios en expediente {identificador}")
        
        # Agregar la nueva entrada al historial
        historial_actual.append(nueva_entrada)
        
        # Actualizar el documento en MongoDB
        resultado = expedientes.update_one(
            {"usuario_id": usuario_id, "identificador": identificador},
            {
                "$set": {
                    "ultima_actualizacion": ultima_actualizacion,
                    "ultimo_chequeo": datetime.utcnow(),
                    "historial": historial_actual
                }
            }
        )
        
        if resultado.modified_count > 0:
            print(f"✅ Historial actualizado para expediente {identificador}")
            return True
        else:
            print(f"⚠️ No se modificó el expediente {identificador}")
            return False
            
    except Exception as e:
        print(f"❌ Error actualizando historial del expediente {identificador}: {e}")
        return False

def check_and_update_expediente(expediente):
    """
    Consulta el expediente en el tribunal, compara con el historial
    y actualiza Mongo si hay cambios.
    
    NOTA: Esta función requiere importar obtener_expediente localmente
    para evitar importaciones circulares.
    """
    from backend.scraper import obtener_expediente
    
    try:
        datos = obtener_expediente(
            expediente["distrito"],
            expediente["juzgado"],
            expediente["numero"],
            expediente["ano"]
        )

        if not datos:
            print(f"⚠️ No se pudieron obtener datos para {expediente['identificador']}")
            return False  # No se pudo consultar

        ultima_actualizacion = str(datos[-1]) if datos else ""

        # Comparar con la última actualización registrada
        if expediente.get("ultima_actualizacion") != ultima_actualizacion:
            # Actualizar usando la función específica
            return update_expediente_historial(
                expediente["usuario_id"],
                expediente["identificador"],
                datos
            )
        else:
            print(f"📄 Sin cambios en {expediente['identificador']}")
            return False  # No hay cambios

    except Exception as e:
        print(f"❌ Error en check_and_update_expediente: {e}")
        return False

def get_expedientes_para_chequeo():
    """
    Obtiene todos los expedientes de usuarios activos para chequeo automático.
    
    Returns:
        list: Lista de expedientes de usuarios con suscripción activa
    """
    try:
        # Obtener usuarios activos
        usuarios_activos = usuarios.find({
            "activo": True,
            "fecha_expiracion": {"$gte": datetime.utcnow()}
        })
        
        user_ids_activos = [user["user_id"] for user in usuarios_activos]
        
        if not user_ids_activos:
            print("📄 No hay usuarios activos")
            return []
        
        # Obtener expedientes de usuarios activos
        expedientes_activos = list(expedientes.find({
            "usuario_id": {"$in": user_ids_activos}
        }))
        
        print(f"📄 Expedientes encontrados para chequeo: {len(expedientes_activos)}")
        return expedientes_activos
        
    except Exception as e:
        print(f"❌ Error obteniendo expedientes para chequeo: {e}")
        return []

def get_expedientes_con_cambios_recientes(horas=24):
    """
    Obtiene expedientes que han tenido cambios en las últimas X horas.
    
    Args:
        horas (int): Número de horas hacia atrás para buscar cambios
        
    Returns:
        list: Lista de expedientes con cambios recientes
    """
    try:
        fecha_limite = datetime.utcnow() - timedelta(hours=horas)
        
        expedientes_con_cambios = list(expedientes.find({
            "ultimo_chequeo": {"$gte": fecha_limite}
        }))
        
        print(f"📄 Expedientes con cambios en últimas {horas}h: {len(expedientes_con_cambios)}")
        return expedientes_con_cambios
        
    except Exception as e:
        print(f"❌ Error obteniendo expedientes con cambios recientes: {e}")
        return []

def get_estadisticas_expedientes():
    """
    Obtiene estadísticas generales de los expedientes registrados.
    
    Returns:
        dict: Diccionario con estadísticas
    """
    try:
        total_expedientes = expedientes.count_documents({})
        usuarios_con_expedientes = len(expedientes.distinct("usuario_id"))
        
        # Expedientes con historial
        con_historial = expedientes.count_documents({
            "historial": {"$ne": [], "$exists": True}
        })
        
        # Expedientes chequeados recientemente (últimas 24 horas)
        fecha_limite = datetime.utcnow() - timedelta(hours=24)
        chequeados_recientes = expedientes.count_documents({
            "ultimo_chequeo": {"$gte": fecha_limite}
        })
        
        estadisticas = {
            "total_expedientes": total_expedientes,
            "usuarios_con_expedientes": usuarios_con_expedientes,
            "expedientes_con_historial": con_historial,
            "chequeados_ultimas_24h": chequeados_recientes,
            "fecha_consulta": datetime.utcnow().isoformat()
        }
        
        print(f"📊 Estadísticas generadas: {estadisticas}")
        return estadisticas
        
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {e}")
        return {}