import json
import os
import time

import requests

TOKEN = os.environ["TELEGRAM_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"

MINUTOS_POR_RESINA = 8    # Genshin Impact: 1 resina cada 8 minutos
TOPE_REGEN = 160          # Genshin Impact: la regeneración se detiene en 160
UMBRAL = int(os.environ.get("UMBRAL", "180"))
ARCHIVO = "estado.json"


def cargar():
    try:
        with open(ARCHIVO) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"chat_id": None, "base": None, "t0": None, "avisado": False, "offset": 0}


def guardar(e):
    with open(ARCHIVO, "w") as f:
        json.dump(e, f, indent=2)


def resina_actual(e):
    if e["base"] is None:
        return None
    if e["base"] >= TOPE_REGEN:
        return e["base"]
    minutos = (time.time() - e["t0"]) / 60
    return min(TOPE_REGEN, e["base"] + int(minutos // MINUTOS_POR_RESINA))


def minutos_hasta_umbral(e):
    actual = resina_actual(e)
    necesaria = UMBRAL - actual
    if necesaria <= 0:
        return 0
    if UMBRAL > TOPE_REGEN:
        return None
    minutos = (time.time() - e["t0"]) / 60
    hasta_siguiente = MINUTOS_POR_RESINA - (minutos % MINUTOS_POR_RESINA)
    return hasta_siguiente + (necesaria - 1) * MINUTOS_POR_RESINA


def enviar(chat_id, texto):
    requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": texto}, timeout=10)


def procesar_mensajes(e):
    r = requests.get(
        f"{API}/getUpdates",
        params={"offset": e["offset"], "timeout": 0},
        timeout=20,
    ).json()

    for u in r.get("result", []):
        e["offset"] = u["update_id"] + 1
        msg = u.get("message") or {}
        texto = msg.get("text", "").strip()
        chat = msg.get("chat", {}).get("id")
        if not chat:
            continue
        e["chat_id"] = chat

        if texto.startswith("/resina"):
            partes = texto.split()
            if len(partes) == 2 and partes[1].isdigit():
                e.update(base=int(partes[1]), t0=time.time(), avisado=False)
                enviar(chat, f"Anotado: {partes[1]} de resina. Te aviso al llegar a {UMBRAL}.")
            else:
                enviar(chat, "Uso: /resina 150")

        elif texto.startswith("/estado"):
            if e["base"] is None:
                enviar(chat, "Primero dime tu resina con /resina 150")
            else:
                actual = resina_actual(e)
                mins = minutos_hasta_umbral(e)
                if mins is None:
                    enviar(chat, f"Resina: {actual}. El umbral {UMBRAL} supera el tope de regeneración ({TOPE_REGEN}).")
                elif mins == 0:
                    enviar(chat, f"Resina: {actual}. ¡Ya has llegado a {UMBRAL}!")
                else:
                    enviar(chat, f"Resina: {actual}. Llegas a {UMBRAL} en unos {int(mins)} min.")

        elif texto.startswith("/start"):
            enviar(chat, "Comandos:\n/resina 150 — fija tu resina actual\n/estado — muestra tu resina")


def main():
    e = cargar()
    procesar_mensajes(e)

    if e["base"] is not None and e["chat_id"] and not e["avisado"]:
        actual = resina_actual(e)
        if actual >= UMBRAL:
            enviar(e["chat_id"], f"⚡ ¡Resina en {actual}! Ya puedes abrir el juego.")
            e["avisado"] = True

    guardar(e)


if __name__ == "__main__":
    main()
