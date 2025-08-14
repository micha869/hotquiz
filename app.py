# -*- coding: utf-8 -*-
"""
HotQuiz – App principal
"""
from flask import Flask, render_template, session, redirect, url_for, flash, request, send_file, jsonify
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from dotenv import load_dotenv
load_dotenv()
from werkzeug.utils import secure_filename
from uuid import uuid4

import os
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import timedelta, datetime
from werkzeug.security import generate_password_hash, check_password_hash
import re
from collections import Counter
import hashlib
import time
import pusher
from gridfs import GridFS
import base64
import certifi

# ---------------------------------------------------------------------------
# Config Flask + Mongo
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_secreta_hotquiz")
app.permanent_session_lifetime = timedelta(days=30) # duración de la cookie
socketio = SocketIO(app)
client = MongoClient(os.getenv("MONGODB_URI"), tlsCAFile=certifi.where())
db = client.hotquiz
fs = GridFS(db)

usuarios_col = db.usuarios
confesiones_col = db.confesiones
retos_col = db.retos
fotos_col = db.fotos_hot
audios_col = db.audios_hot
roulette_col = db.roulette
hotcopy_col = db.hotcopy
adivina_col = db.adivina
publicaciones_col = db.publicaciones
Counter_col = db.Counter
compras_col = db.compras
reacciones_col = db.reacciones
comentarios_hot_col = db.comentarios_hot
comentarios_col = db.comentarios
donaciones_col = db.donaciones_tokens
hotreels_col = db.hotreels
retiros_col = db.retiros
mensajes_col = db.mensajes

# Configuración de Pusher (Chat)
pusher_client = pusher.Pusher(
    app_id=os.getenv("PUSHER_APP_ID", "2031513"),
    key=os.getenv("PUSHER_KEY", "24aebba9248c791c8722"),
    secret=os.getenv("PUSHER_SECRET", "84d7288e7578267c3f6e"),
    cluster=os.getenv("PUSHER_CLUSTER", "mt1"),
    ssl=True
)

# ---------------------------------------------------------------------------
# Archivos multimedia
# ---------------------------------------------------------------------------
# ¡CORRECCIÓN! Eliminamos la configuración de la carpeta UPLOAD_FOLDER local.
# Las extensiones se mantienen para validación.
ALLOWED_IMAGE = {"png", "jpg", "jpeg", "gif"}
ALLOWED_AUDIO = {"mp3", "wav", "ogg", "m4a"}
ALLOWED_VIDEO = {"mp4", "mov", "avi", "wmv", "flv", "webm"}

def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions

# ¡NUEVO! Ruta para servir archivos desde GridFS
@app.route("/media/<file_id>")
def serve_media(file_id):
    try:
        # Se usó fs.get() en lugar de fs.open_download_stream()
        # El método .get() de la clase GridFS retorna un objeto GridOut que es compatible con send_file
        file_obj = fs.get(ObjectId(file_id))
        return send_file(
            file_obj,
            download_name=file_obj.filename,
            mimetype=file_obj.content_type
        )
    except Exception as e:
        print(f"Error al servir el archivo: {e}")
        return "Archivo no encontrado", 404

# ---------------------------------------------------------------------------
# Helper: obtener usuario y saldo
# ---------------------------------------------------------------------------

def get_user_and_saldo():
    alias = session.get("alias")
    if not alias:
        return None, 0, 0
    user = usuarios_col.find_one({"alias": alias})
    oro = int(user.get("tokens_oro", 0)) if user else 0
    plata = int(user.get("tokens_plata", 0)) if user else 0
    return alias, oro, plata

# ---------------------------------------------------------------------------
# Rutas de autenticación
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if session.get("alias"):
        return redirect(url_for("inicio"))
    return render_template("index.html")

@app.route("/inicio")
def inicio():
    alias = session.get("alias")
    if not alias:
        flash("Debes iniciar sesión para ver esta página.")
        return redirect(url_for("index"))
    return render_template("inicio.html", alias=alias)

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        alias = request.form["alias"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]

        if not alias or not email or not password:
            flash("Completa todos los campos")
            return redirect(url_for("registro"))

        acepta_terminos = request.form.get("acepta_terminos")
        acepta_privacidad = request.form.get("acepta_privacidad")
        if not acepta_terminos or not acepta_privacidad:
            flash("Debes aceptar los términos y la política de privacidad")
            return redirect(url_for("registro"))

        if usuarios_col.find_one({"alias": alias}):
            flash("Alias ya registrado")
            return redirect(url_for("registro"))

        hashed_password = generate_password_hash(password)
        usuarios_col.insert_one({
            "alias": alias,
            "email": email,
            "password": hashed_password,
            "tokens_oro": 0,
            "tokens_plata": 100,
            "verificado": False
        })
        flash("Registro exitoso, inicia sesión")
        return redirect(url_for("login"))
    return render_template("registro.html")

@app.route("/terminos")
def terminos():
    return render_template("terminos.html")

@app.route("/privacidad")
def privacidad():
    return render_template("privacidad.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        alias = request.form["alias"].strip()
        password = request.form["password"]
        recordarme = request.form.get("recordarme")

        user = usuarios_col.find_one({"alias": alias})
        if not user or not check_password_hash(user["password"], password):
            flash("Credenciales inválidas")
            return redirect(url_for("login"))

        session.permanent = bool(recordarme)
        session["alias"] = alias
        flash("Sesión iniciada")
        return redirect(url_for("inicio"))
    return render_template("login.html")

@app.route("/salir")
def salir():
    session.clear()
    flash("Sesión cerrada")
    return redirect(url_for("index"))

# ---------------------------------------------------------------------------
# Juego 1 – Foto Hot
# ---------------------------------------------------------------------------
from datetime import datetime, timedelta
from flask import request, redirect, url_for, render_template, flash, jsonify
from bson import ObjectId
from werkzeug.utils import secure_filename
import base64
from uuid import uuid4

# Asegúrate de que 'app', 'fs', 'fotos_col', 'usuarios_col', etc. estén definidos
# y que las importaciones de Flask, ObjectId y datetime sean correctas.

# ... (otras rutas y funciones de tu app) ...

# Nueva función para eliminar duelos antiguos
def delete_old_duels():
    """Elimina duelos con más de 7 días de antigüedad y sus imágenes asociadas."""
    try:
        limite_fecha = datetime.now() - timedelta(days=7)
        duelos_viejos = list(fotos_col.find({"fecha": {"$lt": limite_fecha}}))

        for duelo in duelos_viejos:
            # Elimina las imágenes de GridFS
            if "player_image" in duelo and duelo["player_image"]:
                try:
                    fs.delete(ObjectId(duelo["player_image"]))
                except Exception as e:
                    print(f"Error al eliminar imagen de player de GridFS: {e}")

            if "rival_image" in duelo and duelo["rival_image"]:
                try:
                    fs.delete(ObjectId(duelo["rival_image"]))
                except Exception as e:
                    print(f"Error al eliminar imagen de rival de GridFS: {e}")

        # Elimina los documentos del duelo de la base de datos
        fotos_col.delete_many({"fecha": {"$lt": limite_fecha}})
        print(f"Se eliminaron {len(duelos_viejos)} duelos antiguos.")
    except Exception as e:
        print(f"Error en la tarea de eliminar duelos antiguos: {e}")

# Rutas para el juego
@app.route("/foto_hot", methods=["GET", "POST"])
def foto_hot():
    alias, tokens_oro, tokens_plata = get_user_and_saldo()
    if not alias:
        flash("Inicia sesión para jugar.")
        return redirect(url_for("index"))

    if request.method == "POST":
        rival = request.form.get("rival")
        file = request.files.get("imagen")

        if not file or not allowed_file(file.filename, ALLOWED_IMAGE):
            flash("Sube una imagen válida (.png, .jpg, .jpeg, .gif)")
            return redirect(url_for("foto_hot"))

        file_id = fs.put(file, filename=secure_filename(file.filename), content_type=file.content_type)
        ruta_img = str(file_id)

        duelo = fotos_col.find_one({
            "$or": [
                {"player": alias, "rival": rival, "estado": "pendiente"},
                {"player": rival, "rival": alias, "estado": "pendiente"}
            ]
        })

        if duelo:
            update = {}
            if duelo["player"] == alias and not duelo.get("player_image"):
                update = {"player_image": ruta_img, "player_tokens": 0, "player_votes": 0}
            elif duelo["rival"] == alias and not duelo.get("rival_image"):
                update = {"rival_image": ruta_img, "rival_tokens": 0, "rival_votes": 0}
            else:
                flash("Ya subiste una foto para este duelo.")
                return redirect(url_for("foto_hot"))
            
            # Devolver token de plata usado
            usuarios_col.update_one({"alias": alias}, {"$inc": {"tokens_plata": 1}})
            fotos_col.update_one({"_id": duelo["_id"]}, {"$set": update})
            flash("Foto subida al duelo 🔥")
        else:
            if tokens_plata < 1:
                flash("No tienes suficientes tokens de plata para crear un reto.")
                return redirect(url_for("foto_hot"))

            usuarios_col.update_one({"alias": alias}, {"$inc": {"tokens_plata": -1}})
            fotos_col.insert_one({
                "player": alias,
                "player_image": ruta_img,
                "player_tokens": 0,
                "player_votes": 0,
                "rival": rival or None,
                "rival_image": None,
                "rival_tokens": 0,
                "rival_votes": 0,
                "comentarios": [],
                "fecha": datetime.now(),
                "estado": "pendiente",
                "votantes": []
            })
            flash("Foto subida al duelo 🔥")

        return redirect(url_for("foto_hot"))

    # En la primera carga, solo muestra la primera página
    duelos = list(fotos_col.find({"estado": "pendiente"}).sort("fecha", -1).limit(10))
    return render_template("foto_hot.html", alias=alias, saldo=tokens_oro, saldo_plata=tokens_plata, duelos=duelos)


@app.route("/foto_hot_paginated/<int:page>")
def foto_hot_paginated(page):
    """API para el scroll infinito."""
    page_size = 10
    skip_amount = (page - 1) * page_size
    duelos = list(fotos_col.find({"estado": "pendiente"}).sort("fecha", -1).skip(skip_amount).limit(page_size))
    
    html_duelos = ""
    for d in duelos:
        html_duelos += render_template("_duelo_card.html", d=d, alias=session.get("alias"))
    
    return jsonify({"html": html_duelos, "has_more": len(duelos) == page_size})

# ... (otras rutas como votar_duelo, comentario_duelo, etc.) ...

@app.route("/eliminar_foto_hot/<reto_id>", methods=["POST"])
def eliminar_foto_hot(reto_id):
    alias, _, _ = get_user_and_saldo()
    if not alias:
        flash("Inicia sesión para eliminar el reto.")
        return redirect(url_for("index"))

    duelo = fotos_col.find_one({"_id": ObjectId(reto_id)})
    if not duelo:
        flash("Reto no encontrado.")
        return redirect(url_for("foto_hot"))

    if duelo["player"] != alias:
        flash("No tienes permiso para eliminar este reto.")
        return redirect(url_for("foto_hot"))

    # Devolver el token de plata al usuario
    usuarios_col.update_one({"alias": alias}, {"$inc": {"tokens_plata": 1}})

    # Eliminar de GridFS
    if "player_image" in duelo:
        try:
            fs.delete(ObjectId(duelo["player_image"]))
        except Exception as e:
            print(f"Error al eliminar de GridFS: {e}")

    fotos_col.delete_one({"_id": duelo["_id"]})
    flash("Reto eliminado y tokens devueltos.")
    return redirect(url_for("foto_hot"))
# ---------------------------------------------------------------------------
# Juego 2 – Susurra y Gana (audios sensuales)
# --------------------------------------------------------------------------
from bson.objectid import ObjectId
from flask import send_file
# Asegúrate de que 'fs' y 'app' estén definidos en tu código principal
from bson.objectid import ObjectId
from flask import send_file

# Asegúrate de que 'fs' y 'app' estén definidos en tu código principal

@app.route("/audio_hot", methods=["GET", "POST"])
def audio_hot():
    alias, tokens_oro, tokens_plata = get_user_and_saldo()
    if not alias or alias == "Invitado":
        flash("Inicia sesión para participar.")
        return redirect(url_for("login"))

    if request.method == "POST":
        file = request.files.get("audio")
        descripcion = request.form.get("descripcion", "").strip()

        if not file or file.filename == "":
            flash("No seleccionaste ningún archivo.")
            return redirect(url_for("audio_hot"))

        if not allowed_file(file.filename, ALLOWED_AUDIO):
            flash("Sube un audio válido (mp3, wav, ogg, m4a)")
            return redirect(url_for("audio_hot"))

        # ¡CORRECCIÓN! Usamos GridFS para guardar el archivo
        file_id = fs.put(file, filename=secure_filename(file.filename), content_type=file.content_type)
        
        audios_col.insert_one({
            "user": alias,
            "audio": str(file_id), # Guardamos el ID del archivo
            "descripcion": descripcion,
            "votos": 0,
            "reacciones": [],
            "fecha": datetime.now()
        })

        flash("Audio subido con éxito 🔥")
        return redirect(url_for("audio_hot"))

    # GET: Mostrar audios y datos
    pistas = list(audios_col.find().sort("fecha", -1))
    for pista in pistas:
        pista["comentarios"] = list(comentarios_col.find({"audio_id": str(pista["_id"])}))

    tokens_por_usuario = {
        u.get("alias"): u.get("tokens", 0)
        for u in usuarios_col.find({}, {"alias": 1, "tokens": 1})
    }

    historial = list(donaciones_col.find().sort("fecha", -1).limit(10))

    return render_template("audio_hot.html",
                            alias=alias,
                            tokens_oro=tokens_oro,
                            tokens_plata=tokens_plata,
                            pistas=pistas,
                            tokens_por_usuario=tokens_por_usuario,
                            historial=historial)


@app.route("/apoyar_audio", methods=["POST"])
def apoyar_audio():
    alias, tokens_oro, tokens_plata = get_user_and_saldo()
    if not alias:
        flash("Debes iniciar sesión para apoyar con tokens")
        return redirect(url_for("audio_hot"))

    autor = request.form.get("autor")
    if not autor or alias == autor:
        flash("No puedes apoyarte a ti mismo")
        return redirect(url_for("audio_hot"))

    user = usuarios_col.find_one({"alias": alias})
    if not user:
        flash("Usuario no encontrado")
        return redirect(url_for("audio_hot"))

    if user.get("tokens_oro", 0) >= 1:
        usuarios_col.update_one({"alias": alias}, {"$inc": {"tokens_oro": -1}})
        donaciones_col.insert_one({
            "de": alias,
            "para": autor,
            "fecha": datetime.now(),
            "tipo": "oro"
        })
        flash(f"Apoyaste a {autor} con 1 token de oro ✨")
    elif user.get("tokens_plata", 0) >= 1:
        usuarios_col.update_one({"alias": alias}, {"$inc": {"tokens_plata": -1}})
        donaciones_col.insert_one({
            "de": alias,
            "para": autor,
            "fecha": datetime.now(),
            "tipo": "plata"
        })
        flash(f"Apoyaste a {autor} con 1 token de plata 🤝")
    else:
        flash("No tienes tokens suficientes 💸")
    
    return redirect(url_for("audio_hot"))


@app.route("/votar_audio/<audio_id>", methods=["POST"])
def votar_audio(audio_id):
    alias = session.get("alias")
    if not alias:
        flash("Inicia sesión para votar")
        return redirect(url_for("login"))

    audios_col.update_one({"_id": ObjectId(audio_id)}, {"$inc": {"votos": 1}})
    flash("✅ Voto registrado")
    return redirect(url_for("audio_hot"))

@app.route("/comentar_audio/<audio_id>", methods=["POST"])
def comentar_audio(audio_id):
    alias = session.get("alias")
    comentario = request.form.get("comentario", "").strip()
    if alias and comentario:
        comentarios_col.insert_one({
            "audio_id": audio_id,
            "usuario": alias,
            "comentario": comentario,
            "fecha": datetime.now()
        })
        flash("💬 Comentario agregado")
    else:
        flash("❌ Comentario vacío")
    return redirect(url_for("audio_hot"))

@app.route("/reaccion_audio/<audio_id>/<tipo>", methods=["POST"])
def reaccion_audio(audio_id, tipo):
    alias = session.get("alias")
    if not alias:
        flash("Inicia sesión para reaccionar")
        return redirect(url_for("login"))

    existe = reacciones_col.find_one({
        "audio_id": audio_id,
        "usuario": alias,
        "tipo": tipo
    })

    if existe:
        flash("Ya reaccionaste con ese tipo a este audio")
    else:
        reacciones_col.insert_one({
            "audio_id": audio_id,
            "usuario": alias,
            "tipo": tipo,
            "fecha": datetime.now()
        })
        flash("🔁 Reacción registrada")

    return redirect(url_for("audio_hot"))

@app.route("/audio_eliminar_reto/<audio_id>", methods=["POST"])
def audio_hot_eliminar_reto(audio_id):
    alias, _, _ = get_user_and_saldo()
    if not alias:
        flash("Inicia sesión para eliminar el audio")
        return redirect(url_for("audio_hot"))

    pista = audios_col.find_one({"_id": ObjectId(audio_id)})
    if not pista:
        flash("Audio no encontrado")
        return redirect(url_for("audio_hot"))

    if pista["user"] != alias:
        flash("Solo puedes eliminar tus propios audios")
        return redirect(url_for("audio_hot"))

    # Eliminamos de GridFS
    if "audio" in pista:
        try:
            fs.delete(ObjectId(pista["audio"]))
        except Exception as e:
            print(f"Error al eliminar de GridFS: {e}")

    audios_col.delete_one({"_id": ObjectId(audio_id)})
    flash("Audio eliminado correctamente")
    return redirect(url_for("audio_hot"))
# ---------------------------------------------------------------------------
# Más rutas (lanzar retos, votar, etc.)
# ---------------------------------------------------------------------------
@app.route("/jugar")
def jugar():
    alias, tokens_oro, tokens_plata = get_user_and_saldo()
    if not alias:
        flash("Debes iniciar sesión para jugar")
        return redirect(url_for("index"))
    
    retos = list(retos_col.find({"estado": "pendiente"}))
    return render_template("jugar.html", saldo=tokens_oro, saldo_plata=tokens_plata, retos=retos)

@app.route("/lanzar", methods=["GET", "POST"])
def lanzar():
    alias, tokens_oro, tokens_plata = get_user_and_saldo()
    if not alias:
        flash("Debes iniciar sesión para lanzar retos")
        return redirect(url_for("index"))

    if request.method == "POST":
        pregunta = request.form.get("pregunta")
        retado = request.form.get("retado")
        modo = request.form.get("modo")

        try:
            tokens = int(request.form.get("tokens", 1))
        except ValueError:
            tokens = 1

        if not pregunta or not retado or not modo:
            flash("Completa todos los campos para lanzar un reto")
            return redirect(url_for("lanzar"))

        if tokens < 1 or tokens > tokens_oro:
            flash("No tienes tokens oro suficientes")
            return redirect(url_for("lanzar"))

        retos_col.insert_one({
            "player": alias,
            "pregunta": pregunta,
            "retado": retado,
            "modo": modo,
            "tokens": tokens,
            "fecha": datetime.now(),
            "estado": "pendiente",
            "votos": []
        })

        usuarios_col.update_one({"alias": alias}, {"$inc": {"tokens_oro": -tokens}})

        notificacion = {
            "tipo": "reto_recibido",
            "mensaje": f"Has sido retado por {alias} con la pregunta: '{pregunta}'",
            "leido": False,
            "fecha": datetime.utcnow()
        }

        usuarios_col.update_one(
            {"alias": retado},
            {"$push": {"notificaciones": notificacion}}
        )

        flash("Reto lanzado correctamente 🔥")
        return redirect(url_for("lanzar"))

    retos = list(retos_col.find({"player": alias}).sort("fecha", -1))
    retos_recibidos = list(retos_col.find({"retado": alias}).sort("fecha", -1))
    retos_publicos = list(retos_col.find({
        "modo": "publico", "estado": "pendiente",
        "$or": [
            {"player": {"$ne": alias}},
            {"retado": {"$ne": alias}}
        ]
    }).sort("fecha", -1))

    usuario = usuarios_col.find_one({"alias": alias})
    notificaciones = [n for n in usuario.get("notificaciones", []) if not n.get("leido", False)]
    retos_recibidos_pendientes = any(r["estado"] == "pendiente" for r in retos_recibidos)

    return render_template("lanzar.html", alias=alias, saldo=tokens_oro,
                           retos=retos, retos_recibidos=retos_recibidos,
                           retos_publicos=retos_publicos,
                           notificaciones=notificaciones,
                           retos_recibidos_pendientes=retos_recibidos_pendientes)

@app.route("/eliminar_reto/<reto_id>", methods=["POST"])
def eliminar_reto(reto_id):
    alias, tokens_oro, _ = get_user_and_saldo()
    reto = retos_col.find_one({"_id": ObjectId(reto_id)})

    if reto and reto["player"] == alias and reto["estado"] == "pendiente":
        retos_col.delete_one({"_id": ObjectId(reto_id)})
        usuarios_col.update_one({"alias": alias}, {"$inc": {"tokens_oro": reto["tokens"]}})
        flash("Reto eliminado y tokens devueltos", "success")
    else:
        flash("No puedes eliminar este reto", "error")

    return redirect(url_for("lanzar"))

@app.route("/votar_reto/<reto_id>", methods=["POST"])
def votar_reto(reto_id):
    alias, tokens_oro, _ = get_user_and_saldo()
    if not alias:
        flash("Debes iniciar sesión para votar")
        return redirect(url_for("index"))

    reto = retos_col.find_one({"_id": ObjectId(reto_id)})
    if not reto:
        flash("Reto no encontrado")
        return redirect(url_for("lanzar"))

    if reto["player"] == alias or reto["retado"] == alias:
        flash("No puedes votar en tu propio reto")
        return redirect(url_for("lanzar"))

    ganador = request.form.get("ganador")
    if ganador not in [reto["player"], reto["retado"]]:
        flash("Ganador inválido")
        return redirect(url_for("lanzar"))

    votos = reto.get("votos", [])
    if any(v["alias"] == alias for v in votos):
        flash("Ya has votado en este reto")
        return redirect(url_for("lanzar"))

    votos.append({"alias": alias, "ganador": ganador})
    retos_col.update_one({"_id": reto["_id"]}, {"$set": {"votos": votos}})

    conteo = {reto["player"]: 0, reto["retado"]: 0}
    for v in votos:
        conteo[v["ganador"]] += 1

    if len(votos) >= 3:
        if conteo[reto["player"]] > conteo[reto["retado"]]:
            ganador_final = reto["player"]
        elif conteo[reto["retado"]] > conteo[reto["player"]]:
            ganador_final = reto["retado"]
        else:
            ganador_final = None

        if ganador_final:
            usuarios_col.update_one(
                {"alias": ganador_final},
                {"$inc": {"tokens_oro": reto["tokens"] * 2}}
            )
            retos_col.update_one(
                {"_id": reto["_id"]},
                {"$set": {"estado": f"ganador: {ganador_final}"}}
            )
        else:
            usuarios_col.update_one({"alias": reto["player"]}, {"$inc": {"tokens_oro": reto["tokens"]}})
            usuarios_col.update_one({"alias": reto["retado"]}, {"$inc": {"tokens_oro": reto["tokens"]}})
            retos_col.update_one({"_id": reto["_id"]}, {"$set": {"estado": "empate"}})

    flash("Tu voto ha sido registrado ✅")
    return redirect(url_for("lanzar"))

@app.route('/aceptar_reto/<reto_id>', methods=['POST'])
def aceptar_reto_con_id(reto_id):
    alias, tokens_oro, _ = get_user_and_saldo()
    if not alias:
        flash("Debes iniciar sesión para aceptar retos")
        return redirect(url_for("index"))
    reto = retos_col.find_one({"_id": ObjectId(reto_id)})
    if not reto:
        flash("Reto no encontrado")
        return redirect(url_for("lanzar"))

    if reto["retado"] != alias:
        flash("No tienes permiso para aceptar este reto")
        return redirect(url_for("lanzar"))

    if tokens_oro < reto["tokens"]:
        flash("No tienes tokens oro suficientes para aceptar este reto")
        return redirect(url_for("lanzar"))

    usuarios_col.update_one({"alias": alias}, {"$inc": {"tokens_oro": -reto["tokens"]}})
    flash("Reto aceptado. ¡Ahora pueden comenzar!", "success")
    return redirect(url_for("lanzar"))

@app.route("/reclamar_victoria/<reto_id>", methods=["POST"])
def reclamar_victoria(reto_id):
    alias, _, _ = get_user_and_saldo()
    reto = retos_col.find_one({"_id": ObjectId(reto_id)})

    if not reto:
        flash("Reto no encontrado", "error")
        return redirect(url_for("lanzar"))

    if f"ganador: {alias}" != reto.get("estado", ""):
        flash("Solo el ganador puede reclamar la victoria", "error")
        return redirect(url_for("lanzar"))

    flash("🎉 ¡Felicidades! Has reclamado tu victoria. ¡Disfruta tus tokens!", "success")
    return redirect(url_for("lanzar"))
# ---------------------------------------------------------------------------
import os
import time
import hashlib
import uuid
import re
from flask import Flask, render_template, session, redirect, url_for, flash, request, send_file, abort
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from collections import Counter
from bson.objectid import ObjectId
import pusher
from dotenv import load_dotenv
from gridfs import GridFSBucket, NoFile
from io import BytesIO
from random import choice  # <--- Esta es la línea que faltaba
import base64

# Suponiendo que estas variables están definidas en tu app principal
# app = Flask(__name__)
# usuarios_col = db.usuarios
# confesiones_col = db.confesiones
# mensajes_col = db.mensajes
# fs = GridFSBucket(db) # ¡Importante! Asegúrate de tener esto

ALLOWED_AVATAR = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_CHAT = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav', 'ogg', 'm4a'}
ALLOWED_IMAGE = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Asumo que esta función existe en otro lugar de tu código
# def get_user_and_saldo():
#     ...

@app.route("/hot_roulette")
def hot_roulette():
    alias, _, _ = get_user_and_saldo()
    if not alias:
        flash("Debes iniciar sesión para jugar")
        return redirect(url_for("login"))

    retos = [
        "Besa a alguien en la mejilla",
        "Envía un emoji sugerente a tu crush",
        "Cuenta tu fantasía más loca",
        "Haz una imitación sexy",
        "Verdad o reto candente",
        "Envía un piropo atrevido",
        "Haz un mini striptease (ropa permitida 😅)",
        "Confiesa tu guilty pleasure",
        "Haz una mirada seductora",
        "Haz un reto que el grupo elija 🔥",
        "Envía un audio sexy por WhatsApp",
        "Baila sensualmente por 30 segundos",
        "Escribe un poema erótico en 2 minutos",
        "Manda la foto de tu mejor ángulo",
        "Haz una pose de modelo seductora",
    ]

    publicaciones = list(publicaciones_col.find().sort("fecha", -1).limit(10))
    return render_template(
        "hot_roulette.html",
        retos=retos,
        publicaciones=publicaciones,
        alias=alias
    )

@app.route("/hot_roulette/girar", methods=["POST"])
def hot_roulette_girar():
    alias, _, _ = get_user_and_saldo()
    if not alias:
        return jsonify({"error": "Debes iniciar sesión"}), 401
    
    retos = [
        "Besa a alguien en la mejilla",
        "Envía un emoji sugerente a tu crush",
        "Cuenta tu fantasía más loca",
        "Haz una imitación sexy",
        "Verdad o reto candente",
        "Envía un piropo atrevido",
        "Haz un mini striptease (ropa permitida 😅)",
        "Confiesa tu guilty pleasure",
        "Haz una mirada seductora",
        "Haz un reto que el grupo elija 🔥",
        "Envía un audio sexy por WhatsApp",
        "Baila sensualmente por 30 segundos",
        "Escribe un poema erótico en 2 minutos",
        "Manda la foto de tu mejor ángulo",
        "Haz una pose de modelo seductora",
    ]
    reto = choice(retos)
    return jsonify({"reto": reto})

@app.route("/hot_roulette/publicar_reto", methods=["POST"])
def publicar_reto():
    alias, _, _ = get_user_and_saldo()
    if not alias:
        return jsonify(success=False, message="Debes iniciar sesión"), 401
    data = request.get_json()
    reto = data.get("reto", "").strip()
    if not reto:
        return jsonify(success=False, message="Reto vacío")
    publicaciones_col.insert_one({
        "usuario": alias,
        "reto": reto,
        "fecha": datetime.now(),
        "likes": 0,
        "dislikes": 0
    })
    return jsonify(success=True, message="Reto publicado")

@app.route("/hot_roulette/reaccion", methods=["POST"])
def reaccion_roulette():
    alias, _, _ = get_user_and_saldo()
    if not alias:
        return jsonify(success=False, message="Debes iniciar sesión"), 401
    data = request.get_json()
    reto_id = data.get("retoId")
    tipo = data.get("tipo")
    if tipo not in ["like", "dislike"]:
        return jsonify(success=False, message="Reacción no válida"), 400
    update_field = "likes" if tipo == "like" else "dislikes"
    publicaciones_col.update_one(
        {"_id": ObjectId(reto_id)},
        {"$inc": {update_field: 1}}
    )
    return jsonify(success=True)

# 💡 CORRECCIÓN: Ruta renombrada a aceptar_reto_roulette para evitar conflicto
@app.route("/hot_roulette/aceptar_reto_roulette", methods=["POST"])
def aceptar_reto_roulette():
    alias, _, _ = get_user_and_saldo()
    if not alias:
        return jsonify(success=False, message="Debes iniciar sesión"), 401
    data = request.get_json()
    publicaciones_col.update_one(
        {"_id": ObjectId(data["retoId"])},
        {"$set": {"aceptado_por": alias, "fecha_aceptado": datetime.now()}}
    )
    return jsonify(success=True, message="Reto aceptado")

@app.route("/hot_roulette/cumplir_reto", methods=["POST"])
def cumplir_reto():
    alias, _, _ = get_user_and_saldo()
    data = request.get_json()
    imagen_data = data.get("imagen")
    reto_id = data.get("retoId")
    if not alias:
        return jsonify(success=False, message="Debes iniciar sesión"), 401
    if not imagen_data:
        return jsonify(success=False, message="Imagen no encontrada")
    try:
        header, b64 = imagen_data.split(",", 1)
        ext = header.split("/")[1].split(";")[0]
        if ext.lower() not in ALLOWED_IMAGE:
            return jsonify(success=False, message="Formato de imagen no permitido"), 400
        
        # ¡CORRECCIÓN! Usamos GridFS para guardar la imagen
        file_id = fs.put(base64.b64decode(b64), filename=f"{uuid.uuid4().hex}.{ext}", content_type=f"image/{ext}")
        ruta_relativa = str(file_id)

        publicaciones_col.update_one(
            {"_id": ObjectId(reto_id)},
            {"$set": {
                "imagen_cumplimiento": ruta_relativa,
                "cumplido_por": alias,
                "fecha_cumplido": datetime.now()
            }}
        )
        return jsonify(success=True, message="Reto cumplido registrado")
    except Exception as e:
        return jsonify(success=False, message=f"Error: {str(e)}")

@app.route("/hot_roulette/eliminar_cumplido", methods=["POST"])
def eliminar_cumplido():
    alias, _, _ = get_user_and_saldo()
    if not alias:
        return jsonify(success=False, message="Debes iniciar sesión"), 401
    data = request.get_json()
    reto_id = data.get("retoId")
    if not reto_id:
        return jsonify(success=False, message="ID del reto no proporcionado"), 400
    publicacion = publicaciones_col.find_one({"_id": ObjectId(reto_id)})
    # ... el resto del código parece estar incompleto aquí
# ---------------------------------------------------------------------------
# Más rutas (lanzar retos, votar, etc.)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

# 📸 Página principal de HotCopy
# Funciones de utilidad
# 📸 Página principal de HotCopy
# Funciones de utilidad
# ---------------------------------------------------------------------------
# Juego 4 – HotCopy
# --------------------------------------------------------------------------
def asegurar_reacciones(fotos):
    """Asegura que cada foto tenga reacciones inicializadas"""
    for foto in fotos:
        if "reacciones" not in foto or not isinstance(foto["reacciones"], dict):
            foto["reacciones"] = {"🔥": 0, "😍": 0, "😂": 0, "😮": 0}
    return fotos

@app.route("/hotcopy", methods=["GET", "POST"])
def hotcopy():
    alias, tokens_oro, tokens_plata = get_user_and_saldo()
    if not alias:
        flash("Inicia sesión para participar.")
        return redirect(url_for("login"))

    if request.method == "POST":
        original_id = request.form.get("original_id") or None
        file = request.files.get("imagen")
        
        if not file or file.filename == "" or not allowed_file(file.filename, ALLOWED_IMAGE):
            flash("Sube una imagen válida (png, jpg, jpeg, gif).")
            return redirect(url_for("hotcopy"))
        
        # 💡 Corrección: Usamos GridFS para guardar el archivo
        file_id = fs.put(file, filename=secure_filename(file.filename), content_type=file.content_type)

        hotcopy_col.insert_one({
            "user": alias,
            "original_id": ObjectId(original_id) if original_id else None,
            "image": str(file_id), # Guardamos el ID del archivo
            "votos": 0,
            "reacciones": {"🔥": 0, "😍": 0, "😂": 0, "😮": 0},
            "fecha": datetime.now(),
            "comentarios": [],
        })
        flash("✅ Tu foto ha sido subida exitosamente.")
        return redirect(url_for("hotcopy"))

    originals_cursor = hotcopy_col.find({"original_id": None}).sort("fecha", -1)
    originals = []
    for original in originals_cursor:
        original = asegurar_reacciones([original])[0]
        imitations = list(hotcopy_col.find({"original_id": original["_id"]}).sort("fecha", 1))
        imitations = asegurar_reacciones(imitations)
        original["imitations"] = imitations
        originals.append(original)
        
    saldo = tokens_oro + tokens_plata
    
    return render_template("hotcopy.html", alias=alias, saldo=saldo, originals=originals)

@app.route("/votar/<foto_id>", methods=["POST"])
def votar(foto_id):
    alias, tokens_oro, tokens_plata = get_user_and_saldo()
    if not alias:
        return jsonify(success=False, message="Debes iniciar sesión para votar.")
    
    if tokens_oro < 1:
        return jsonify(success=False, message="No tienes tokens de oro suficientes para votar.")
    
    usuarios_col.update_one({"alias": alias}, {"$inc": {"tokens_oro": -1}})
    hotcopy_col.update_one({"_id": ObjectId(foto_id)}, {"$inc": {"votos": 1}})
    
    return jsonify(success=True, message="✅ Voto registrado correctamente y se descontó 1 token oro.")

@app.route("/reaccion/<foto_id>/<tipo>", methods=["POST"])
def reaccion(foto_id, tipo):
    if tipo not in ["🔥", "😍", "😂", "😮"]:
        return jsonify(success=False, message="⚠️ Reacción inválida.")
    hotcopy_col.update_one({"_id": ObjectId(foto_id)}, {"$inc": {f"reacciones.{tipo}": 1}})
    return jsonify(success=True, message=f"Reacción {tipo} agregada 👍")

@app.route("/comentar_hotcopy", methods=["POST"])
def comentar_hotcopy():
    data = request.get_json()
    foto_id = data.get("id")
    texto = data.get("texto")
    alias = session.get("alias")

    if not alias or not foto_id or not texto:
        return jsonify(success=False, message="❌ Datos incompletos o no autenticado.")

    comentario = {"usuario": alias, "texto": texto}

    hotcopy_col.update_one(
        {"_id": ObjectId(foto_id)},
        {"$push": {"comentarios": comentario}}
    )
    return jsonify(success=True, message="✅ Comentario guardado.")

@app.route("/hotcopy/eliminar/<foto_id>", methods=["POST"])
def eliminar_hotcopy(foto_id):
    alias, _, _ = get_user_and_saldo()
    if not alias:
        flash("Debes iniciar sesión para eliminar fotos.")
        return redirect(url_for("hotcopy"))

    foto = hotcopy_col.find_one({"_id": ObjectId(foto_id)})
    if not foto:
        flash("Foto no encontrada.")
        return redirect(url_for("hotcopy"))
    
    if foto["user"] != alias:
        flash("No puedes eliminar fotos que no son tuyas.")
        return redirect(url_for("hotcopy"))
    
    # 💡 Corrección: Eliminamos de GridFS
    try:
        if "image" in foto:
            fs.delete(ObjectId(foto["image"]))
    except Exception as e:
        print(f"Error al eliminar de GridFS: {e}")
    
    # Eliminar de la base de datos
    hotcopy_col.delete_one({"_id": ObjectId(foto_id)})
    
    # Si la foto eliminada era una original, también se eliminan sus imitaciones
    if "original_id" not in foto:
        imitations_to_delete = hotcopy_col.find({"original_id": ObjectId(foto_id)})
        for imitation in imitations_to_delete:
            try:
                fs.delete(ObjectId(imitation["image"]))
            except Exception as e:
                print(f"Error al eliminar la imitación de GridFS: {e}")
        hotcopy_col.delete_many({"original_id": ObjectId(foto_id)})
    
    flash("Foto eliminada correctamente.")
    return redirect(url_for("hotcopy"))

# ---------------------------------------------------------------------------
# – ¿Quién lo dijo adiviona ?
# ---------------------------------------------------------------------------
# Ruta para agregar comentario
from flask import request, jsonify, flash, redirect, url_for, render_template, session
from datetime import datetime
from bson import ObjectId

# --- Suponiendo que estas variables están definidas en tu app principal ---
# app = Flask(__name__)
# adivina_col = db.adivina
# get_user_and_saldo = ...

@app.route("/adivina", methods=["GET"])
def adivina():
    alias, _, _ = get_user_and_saldo()
    if not alias:
        flash("Inicia sesión")
        return redirect(url_for("index"))

    textos = list(adivina_col.find().sort("fecha", -1))
    return render_template("adivina.html", textos=textos, alias=alias)

@app.route("/adivina/agregar", methods=["POST"])
def adivina_agregar():
    alias, _, _ = get_user_and_saldo()
    if not alias:
        return jsonify({"success": False, "message": "Debes iniciar sesión"}), 401

    data = request.get_json()
    texto = data.get("texto", "").strip()

    if not texto:
        return jsonify({"success": False, "message": "Escribe algo para agregar"}), 400

    adivina_col.insert_one({
        "user": alias,
        "texto": texto,
        "fecha": datetime.now(),
        "comentarios": [],
        # ✅ Reacciones inicializadas con emojis, consistente con la ruta de reaccionar
        "reacciones": {"👍": 0, "❤️": 0, "😂": 0, "😮": 0, "👎": 0} 
    })

    return jsonify({"success": True, "message": "Confesión añadida al juego 🕵️"})


@app.route("/adivina/comentar", methods=["POST"])
def adivina_comentar():
    alias, _, _ = get_user_and_saldo()
    if not alias:
        return jsonify({"success": False, "message": "Debes iniciar sesión"}), 401
    
    data = request.get_json()
    texto = data.get("texto", "").strip()
    conf_id = data.get("confesionId")

    if not texto or not conf_id:
        return jsonify({"success": False, "message": "Faltan datos"}), 400

    comentario = {
        "user": alias,
        "texto": texto,
        "fecha": datetime.now()
    }

    res = adivina_col.update_one(
        {"_id": ObjectId(conf_id)},
        {"$push": {"comentarios": comentario}}
    )

    if res.modified_count == 1:
        return jsonify({"success": True, "message": "Comentario agregado"})
    else:
        return jsonify({"success": False, "message": "Error al agregar comentario"})

# Reaccionar
@app.route("/adivina/reaccionar", methods=["POST"])
def adivina_reaccionar():
    alias, _, _ = get_user_and_saldo()
    if not alias:
        return jsonify({"success": False, "message": "Debes iniciar sesión"}), 401
    
    data = request.get_json()
    conf_id = data.get("confesionId")
    tipo = data.get("tipo")

    # ✅ Validación con los mismos emojis inicializados
    if not conf_id or tipo not in ["👍", "❤️", "😂", "😮", "👎"]:
        return jsonify({"success": False, "message": "Datos de reacción inválidos"}), 400

    # Incrementar contador atómico
    res = adivina_col.update_one(
        {"_id": ObjectId(conf_id)},
        {"$inc": {f"reacciones.{tipo}": 1}}
    )

    if res.modified_count == 1:
        return jsonify({"success": True, "message": "Reacción registrada"})
    else:
        return jsonify({"success": False, "message": "Error al reaccionar"})

# Rutas de confesiones
# Rutas de confesiones
from flask import Flask, request, session, redirect, url_for, render_template, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime
from uuid import uuid4
from bson.objectid import ObjectId
import os
import random
from pymongo import MongoClient
# Es necesario importar GridFSBucket
from gridfs import GridFSBucket

# --- Suponiendo que estas variables están definidas en tu app principal ---
# app = Flask(__name__)
# client = MongoClient(...)
# db = client.hotquiz
# fs = GridFSBucket(db) # ¡Importante! Asegúrate de tener esto
# confesiones_col = db.confesiones
# get_user = ...

# Extensiones permitidas (ahora usadas para validación)
ALLOWED_IMG = {"png", "jpg", "jpeg", "gif"}
ALLOWED_AUDIO = {"mp3", "wav", "ogg"}
ALLOWED_MEDIA = ALLOWED_IMG.union(ALLOWED_AUDIO)

def get_user():
    return session.get("alias", "Anónimo")

def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions

@app.route("/confesiones", methods=["GET", "POST"])
def confesiones():
    alias = get_user()
    if request.method == "POST":
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            return jsonify(success=False, message="Debe usarse AJAX")
        texto = request.form.get("texto", "").strip()
        color = request.form.get("color", "#111")
        file = request.files.get("media")
        imagen, audio = None, None

        if file and allowed_file(file.filename, ALLOWED_MEDIA):
            # 💡 Corrección: Usamos GridFS para guardar el archivo
            file_id = fs.put(file, filename=secure_filename(file.filename), content_type=file.content_type)
            ext = file.filename.rsplit(".", 1)[1].lower()
            if ext in ALLOWED_AUDIO:
                audio = str(file_id)
            elif ext in ALLOWED_IMG:
                imagen = str(file_id)

        conf = {
            "usuario": alias,
            "texto": texto,
            "color": color,
            "fecha": datetime.now(),
            "imagen": imagen,
            "audio": audio,
            "reacciones": {"❤️": 0, "🔥": 0, "😂": 0, "😮": 0},
            "comentarios": [],
        }
        inserted = confesiones_col.insert_one(conf)
        conf["_id"] = str(inserted.inserted_id)
        html_card = render_template("confesiones_card.html", conf=conf, alias=alias)
        return jsonify(success=True, html=html_card)

    todas = list(confesiones_col.find().sort("fecha", -1).limit(20))
    for c in todas:
        c["_id"] = str(c["_id"])
    return render_template("confesiones.html", alias=alias, confesiones=todas)

@app.route("/reaccion_conf/<id>/<tipo>", methods=["POST"])
def reaccion_conf(id, tipo):
    if tipo not in ["❤️", "🔥", "😂", "😮"]:
        return jsonify(success=False)
    confesiones_col.update_one({"_id": ObjectId(id)}, {"$inc": {f"reacciones.{tipo}": 1}})
    return jsonify(success=True)

@app.route("/comentar_conf", methods=["POST"])
def comentar_conf():
    data = request.get_json()
    conf_id = data.get("id")
    texto = data.get("texto")
    alias = get_user()
    if not conf_id or not texto:
        return jsonify(success=False)
    comentario = {
        "usuario": alias,
        "texto": texto,
        "fecha": datetime.now()
    }
    confesiones_col.update_one({"_id": ObjectId(conf_id)}, {"$push": {"comentarios": comentario}})
    comentario["fecha"] = comentario["fecha"].isoformat()
    return jsonify(success=True, comentario=comentario)

@app.route("/eliminar_conf/<id>", methods=["POST"])
def eliminar_conf(id):
    alias = get_user()
    conf = confesiones_col.find_one({"_id": ObjectId(id)})
    if conf and conf.get("usuario") == alias:
        # 💡 Corrección: Eliminamos de GridFS si existe imagen o audio
        try:
            if conf.get("imagen"):
                fs.delete(ObjectId(conf["imagen"]))
            if conf.get("audio"):
                fs.delete(ObjectId(conf["audio"]))
        except Exception as e:
            print(f"Error al eliminar archivo de GridFS: {e}")
        
        confesiones_col.delete_one({"_id": ObjectId(id)})
        return jsonify(success=True)
    return jsonify(success=False, message="No tienes permiso para eliminar esta confesión.")

@app.route("/confesiones/filtro/<tipo>")
def confesiones_filtro(tipo):
    alias = get_user()
    if tipo == "populares":
        confesiones = list(confesiones_col.find().sort("reacciones.🔥", -1).limit(20))
    elif tipo == "aleatorio":
        confesiones = list(confesiones_col.aggregate([{"$sample": {"size": 1}}]))
    else:
        confesiones = list(confesiones_col.find().sort("fecha", -1).limit(20))
    for c in confesiones:
        c["_id"] = str(c["_id"])
    html = "".join(render_template("confesiones_card.html", conf=c, alias=alias) for c in confesiones)
    return jsonify({"html": html, "count": len(confesiones)})

@app.route("/confesiones_scroll")
def confesiones_scroll():
    try:
        offset = int(request.args.get("offset", 0))
    except ValueError:
        offset = 0
    limite = 10
    confesiones = list(confesiones_col.find().sort("fecha", -1).skip(offset).limit(limite))
    for c in confesiones:
        c["_id"] = str(c["_id"])
    html_cards = "".join(render_template("confesiones_card.html", conf=c, alias=get_user()) for c in confesiones)
    return jsonify({"html": html_cards, "count": len(confesiones)})
# ---------------------------------------------------------------------------
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, send_file
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from uuid import uuid4
from datetime import datetime
from pymongo import MongoClient
from gridfs import GridFSBucket, NoFile
import os
import certifi
from io import BytesIO


def get_user_and_saldo():
    alias = session.get("alias")
    if not alias:
        return None, 0, 0
    user = usuarios_col.find_one({"alias": alias})
    if user:
        return alias, int(user.get("tokens_oro", 0)), int(user.get("tokens_plata", 0))
    return None, 0, 0


@app.route('/hot_shorts', methods=['GET', 'POST'])
def hot_shorts():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        file = request.files.get('archivo')
        alias = session.get("alias")

        if not alias:
            flash("Debes iniciar sesión para subir videos.", "error")
            return redirect(url_for('hot_shorts'))

        if not file:
            flash("No se envió archivo.", "error")
            return redirect(url_for('hot_shorts'))
        
        # Guardamos el archivo directamente en GridFS
        file_id = fs.put(file, filename=secure_filename(file.filename), content_type=file.content_type)
        
        reel = {
            "usuario": alias,
            "titulo": titulo,
            "archivo_id": str(file_id),  # Guardamos el ID del archivo en GridFS
            "fecha": datetime.utcnow(),
            "likes": 0,
            "fuegos": 0,
            "tokens_recibidos": 0,
            "comentarios": []
        }
        hotreels_col.insert_one(reel)
        flash("Reel subido con éxito!", "success")
        return redirect(url_for('hot_shorts'))
    
    reels = list(hotreels_col.find().sort("fecha", -1).limit(5))
    return render_template('hot_shorts.html', reels=reels)

@app.route('/hot_shorts/video/<file_id>')
def stream_video(file_id):
    try:
        file = fs.get(ObjectId(file_id))
        return send_file(BytesIO(file.read()), mimetype=file.content_type)
    except NoFile:
        return "Archivo no encontrado", 404
    except Exception as e:
        return f"Error al servir el archivo: {e}", 500

@app.route('/hot_shorts/load_more', methods=['GET'])
def load_more_reels():
    skip = int(request.args.get('skip', 0))
    limit = int(request.args.get('limit', 5))
    reels = list(hotreels_col.find().sort("fecha", -1).skip(skip).limit(limit))
    for r in reels:
        r["_id"] = str(r["_id"])
    return jsonify(reels)

@app.route('/reel/<reel_id>/like', methods=['POST'])
def like_reel(reel_id):
    hotreels_col.update_one({"_id": ObjectId(reel_id)}, {"$inc": {"likes": 1}})
    return jsonify(success=True)

@app.route('/reel/<reel_id>/fire', methods=['POST'])
def fire_reel(reel_id):
    hotreels_col.update_one({"_id": ObjectId(reel_id)}, {"$inc": {"fuegos": 1}})
    return jsonify(success=True)

@app.route('/reel/<reel_id>/regalar', methods=['POST'])
def regalar_reel(reel_id):
    alias, tokens_oro, tokens_plata = get_user_and_saldo()
    if not alias:
        return jsonify(success=False, message="Debes iniciar sesión para regalar"), 401

    reel = hotreels_col.find_one({"_id": ObjectId(reel_id)})
    if not reel:
        return jsonify(success=False, message="Reel no encontrado"), 404

    autor = reel.get("usuario")
    if not autor:
        return jsonify(success=False, message="Autor del reel no encontrado"), 404

    if alias == autor:
        return jsonify(success=False, message="No puedes regalarte a ti mismo"), 403

    if tokens_oro < 1:
        return jsonify(success=False, message="No tienes tokens de oro suficientes"), 403

    usuarios_col.update_one({"alias": alias}, {"$inc": {"tokens_oro": -1}})
    usuarios_col.update_one({"alias": autor}, {"$inc": {"tokens_oro": 1}})
    hotreels_col.update_one({"_id": ObjectId(reel_id)}, {"$inc": {"tokens_recibidos": 1}})
    
    donaciones_col.insert_one({
        "de": alias,
        "para": autor,
        "reel_id": str(reel_id),
        "fecha": datetime.now(),
        "tipo": "oro"
    })

    return jsonify(success=True, message=f"Le regalaste 1 token de oro a {autor}")

@app.route('/reel/<reel_id>/comentar', methods=['POST'])
def comentar_reel(reel_id):
    alias = session.get("alias")
    if not alias:
        return jsonify(success=False, message="Debes iniciar sesión para comentar"), 401
    
    texto = request.json.get("texto")
    comentario = {
        "alias": alias,
        "texto": texto,
        "fecha": datetime.utcnow()
    }
    hotreels_col.update_one({"_id": ObjectId(reel_id)}, {"$push": {"comentarios": comentario}})
    return jsonify(success=True)
@app.route('/eliminar_shorts/<reel_id>', methods=['POST'])
def eliminar_shorts(reel_id):
    alias = session.get("alias")
    if not alias:
        return jsonify(success=False, message="Debes iniciar sesión para eliminar videos"), 401

    try:
        reel_object_id = ObjectId(reel_id)
        reel = hotreels_col.find_one({"_id": reel_object_id})

        if not reel:
            return jsonify(success=False, message="Reel no encontrado"), 404

        # Solo puede eliminar el dueño o un administrador
        if reel.get("usuario") != alias and alias != "admin":
            return jsonify(success=False, message="No tienes permisos para eliminar este video"), 403

        # Borrar video de GridFS si existe
        if reel.get("archivo_id"):
            try:
                fs.delete(ObjectId(reel["archivo_id"]))
            except Exception as e:
                print(f"⚠ No se pudo borrar el archivo de GridFS: {e}")

        # Borrar documento en MongoDB
        hotreels_col.delete_one({"_id": reel_object_id})

        return jsonify(success=True, message="Video eliminado con éxito")
    except Exception as e:
        return jsonify(success=False, message=f"Error al eliminar el video: {e}"), 500


    
# app.py fragmento del código
# Comprar tokens vista básica
from flask import render_template, redirect, url_for, session, flash, request
from werkzeug.utils import secure_filename
from datetime import datetime
from uuid import uuid4
from bson.objectid import ObjectId
import os
# Se requiere importar GridFSBucket
from gridfs import GridFSBucket

# Define la carpeta donde se guardarán los comprobantes
UPLOAD_FOLDER_COMPROBANTES = 'static/comprobantes'
os.makedirs(UPLOAD_FOLDER_COMPROBANTES, exist_ok=True)
app.config['UPLOAD_FOLDER_COMPROBANTES'] = UPLOAD_FOLDER_COMPROBANTES

# Comprar tokens (vista básica)
# ---------------------------------------------------------------------------
# app.py (fragmento del código)

# Suponiendo que estas variables están definidas en tu archivo principal de la app
# app = Flask(__name__)
# usuarios_col = db.users
# compras_col = db.compras
# fs = GridFSBucket(db) # ¡Importante! Asegúrate de tener esto

# Comprar tokens (vista básica)
# ---------------------------------------------------------------------------
@app.route('/tokens')
def tokens():
    alias = session.get('alias')
    if not alias:
        flash("Debes iniciar sesión para comprar tokens")
        return redirect(url_for('index'))
    
    # Obtener el saldo actual del usuario
    usuario = usuarios_col.find_one({'alias': alias})
    saldo_tokens = usuario.get('tokens_oro', 0) if usuario else 0

    return render_template('tokens.html', saldo=saldo_tokens)

@app.route('/comprar_tokens', methods=['GET', 'POST'])
def comprar_tokens():
    alias = session.get('alias')
    if not alias:
        flash('Debes iniciar sesión para comprar tokens.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        cantidad = int(request.form.get('cantidad'))
        correo = request.form.get('correo')
        numero_whatsapp = request.form.get('numero_whatsapp')
        comprobante_file = request.files.get('comprobante')

        if not correo or not comprobante_file or comprobante_file.filename == '':
            flash("Todos los campos son obligatorios.")
            return redirect(url_for('tokens'))

        # 💡 Corrección: Guardar el archivo directamente en GridFS
        file_id = fs.put(comprobante_file, filename=secure_filename(comprobante_file.filename), content_type=comprobante_file.content_type)
        
        # Guardar la solicitud en la base de datos
        compra = {
            'alias': alias,
            'correo': correo,
            'numero_whatsapp': numero_whatsapp,
            'comprobante_id': str(file_id), # 💡 Corrección: Guardamos el ID del archivo de GridFS
            'cantidad': cantidad,
            'estado': 'pendiente',
            'timestamp': datetime.now()
        }
        compras_col.insert_one(compra)

        flash("¡Solicitud registrada! Tu compra se validará en unos minutos.")
        return redirect(url_for('tokens'))

    return redirect(url_for('tokens'))
import os
import time
import hashlib
import uuid
import re
from flask import Flask, render_template, session, redirect, url_for, flash, request, send_file, abort
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from collections import Counter
from bson.objectid import ObjectId
import pusher
from dotenv import load_dotenv
from gridfs import GridFSBucket, NoFile
from io import BytesIO


# Suponiendo que estas variables están definidas en tu app principal
# app = Flask(__name__)
# usuarios_col = db.usuarios
# confesiones_col = db.confesiones
# mensajes_col = db.mensajes
# fs = GridFSBucket(db) # ¡Importante! Asegúrate de tener esto

ALLOWED_AVATAR = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_CHAT = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav', 'ogg', 'm4a'}

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_gravatar_hash(alias):
    """Calcula el hash MD5 para Gravatar."""
    return hashlib.md5(alias.lower().encode('utf-8')).hexdigest()

# 💡 Corrección: Filtro para avatares actualizado para usar la nueva ruta de GridFS
@app.template_filter('avatar_url')
def avatar_url_filter(user_alias):
    """Genera la URL del avatar, usando un avatar personalizado si existe."""
    user = usuarios_col.find_one({'alias': user_alias})
    if user and 'avatar' in user and user['avatar'] != 'default':
        return url_for('stream_avatar', file_id=user['avatar'])
    else:
        gravatar_hash = get_gravatar_hash(user_alias)
        return f"https://www.gravatar.com/avatar/{gravatar_hash}?d=identicon&s=64"

@app.template_filter('gravatar')
def gravatar_filter(s):
    h = hashlib.md5(s.lower().encode('utf-8')).hexdigest()
    return f"https://www.gravatar.com/avatar/{h}?d=identicon&s=64"
    
def sanitize_for_pusher(name):
    """Elimina caracteres no válidos para nombres de canales de Pusher."""
    return re.sub(r'[^a-zA-Z0-9_\-=@,.;]+', '', name)

# --- Rutas de la aplicación ---

# 💡 Corrección: Ruta para servir avatares desde GridFS
@app.route('/avatar/<file_id>')
def stream_avatar(file_id):
    try:
        file = fs.get(ObjectId(file_id))
        return send_file(BytesIO(file.read()), mimetype=file.content_type, as_attachment=False)
    except NoFile:
        return abort(404)

# 💡 Corrección: Ruta para subir y cambiar avatares con GridFS
@app.route('/cambiar_avatar', methods=['POST'])
def cambiar_avatar():
    if 'alias' not in session:
        flash("Debes iniciar sesión")
        return redirect(url_for('login'))

    archivo = request.files.get('avatar')
    if not archivo or archivo.filename == '':
        flash("No se seleccionó ningún archivo")
        return redirect(url_for('perfiles'))

    if allowed_file(archivo.filename, ALLOWED_AVATAR):
        # Subir el archivo a GridFS
        file_id = fs.put(archivo, filename=secure_filename(f"{uuid.uuid4().hex}_{archivo.filename}"), content_type=archivo.content_type)
        # Guardar el ID del archivo en el perfil del usuario
        usuarios_col.update_one({'alias': session['alias']}, {'$set': {'avatar': str(file_id)}})
        flash("Avatar actualizado correctamente")
    else:
        flash("Formato de imagen no permitido. Usa .png, .jpg o .jpeg")

    return redirect(url_for('perfiles'))

@app.route('/perfiles')
def perfiles():
    alias = session.get('alias')
    if not alias:
        flash("Debes iniciar sesión")
        return redirect(url_for('login'))

    usuarios = [c.get('usuario', 'Anónimo') for c in confesiones_col.find()]
    top = Counter(usuarios).most_common()

    perfiles = []
    me_doc = usuarios_col.find_one({'alias': alias})
    me_following = me_doc.get('following', []) if me_doc else []

    for i, (usuario, pubs) in enumerate(top, start=1):
        doc = usuarios_col.find_one({'alias': usuario}) or {}
        perfiles.append({
            'usuario': usuario,
            'publicaciones': pubs,
            'rank': i,
            'token_oro': doc.get('tokens_oro', 0),
            'followers': len(doc.get('followers', [])),
            'following': len(doc.get('following', [])),
            'is_following': usuario in me_following,
            'avatar': doc.get('avatar', 'default.png'),
            'verificado': doc.get('verificado', False),
        })

    return render_template('perfiles.html', perfiles=perfiles, me=alias)

@app.route('/follow/<usuario>', methods=['POST'])
def follow(usuario):
    me = session.get('alias')
    if me and me != usuario:
        usuarios_col.update_one({'alias': me}, {'$addToSet': {'following': usuario}})
        usuarios_col.update_one({'alias': usuario}, {'$addToSet': {'followers': me}})
    return redirect(url_for('perfiles'))

@app.route('/unfollow/<usuario>', methods=['POST'])
def unfollow(usuario):
    me = session.get('alias')
    usuarios_col.update_one({'alias': me}, {'$pull': {'following': usuario}})
    usuarios_col.update_one({'alias': usuario}, {'$pull': {'followers': me}})
    return redirect(url_for('perfiles'))

@app.route('/chat/<target>')
def chat(target):
    if 'alias' not in session:
        return redirect(url_for('login'))
    me = session['alias']
    
    sala = "_".join(sorted([sanitize_for_pusher(me), sanitize_for_pusher(target)]))

    mensajes = list(mensajes_col.find({'sala': sala}).sort('timestamp', 1))

    for m in mensajes:
        m['avatar_url'] = avatar_url_filter(m['from'])
    me_avatar_url = avatar_url_filter(me)
    target_avatar_url = avatar_url_filter(target)
    
    return render_template('chat.html',
                           me=me,
                           target=target,
                           mensajes=mensajes,
                           me_avatar_url=me_avatar_url,
                           target_avatar_url=target_avatar_url,
                           pusher_key=os.getenv("PUSHER_KEY", "24aebba9248c791c8722"),
                           pusher_cluster=os.getenv("PUSHER_CLUSTER", "mt1"))

# 💡 Corrección: Ruta para servir archivos de chat desde GridFS
@app.route('/chat_media/<file_id>')
def stream_chat_media(file_id):
    try:
        file = fs.get(ObjectId(file_id))
        return send_file(BytesIO(file.read()), mimetype=file.content_type, as_attachment=False)
    except NoFile:
        return abort(404)

# 💡 Corrección: Ruta para enviar mensajes con archivos multimedia en GridFS
@app.route('/send_message', methods=['POST'])
def send_message():
    from_user = session.get('alias')
    if not from_user:
        return 'No autorizado', 401
    to_user = request.form.get('to')
    msg_text = request.form.get('message', '').strip()
    timestamp = request.form.get('timestamp')
    
    sala = "_".join(sorted([sanitize_for_pusher(from_user), sanitize_for_pusher(to_user)]))
    
    tipo = 'text'
    mensaje_a_guardar = msg_text

    if 'media' in request.files:
        media_file = request.files['media']
        if media_file and allowed_file(media_file.filename, ALLOWED_CHAT):
            # Subir el archivo a GridFS
            file_id = fs.put(media_file, filename=secure_filename(f"{from_user}_{int(time.time())}_{media_file.filename}"), content_type=media_file.content_type)
            # Guardar el ID del archivo en el mensaje
            mensaje_a_guardar = str(file_id)
            ext = media_file.filename.rsplit('.', 1)[1].lower()
            tipo = 'image' if ext in {'png', 'jpg', 'jpeg', 'gif'} else 'audio'
            msg_text = ''
        elif media_file:
            return 'Archivo no permitido', 400

    if not msg_text and tipo == 'text':
        return 'Mensaje vacío', 400

    mensajes_col.insert_one({
        'sala': sala,
        'from': from_user,
        'to': to_user,
        'message': mensaje_a_guardar,
        'tipo': tipo,
        'timestamp': timestamp
    })

    # Obtener la URL del avatar para enviarla a Pusher
    from_user_avatar_url = avatar_url_filter(from_user)

    pusher_client.trigger(sala, 'receive_message', {
        'from': from_user,
        'to': to_user,
        'message': mensaje_a_guardar,
        'tipo': tipo,
        'timestamp': timestamp,
        'avatar_url': from_user_avatar_url
    })

    return 'OK'

# -----------------------
# FORMULARIO DE VERIFICACIÓN
# -----------------------
from flask import render_template, redirect, url_for, session, flash, request
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from uuid import uuid4
from datetime import datetime
import os
from gridfs import GridFSBucket

# Suponiendo que estas variables están definidas en tu app principal
# app = Flask(__name__)
# usuarios_col = db.users
# retiros_col = db.retiros
# fs = GridFSBucket(db) # ¡Importante! Asegúrate de tener esto

@app.route("/verificar", methods=["GET", "POST"])
def verificar():
    alias = session.get("alias")
    if not alias:
        flash("Debes iniciar sesión para verificarte.")
        return redirect(url_for("login"))

    if request.method == "POST":
        nombre = request.form.get("nombre")
        cuenta_bancaria = request.form.get("cuenta_bancaria")
        correo = request.form.get("correo")

        # Guardar archivos en GridFS
        ine_frontal = request.files.get("ine_frontal")
        ine_trasera = request.files.get("ine_trasera")
        selfie_ine = request.files.get("selfie_ine")

        ine_frontal_id = None
        ine_trasera_id = None
        selfie_ine_id = None

        if ine_frontal:
            ine_frontal_id = fs.put(ine_frontal, filename=f"{alias}_ine_frontal", content_type=ine_frontal.content_type)
        if ine_trasera:
            ine_trasera_id = fs.put(ine_trasera, filename=f"{alias}_ine_trasera", content_type=ine_trasera.content_type)
        if selfie_ine:
            selfie_ine_id = fs.put(selfie_ine, filename=f"{alias}_selfie_ine", content_type=selfie_ine.content_type)
        
        # Marcar como verificado en Mongo y guardar los datos de verificación
        usuarios_col.update_one(
            {"alias": alias},
            {"$set": {
                "verificado": True,
                "nombre": nombre,
                "cuenta_bancaria": cuenta_bancaria,
                "correo": correo,
                "ine_frontal_id": str(ine_frontal_id),
                "ine_trasera_id": str(ine_trasera_id),
                "selfie_ine_id": str(selfie_ine_id)
            }}
        )

        flash("✅ Verificación enviada correctamente.")
        return redirect(url_for("perfiles"))

    return render_template("verificar.html")

# -----------------------
# RETIRO DE TOKENS
# -----------------------
@app.route("/retiro", methods=["GET", "POST"])
def retiro():
    alias = session.get("alias")
    if not alias:
        flash("Debes iniciar sesión para retirar tokens.")
        return redirect(url_for("login"))

    user = usuarios_col.find_one({"alias": alias})
    if not user:
        flash("Usuario no encontrado.")
        return redirect(url_for("perfiles"))

    oro = int(user.get("tokens_oro", 0))
    verificado = user.get("verificado", False)

    if not verificado:
        flash("Debes verificar tu identidad antes de retirar.")
        return redirect(url_for("verificar"))

    if request.method == "POST":
        if oro < 500:
            flash("Necesitas mínimo 500 tokens para retirar.")
            return redirect(url_for("retiro"))

        # El nombre, cuenta y correo ya están en el perfil del usuario, los recuperamos de ahí
        nombre = user.get("nombre")
        cuenta_bancaria = user.get("cuenta_bancaria")
        correo = user.get("correo")

        # Calcular dinero
        monto_mxn = (oro // 500) * 100

        retiros_col.insert_one({
            "alias": alias,
            "nombre": nombre,
            "cuenta_bancaria": cuenta_bancaria,
            "correo": correo,
            "tokens_retirados": oro,
            "monto_mxn": monto_mxn,
            "estado": "pendiente",
            "timestamp": datetime.now() # Agregamos el timestamp
        })

        usuarios_col.update_one({"alias": alias}, {"$set": {"tokens_oro": 0}})

        flash(f"💰 Solicitud de retiro enviada: ${monto_mxn} MXN en 72h.")
        return redirect(url_for("perfiles"))

    return render_template("retiro_tokens.html", oro=oro)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
