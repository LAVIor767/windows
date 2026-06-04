# ===== IMPORTS & SESSION =====
import logging
import os
import time
import pandas as pd
import numpy as np
import requests
import pytz
from flask import jsonify
from collections import Counter
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import Flask, request, render_template, Response, url_for
import finnhub
import pandas_market_calendars as mcal
from config import PROJECT_FOLDER, FINNHUB_API_KEY, FLASK_SECRET_KEY, IS_PRODUCTION
from cache import cache_get_disk, cache_set_disk

finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)
# ===== FLASK APP =====
app = Flask(__name__)

@app.route("/api/signal/<symbol>")
def api_signal(symbol):

    stock_data = fetch_finnhub_quote(symbol)

    market_data = fetch_all_market_data(symbol)

    daily_df = build_df(market_data["daily"])
    hourly_df = build_df(market_data["hourly"])
    m5_df = build_df(market_data["m5"])

    daily_result = build_indicator_set(daily_df, "1D")
    hourly_result = build_indicator_set(hourly_df, "1H")
    five_result = build_indicator_set(m5_df, "5M")

    combined_signal = get_combined_signal(
        daily_result,
        hourly_result,
        five_result
    )

    return jsonify({

        # STOCK
        "price": stock_data["Price"],
        "previous_close": stock_data["Previous Close"],
        "day_high": stock_data["Day High"],
        "day_low": stock_data["Day Low"],

        # AI SIGNAL
        "signal": combined_signal["signal"],
        "score": combined_signal["score"],
        "confidence": combined_signal["confidence"],

        "momentum": combined_signal["momentum"],
        "trend": combined_signal["trend"],
        "volatility": combined_signal["volatility"],

        "adx": combined_signal["adx"],
        "agreement": combined_signal["agreement"],

        "market_state": combined_signal["market_state"],

        # INDICATORS
        "daily": daily_result,
        "hourly": hourly_result,
        "m5": five_result,

        # DETAILS
        "details": combined_signal["details"]
    })

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Requests session with retries/backoff and proper User-Agent
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "MyStockApp/1.0 (pythonanywhere) "})
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "POST"])
SESSION.mount("https://", HTTPAdapter(max_retries=retries))

# Use environment-aware cookie config
app.config.update(
    SECRET_KEY=FLASK_SECRET_KEY,
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)
# ===== STOCKS =====
stocks = {
    "Apple Inc.": "AAPL",
    "Microsoft Corporation": "MSFT",
    "NVIDIA Corporation": "NVDA",
    "Amazon.com, Inc.": "AMZN",
    "Meta Platforms, Inc.": "META",
    "Alphabet Inc. Class A": "GOOGL",
    "Alphabet Inc. Class C": "GOOG",
    "Tesla, Inc.": "TSLA",
    "Broadcom Inc.": "AVGO",
    "Berkshire Hathaway Inc. Class B": "BRK.B",
    "JPMorgan Chase & Co.": "JPM",
    "Visa Inc.": "V",
    "Mastercard Incorporated": "MA",
    "Eli Lilly and Company": "LLY",
    "UnitedHealth Group Incorporated": "UNH",
    "Exxon Mobil Corporation": "XOM",
    "Johnson & Johnson": "JNJ",
    "Procter & Gamble Company": "PG",
    "Costco Wholesale Corporation": "COST",
    "Netflix, Inc.": "NFLX",
    "Adobe Inc.": "ADBE",
    "Salesforce, Inc.": "CRM",
    "Oracle Corporation": "ORCL",
    "Advanced Micro Devices, Inc.": "AMD",
    "Qualcomm Incorporated": "QCOM",
    "Intel Corporation": "INTC",
    "Cisco Systems, Inc.": "CSCO",
    "Texas Instruments Incorporated": "TXN",
    "Palantir Technologies Inc.": "PLTR",
    "ServiceNow, Inc.": "NOW",
    "Shopify Inc.": "SHOP",
    "Uber Technologies, Inc.": "UBER",
    "Airbnb, Inc.": "ABNB",
    "CrowdStrike Holdings, Inc.": "CRWD",
    "Palo Alto Networks, Inc.": "PANW",
    "Fortinet, Inc.": "FTNT",
    "Zscaler, Inc.": "ZS",
    "Datadog, Inc.": "DDOG",
    "Snowflake Inc.": "SNOW",
    "The Trade Desk, Inc.": "TTD",
    "ASML Holding N.V.": "ASML",
    "Taiwan Semiconductor Manufacturing Company Limited": "TSM",
    "Micron Technology, Inc.": "MU",
    "Lam Research Corporation": "LRCX",
    "Applied Materials, Inc.": "AMAT",
    "KLA Corporation": "KLAC",
    "Marvell Technology, Inc.": "MRVL",
    "Monolithic Power Systems, Inc.": "MPWR",
    "Synopsys, Inc.": "SNPS",
    "Cadence Design Systems, Inc.": "CDNS",
    "Intuitive Surgical, Inc.": "ISRG",
    "Vertex Pharmaceuticals Incorporated": "VRTX",
    "Regeneron Pharmaceuticals, Inc.": "REGN",
    "Amgen Inc.": "AMGN",
    "Moderna, Inc.": "MRNA",
    "Gilead Sciences, Inc.": "GILD",
    "AbbVie Inc.": "ABBV",
    "Merck & Co., Inc.": "MRK",
    "Pfizer Inc.": "PFE",
    "Coca-Cola Company": "KO",
    "PepsiCo, Inc.": "PEP",
    "McDonald's Corporation": "MCD",
    "Nike, Inc.": "NKE",
    "Starbucks Corporation": "SBUX",
    "Walmart Inc.": "WMT",
    "Target Corporation": "TGT",
    "Home Depot, Inc.": "HD",
    "Lowe's Companies, Inc.": "LOW",
    "Chevron Corporation": "CVX",
    "ConocoPhillips": "COP",
    "NextEra Energy, Inc.": "NEE",
    "American Electric Power Company, Inc.": "AEP",
    "Exelon Corporation": "EXC",
    "Xcel Energy Inc.": "XEL",
    "Goldman Sachs Group, Inc.": "GS",
    "Morgan Stanley": "MS",
    "Bank of America Corporation": "BAC",
    "Wells Fargo & Company": "WFC",
    "BlackRock, Inc.": "BLK",
    "PayPal Holdings, Inc.": "PYPL",
    "Block, Inc.": "SQ",
    "Coinbase Global, Inc.": "COIN",
    "Robinhood Markets, Inc.": "HOOD",
    "Booking Holdings Inc.": "BKNG",
    "Expedia Group, Inc.": "EXPE",
    "Electronic Arts Inc.": "EA",
    "Take-Two Interactive Software, Inc.": "TTWO",
    "Roblox Corporation": "RBLX",
    "Spotify Technology S.A.": "SPOT",
    "Zoom Communications, Inc.": "ZM",
    "Atlassian Corporation": "TEAM",
    "Workday, Inc.": "WDAY",
    "Roku, Inc.": "ROKU",
    "Lululemon Athletica Inc.": "LULU",
    "MercadoLibre, Inc.": "MELI",
    "Baidu, Inc.": "BIDU",
    "JD.com, Inc.": "JD",
    "PDD Holdings Inc.": "PDD",
    "eBay Inc.": "EBAY",
    "Dollar Tree, Inc.": "DLTR",
    "Monster Beverage Corporation": "MNST",
    "Keurig Dr Pepper Inc.": "KDP",
    "Copart, Inc.": "CPRT",
    "Fastenal Company": "FAST",
    "Cintas Corporation": "CTAS"
}

# ===== HELPERS =====
def safe_float(x):
    try:
        return float(x)
    except:
        return None

last_request_time = {}

def build_df(raw):
    if raw is None:
        return pd.DataFrame()

    if isinstance(raw, pd.DataFrame):
        return raw

    try:
        df = pd.DataFrame({
            "Open": raw.get("o", []),
            "High": raw.get("h", []),
            "Low": raw.get("l", []),
            "Close": raw.get("c", []),
            "Volume": raw.get("v", [])
        })

        df.index = pd.to_datetime(raw.get("t", []), unit='s')
        df.sort_index(inplace=True)
        return df

    except Exception:
        logger.exception("Error building dataframe")
        return pd.DataFrame()

def safe_calc(func, df):
    """מחזיר תוצאה אחרונה בצורה בטוחה (לעולם לא list)"""
    try:
        result = func(df)
        if result is None:
            return None

        # אם זה Series (פנדס)
        if hasattr(result, "dropna"):
            val = result.dropna()
            if len(val) == 0:
                return None
            return round(float(val.iloc[-1]), 2)

        # אם זה tuple או list → תמיד ניקח רק את הערך האחרון
        if isinstance(result, (tuple, list, np.ndarray)):
            arr = [x for x in result if x is not None and not (isinstance(x, float) and np.isnan(x))]
            if len(arr) == 0:
                return None
            return round(float(arr[-1]), 2)

        # ערך בודד
        if isinstance(result, (int, float, np.floating)):
            if np.isnan(result):
                return None
            return round(float(result), 2)

        return None

    except Exception:
        logger.exception("Error in %s", func.__name__)
        return None

def get_market_status():

    nyse = mcal.get_calendar("NYSE")

    ny_tz = pytz.timezone("America/New_York")

    now = datetime.now(ny_tz)

    schedule = nyse.schedule(
        start_date=now.date(),
        end_date=now.date()
    )

    # Weekend / Holiday
    if schedule.empty:
        return {
            "is_open": False,
            "message": "Market closed today (Weekend / Holiday)"
        }

    market_open = schedule.iloc[0]["market_open"]
    market_close = schedule.iloc[0]["market_close"]

    # Convert safely to NY timezone
    market_open = market_open.tz_convert(ny_tz)
    market_close = market_close.tz_convert(ny_tz)

    is_open = market_open <= now <= market_close

    # Market Open
    if is_open:
        return {
            "is_open": True,
            "message": "Market OPEN"
        }

    # Before market opens
    if now < market_open:
        return {
            "is_open": False,
            "message": f"Market opens at {market_open.strftime('%H:%M')} ET"
        }

    # After market close
    return {
        "is_open": False,
        "message": f"Market closed at {market_close.strftime('%H:%M')} ET"
    }

def can_fetch(symbol, cooldown=30):
    now = time.time()
    last = last_request_time.get(symbol, 0)
    if now - last > cooldown:
        last_request_time[symbol] = now
        return True
    return False

# ===== INDICATORS =====
def RSI(df, period=14):
    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def StochRSI(df, period=14):
    rsi = RSI(df, period)
    stoch_rsi = (rsi - rsi.rolling(window=period).min()) / (rsi.rolling(window=period).max() - rsi.rolling(window=period).min()) * 100
    return stoch_rsi

def WilliamsR(df, period=14):
    highest_high = df['High'].rolling(period).max()
    lowest_low = df['Low'].rolling(period).min()
    return (highest_high - df['Close']) / (highest_high - lowest_low) * -100

def MACD(df, short=12, long=26, signal=9):
    ema_short = df['Close'].ewm(span=short, adjust=False).mean()
    ema_long = df['Close'].ewm(span=long, adjust=False).mean()
    macd_line = ema_short - ema_long
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def ADX(df, period=14):
    high = df['High']
    low = df['Low']
    close = df['Close']
    up_move = high.diff()
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False, min_periods=period).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(span=period, adjust=False, min_periods=period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(span=period, adjust=False, min_periods=period).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(span=period, adjust=False, min_periods=period).mean()
    return adx

def CCI(df, period=20):
    TP = (df['High'] + df['Low'] + df['Close']) / 3
    MA = TP.rolling(period).mean()
    MAD = TP.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    CCI = (TP - MA) / (0.015 * MAD)
    return CCI

def EMA(df, period=20):
    return df['Close'].ewm(span=period, adjust=False).mean()

def BollingerBands(df, period=20):
    sma = df['Close'].rolling(period).mean()
    std = df['Close'].rolling(period).std()
    upper = sma + (2 * std)
    lower = sma - (2 * std)
    return upper, lower

def ATR(df, period=14):
    high = df['High']
    low = df['Low']
    close = df['Close']

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()
    return atr

def MFI(df, period=14):
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    mf = tp * df['Volume']

    positive = []
    negative = []

    for i in range(1, len(tp)):
        if tp.iloc[i] > tp.iloc[i - 1]:
            positive.append(mf.iloc[i])
            negative.append(0)
        else:
            positive.append(0)
            negative.append(mf.iloc[i])

    pos_mf = pd.Series(positive, index=df.index[1:]).rolling(period).sum()
    neg_mf = pd.Series(negative, index=df.index[1:]).rolling(period).sum()

    mfi = 100 - (100 / (1 + pos_mf / neg_mf))
    return mfi


def ROC(df, period=10):
    return (df['Close'] / df['Close'].shift(period) - 1) * 100

#def get_signal(indicators, suffix):
#    score = 0
#    max_score = 0

#    rsi = indicators.get(f"RSI_14_{suffix}")
#    macd = indicators.get(f"MACD_Line_{suffix}") or indicators.get(f"MACD_Line[12,26]_{suffix}")
#    signal = indicators.get(f"Signal_Line_{suffix}") or indicators.get(f"Signal_Line[12,26]_{suffix}")
#    cci = indicators.get(f"CCI_20_{suffix}")
#    williams = indicators.get(f"WilliamsR_14_{suffix}")
#    mfi = indicators.get(f"MFI_14_{suffix}")
#    ema20 = indicators.get(f"EMA_20_{suffix}")
#    ema50 = indicators.get(f"EMA_50_{suffix}")
#    price = indicators.get(f"Close_{suffix}")
#    bb_upper = indicators.get(f"Bollinger_Upper_{suffix}")
#    bb_lower = indicators.get(f"Bollinger_Lower_{suffix}")
#    adx = indicators.get(f"ADX_14_{suffix}")
#    roc = indicators.get(f"ROC_10_{suffix}")

    # ===== RSI (משקל בינוני) =====
#    if rsi is not None:
#        max_score += 1
#        if rsi < 30:
#            score += 1
#        elif rsi > 70:
#            score -= 1

    # ===== MACD (משקל גבוה) =====
#    if macd is not None and signal is not None:
#        max_score += 2
#        if macd > signal:
#            score += 2
#        elif macd < signal:
#            score -= 2

    # ===== CCI =====
#    if cci is not None:
#        max_score += 1
#        if cci < -100:
#            score += 1
#        elif cci > 100:
#            score -= 1

    # ===== Williams =====
#    if williams is not None:
#        max_score += 0.5
#        if williams < -80:
#            score += 0.5
#        elif williams > -20:
#            score -= 0.5

    # ===== MFI =====
#    if mfi is not None:
#        max_score += 1
#        if mfi < 20:
#            score += 1
#        elif mfi > 80:
#            score -= 1

    # ===== EMA TREND (קריטי!) =====
#    if ema20 is not None and ema50 is not None and price is not None:
#        max_score += 2

#        if price > ema20 > ema50:
#            score += 2
#        elif price < ema20 < ema50:
#            score -= 2
#        else:
#            score += 0  # sideways

    # ===== Bollinger =====
#    if price is not None and bb_upper is not None and bb_lower is not None:
#        max_score += 1
#        if price < bb_lower:
#            score += 1
#        elif price > bb_upper:
#            score -= 1

    # ===== ROC =====
#    if roc is not None:
#        max_score += 1
#        if roc > 0:
#            score += 1
#        elif roc < 0:
#            score -= 1

    # ===== ADX (רק חיזוק, לא שינוי כיוון) =====
#    trend_bonus = 0
#    if adx is not None:
#        if adx > 40:
#            trend_bonus = 2
#        elif adx > 25:
#            trend_bonus = 1

    # ===== APPLY ADX נכון =====
#    if score > 0:
#        final_score = score + trend_bonus
#    elif score < 0:
#        final_score = score - trend_bonus
#    else:
#        final_score = score

    # ===== סינון שוק מת =====
#    if adx is not None and adx < 15:
#        return {
#            "signal": "NEUTRAL",
#            "score": final_score,
#            "raw_score": score,
#            "max_score": max_score,
#            "trend_bonus": trend_bonus
#        }

    # ===== החלטה =====
#    if suffix == "5M":
#        if final_score >= 2:
#            signal_final = "BUY"
#        elif final_score <= -2:
#            signal_final = "SELL"
#        else:
#            signal_final = "NEUTRAL"
#    else:
#        if final_score >= 3:
#            signal_final = "BUY"
#        elif final_score <= -3:
#            signal_final = "SELL"
#        else:
#            signal_final = "NEUTRAL"
#
#    return {
#        "signal": signal_final,
#        "score": round(final_score, 2),
#        "raw_score": round(score, 2),
#        "max_score": max_score,
#        "trend_bonus": trend_bonus
#    }

def normalize_score(score, max_abs=20):
    """
    ממיר score גולמי לטווח 0–100
    """
    normalized = (score + max_abs) / (2 * max_abs) * 100
    return max(0, min(100, round(normalized, 2)))


def get_combined_signal(daily, hourly, five_min):

    def safe(x):
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return None
        return float(x)

    def clamp(x, low=-1, high=1):
        return max(low, min(high, x))

    def norm(x, center=0, scale=1):
        if x is None:
            return 0
        return clamp((x - center) / scale)

    # =========================================
    # TIMEFRAMES
    # =========================================
    frames = [
        ("1D", daily, 3.0),
        ("1H", hourly, 2.0),
        ("5M", five_min, 1.0),
    ]

    total_score = 0
    total_weight = 0

    tf_scores = []

    momentum_sum = 0
    trend_sum = 0
    volatility_sum = 0

    bullish_weight = 0
    bearish_weight = 0

    adx_values = []

    details = {}

    # =========================================
    # LOOP
    # =========================================
    for tf, data, weight in frames:

        if not data:
            continue

        # =========================================
        # EXTRACT
        # =========================================
        rsi = safe(data.get(f"RSI_14_{tf}"))

        macd = safe(
            data.get(f"MACD_Line_{tf}") or
            data.get(f"MACD_Line[12,26]_{tf}")
        )

        signal = safe(
            data.get(f"Signal_Line_{tf}") or
            data.get(f"Signal_Line[12,26]_{tf}")
        )

        cci = safe(data.get(f"CCI_20_{tf}"))
        mfi = safe(data.get(f"MFI_14_{tf}"))
        roc = safe(data.get(f"ROC_10_{tf}"))

        adx = safe(data.get(f"ADX_14_{tf}"))

        ema20 = safe(data.get(f"EMA_20_{tf}"))
        ema50 = safe(data.get(f"EMA_50_{tf}"))

        price = safe(data.get(f"Close_{tf}"))

        atr = safe(data.get(f"ATR_14_{tf}"))

        if adx is not None:
            adx_values.append(adx)

        # =========================================
        # MOMENTUM
        # =========================================
        momentum_parts = []

        if rsi is not None:
            momentum_parts.append(
                norm(rsi, 50, 20)
            )

        if roc is not None:
            momentum_parts.append(
                norm(roc, 0, 4)
            )

        if macd is not None and signal is not None:
            momentum_parts.append(
                norm(macd - signal, 0, 0.8)
            )

        if cci is not None:
            momentum_parts.append(
                norm(cci, 0, 120)
            )

        if mfi is not None:
            momentum_parts.append(
                norm(mfi, 50, 25)
            )

        momentum = (
            np.mean(momentum_parts)
            if momentum_parts else 0
        )

        # =========================================
        # TREND
        # =========================================
        trend = 0

        if (
            ema20 is not None and
            ema50 is not None and
            price is not None
        ):

            ema_distance = (
                (ema20 - ema50) / ema50
            )

            price_distance = (
                (price - ema20) / ema20
            )

            trend = (
                ema_distance * 0.6 +
                price_distance * 0.4
            )

            trend = clamp(trend * 12)

        # =========================================
        # STRUCTURE
        # =========================================
        structure = 0

        if (
            ema20 is not None and
            ema50 is not None and
            price is not None
        ):

            if price > ema20 > ema50:
                structure = 1

            elif price < ema20 < ema50:
                structure = -1

            else:
                structure = 0

        # =========================================
        # VOLATILITY
        # =========================================
        volatility = 0

        if (
            atr is not None and
            price is not None and
            price != 0
        ):
            volatility = atr / price

        # =========================================
        # TREND STRENGTH (ADX)
        # =========================================
        trend_strength = 1

        if adx is not None:

            if adx > 40:
                trend_strength = 1.35

            elif adx > 25:
                trend_strength = 1.15

            elif adx < 18:
                trend_strength = 0.7

        # =========================================
        # REGIME
        # =========================================
        regime = "MIXED"

        if adx is not None and adx < 18:
            regime = "RANGE"

        elif volatility > 0.08:
            regime = "HIGH_VOL"

        elif abs(trend) > 0.4:
            regime = "TRENDING"

        # =========================================
        # DYNAMIC WEIGHTS
        # =========================================
        momentum_weight = 0.35
        trend_weight = 0.45
        structure_weight = 0.20

        if regime == "RANGE":
            momentum_weight = 0.55
            trend_weight = 0.25
            structure_weight = 0.20

        elif regime == "TRENDING":
            momentum_weight = 0.25
            trend_weight = 0.50
            structure_weight = 0.25

        # =========================================
        # TF SCORE
        # =========================================
        tf_score = (
            momentum * momentum_weight +
            trend * trend_weight +
            structure * structure_weight
        )

        # =========================================
        # APPLY ADX
        # =========================================
        tf_score *= trend_strength

        # =========================================
        # VOLATILITY PENALTY
        # =========================================
        volatility_penalty = 1

        if volatility > 0.06:
            volatility_penalty = 0.85

        if volatility > 0.10:
            volatility_penalty = 0.70

        tf_score *= volatility_penalty

        # =========================================
        # FINAL CLAMP
        # =========================================
        tf_score = clamp(tf_score)

        # =========================================
        # STORE
        # =========================================
        tf_scores.append(tf_score)

        total_score += tf_score * weight
        total_weight += weight

        momentum_sum += momentum * weight
        trend_sum += trend * weight
        volatility_sum += volatility * weight

        if tf_score > 0.2:
            bullish_weight += weight

        elif tf_score < -0.2:
            bearish_weight += weight

        details[tf] = {
            "score": round(tf_score, 4),
            "momentum": round(momentum, 4),
            "trend": round(trend, 4),
            "structure": structure,
            "volatility": round(volatility, 4),
            "adx": adx,
            "regime": regime
        }

    # =========================================
    # NO DATA
    # =========================================
    if total_weight == 0:

        return {
            "signal": "NEUTRAL",
            "score": 50,
            "confidence": 0
        }

    # =========================================
    # GLOBAL
    # =========================================
    raw_score = total_score / total_weight

    momentum = momentum_sum / total_weight
    trend = trend_sum / total_weight
    volatility = volatility_sum / total_weight

    avg_adx = (
        sum(adx_values) / len(adx_values)
        if adx_values else 20
    )

    # =========================================
    # CONSENSUS
    # =========================================
    variance = np.var(tf_scores)

    consensus = (
        1 - min(variance / 0.5, 1)
    )

    agreement = (
        max(bullish_weight, bearish_weight)
        / total_weight
    )

    # =========================================
    # LOW TREND FILTER
    # =========================================
    if avg_adx < 15:

        return {
            "signal": "NEUTRAL",
            "score": 50,
            "raw_score": round(raw_score, 4),
            "confidence": 20,

            "momentum": round(momentum, 3),
            "trend": round(trend, 3),
            "volatility": round(volatility, 3),

            "adx": round(avg_adx, 2),
            "agreement": round(agreement, 3),
            "consensus": round(consensus, 3),

            "market_state": "RANGE",

            "details": details
        }

    # =========================================
    # CONFIDENCE
    # =========================================
    confidence = 0

    # signal strength
    confidence += min(
        abs(raw_score) * 45,
        45
    )

    # adx quality
    confidence += min(
        avg_adx,
        40
    ) * 0.6

    # timeframe agreement
    confidence += consensus * 25

    # lower volatility = higher confidence
    confidence += max(
        0,
        15 - (volatility * 100)
    )

    # =========================================
    # CONFIDENCE PENALTIES
    # =========================================
    if abs(raw_score) < 0.15:
        confidence *= 0.6

    if consensus < 0.4:
        confidence *= 0.7

    confidence = round(
        min(confidence, 100),
        2
    )

    # =========================================
    # SIGNAL
    # =========================================
    if raw_score >= 0.65:
        signal = "STRONG BUY"

    elif raw_score >= 0.30:
        signal = "BUY"

    elif raw_score <= -0.65:
        signal = "STRONG SELL"

    elif raw_score <= -0.30:
        signal = "SELL"

    else:
        signal = "NEUTRAL"

    # =========================================
    # MARKET STATE
    # =========================================
    if avg_adx < 20:

        market_state = "RANGE"

    elif volatility > 0.08:

        market_state = "HIGH VOLATILITY"

    elif trend > 0.35:

        market_state = "UPTREND"

    elif trend < -0.35:

        market_state = "DOWNTREND"

    else:

        market_state = "MIXED"

    # =========================================
    # SCORE (0-100)
    # =========================================
    score = (
        (raw_score + 1) * 40 +
        consensus * 15 +
        min(avg_adx / 50, 1) * 5
    )

    score = round(
        max(0, min(score, 100)),
        2
    )

    # =========================================
    # RETURN
    # =========================================
    return {

        "signal": signal,

        "score": score,

        "raw_score": round(raw_score, 4),

        "confidence": confidence,

        "momentum": round(momentum, 3),

        "trend": round(trend, 3),

        "volatility": round(volatility, 3),

        "adx": round(avg_adx, 2),

        "agreement": round(agreement, 3),

        "consensus": round(consensus, 3),

        "market_state": market_state,

        "details": details
    }


def fetch_all_market_data(symbol):
    now = int(time.time())

    daily_key = f"daily_{symbol}"
    hourly_key = f"hourly_{symbol}"
    m5_key = f"m5_{symbol}"

    daily_cached = cache_get_disk(daily_key)

    if daily_cached and now - daily_cached.get("timestamp",0) < 1800:

        daily = daily_cached["data"]

    else:

        daily = finnhub_client.stock_candles(
            symbol,
            "D",
            now - 200*86400,
            now
        )

        cache_set_disk(daily_key,{
            "timestamp": now,
            "data": daily
        })


    hourly_cached = cache_get_disk(hourly_key)

    if hourly_cached and now - hourly_cached.get("timestamp",0) < 300:

        hourly = hourly_cached["data"]

    else:

        hourly = finnhub_client.stock_candles(
            symbol,
            "60",
            now - 200*3600,
            now
        )

        cache_set_disk(hourly_key,{
            "timestamp": now,
            "data": hourly
        })


    m5_cached = cache_get_disk(m5_key)

    if m5_cached and now - m5_cached.get("timestamp",0) < 60:

        m5 = m5_cached["data"]

    else:

        m5 = finnhub_client.stock_candles(
        symbol,
        "5",
        now - 200*300,
        now
        )

        cache_set_disk(m5_key,{
            "timestamp": now,
            "data": m5
        })

    data = {
        "daily": daily,
        "hourly": hourly,
        "m5": m5
    }

    return data

# ===== FETCH FUNCTIONS FINNHUB =====
def fetch_stock_data(symbol, days=150):
    """Fetch historical stock data from Finnhub without cache"""
    try:
        now = int(time.time())
        from_time = now - days * 24 * 60 * 60

        candles = finnhub_client.stock_candles(
            symbol,
            'D',  # Daily candles
            from_time,
            now
        )

        if candles.get("s") != "ok":
            logger.warning("Finnhub returned no data for %s: %s", symbol, candles)
            return pd.DataFrame()

        df = pd.DataFrame({
            "Open": candles.get("o", []),
            "High": candles.get("h", []),
            "Low": candles.get("l", []),
            "Close": candles.get("c", []),
            "Volume": candles.get("v", [])
        })

        # המרת timestamps לאינדקס
        df.index = pd.to_datetime(candles.get("t", []), unit='s')

        # מיון
        df.sort_index(inplace=True)

        return df.tail(days)

    except Exception as e:
        logger.exception("Error fetching Finnhub historical data for %s: %s", symbol, e)
        return pd.DataFrame()

def fetch_intraday_data(symbol, interval="60", points=200):
    """Fetch intraday data from Finnhub"""
    try:
        # ===== המרת interval =====
        interval_map = {
            "1min": "1",
            "5min": "5",
            "15min": "15",
            "30min": "30",
            "60min": "60"
        }

        resolution = interval_map.get(interval, "60")

        now = int(time.time())
        from_time = now - points * int(resolution) * 60  # כמה אחורה להביא

        candles = finnhub_client.stock_candles(
            symbol,
            resolution,
            from_time,
            now
        )

        if candles.get("s") != "ok":
            logger.warning("Finnhub returned no intraday data for %s: %s", symbol, candles)
            return pd.DataFrame()

        df = pd.DataFrame({
            "High": candles.get("h", []),
            "Low": candles.get("l", []),
            "Close": candles.get("c", []),
            "Volume": candles.get("v", [])
        })

        # אינדקס זמן
        df.index = pd.to_datetime(candles.get("t", []), unit='s')

        df.sort_index(inplace=True)

        return df.tail(points)

    except Exception:
        logger.exception("Error fetching Finnhub intraday data for %s", symbol)
        return pd.DataFrame()


def fetch_finnhub_quote(symbol):
    """
    מחזיר מחירים מעודכנים מ-Finnhub:
    - Price
    - Previous Close
    - Day High / Low
    - שם המניה
    """

    result = {
        "Symbol": symbol,
        "Name": None,
        "Price": None,
        "Previous Close": None,
        "Day High": None,
        "Day Low": None
    }

    try:
        # ===== 1. Quote (מחירים) =====
        quote = finnhub_client.quote(symbol)

        if quote:
            # c = current price
            # pc = previous close
            # h = high
            # l = low
            result["Price"] = safe_float(quote.get("c"))
            result["Previous Close"] = safe_float(quote.get("pc"))
            result["Day High"] = safe_float(quote.get("h"))
            result["Day Low"] = safe_float(quote.get("l"))

        # ===== 3. fallback אם חסר מידע =====
        if result["Previous Close"] is None or result["Price"] is None:
            now = int(time.time())
            two_days_ago = now - 2 * 24 * 60 * 60

            candles = finnhub_client.stock_candles(
                symbol,
                'D',
                two_days_ago,
                now
            )

            if candles.get("s") == "ok" and len(candles["c"]) >= 2:
                closes = candles["c"]
                highs = candles["h"]
                lows = candles["l"]

                if result["Previous Close"] is None:
                    result["Previous Close"] = safe_float(closes[-2])

                if result["Price"] is None:
                    result["Price"] = safe_float(closes[-1])

                if result["Day High"] is None:
                    result["Day High"] = safe_float(highs[-1])

                if result["Day Low"] is None:
                    result["Day Low"] = safe_float(lows[-1])

        return result

    except Exception:
        logger.exception("Error fetching Finnhub quote for %s", symbol)
        return cached if cached else result


def build_indicator_set(df, suffix):
    if df.empty:
        return None

    rsi = RSI(df)
    stoch = StochRSI(df)
    williams = WilliamsR(df)
    adx = ADX(df)
    cci = CCI(df)

    ema20 = EMA(df, 20)
    ema50 = EMA(df, 50)

    bb_upper, bb_lower = BollingerBands(df)

    atr = ATR(df)
    mfi = MFI(df)
    roc = ROC(df)

    macd_line, signal_line = MACD(df)

    return {
        f"RSI_14_{suffix}": safe_calc(lambda x: rsi, df),
        f"StochRSI_14_{suffix}": safe_calc(lambda x: stoch, df),
        f"WilliamsR_14_{suffix}": safe_calc(lambda x: williams, df),
        f"ADX_14_{suffix}": safe_calc(lambda x: adx, df),
        f"CCI_20_{suffix}": safe_calc(lambda x: cci, df),

        f"EMA_20_{suffix}": safe_calc(lambda x: ema20, df),
        f"EMA_50_{suffix}": safe_calc(lambda x: ema50, df),

        f"Bollinger_Upper_{suffix}": safe_calc(lambda x: bb_upper, df),
        f"Bollinger_Lower_{suffix}": safe_calc(lambda x: bb_lower, df),

        f"ATR_14_{suffix}": safe_calc(lambda x: atr, df),
        f"MFI_14_{suffix}": safe_calc(lambda x: mfi, df),
        f"ROC_10_{suffix}": safe_calc(lambda x: roc, df),

        f"MACD_Line[12,26]_{suffix}": safe_calc(lambda x: macd_line, df),
        f"Signal_Line[12,26]_{suffix}": safe_calc(lambda x: signal_line, df),

        f"Close_{suffix}": safe_calc(lambda x: df["Close"], df)
    }


# ===== FLASK ROUTE =====
@app.after_request
def add_security_headers(response):
    if request.headers.get("X-Forwarded-Proto") == "https":
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


@app.route("/", methods=["GET","POST"])
def index():
    try:
        selected_stock = None
        stock_data = None
        calc_result = None
        hourly_result = None
        five_min_result = None
        data = None
        combined_signal = None

        file_path = os.path.join(PROJECT_FOLDER,"data.csv")

        if request.method=="POST":
            selected_stock = request.form.get("stock")
            if os.path.exists(file_path):
                try: df_csv = pd.read_csv(file_path); data = df_csv.to_dict(orient="records")
                except: logger.exception("Error reading CSV")
            if  selected_stock in stocks:
                symbol = stocks[selected_stock]

    # 2. 🔥 כאן נכנס השינוי שלך
                # 2. 🔥 כאן נכנס השינוי שלך
                market_data = fetch_all_market_data(symbol)
                quote = fetch_finnhub_quote(symbol)

                stock_data = {
                    "Symbol": symbol,
                    "Price": quote["Price"],
                    "Previous Close": quote["Previous Close"],
                    "Day High": quote["Day High"],
                    "Day Low": quote["Day Low"],
                    "Name": selected_stock
                }

                # --- DAILY ---
                hist = build_df(market_data["daily"])
                calc_result = build_indicator_set(hist, "1D")

                # --- HOURLY ---
                intraday = build_df(market_data["hourly"])
                hourly_result = build_indicator_set(intraday, "1H")

                # --- 5 MIN ---
                intraday_5m = build_df(market_data["m5"])
                five_min_result = build_indicator_set(intraday_5m, "5M")

                # ===== COMBINED SIGNAL =====

                if calc_result:  # חייב להיות לפחות daily
                    combined_signal = get_combined_signal(
                        daily=calc_result,
                        hourly=hourly_result if hourly_result else None,
                        five_min=five_min_result if five_min_result else None
                    )

        # ==== בדיקה ידנית של User-Agent במקום is_mobile ====
        user_agent = request.headers.get("User-Agent", "").lower()
        if "mobile" in user_agent or "android" in user_agent or "iphone" in user_agent:
            template = "mobile.html"
        else:
            template = "index.html"
        market = get_market_status()
        return render_template(
            template,
            stocks=stocks,
            selected_stock=selected_stock,
            stock_data=stock_data,
            calc_result=calc_result,
            hourly_result=hourly_result,
            five_min_result=five_min_result,
            data=data,
            market=market,
            combined_signal=combined_signal
        )

    except Exception:
        logger.exception("Unexpected error in index route")
        return "An unexpected error occurred. Please try again later.", 500

@app.route('/mavohim')
def mavohim():
    return render_template('mavohim.html')


# ======= ה-sitemap המותאם =======
from datetime import datetime

@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    pages = [
        {"loc": url_for('index', _external=True), "changefreq": "daily", "priority": 1.0},
        {"loc": url_for('mavohim', _external=True), "changefreq": "monthly", "priority": 0.8},
    ]
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for page in pages:
        sitemap_xml += "  <url>\n"
        sitemap_xml += f"    <loc>{page['loc']}</loc>\n"
        sitemap_xml += f"    <lastmod>{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}</lastmod>\n"
        sitemap_xml += f"    <changefreq>{page['changefreq']}</changefreq>\n"
        sitemap_xml += f"    <priority>{page['priority']}</priority>\n"
        sitemap_xml += "  </url>\n"

    sitemap_xml += '</urlset>'

    return Response(sitemap_xml, mimetype='application/xml')

@app.route("/quote/<symbol>")
def quote_api(symbol):
    """
    מחזיר JSON עם מחירי מניה מעודכנים (Price, Day High, Day Low)
    """
    try:
        data = fetch_finnhub_quote(symbol)
        return {
            "Price": data.get("Price"),
            "Day High": data.get("Day High"),
            "Day Low": data.get("Day Low"),
            "timestamp": int(time.time())
        }
    except Exception as e:
        logger.exception("Error fetching quote for %s", symbol)
        return {"error": str(e)}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))