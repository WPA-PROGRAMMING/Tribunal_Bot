import os

# Estructura de carpetas y archivos
estructura = {
    "bot": ["__init__.py", "main.py", "handlers.py", "keyboards.py", "notifications.py"],
    "backend": ["__init__.py", "api.py", "models.py", "db.py", "scheduler.py", "scraper.py"],
    "config": ["settings.py"],
    "utils": ["helpers.py", "validators.py"],
    "": ["requirements.txt", "README.md"]  # Archivos en raíz
}

def crear_estructura():
    for carpeta, archivos in estructura.items():
        if carpeta:  # Si no es la raíz
            os.makedirs(carpeta, exist_ok=True)
        for archivo in archivos:
            ruta = os.path.join(carpeta, archivo) if carpeta else archivo
            if not os.path.exists(ruta):
                with open(ruta, "w", encoding="utf-8") as f:
                    if archivo == "__init__.py":
                        f.write("")  # Archivo vacío
                    elif archivo == "README.md":
                        f.write("# Bot de Seguimiento de Expedientes – TSJ Tlaxcala\n")
                    elif archivo == "requirements.txt":
                        f.write("fastapi\nuvicorn\npython-telegram-bot==20.0\npymongo\nrequests\nbeautifulsoup4\napscheduler\npydantic\n")
                    else:
                        f.write("# " + archivo + "\n")
                print(f"✅ Creado: {ruta}")

if __name__ == "__main__":
    crear_estructura()

