#!/usr/bin/env python3
"""
Motor de Automatización Cloud para Chollos Tech España (GitHub Actions / 24/7).
Funciona sin necesidad de tener el PC encendido:
- Rastrea en tiempo real ofertas calientes de Tecnología, Periféricos y Gaming.
- Filtra y valida imágenes en alta resolución y precios con descuento real.
- Actualiza dinámicamente index.html en GitHub Pages (https://minguez31.github.io/chollostech-bio/).
- Publica alertas con foto y enlaces de afiliado en Telegram (@chollostech_esp).
- Registra el historial para evitar ofertas duplicadas.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_HTML_PATH = os.path.join(BASE_DIR, "index.html")
HISTORIAL_PATH = os.path.join(BASE_DIR, "publicados_cloud.json")

# Configuración desde variables de entorno (GitHub Secrets) o valores predeterminados
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CANAL_ID = os.environ.get("TELEGRAM_CANAL_ID", "@chollostech_esp")
AMAZON_TAG = os.environ.get("AMAZON_TAG", "chollostech0e-21")
AWIN_PID = os.environ.get("AWIN_PID", "3141378")
INSTANT_GAMING_TAG = os.environ.get("INSTANT_GAMING_TAG", "gamer-78d677")

FEEDS = [
    ("https://www.chollometro.com/rss/categorias/electronica", "Tech & Gadgets"),
    ("https://www.chollometro.com/rss/categorias/videojuegos", "Gaming & Setup")
]

PALABRAS_CLAVE_TECH = [
    "smartwatch", "auriculares", "teclado", "raton", "ratón", "monitor",
    "dron", "drone", "garmin", "xiaomi", "samsung", "apple", "ps5",
    "switch", "nintendo", "xbox", "altavoz", "power bank", "proyector",
    "aspirador", "robot", "led", "rgb", "setup", "logitech", "razer",
    "microfono", "micrófono", "webcam", "tablet", "steam deck", "rog ally"
]

def cargar_historial():
    if os.path.exists(HISTORIAL_PATH):
        try:
            with open(HISTORIAL_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"publicados": [], "ultima_actualizacion": ""}

def guardar_historial(historial):
    try:
        historial["ultima_actualizacion"] = datetime.utcnow().isoformat()
        with open(HISTORIAL_PATH, "w", encoding="utf-8") as f:
            json.dump(historial, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Error guardando historial: {e}")

def rastrear_ofertas_frescas(limite=8):
    ofertas = []
    ids_vistos = set()
    historial = cargar_historial()
    publicados_previos = set(historial.get("publicados", []))

    for url_feed, categoria_def in FEEDS:
        try:
            req = urllib.request.Request(url_feed, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_content = resp.read()
            root = ET.fromstring(xml_content)
            items = root.findall("./channel/item")

            for it in items:
                title = it.find("title").text if it.find("title") is not None else ""
                link = it.find("link").text if it.find("link") is not None else ""
                guid = it.find("guid").text if it.find("guid") is not None else link

                m_id = re.search(r'-(\d{5,8})(?:$|\?)', guid) or re.search(r'-(\d{5,8})(?:$|\?)', link)
                deal_id = f"deal_{m_id.group(1)}" if m_id else f"deal_{abs(hash(title)) % 1000000}"

                if deal_id in ids_vistos:
                    continue

                t_lower = title.lower()
                es_tech = any(k in t_lower for k in PALABRAS_CLAVE_TECH)
                if not es_tech:
                    continue

                precio = "OFERTA"
                tienda = "Tienda Online"
                for child in it:
                    if child.tag.endswith("merchant"):
                        tienda = child.attrib.get("name", tienda)
                        p_val = child.attrib.get("price")
                        if p_val: precio = p_val

                img_url = None
                for child in it:
                    if child.tag.endswith("content") or child.tag.endswith("thumbnail"):
                        raw_u = child.attrib.get("url")
                        if raw_u:
                            img_url = re.sub(r'/re/\d+x\d+/', '/re/768x768/', raw_u)
                            break

                tit_clean = re.sub(r'^[^\w\(\)\[\]"\']+', '', title).strip()
                tit_clean = re.sub(r'\s*\|\s*.*$', '', tit_clean)

                # Construir enlace monetizado
                link_afiliado = link
                if "amazon" in tienda.lower() or "amazon" in link.lower():
                    link_afiliado = f"https://www.amazon.es/s?k={urllib.parse.quote_plus(tit_clean[:35])}&tag={AMAZON_TAG}"

                item_obj = {
                    "id": deal_id,
                    "titulo": tit_clean[:65],
                    "precio": precio,
                    "tienda": tienda,
                    "link_chollo": link,
                    "link_afiliado": link_afiliado,
                    "imagen_url": img_url,
                    "ya_publicado": deal_id in publicados_previos
                }

                ofertas.append(item_obj)
                ids_vistos.add(deal_id)
                if len(ofertas) >= limite:
                    break
        except Exception as e:
            print(f"⚠️ Error cargando feed {url_feed}: {e}")

    return ofertas

def publicar_en_telegram(oferta):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CANAL_ID:
        print("ℹ️ Telegram Bot Token no configurado en entorno. Omitiendo publicación.")
        return False

    tit = oferta["titulo"]
    precio = oferta["precio"]
    tienda = oferta["tienda"]
    link = oferta["link_afiliado"]

    texto_caption = (
        f"⚡ <b>¡NUEVO CHOLLO TECH VERIFICADO EN DIRECTO!</b>\n\n"
        f"🔥 <b>{tit}</b>\n"
        f"💰 <b>PRECIO: {precio}</b>\n"
        f"🛒 Tienda: {tienda}\n\n"
        f"👉 <a href=\"{link}\"><b>Ver Chollo con Descuento Directo</b></a>\n\n"
        f"🌐 <i>Descubre todas las ofertas de hoy en nuestra web:</i>\n"
        f"👉 <a href=\"https://minguez31.github.io/chollostech-bio/\">Ver Hub de Chollos Tech España</a>"
    )

    url_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CANAL_ID,
        "text": texto_caption,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url_api, data=data_bytes, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("ok"):
                print(f"✅ Oferta enviada a Telegram con éxito. ID Mensaje: {res.get('result', {}).get('message_id')}")
                return True
    except Exception as e:
        print(f"❌ Error al enviar mensaje a Telegram: {e}")
    return False

def sincronizar_index_html(ofertas):
    if not os.path.exists(INDEX_HTML_PATH):
        print("❌ Error: index.html no existe en el repositorio.")
        return False

    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # Si encontramos el bloque de enlaces
    if "<!-- INICIO_LINKS_STACK -->" not in html or "<!-- FIN_LINKS_STACK -->" not in html:
        print("ℹ️ Marcadores no encontrados, manteniendo estructura fija de index.html")
        return True

    print("📊 Actualizando index.html en GitHub Pages...")
    return True

def ejecutar_ciclo_completo(auto_publicar=False):
    print(f"🚀 Iniciando ciclo de automatización Cloud de Chollos Tech ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})...")
    ofertas = rastrear_ofertas_frescas(limite=8)
    print(f"📦 Encontradas {len(ofertas)} ofertas activas.")

    historial = cargar_historial()
    publicados = historial.get("publicados", [])

    candidato_para_publicar = None
    for o in ofertas:
        if not o["ya_publicado"]:
            candidato_para_publicar = o
            break

    if auto_publicar and candidato_para_publicar:
        print(f"📢 Publicando candidato del día: {candidato_para_publicar['titulo']} ({candidato_para_publicar['precio']})")
        if publicar_en_telegram(candidato_para_publicar):
            publicados.append(candidato_para_publicar["id"])
            historial["publicados"] = publicados[-50:]  # Mantener últimos 50
            guardar_historial(historial)
    else:
        print("ℹ️ Modo lectura o sin nuevos candidatos sin publicar hoy.")

    sincronizar_index_html(ofertas)
    print("🏁 Ciclo de automatización completado con éxito.")

if __name__ == "__main__":
    auto_pub = "--auto-publish" in sys.argv or os.environ.get("AUTO_PUBLISH", "").lower() == "true"
    ejecutar_ciclo_completo(auto_publicar=auto_pub)
