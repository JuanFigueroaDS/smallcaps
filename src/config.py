"""Configuración central del scanner. Todo se puede sobreescribir con variables de entorno."""
import os

def _int_env(name: str, default: int) -> int:
    val = os.environ.get(name)
    try:
        return int(val) if val else default
    except ValueError:
        return default

# --- Credenciales (obligatorias) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ALPHAVANTAGE_API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

# --- Universo de small caps ---
MARKET_CAP_MIN = _int_env("MARKET_CAP_MIN", 50_000_000)      # $50M
MARKET_CAP_MAX = _int_env("MARKET_CAP_MAX", 2_000_000_000)   # $2B
UNIVERSE_FILE = os.environ.get("UNIVERSE_FILE", "universe.csv")

# --- Ventana de búsqueda ---
# Debe ser un poco mayor al intervalo real entre corridas (5 min) para
# absorber retrasos de scheduling de GitHub Actions.
LOOKBACK_MINUTES = _int_env("LOOKBACK_MINUTES", 1440)

# --- Estado / dedup ---
STATE_FILE = os.environ.get("STATE_FILE", "state/seen.json")
STATE_RETENTION_HOURS = _int_env("STATE_RETENTION_HOURS", 72)

# --- Cache de market cap (evita golpear Finnhub en cada corrida) ---
MARKET_CAP_CACHE_FILE = os.environ.get("MARKET_CAP_CACHE_FILE", "state/market_cap_cache.json")
MARKET_CAP_CACHE_HOURS = _int_env("MARKET_CAP_CACHE_HOURS", 24)

# --- Relevancia mínima de Alpha Vantage para considerar un ticker mencionado ---
AV_MIN_RELEVANCE = float(os.environ.get("AV_MIN_RELEVANCE", "0.3"))

# --- Topics de Alpha Vantage a consultar (catalizadores) ---
AV_TOPICS = os.environ.get(
    "AV_TOPICS",
    "mergers_and_acquisitions,earnings,ipo,life_sciences,financial_markets",
)

# --- Palabras clave de catalizadores (para Finnhub, que no trae topics) ---
CATALYST_KEYWORDS = [
    # Regulatorio / FDA
    "fda", "approval", "approves", "clearance", "breakthrough therapy",
    "orphan drug", "fast track", "emergency use authorization", "phase 1",
    "phase 2", "phase 3", "clinical trial", "nda", "pdufa",
    # M&A
    "acquire", "acquisition", "merger", "merge", "buyout", "tender offer",
    "to be acquired", "strategic alternatives", "definitive agreement",
    # Contratos / negocio
    "contract award", "awarded a contract", "partnership", "licensing agreement",
    "collaboration agreement", "purchase order",
    # Resultados financieros
    "earnings", "quarterly results", "guidance", "raises guidance",
    "cuts guidance", "eps of", "revenue of", "beats estimates", "misses estimates",
]

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
