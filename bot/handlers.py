# bot/handlers.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from backend.db import save_user_if_not_exists, get_user, is_subscription_active, save_expediente, get_user_expedientes, update_expediente_historial, eliminar_expediente
from backend.scraper import obtener_distritos, obtener_juzgados_por_distrito, obtener_expediente, validar_expediente_existe

# Estados para el flujo de registro
DIST, JUZGADO, NUMERO, ANO, IDENTIFICADOR = range(5)

# -------------------- CONSULTAR ACTUALIZACIONES --------------------

async def consultar_expediente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra lista de expedientes para consultar actualizaciones"""
    user = update.effective_user
    
    try:
        expedientes = get_user_expedientes(user.id)
        if not expedientes:
            message = "📄 No tienes expedientes registrados.\n\nUsa /menu → 'Registrar expediente' para agregar uno."
            if update.message:
                await update.message.reply_text(message)
            elif update.callback_query:
                await update.callback_query.message.reply_text(message)
            return
            
        # Crear botones para cada expediente
        keyboard = []
        for i, exp in enumerate(expedientes):
            keyboard.append([
                InlineKeyboardButton(
                    f"📋 {exp['identificador']} ({exp.get('numero', 'N/A')}/{exp.get('ano', 'N/A')})",
                    callback_data=f"consultar_{i}"
                )
            ])
        
        # Agregar botón para consultar todos
        keyboard.append([
            InlineKeyboardButton("🔄 Actualizar todos", callback_data="consultar_todos")
        ])
        keyboard.append([
            InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = "🔍 Selecciona el expediente que deseas consultar:"
        
        if update.message:
            await update.message.reply_text(message, reply_markup=reply_markup)
        elif update.callback_query:
            await update.callback_query.message.reply_text(message, reply_markup=reply_markup)
            
    except Exception as e:
        print(f"❌ Error en consultar_expediente: {e}")
        error_msg = "❌ Error al obtener tus expedientes."
        if update.message:
            await update.message.reply_text(error_msg)
        elif update.callback_query:
            await update.callback_query.message.reply_text(error_msg)

async def procesar_consulta_expediente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa la consulta de un expediente específico o todos"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    data = query.data
    
    try:
        if data == "consultar_todos":
            await consultar_todos_expedientes(query, user.id)
        elif data.startswith("consultar_"):
            index = int(data.replace("consultar_", ""))
            await consultar_expediente_individual(query, user.id, index)
        elif data == "volver_menu":
            await mostrar_menu_principal(query)
            
    except Exception as e:
        print(f"❌ Error procesando consulta: {e}")
        await query.message.reply_text("❌ Error al procesar la consulta.")

async def consultar_expediente_individual(query, user_id, index):
    """Consulta un expediente específico"""
    expedientes = get_user_expedientes(user_id)
    
    if index >= len(expedientes):
        await query.message.reply_text("❌ Expediente no encontrado.")
        return
        
    exp = expedientes[index]
    await query.message.reply_text(f"🔄 Consultando expediente '{exp['identificador']}'...")
    
    # Obtener datos actuales del tribunal
    datos_actuales = obtener_expediente(
        exp['distrito'], 
        exp['juzgado'], 
        exp['numero'], 
        exp['ano']
    )
    
    if datos_actuales is None:
        await query.message.reply_text(
            f"❌ No se pudo consultar el expediente '{exp['identificador']}'.\n"
            "Posibles causas:\n"
            "• El expediente no existe o fue archivado\n"
            "• Error de conexión con el tribunal\n"
            "• Datos del expediente incorrectos"
        )
        return
        
    if not datos_actuales:
        await query.message.reply_text(
            f"📄 Expediente '{exp['identificador']}' consultado.\n"
            "⚠️ No se encontraron actualizaciones o el expediente está sin movimiento."
        )
        return
    
    # Actualizar historial en base de datos
    update_expediente_historial(user_id, exp['identificador'], datos_actuales)
    
    # Preparar mensaje con últimas actualizaciones
    message = f"📋 **{exp['identificador']}** (Exp: {exp['numero']}/{exp['ano']})\n\n"
    message += "📅 **Últimas actualizaciones:**\n\n"
    
    # Mostrar las 3 actualizaciones más recientes
    for i, dato in enumerate(datos_actuales[-3:]):
        message += f"{i+1}. 📍 {dato.get('ubicacion', 'N/A')}\n"
        message += f"   📅 {dato.get('fecha', 'N/A')}\n"
        message += f"   📝 {dato.get('detalle', 'Sin detalles')}\n\n"
    
    if len(datos_actuales) > 3:
        message += f"... y {len(datos_actuales) - 3} actualizaciones más.\n\n"
    
    message += f"✅ Total de registros: {len(datos_actuales)}"
    
    # Botón para volver
    keyboard = [[InlineKeyboardButton("🔙 Volver a consultas", callback_data="menu_consultas")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def consultar_todos_expedientes(query, user_id):
    """Consulta todos los expedientes del usuario"""
    expedientes = get_user_expedientes(user_id)
    
    if not expedientes:
        await query.message.reply_text("📄 No tienes expedientes registrados.")
        return
        
    await query.message.reply_text(f"🔄 Consultando {len(expedientes)} expedientes...")
    
    actualizados = 0
    errores = 0
    sin_cambios = 0
    
    for exp in expedientes:
        try:
            datos_actuales = obtener_expediente(
                exp['distrito'], 
                exp['juzgado'], 
                exp['numero'], 
                exp['ano']
            )
            
            if datos_actuales is None:
                errores += 1
                continue
            elif not datos_actuales:
                sin_cambios += 1
                continue
            else:
                # Actualizar historial
                update_expediente_historial(user_id, exp['identificador'], datos_actuales)
                actualizados += 1
                
        except Exception as e:
            print(f"❌ Error consultando {exp['identificador']}: {e}")
            errores += 1
    
    # Resumen de resultados
    message = "📊 **Resumen de consulta:**\n\n"
    message += f"✅ Expedientes actualizados: {actualizados}\n"
    message += f"⚠️ Sin cambios: {sin_cambios}\n"
    message += f"❌ Errores: {errores}\n\n"
    
    if actualizados > 0:
        message += "Usa 'Ver historial' para ver las nuevas actualizaciones."
    
    # Botón para volver
    keyboard = [[InlineKeyboardButton("🔙 Volver a consultas", callback_data="menu_consultas")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

# -------------------- ELIMINAR EXPEDIENTES --------------------

async def mostrar_menu_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra lista de expedientes para eliminar"""
    user = update.effective_user
    
    try:
        expedientes = get_user_expedientes(user.id)
        if not expedientes:
            message = "📄 No tienes expedientes registrados para eliminar.\n\nUsa /menu → 'Registrar expediente' para agregar uno."
            if update.message:
                await update.message.reply_text(message)
            elif update.callback_query:
                await update.callback_query.message.reply_text(message)
            return
            
        # Crear botones para cada expediente
        keyboard = []
        for i, exp in enumerate(expedientes):
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑️ {exp['identificador']} ({exp.get('numero', 'N/A')}/{exp.get('ano', 'N/A')})",
                    callback_data=f"eliminar_{i}"
                )
            ])
        
        # Botón para volver al menú
        keyboard.append([
            InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = "🗑️ **Eliminar expedientes**\n\n⚠️ Selecciona el expediente que deseas eliminar del seguimiento:\n\n*Esta acción no se puede deshacer.*"
        
        if update.message:
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
    except Exception as e:
        print(f"❌ Error en mostrar_menu_eliminar: {e}")
        error_msg = "❌ Error al obtener tus expedientes."
        if update.message:
            await update.message.reply_text(error_msg)
        elif update.callback_query:
            await update.callback_query.message.reply_text(error_msg)

async def confirmar_eliminacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra confirmación antes de eliminar un expediente"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    data = query.data
    
    try:
        if not data.startswith("eliminar_"):
            return
            
        index = int(data.replace("eliminar_", ""))
        expedientes = get_user_expedientes(user.id)
        
        if index >= len(expedientes):
            await query.message.reply_text("❌ Expediente no encontrado.")
            return
            
        exp = expedientes[index]
        
        # Crear botones de confirmación
        keyboard = [
            [
                InlineKeyboardButton("✅ Sí, eliminar", callback_data=f"confirmar_eliminar_{index}"),
                InlineKeyboardButton("❌ Cancelar", callback_data="menu_eliminar")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"🗑️ **Confirmar eliminación**\n\n"
        message += f"¿Estás seguro de que deseas eliminar el expediente?\n\n"
        message += f"📋 **Identificador:** {exp['identificador']}\n"
        message += f"📄 **Expediente:** {exp.get('numero', 'N/A')}/{exp.get('ano', 'N/A')}\n\n"
        message += f"⚠️ **Esta acción no se puede deshacer.**\n"
        message += f"Se perderá todo el historial de seguimiento."
        
        await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
    except Exception as e:
        print(f"❌ Error en confirmar_eliminacion: {e}")
        await query.message.reply_text("❌ Error al procesar la eliminación.")

async def procesar_eliminacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa la eliminación confirmada de un expediente"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    data = query.data
    
    try:
        if not data.startswith("confirmar_eliminar_"):
            return
            
        index = int(data.replace("confirmar_eliminar_", ""))
        expedientes = get_user_expedientes(user.id)
        
        if index >= len(expedientes):
            await query.message.reply_text("❌ Expediente no encontrado.")
            return
            
        exp = expedientes[index]
        identificador = exp['identificador']
        
        # Eliminar el expediente
        if eliminar_expediente(user.id, identificador):
            message = f"✅ **Expediente eliminado**\n\n"
            message += f"El expediente '{identificador}' ha sido eliminado del seguimiento.\n\n"
            message += f"📋 Datos eliminados:\n"
            message += f"• Identificador: {identificador}\n"
            message += f"• Expediente: {exp.get('numero', 'N/A')}/{exp.get('ano', 'N/A')}\n"
            message += f"• Historial completo\n\n"
            message += f"Si necesitas volver a seguir este expediente, deberás registrarlo nuevamente."
            
            # Botón para volver al menú
            keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.message.reply_text("❌ No se pudo eliminar el expediente. Intenta más tarde.")
            
    except Exception as e:
        print(f"❌ Error en procesar_eliminacion: {e}")
        await query.message.reply_text("❌ Error al eliminar el expediente.")

async def mostrar_menu_principal(query):
    """Muestra el menú principal"""
    keyboard = [
        [InlineKeyboardButton("📥 Registrar expediente", callback_data="registrar")],
        [InlineKeyboardButton("🔍 Consultar actualizaciones", callback_data="menu_consultas")],
        [InlineKeyboardButton("📄 Ver historial", callback_data="historial")],
        [InlineKeyboardButton("🗑️ Eliminar expedientes", callback_data="menu_eliminar")],
        [InlineKeyboardButton("ℹ️ Estado de suscripción", callback_data="status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Elige una opción:", reply_markup=reply_markup)

# -------------------- REGISTRO GUIADO CON VALIDACIÓN --------------------

async def start_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicio del registro: mostrar distritos"""
    print("🔍 Iniciando registro, obteniendo distritos...")
    
    try:
        distritos = obtener_distritos()
        print(f"📍 Distritos obtenidos: {distritos}")
        
        if not distritos:
            await update.callback_query.message.reply_text("❌ Error: No se pudieron obtener los distritos. Intenta más tarde.")
            return ConversationHandler.END
            
        context.user_data['distritos'] = distritos

        keyboard = [
            [InlineKeyboardButton(nombre, callback_data=f"distrito_{key}")]
            for key, nombre in distritos.items()
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.message:
            await update.message.reply_text("📌 Selecciona el Distrito:", reply_markup=reply_markup)
        elif update.callback_query:
            await update.callback_query.message.reply_text("📌 Selecciona el Distrito:", reply_markup=reply_markup)

        return DIST
        
    except Exception as e:
        print(f"❌ Error en start_registro: {e}")
        if update.callback_query:
            await update.callback_query.message.reply_text("❌ Error al obtener distritos. Intenta más tarde.")
        return ConversationHandler.END

async def get_distrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se selecciona un distrito y se muestran juzgados disponibles"""
    query = update.callback_query
    await query.answer()

    distrito_id = query.data.replace("distrito_", "")
    context.user_data['distrito'] = distrito_id
    
    print(f"🏛️ Distrito seleccionado: {distrito_id}")

    try:
        juzgados = obtener_juzgados_por_distrito(distrito_id)
        print(f"⚖️ Juzgados obtenidos: {juzgados}")
        
        if not juzgados:
            await query.message.reply_text("❌ No se encontraron juzgados activos para este distrito.")
            return ConversationHandler.END
            
        context.user_data['juzgados'] = {j['id']: j['nombre_juzgado'] for j in juzgados}

        keyboard = [
            [InlineKeyboardButton(nombre, callback_data=f"juzgado_{jid}")]
            for jid, nombre in context.user_data['juzgados'].items()
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("📌 Selecciona el Juzgado:", reply_markup=reply_markup)

        return JUZGADO
        
    except Exception as e:
        print(f"❌ Error en get_distrito: {e}")
        await query.message.reply_text("❌ Error al obtener juzgados. Intenta más tarde.")
        return ConversationHandler.END

async def get_juzgado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se selecciona un juzgado y se solicita número de expediente"""
    query = update.callback_query
    await query.answer()

    juzgado_id = query.data.replace("juzgado_", "")
    context.user_data['juzgado'] = juzgado_id
    
    print(f"⚖️ Juzgado seleccionado: {juzgado_id}")

    await query.message.reply_text("📌 Ingresa el Número de expediente:")
    return NUMERO

async def get_numero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    numero = update.message.text.strip()
    
    if not numero:
        await update.message.reply_text("❌ Por favor ingresa un número de expediente válido:")
        return NUMERO
    
    context.user_data['numero'] = numero
    await update.message.reply_text("📌 Ingresa el Año (formato: YYYY):")
    return ANO

async def get_ano(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ano = update.message.text.strip()
    
    if not ano.isdigit() or len(ano) != 4:
        await update.message.reply_text("❌ Por favor ingresa un año válido (formato: YYYY):")
        return ANO
    
    context.user_data['ano'] = ano
    
    # 🆕 VALIDAR QUE EL EXPEDIENTE EXISTE ANTES DE CONTINUAR
    await update.message.reply_text("🔍 Verificando que el expediente existe...")
    
    data = context.user_data
    resultado_validacion = validar_expediente_existe(data['distrito'], data['juzgado'], data['numero'], data['ano'])
    
    if isinstance(resultado_validacion, dict):
        if resultado_validacion.get('existe') == False:
            await update.message.reply_text(
                "❌ **Expediente no encontrado**\n\n"
                f"No se pudo encontrar el expediente {data['numero']}/{data['ano']} "
                f"en el juzgado seleccionado.\n\n"
                "Por favor verifica:\n"
                "• Número de expediente correcto\n"
                "• Año correcto\n"
                "• Distrito y juzgado correctos\n\n"
                "Usa /cancelar para empezar de nuevo.",
                parse_mode='Markdown'
            )
            return ANO  # Volver a pedir el año
        elif resultado_validacion.get('existe') == None:
            await update.message.reply_text(
                "⚠️ **No se pudo verificar el expediente**\n\n"
                "Hubo un problema al verificar si el expediente existe. "
                "Puedes continuar bajo tu propio riesgo.\n\n"
                "📌 Ingresa un identificador personal para este expediente:"
            )
            return IDENTIFICADOR
    else:
        # Compatibilidad con el método anterior
        if not resultado_validacion:
            await update.message.reply_text(
                "❌ **Expediente no encontrado**\n\n"
                f"No se pudo encontrar el expediente {data['numero']}/{data['ano']} "
                f"en el juzgado seleccionado.\n\n"
                "Por favor verifica:\n"
                "• Número de expediente correcto\n"
                "• Año correcto\n"
                "• Distrito y juzgado correctos\n\n"
                "Usa /cancelar para empezar de nuevo.",
                parse_mode='Markdown'
            )
            return ANO  # Volver a pedir el año
    
    await update.message.reply_text(
        "✅ ¡Expediente encontrado!\n\n"
        "📌 Ahora ingresa un identificador personal para este expediente:"
    )
    return IDENTIFICADOR

async def get_identificador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    identificador = update.message.text.strip()
    
    if not identificador:
        await update.message.reply_text("❌ Por favor ingresa un identificador válido:")
        return IDENTIFICADOR
        
    context.user_data['identificador'] = identificador
    data = context.user_data
    
    print(f"💾 Guardando expediente: {data}")
    
    try:
        exito = save_expediente(
            user_id,
            data['distrito'],
            data['juzgado'],
            data['numero'],
            data['ano'],
            data['identificador']
        )

        if exito:
            await update.message.reply_text(
                f"✅ Expediente '{data['identificador']}' registrado correctamente.\n\n"
                f"📋 Distrito: {data.get('distritos', {}).get(data['distrito'], data['distrito'])}\n"
                f"⚖️ Juzgado: {data.get('juzgados', {}).get(data['juzgado'], data['juzgado'])}\n"
                f"📄 Expediente: {data['numero']}/{data['ano']}\n\n"
                "Usa /menu → 'Consultar actualizaciones' para ver el estado actual."
            )
        else:
            await update.message.reply_text(f"⚠️ Ya existe un expediente con el identificador '{data['identificador']}'.")

    except Exception as e:
        print(f"❌ Error guardando expediente: {e}")
        await update.message.reply_text("❌ Error al guardar el expediente. Intenta más tarde.")

    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("❌ Registro cancelado.")
    elif update.callback_query:
        await update.callback_query.message.reply_text("❌ Registro cancelado.")
    return ConversationHandler.END

# -------------------- COMANDOS BÁSICOS --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    nuevo = save_user_if_not_exists(user.id, user.username, user.first_name)
    
    if nuevo:
        await update.message.reply_text(
            f"Hola {user.first_name} 👋\n"
            "Te has registrado y ahora tienes una prueba gratuita de 10 días.\n"
            "Podrás recibir notificaciones de tus expedientes.\n\n"
            "Usa /menu para ver las opciones disponibles."
        )
    else:
        await update.message.reply_text("Ya estabas registrado. Usa /menu para ver opciones.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    try:
        data = get_user(user.id)
        if not data:
            message = "No estás registrado. Usa /start para registrarte."
        else:
            fecha_exp = data["fecha_expiracion"].strftime("%Y-%m-%d %H:%M:%S UTC")
            activo = is_subscription_active(user.id)
            estado = "✅ Activa" if activo else "❌ Expirada"
            message = f"📅 Tu suscripción expira el: {fecha_exp}\nEstado: {estado}"
    except Exception as e:
        print(f"❌ Error en status: {e}")
        message = "❌ Error al consultar el estado de tu suscripción."
    
    if update.message:
        await update.message.reply_text(message)
    elif update.callback_query:
        await update.callback_query.message.reply_text(message)

async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra lista de expedientes para ver historial detallado"""
    user = update.effective_user
    
    try:
        expedientes = get_user_expedientes(user.id)
        if not expedientes:
            message = "📄 No tienes expedientes registrados.\n\nUsa /menu → 'Registrar expediente' para agregar uno."
            if update.message:
                await update.message.reply_text(message)
            elif update.callback_query:
                await update.callback_query.message.reply_text(message)
            return
            
        # Crear botones para cada expediente
        keyboard = []
        for i, exp in enumerate(expedientes):
            # Obtener información resumida para el botón
            historial_exp = exp.get("historial", [])
            total_actualizaciones = len(historial_exp)
            
            keyboard.append([
                InlineKeyboardButton(
                    f"📋 {exp['identificador']} ({total_actualizaciones} act.)",
                    callback_data=f"detalle_historial_{i}"
                )
            ])
        
        # Botón para volver al menú
        keyboard.append([
            InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = "📄 **Historial de expedientes**\n\nSelecciona un expediente para ver su información detallada:"
        
        if update.message:
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
    except Exception as e:
        print(f"❌ Error en historial: {e}")
        error_msg = "❌ Error al obtener el historial de expedientes."
        if update.message:
            await update.message.reply_text(error_msg)
        elif update.callback_query:
            await update.callback_query.message.reply_text(error_msg)

async def mostrar_detalle_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el historial detallado de un expediente específico"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    data = query.data
    
    try:
        if not data.startswith("detalle_historial_"):
            return
            
        index = int(data.replace("detalle_historial_", ""))
        expedientes = get_user_expedientes(user.id)
        
        if index >= len(expedientes):
            await query.message.reply_text("❌ Expediente no encontrado.")
            return
            
        exp = expedientes[index]
        
        # Construir mensaje detallado
        message = f"📋 **HISTORIAL DETALLADO**\n\n"
        
        # ===== INFORMACIÓN BÁSICA =====
        message += f"🏷️ **Identificador:** {exp['identificador']}\n"
        message += f"📄 **Expediente:** {exp.get('numero', 'N/A')}/{exp.get('ano', 'N/A')}\n"
        
        # Obtener nombres legibles de distrito y juzgado si están disponibles
        from backend.scraper import obtener_distritos, obtener_juzgados_por_distrito
        
        distrito_nombre = exp.get('distrito', 'N/A')
        juzgado_nombre = exp.get('juzgado', 'N/A')
        
        try:
            # Intentar obtener nombre del distrito
            distritos = obtener_distritos()
            if distritos and str(exp.get('distrito')) in distritos:
                distrito_nombre = distritos[str(exp.get('distrito'))]
        except:
            pass
            
        try:
            # Intentar obtener nombre del juzgado
            if exp.get('distrito'):
                juzgados = obtener_juzgados_por_distrito(str(exp.get('distrito')))
                for juzgado in juzgados:
                    if juzgado.get('id') == str(exp.get('juzgado')):
                        juzgado_nombre = juzgado.get('nombre_juzgado', juzgado_nombre)
                        break
        except:
            pass
            
        message += f"🏛️ **Distrito:** {distrito_nombre}\n"
        message += f"⚖️ **Juzgado:** {juzgado_nombre}\n\n"
        
        # ===== FECHAS IMPORTANTES =====
        message += f"📅 **INFORMACIÓN DE SEGUIMIENTO:**\n"
        
        # Fecha de registro (se puede obtener del historial o agregar al esquema)
        historial_exp = exp.get("historial", [])
        if historial_exp:
            fecha_registro = historial_exp[0].get("fecha_chequeo")
            if fecha_registro:
                message += f"📌 **Agregado el:** {fecha_registro.strftime('%d/%m/%Y %H:%M')}\n"
        
        # Última consulta
        ultimo_chequeo = exp.get("ultimo_chequeo")
        if ultimo_chequeo:
            message += f"🔍 **Última consulta:** {ultimo_chequeo.strftime('%d/%m/%Y %H:%M')}\n"
        else:
            message += f"🔍 **Última consulta:** Nunca consultado\n"
            
        # Total de actualizaciones
        total_actualizaciones = len(historial_exp)
        message += f"📊 **Total de consultas:** {total_actualizaciones}\n\n"
        
        # ===== HISTORIAL DE ACTUALIZACIONES =====
        if historial_exp:
            message += f"📋 **HISTORIAL DE ACTUALIZACIONES:**\n\n"
            
            # Mostrar las últimas 5 consultas
            ultimas_consultas = historial_exp[-5:]
            
            for i, entrada in enumerate(reversed(ultimas_consultas)):
                fecha_consulta = entrada.get("fecha_chequeo")
                datos = entrada.get("datos", [])
                
                if fecha_consulta:
                    message += f"🔹 **{fecha_consulta.strftime('%d/%m/%Y %H:%M')}**\n"
                
                if datos:
                    # Mostrar solo las 2 actualizaciones más recientes de esa consulta
                    for j, dato in enumerate(datos[-2:]):
                        ubicacion = dato.get('ubicacion', dato.get('columna_0', 'N/A'))
                        fecha = dato.get('fecha', dato.get('columna_1', 'N/A'))
                        detalle = dato.get('detalle', dato.get('columna_2', 'Sin detalles'))
                        
                        message += f"   📍 {ubicacion}\n"
                        message += f"   📅 {fecha}\n"
                        message += f"   📝 {detalle[:80]}{'...' if len(str(detalle)) > 80 else ''}\n\n"
                        
                        if j == 0 and len(datos) > 1:
                            message += f"   ... y {len(datos) - 1} actualizaciones más\n\n"
                            break
                else:
                    message += f"   ⚠️ Sin actualizaciones encontradas\n\n"
                    
                if i == 2:  # Limitar a 3 consultas mostradas
                    break
            
            if len(historial_exp) > 5:
                message += f"... y {len(historial_exp) - 5} consultas anteriores.\n\n"
        else:
            message += f"📋 **HISTORIAL:**\n⚠️ Este expediente aún no ha sido consultado.\n"
            message += f"Usa 'Consultar actualizaciones' para obtener datos.\n\n"
        
        # ===== ESTADO ACTUAL =====
        if historial_exp and historial_exp[-1].get("datos"):
            ultima_entrada = historial_exp[-1]
            ultimos_datos = ultima_entrada.get("datos", [])
            
            if ultimos_datos:
                ultimo_registro = ultimos_datos[-1]
                message += f"🔄 **ÚLTIMO REGISTRO CONOCIDO:**\n"
                message += f"📍 {ultimo_registro.get('ubicacion', ultimo_registro.get('columna_0', 'N/A'))}\n"
                message += f"📅 {ultimo_registro.get('fecha', ultimo_registro.get('columna_1', 'N/A'))}\n"
                message += f"📝 {ultimo_registro.get('detalle', ultimo_registro.get('columna_2', 'Sin detalles'))}\n"
        
        # Botones de acción
        keyboard = [
            [
                InlineKeyboardButton("🔄 Consultar ahora", callback_data=f"consultar_{index}"),
                InlineKeyboardButton("🗑️ Eliminar", callback_data=f"eliminar_{index}")
            ],
            [InlineKeyboardButton("🔙 Volver al historial", callback_data="historial")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Dividir el mensaje si es muy largo
        if len(message) > 4000:
            # Dividir en dos partes
            parte1 = message[:message.find("📋 **HISTORIAL DE ACTUALIZACIONES:**")]
            parte2 = message[message.find("📋 **HISTORIAL DE ACTUALIZACIONES:**"):]
            
            await query.message.reply_text(parte1, parse_mode='Markdown')
            await query.message.reply_text(parte2, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
    except Exception as e:
        print(f"❌ Error en mostrar_detalle_historial: {e}")
        await query.message.reply_text("❌ Error al obtener el historial detallado.")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📥 Registrar expediente", callback_data="registrar")],
        [InlineKeyboardButton("🔍 Consultar actualizaciones", callback_data="menu_consultas")],
        [InlineKeyboardButton("📄 Ver historial", callback_data="historial")],
        [InlineKeyboardButton("🗑️ Eliminar expedientes", callback_data="menu_eliminar")],
        [InlineKeyboardButton("ℹ️ Estado de suscripción", callback_data="status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Elige una opción:", reply_markup=reply_markup)

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los callbacks que no son parte del ConversationHandler"""
    query = update.callback_query
    await query.answer()
    data = query.data

    print(f"🔘 Callback recibido: {data}")

    if data == "registrar":
        return await start_registro(update, context)
    elif data == "menu_consultas":
        await consultar_expediente(update, context)
    elif data == "historial":
        await historial(update, context)
    elif data == "status":
        await status(update, context)
    elif data == "menu_eliminar":
        await mostrar_menu_eliminar(update, context)
    elif data.startswith("eliminar_"):
        await confirmar_eliminacion(update, context)
    elif data.startswith("confirmar_eliminar_"):
        await procesar_eliminacion(update, context)
    elif data.startswith("consultar_") or data == "consultar_todos" or data == "volver_menu":
        await procesar_consulta_expediente(update, context)
    else:
        print(f"⚠️ Callback no reconocido: {data}")

# -------------------- REGISTRAR HANDLERS --------------------

def registrar_handlers(app):
    """Registra todos los handlers en el orden correcto"""
    
    # Comandos básicos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("historial", historial))
    app.add_handler(CommandHandler("menu", menu))
    
    # ConversationHandler para registro de expedientes
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_registro, pattern="^registrar$")
        ],
        states={
            DIST: [CallbackQueryHandler(get_distrito, pattern="^distrito_")],
            JUZGADO: [CallbackQueryHandler(get_juzgado, pattern="^juzgado_")],
            NUMERO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_numero)],
            ANO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ano)],
            IDENTIFICADOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_identificador)],
        },
        fallbacks=[CommandHandler('cancelar', cancelar)],
        name="conv_registro",
        persistent=False
    )
    
    app.add_handler(conv_handler)
    
    # Callbacks del menú (deben ir después del ConversationHandler)
    app.add_handler(CallbackQueryHandler(menu_callback))
    
    print("✅ Handlers registrados correctamente")