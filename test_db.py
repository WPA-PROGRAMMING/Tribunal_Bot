from backend.db import users_collection

print("Probando conexión a MongoDB Atlas...")

try:
    users_collection.insert_one({"telegram_id": 1, "nombre": "UsuarioPrueba"})
    print("✅ Inserción correcta.")
    
    usuarios = list(users_collection.find())
    print("Usuarios en la BD:", usuarios)
except Exception as e:
    print("❌ Error:", e)
