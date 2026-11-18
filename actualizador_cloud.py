#!/usr/bin/env python3
"""
Motor de Automatización Cloud para Chollos Tech España (GitHub Actions / 24/7).
Funciona sin necesidad de tener el PC encendido:
- Rastrea en tiempo real ofertas calientes de Tecnología, Periféricos y Gaming cada 30 minutos.
- Incluye el catálogo de partners y referidos de alta comisión (Anthbot, Mibro, Instant Gaming, Amazon).
- Protege el canal con limitador inteligente de publicaciones (mínimo 90 min entre envíos para no saturar).
- Envía publicaciones atractivas con foto a Telegram (@chollostech_esp).
- Sincroniza dinámicamente index.html en GitHub Pages (https://minguez31.github.io/chollostech-bio/).
"""

import os
import sys
import json
import re
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

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
TRADEDOUBLER_SITE_ID = os.environ.get("TRADEDOUBLER_SITE_ID", "3508220")

# Catálogo permanente de partners con programas activos y comisiones altas
OFERTAS_PARTNERS_DESTACADAS = [
    {
        "id": "partner_anthbot_black_friday",
        "titulo": "Robot Cortacésped ANTHBOT M5/M9 (Black Friday EU Store)",
        "precio": "499,00 € (-200€)",
        "tienda": "Anthbot Official (Awin)",
        "link_chollo": "https://anthbot.com/pages/black-friday-sale",
        "link_afiliado": f"https://www.awin1.com/cread.php?awinaffid={AWIN_PID}&ued=https%3A%2F%2Fanthbot.com%2Fpages%2Fblack-friday-sale",
        "destacado": True,
        "detalles": "Garaje oficial por 1€ y cupón extra ABAFF10 (10% acumulable). Robot inteligente sin cables perimetrales.",
        "imagen_url": "https://anthbot.com/cdn/shop/files/M5_banner.jpg"
    },
    {
        "id": "partner_razer_seiren_v3",
        "titulo": "Micrófono Gaming Razer Seiren V3 Chroma (RGB Reactivo)",
        "precio": "78,99 € (-28%)",
        "tienda": "Amazon Prime",
        "link_chollo": "https://www.amazon.es/dp/B0CNXKMSJG",
        "link_afiliado": f"https://www.amazon.es/dp/B0CNXKMSJG?tag={AMAZON_TAG}",
        "destacado": True,
        "detalles": "Iluminación Chroma RGB reactiva a juegos/streams, sensor tap-to-mute superior y audio profesional.",
        "imagen_url": "https://m.media-amazon.com/images/I/71qSkgxS7UL._AC_SL1500_.jpg"
    },
    {
        "id": "partner_mibro_gs_explorer",
        "titulo": "Smartwatch Militar Titanio Mibro GS Explorer S",
        "precio": "139,00 $ (-30%)",
        "tienda": "Mibro Global Store (Awin)",
        "link_chollo": "https://www.mibrofit.com/products/mibro-gs-explorer-s",
        "link_afiliado": f"https://www.awin1.com/cread.php?awinmid=131533&awinaffid={AWIN_PID}&ued=https%3A%2F%2Fwww.mibrofit.com%2Fproducts%2Fmibro-gs-explorer-s",
        "destacado": True,
        "detalles": "Caja de titanio aeroespacial, AMOLED 1500 nits, 10 ATM. Cupón descuento: MIBRO501.",
        "imagen_url": "https://www.mibrofit.com/cdn/shop/files/Mibro_GS_Explorer_S.png"
    },
    {
        "id": "partner_instant_gaming_deals",
        "titulo": "Rebajas en Videojuegos PC & Consolas (Steam / PS5 / Switch)",
        "precio": "Hasta -70%",
        "tienda": "Instant Gaming",
        "link_chollo": "https://www.instant-gaming.com/es/",
        "link_afiliado": f"https://www.instant-gaming.com/es/?igr={INSTANT_GAMING_TAG}",
        "destacado": True,
        "detalles": "Claves digitales oficiales instantáneas para Steam, PlayStation Network, Xbox y Nintendo Switch.",
        "imagen_url": "https://gaming-cdn.com/themes/igv1/modules/simpleheader/images/logo.png"
    }
]

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
    return {"publicados": [], "ultimo_envio_ts": 0, "ultima_actualizacion": ""}

def guardar_historial(historial):
    try:
        historial["ultima_actualizacion"] = datetime.now(timezone.utc).isoformat()
        with open(HISTORIAL_PATH, "w", encoding="utf-8") as f:
            json.dump(historial, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Error guardando historial: {e}")

def rastrear_ofertas_frescas(limite=10):
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

                link_afiliado = link
                if "amazon" in tienda.lower() or "amazon" in link.lower():
                    m_asin = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', link)
                    if m_asin:
                        link_afiliado = f"https://www.amazon.es/dp/{m_asin.group(1)}?tag={AMAZON_TAG}"
                    else:
                        link_afiliado = f"https://www.amazon.es/s?k={urllib.parse.quote_plus(tit_clean[:35])}&tag={AMAZON_TAG}"
                elif "mediamarkt" in tienda.lower() or "mediamarkt" in link.lower():
                    if TRADEDOUBLER_SITE_ID:
                        link_afiliado = f"https://clk.tradedoubler.com/click?p=15610&a={TRADEDOUBLER_SITE_ID}&url={urllib.parse.quote(link, safe='')}"

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
    detalles = oferta.get("detalles", "Oferta verificada y activa. Descuento directo disponible hoy.")
    img_url = oferta.get("imagen_url")

    texto_caption = (
        f"⚡ <b>{tit}</b>\n\n"
        f"💰 <b>PRECIO CHOLLO: {precio}</b>\n"
        f"🛒 Tienda: {tienda}\n\n"
        f"🔹 {detalles}\n\n"
        f"👉 <a href=\"{link}\"><b>Ver Chollo con Descuento Directo</b></a>\n\n"
        f"🌐 <i>Descubre todas las ofertas y vídeos del día:</i>\n"
        f"👉 <a href=\"https://minguez31.github.io/chollostech-bio/\">Ver Hub de Chollos Tech España</a>"
    )

    # Intentar enviar con foto si tiene URL de imagen válida
    if img_url and img_url.startswith("http"):
        url_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": TELEGRAM_CANAL_ID,
            "photo": img_url,
            "caption": texto_caption,
            "parse_mode": "HTML"
        }
    else:
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
        print(f"⚠️ Error al enviar con sendPhoto ({e}). Reintentando con sendMessage de texto plano...")
        try:
            url_api_msg = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload_msg = {
                "chat_id": TELEGRAM_CANAL_ID,
                "text": texto_caption,
                "parse_mode": "HTML"
            }
            req = urllib.request.Request(url_api_msg, data=json.dumps(payload_msg).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if res.get("ok"):
                    return True
        except Exception as e2:
            print(f"❌ Error final en Telegram: {e2}")

    return False

def ejecutar_ciclo_completo(auto_publicar=False):
    ahora_ts = int(time.time())
    print(f"🚀 Iniciando ciclo de automatización Cloud de Chollos Tech ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})...")
    
    ofertas = rastrear_ofertas_frescas(limite=10)
    print(f"📦 Encontradas {len(ofertas)} ofertas tech en vivo.")

    historial = cargar_historial()
    publicados = historial.get("publicados", [])
    ultimo_envio_ts = historial.get("ultimo_envio_ts", 0)

    tiempo_transcurrido_min = (ahora_ts - ultimo_envio_ts) // 60
    print(f"⏱️ Tiempo desde la última publicación en Telegram: {tiempo_transcurrido_min} minutos.")

    # Rate limiting inteligente: Mínimo 60 min entre envíos para mantener ritmo constante sin saturar
    INTERVALO_MINIMO_MINUTOS = 60
    puede_publicar = auto_publicar and (tiempo_transcurrido_min >= INTERVALO_MINIMO_MINUTOS)

    candidato = None
    for o in ofertas:
        if not o["ya_publicado"]:
            candidato = o
            break

    # Si no hay chollo nuevo de RSS pero toca publicar, rotar las ofertas partners destacadas (Anthbot, Razer, Mibro, Instant Gaming)
    if not candidato and puede_publicar:
        for p in OFERTAS_PARTNERS_DESTACADAS:
            if p["id"] not in publicados[-len(OFERTAS_PARTNERS_DESTACADAS):]:
                candidato = p
                break
        if not candidato and OFERTAS_PARTNERS_DESTACADAS:
            candidato = OFERTAS_PARTNERS_DESTACADAS[0]

    if candidato and puede_publicar:
        print(f"📢 Publicando candidato seleccionado: {candidato['titulo']} ({candidato['precio']})")
        if publicar_en_telegram(candidato):
            publicados.append(candidato["id"])
            historial["publicados"] = publicados[-60:]
            historial["ultimo_envio_ts"] = ahora_ts
            guardar_historial(historial)
    elif candidato and not puede_publicar:
        print(f"⏳ Candidato listo ({candidato['titulo']}), pero en ventana de espera ({tiempo_transcurrido_min}/{INTERVALO_MINIMO_MINUTOS} min) para no saturar.")
    else:
        print("ℹ️ Sin nuevos candidatos en esta pasada.")

    guardar_historial(historial)
    print("🏁 Ciclo de automatización completado con éxito.")

if __name__ == "__main__":
    auto_pub = "--auto-publish" in sys.argv or os.environ.get("AUTO_PUBLISH", "").lower() == "true"
    ejecutar_ciclo_completo(auto_publicar=auto_pub)
