# bot/main.py
from telegram.ext import Application
from config.settings import TELEGRAM_TOKEN
from bot.handlers import registrar_handlers
from bot.jobs import check_expired_subscriptions, revisar_expedientes
import pytz
from datetime import time

def main():
    # Crear la aplicación
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Registrar comandos
    registrar_handlers(app)

    # Configurar zona horaria México
    mexico_tz = pytz.timezone("America/Mexico_City")

    # Job diario: revisar suscripciones expiradas a las 12:00 PM
    app.job_queue.run_daily(
        check_expired_subscriptions,
        time=time(hour=12, minute=0, tzinfo=mexico_tz),
        name="check_expired"
    )

    # Job repetitivo: revisar expedientes cada 30 minutos
    app.job_queue.run_repeating(
        lambda context: context.application.create_task(revisar_expedientes(context.application)),
        interval=1800,  # 30 minutos
        first=10,       # esperar 10 segundos al iniciar
        name="revisar_expedientes"
    )

    print("🤖 Bot iniciado. Esperando mensajes y revisando expedientes...")
    app.run_polling()

if __name__ == "__main__":
    main()
