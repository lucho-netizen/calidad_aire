from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit
import mysql.connector
from datetime import datetime
import time
import threading
import random

app = Flask(__name__)
socketio = SocketIO(app)

# Conexión a la base de datos
db = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password='iq2103huila',
    database="calidad_aire"
)

# Variable para controlar si hubo un nuevo dato insertado
new_data_flag = False

@app.route('/upload', methods=['POST'])
def upload_data():
    global new_data_flag  # Declaramos que estamos usando la variable global
    if request.is_json:
        data = request.get_json()
        print(f"Datos recibidos: {data}")
        valores = {}
        try:
            partes = data["data"].split()  # separa por espacios
            for parte in partes:
                if ":" in parte:
                    clave, valor = parte.split(":")
                    valores[clave.strip()] = float(valor.strip())
        except Exception as e:
            print(f"Error al parsear los datos: {e}")
            return jsonify({"error": "Formato inválido"}), 400

        temperatura = valores.get("Tmp")
        humedad = valores.get("Hmd")
        co2 = valores.get("CO2")
        alcohol = valores.get("Alc")
        benzeno = valores.get("Bzn")
        amoniaco = valores.get("NH3")

        if temperatura is None or humedad is None or co2 is None or alcohol is None or benzeno is None or amoniaco is None:
            return jsonify({"error": "Datos incompletos"}), 400

        # Guardar en la base de datos con fecha y hora actual
        cursor = db.cursor()
        now = datetime.now()
        fecha = now.date()
        hora = now.time()
        query = "INSERT INTO datas (fecha, hora, temperatura, humedad, co2, alcohol, benzeno, amoniaco) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        values = (fecha, hora, temperatura, humedad, co2, alcohol, benzeno, amoniaco)
        cursor.execute(query, values)
        print(query)
        db.commit()
        cursor.close()

        new_data_flag = True  # Señalamos que hay nuevo dato

        return jsonify({"message": "Datos guardados correctamente en la base de datos"}), 200
    else:
        return jsonify({"message": "Formato JSON esperado"}), 400


# Esta función revisará si hubo cambios en la base de datos
def check_for_new_data():
    global new_data_flag  # Aseguramos que usamos la variable global
    while True:
        if new_data_flag:
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT fecha, hora, temperatura, humedad, co2, alcohol, benzeno, amoniaco FROM datas ORDER BY id DESC LIMIT 1")
            data = cursor.fetchone()
            cursor.close()

            if data:
                event_data = {
                    "temperatura": data['temperatura'],
                    "humedad": data['humedad'],
                    "co2": data['co2'],
                    "fecha": f"{data['fecha']} {data['hora']}",
                    "alcohol": f"{data['alcohol']} {data['alcohol']}",
                    "benzeno": f"{data['benzeno']} {data['benzeno']}",
                    "amoniaco": f"{data['amoniaco']} {data['amoniaco']}"
                }
                socketio.emit('new_data', event_data)
                new_data_flag = False  # Reiniciamos el flag

        time.sleep(1)


@app.route('/api/estadisticas')
def estadisticas():
    periodo = request.args.get('periodo', 'hora')  # hora, dia, mes
    cursor = db.cursor(dictionary=True)

    if periodo == 'hora':
        group_format = "%Y-%m-%d %H"
    elif periodo == 'dia':
        group_format = "%Y-%m-%d"
    elif periodo == 'mes':
        group_format = "%Y-%m"
    else:
        group_format = "%Y-%m-%d %H"

    # Agrupar por el formato correspondiente
    query = f"""
        SELECT 
            DATE_FORMAT(CONCAT(fecha, ' ', hora), '{group_format}') AS periodo,
            AVG(temperatura) AS temperatura,
            AVG(humedad) AS humedad,
            AVG(co2) AS co2,
            AVG(alcohol) AS alcohol,
            AVG(benzeno) AS benzeno,
            AVG(amoniaco) AS amoniaco
        FROM mediciones
        GROUP BY periodo
        ORDER BY periodo DESC
        LIMIT 10000
    """

    cursor.execute(query)
    datos = cursor.fetchall()
    cursor.close()

    return jsonify(datos)

# Ruta principal
@app.route('/')
def index():
    return render_template('index.html')


# Iniciar un thread para verificar si hay nuevos datos
def start_background_task():
    threading.Thread(target=check_for_new_data, daemon=True).start()

# Iniciar un hilo separado para la inserción de datos
def start_insertion_thread():
    thread = threading.Thread(target=insert_random_data)
    thread.daemon = True  # Hacer que el hilo se cierre cuando se cierre el servidor
    thread.start()

# Corregir la ejecución de la inserción de datos
def insert_random_data():
    while True:
        cursor = db.cursor()
        fecha = time.strftime('%Y-%m-%d')
        hora = time.strftime('%H:%M:%S')
        temperatura = random.uniform(18, 30)
        humedad = random.uniform(40, 80)
        co2 = random.randint(300, 1000)
        alcohol = random.uniform(0, 2)
        benzeno = random.uniform(0, 1)
        amoniaco = random.uniform(0, 1)

        query = """
            INSERT INTO mediciones (fecha, hora, temperatura, humedad, co2, alcohol, benzeno, amoniaco) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (fecha, hora, temperatura, humedad, co2, alcohol, benzeno, amoniaco))
        db.commit()
        cursor.close()
        time.sleep(1) # Esperar 1 segundo antes de insertar el siguiente registro

# Comenzar el hilo cuando se inicia la aplicación
if __name__ == '__main__':
    start_background_task()  # Iniciar la comprobación de nuevos datos
    # start_insertion_thread()  # Iniciar la inserción de datos aleatorios
    # check_for_new_data()
    socketio.run(app, debug=True, port=6700)
