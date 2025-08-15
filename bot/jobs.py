# bot/jobs.py

from backend.db import get_expired_users, deactivate_user

async def check_expired_subscriptions(app):
    expired_users = get_expired_users()
    for user in expired_users:
        deactivate_user(user["user_id"])
        try:
            await app.bot.send_message(
                chat_id=user["user_id"],
                text=(
                    "⚠️ Tu suscripción ha expirado.\n"
                    "Para seguir recibiendo notificaciones, por favor renueva tu plan."
                )
            )
        except Exception as e:
            print(f"Error enviando mensaje a {user['user_id']}: {e}")

from backend.db import get_user_expedientes
from backend.db import check_and_update_expediente

async def revisar_expedientes(app):
    """
    Revisa todos los expedientes de todos los usuarios suscritos y envía notificaciones
    si hay cambios.
    """
    from backend.db import usuarios

    usuarios_activos = list(usuarios.find({"activo": True}))
    for user in usuarios_activos:
        expedientes_usuario = get_user_expedientes(user["user_id"])
        for expediente in expedientes_usuario:
            cambio = check_and_update_expediente(expediente)
            if cambio:
                try:
                    await app.bot.send_message(
                        chat_id=user["user_id"],
                        text=f"📢 Cambio detectado en expediente '{expediente['identificador']}'"
                    )
                except Exception as e:
                    print(f"Error notificando a {user['user_id']}: {e}")
