"""Envío de alertas a Telegram."""
import logging
import requests

from . import config

log = logging.getLogger(__name__)


def send_message(text: str) -> bool:
    """Envía un mensaje de texto (Markdown) al chat configurado.

    Devuelve True si Telegram confirmó la entrega, False si falló
    (se loguea el error pero nunca se lanza una excepción: un fallo de
    Telegram no debe tumbar el resto del scan).
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.error("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID; no se puede notificar.")
        return False

    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(config.TELEGRAM_API_URL, data=payload, timeout=15)
        if resp.status_code != 200:
            log.error("Telegram respondió %s: %s", resp.status_code, resp.text[:300])
            return False
        return True
    except requests.RequestException as e:
        log.error("Error enviando a Telegram: %s", e)
        return False


def format_alert(
    ticker: str,
    company: str,
    market_cap: float,
    headline: str,
    url: str,
    source: str,
    catalyst_tags: list,
    sentiment: str = "",
) -> str:
    cap_m = market_cap / 1_000_000
    tags = " ".join(f"#{t.replace(' ', '_')}" for t in catalyst_tags) if catalyst_tags else ""
    sentiment_line = f"\nSentimiento: {sentiment}" if sentiment else ""
    return (
        f"🚨 *{ticker}* — {company}\n"
        f"Market cap: ${cap_m:,.0f}M\n"
        f"{headline}{sentiment_line}\n"
        f"Fuente: {source}\n"
        f"{url}\n"
        f"{tags}"
    ).strip()
