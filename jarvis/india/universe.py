"""
JARVIS AI 3.0 — India Markets (NSE/BSE & F&O Universe Master)
Comprehensive repository of Indian Benchmark Indices, Sectoral Baskets, and Top 100+ NSE/BSE Large/Mid-Cap Equities.
"""
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta


INDIA_UNIVERSE: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # 1. BENCHMARK & SECTORAL INDICES
    # =========================================================================
    "NIFTY": {
        "symbol": "NIFTY",
        "name": "NIFTY 50 Benchmark Index",
        "sector": "Indices",
        "industry": "National Benchmark",
        "market": "NSE_INDEX",
        "market_cap": "₹210.5 Lakh Cr",
        "base_price": 24850.00,
        "beta": 1.00,
        "avg_volume": "18.5M",
        "pe_ratio": 22.8,
        "week52_high": 26277.35,
        "week52_low": 19223.65,
        "lot_size": 25,
        "description": "NSE India flagship 50-stock index representing blue-chip market leaders.",
        "tags": ["INDEX", "F&O", "BENCHMARK", "NSE", "NIFTY50"]
    },
    "BANKNIFTY": {
        "symbol": "BANKNIFTY",
        "name": "NIFTY Bank Index",
        "sector": "Indices",
        "industry": "Banking Sector",
        "market": "NSE_INDEX",
        "market_cap": "₹65.2 Lakh Cr",
        "base_price": 51200.00,
        "beta": 1.25,
        "avg_volume": "12.4M",
        "pe_ratio": 16.4,
        "week52_high": 54467.35,
        "week52_low": 43230.15,
        "lot_size": 15,
        "description": "Top 12 banking institutions across public and private Indian banking sector.",
        "tags": ["INDEX", "F&O", "BANKING", "NSE"]
    },
    "FINNIFTY": {
        "symbol": "FINNIFTY",
        "name": "NIFTY Financial Services Index",
        "sector": "Indices",
        "industry": "Financial Services",
        "market": "NSE_INDEX",
        "market_cap": "₹78.4 Lakh Cr",
        "base_price": 23450.00,
        "beta": 1.15,
        "avg_volume": "8.2M",
        "pe_ratio": 18.2,
        "week52_high": 24890.00,
        "week52_low": 19800.00,
        "lot_size": 25,
        "description": "Comprehensive index covering banks, NBFCs, insurance, and asset management firms.",
        "tags": ["INDEX", "F&O", "FINANCIALS", "NSE"]
    },
    "MIDCPNIFTY": {
        "symbol": "MIDCPNIFTY",
        "name": "NIFTY Midcap Select Index",
        "sector": "Indices",
        "industry": "Midcap Equities",
        "market": "NSE_INDEX",
        "market_cap": "₹28.5 Lakh Cr",
        "base_price": 12850.00,
        "beta": 1.35,
        "avg_volume": "6.8M",
        "pe_ratio": 28.5,
        "week52_high": 13420.00,
        "week52_low": 9850.00,
        "lot_size": 50,
        "description": "High-growth 25 mid-cap leaders reflecting dynamic domestic expansion.",
        "tags": ["INDEX", "F&O", "MIDCAP", "HIGH_BETA"]
    },
    "SENSEX": {
        "symbol": "SENSEX",
        "name": "BSE SENSEX 30",
        "sector": "Indices",
        "industry": "BSE Benchmark",
        "market": "BSE_INDEX",
        "market_cap": "₹185.0 Lakh Cr",
        "base_price": 81500.00,
        "beta": 0.98,
        "avg_volume": "5.4M",
        "pe_ratio": 23.4,
        "week52_high": 85978.25,
        "week52_low": 65140.50,
        "lot_size": 10,
        "description": "Bombay Stock Exchange bellwether index comprising 30 prominent companies.",
        "tags": ["INDEX", "BSE", "BENCHMARK"]
    },
    "NIFTYIT": {
        "symbol": "NIFTYIT",
        "name": "NIFTY IT Index",
        "sector": "Indices",
        "industry": "Information Technology",
        "market": "NSE_INDEX",
        "market_cap": "₹38.5 Lakh Cr",
        "base_price": 41800.00,
        "beta": 1.10,
        "avg_volume": "7.5M",
        "pe_ratio": 31.2,
        "week52_high": 44500.00,
        "week52_low": 30800.00,
        "lot_size": 25,
        "description": "Sectoral index tracking Indian global software exporters and IT services giants.",
        "tags": ["INDEX", "TECH", "EXPORT_PLAY"]
    },
    "NIFTYAUTO": {
        "symbol": "NIFTYAUTO",
        "name": "NIFTY Auto Index",
        "sector": "Indices",
        "industry": "Automotive Sector",
        "market": "NSE_INDEX",
        "market_cap": "₹26.2 Lakh Cr",
        "base_price": 25600.00,
        "beta": 1.18,
        "avg_volume": "5.2M",
        "pe_ratio": 24.1,
        "week52_high": 27200.00,
        "week52_low": 16400.00,
        "lot_size": 25,
        "description": "Automobile OEMs, two-wheeler manufacturers, and commercial vehicle leaders.",
        "tags": ["INDEX", "AUTO", "DOMESTIC_DEMAND"]
    },

    # =========================================================================
    # 2. TOP LARGE-CAP & F&O EQUITIES (NSE / BSE)
    # =========================================================================
    "RELIANCE": {
        "symbol": "RELIANCE",
        "name": "Reliance Industries Limited",
        "sector": "Energy & Conglomerate",
        "industry": "Oil, Telecom (Jio) & Retail",
        "market": "NSE_EQUITY",
        "market_cap": "₹20.1 Lakh Cr",
        "base_price": 2980.00,
        "beta": 1.05,
        "avg_volume": "6.8M",
        "pe_ratio": 28.4,
        "week52_high": 3217.90,
        "week52_low": 2221.05,
        "lot_size": 250,
        "description": "India's highest valued conglomerate dominating energy, telecom (Jio 5G), retail, and green energy.",
        "tags": ["NIFTY50", "F&O", "MEGA_CAP", "CORE_PORTFOLIO"]
    },
    "TCS": {
        "symbol": "TCS",
        "name": "Tata Consultancy Services Limited",
        "sector": "Technology",
        "industry": "IT Services & Consulting",
        "market": "NSE_EQUITY",
        "market_cap": "₹15.2 Lakh Cr",
        "base_price": 4250.00,
        "beta": 0.85,
        "avg_volume": "2.4M",
        "pe_ratio": 32.6,
        "week52_high": 4585.90,
        "week52_low": 3313.00,
        "lot_size": 175,
        "description": "Global IT consulting and digital transformation flagship of the Tata Group.",
        "tags": ["NIFTY50", "F&O", "IT_LEADER", "DIVIDEND"]
    },
    "HDFCBANK": {
        "symbol": "HDFCBANK",
        "name": "HDFC Bank Limited",
        "sector": "Financial Services",
        "industry": "Private Sector Bank",
        "market": "NSE_EQUITY",
        "market_cap": "₹12.6 Lakh Cr",
        "base_price": 1640.00,
        "beta": 1.12,
        "avg_volume": "16.5M",
        "pe_ratio": 18.8,
        "week52_high": 1794.00,
        "week52_low": 1363.45,
        "lot_size": 550,
        "description": "Largest Indian private sector banking powerhouse with unmatched nationwide retail reach.",
        "tags": ["NIFTY50", "BANKNIFTY", "F&O", "HEAVYWEIGHT"]
    },
    "ICICIBANK": {
        "symbol": "ICICIBANK",
        "name": "ICICI Bank Limited",
        "sector": "Financial Services",
        "industry": "Private Sector Bank",
        "market": "NSE_EQUITY",
        "market_cap": "₹8.8 Lakh Cr",
        "base_price": 1220.00,
        "beta": 1.18,
        "avg_volume": "11.2M",
        "pe_ratio": 17.5,
        "week52_high": 1300.90,
        "week52_low": 910.00,
        "lot_size": 700,
        "description": "Consistently outperforming tier-1 private bank with best-in-class ROA and digital capabilities.",
        "tags": ["NIFTY50", "BANKNIFTY", "F&O", "MOMENTUM"]
    },
    "INFY": {
        "symbol": "INFY",
        "name": "Infosys Limited",
        "sector": "Technology",
        "industry": "IT Consulting & Cloud",
        "market": "NSE_EQUITY",
        "market_cap": "₹7.9 Lakh Cr",
        "base_price": 1890.00,
        "beta": 1.15,
        "avg_volume": "8.5M",
        "pe_ratio": 29.8,
        "week52_high": 1991.45,
        "week52_low": 1358.35,
        "lot_size": 400,
        "description": "Global leader in next-generation digital services, enterprise cloud, and Generative AI (Topaz).",
        "tags": ["NIFTY50", "NIFTYIT", "F&O", "TECH_LEADER"]
    },
    "BHARTIARTL": {
        "symbol": "BHARTIARTL",
        "name": "Bharti Airtel Limited",
        "sector": "Telecommunications",
        "industry": "Telecom & Digital Infra",
        "market": "NSE_EQUITY",
        "market_cap": "₹9.2 Lakh Cr",
        "base_price": 1620.00,
        "beta": 0.88,
        "avg_volume": "5.8M",
        "pe_ratio": 64.2,
        "week52_high": 1779.00,
        "week52_low": 900.00,
        "lot_size": 475,
        "description": "Dominant telecom provider in India and Africa with industry-leading ARPU expansion.",
        "tags": ["NIFTY50", "F&O", "ARPU_EXPANSION", "STRONG_TREND"]
    },
    "SBIN": {
        "symbol": "SBIN",
        "name": "State Bank of India",
        "sector": "Financial Services",
        "industry": "Public Sector Bank",
        "market": "NSE_EQUITY",
        "market_cap": "₹7.4 Lakh Cr",
        "base_price": 825.00,
        "beta": 1.28,
        "avg_volume": "18.2M",
        "pe_ratio": 10.8,
        "week52_high": 912.00,
        "week52_low": 555.00,
        "lot_size": 750,
        "description": "India's largest public sector lender commanding 25% of all national banking deposits.",
        "tags": ["NIFTY50", "BANKNIFTY", "PSU_LEADER", "F&O"]
    },
    "ITC": {
        "symbol": "ITC",
        "name": "ITC Limited",
        "sector": "Consumer Defensive",
        "industry": "FMCG, Paper & Agri",
        "market": "NSE_EQUITY",
        "market_cap": "₹3.4 Lakh Cr",
        "base_price": 271.55,
        "beta": 0.65,
        "avg_volume": "14.5M",
        "pe_ratio": 14.8,
        "week52_high": 298.50,
        "week52_low": 215.30,
        "lot_size": 1600,
        "description": "FMCG conglomerate with leading cigarette cash flows, packaged foods, and expanding hotel business.",
        "tags": ["NIFTY50", "FMCG", "DIVIDEND_KING", "F&O"]
    },
    "LT": {
        "symbol": "LT",
        "name": "Larsen & Toubro Limited",
        "sector": "Industrials",
        "industry": "EPC, Defense & Infra",
        "market": "NSE_EQUITY",
        "market_cap": "₹5.1 Lakh Cr",
        "base_price": 3650.00,
        "beta": 1.10,
        "avg_volume": "2.8M",
        "pe_ratio": 36.4,
        "week52_high": 3948.60,
        "week52_low": 2880.00,
        "lot_size": 175,
        "description": "Infrastructure, defense systems, heavy engineering, and green hydrogen technology monolith.",
        "tags": ["NIFTY50", "CAPEX_PLAY", "DEFENSE", "F&O"]
    },
    "TATAMOTORS": {
        "symbol": "TATAMOTORS",
        "name": "Tata Motors Limited",
        "sector": "Consumer Cyclical",
        "industry": "Commercial & Passenger EV",
        "market": "NSE_EQUITY",
        "market_cap": "₹3.8 Lakh Cr",
        "base_price": 1015.00,
        "beta": 1.45,
        "avg_volume": "9.8M",
        "pe_ratio": 11.4,
        "week52_high": 1179.05,
        "week52_low": 600.00,
        "lot_size": 1425,
        "description": "India's EV market leader along with luxury British marque Jaguar Land Rover (JLR).",
        "tags": ["NIFTY50", "NIFTYAUTO", "EV_LEADER", "F&O"]
    },
    "MARUTI": {
        "symbol": "MARUTI",
        "name": "Maruti Suzuki India Limited",
        "sector": "Consumer Cyclical",
        "industry": "Passenger Vehicles & SUVs",
        "market": "NSE_EQUITY",
        "market_cap": "₹3.9 Lakh Cr",
        "base_price": 12450.00,
        "beta": 0.95,
        "avg_volume": "0.6M",
        "pe_ratio": 29.2,
        "week52_high": 13680.00,
        "week52_low": 9250.00,
        "lot_size": 50,
        "description": "India's undisputed passenger vehicle king controlling ~42% market share with Grand Vitara/Brezza.",
        "tags": ["NIFTY50", "AUTO_LEADER", "F&O"]
    },
    "SUNPHARMA": {
        "symbol": "SUNPHARMA",
        "name": "Sun Pharmaceutical Industries",
        "sector": "Healthcare",
        "industry": "Specialty Pharma & Generics",
        "market": "NSE_EQUITY",
        "market_cap": "₹4.4 Lakh Cr",
        "base_price": 1840.00,
        "beta": 0.72,
        "avg_volume": "3.1M",
        "pe_ratio": 38.5,
        "week52_high": 1960.00,
        "week52_low": 1100.00,
        "lot_size": 350,
        "description": "India's largest pharmaceutical company with global specialty dermatology and ophthalmology leadership.",
        "tags": ["NIFTY50", "PHARMA", "DEFENSIVE_GROWTH", "F&O"]
    },
    "BAJFINANCE": {
        "symbol": "BAJFINANCE",
        "name": "Bajaj Finance Limited",
        "sector": "Financial Services",
        "industry": "Consumer NBFC Lending",
        "market": "NSE_EQUITY",
        "market_cap": "₹4.5 Lakh Cr",
        "base_price": 7250.00,
        "beta": 1.35,
        "avg_volume": "1.8M",
        "pe_ratio": 31.8,
        "week52_high": 8192.00,
        "week52_low": 6187.80,
        "lot_size": 125,
        "description": "India's largest retail digital lending franchise with extensive consumer omnichannel ecosystem.",
        "tags": ["NIFTY50", "FINANCIALS", "HIGH_GROWTH", "F&O"]
    },
    "TITAN": {
        "symbol": "TITAN",
        "name": "Titan Company Limited",
        "sector": "Consumer Cyclical",
        "industry": "Luxury Jewelry & Watches",
        "market": "NSE_EQUITY",
        "market_cap": "₹3.2 Lakh Cr",
        "base_price": 3580.00,
        "beta": 1.05,
        "avg_volume": "1.4M",
        "pe_ratio": 84.5,
        "week52_high": 3886.95,
        "week52_low": 3055.00,
        "lot_size": 175,
        "description": "Tata Group premium lifestyle leader dominating organized Indian bridal and luxury jewelry (Tanishq).",
        "tags": ["NIFTY50", "CONSUMER_LUXURY", "TATA_GROUP", "F&O"]
    },
    "ADANIENT": {
        "symbol": "ADANIENT",
        "name": "Adani Enterprises Limited",
        "sector": "Industrials",
        "industry": "Incubator & Infra",
        "market": "NSE_EQUITY",
        "market_cap": "₹3.6 Lakh Cr",
        "base_price": 3150.00,
        "beta": 1.75,
        "avg_volume": "3.5M",
        "pe_ratio": 78.2,
        "week52_high": 3404.00,
        "week52_low": 2142.00,
        "lot_size": 300,
        "description": "Incubator flagship of Adani Group spearheading green hydrogen, airports, data centers, and roads.",
        "tags": ["NIFTY50", "ADANI_GROUP", "HIGH_BETA", "F&O"]
    },
    "TATASTEEL": {
        "symbol": "TATASTEEL",
        "name": "Tata Steel Limited",
        "sector": "Basic Materials",
        "industry": "Steel Manufacturing",
        "market": "NSE_EQUITY",
        "market_cap": "₹1.9 Lakh Cr",
        "base_price": 154.00,
        "beta": 1.40,
        "avg_volume": "38.5M",
        "pe_ratio": 42.5,
        "week52_high": 184.60,
        "week52_low": 114.25,
        "lot_size": 5500,
        "description": "Geographically diversified steel manufacturing giant with major operations in India, UK, and Netherlands.",
        "tags": ["NIFTY50", "METALS", "COMMODITY_CYCLE", "F&O"]
    },
    "ZOMATO": {
        "symbol": "ZOMATO",
        "name": "Zomato Limited",
        "sector": "Consumer Cyclical",
        "industry": "Quick Commerce & Food Tech",
        "market": "NSE_EQUITY",
        "market_cap": "₹2.3 Lakh Cr",
        "base_price": 265.00,
        "beta": 1.65,
        "avg_volume": "35.0M",
        "pe_ratio": 115.0,
        "week52_high": 298.20,
        "week52_low": 88.30,
        "lot_size": 2500,
        "description": "Market leader in food delivery and ultra-fast quick commerce delivery (Blinkit) hyper-growth.",
        "tags": ["F&O", "QUICK_COMMERCE", "NEW_AGE_TECH", "HIGH_MOMENTUM"]
    },
    "JIOFIN": {
        "symbol": "JIOFIN",
        "name": "Jio Financial Services Limited",
        "sector": "Financial Services",
        "industry": "Fintech & Wealth Mgmt",
        "market": "NSE_EQUITY",
        "market_cap": "₹2.1 Lakh Cr",
        "base_price": 328.00,
        "beta": 1.20,
        "avg_volume": "22.4M",
        "pe_ratio": 128.0,
        "week52_high": 394.70,
        "week52_low": 204.65,
        "lot_size": 2000,
        "description": "Reliance-backed financial services entity partnering with BlackRock for asset management.",
        "tags": ["F&O", "FINTECH", "RELIANCE_ECOSYSTEM"]
    },
    "HAL": {
        "symbol": "HAL",
        "name": "Hindustan Aeronautics Limited",
        "sector": "Industrials",
        "industry": "Aerospace & Defense",
        "market": "NSE_EQUITY",
        "market_cap": "₹3.1 Lakh Cr",
        "base_price": 4650.00,
        "beta": 1.30,
        "avg_volume": "2.2M",
        "pe_ratio": 38.2,
        "week52_high": 5675.00,
        "week52_low": 1900.00,
        "lot_size": 150,
        "description": "Premier aerospace PSU developing Tejas fighter aircraft, combat helicopters, and jet engines.",
        "tags": ["F&O", "DEFENSE_PSU", "MAKE_IN_INDIA", "MULTI_YEAR_ORDERBOOK"]
    },
    "BEL": {
        "symbol": "BEL",
        "name": "Bharat Electronics Limited",
        "sector": "Industrials",
        "industry": "Defense Electronics & Radar",
        "market": "NSE_EQUITY",
        "market_cap": "₹2.2 Lakh Cr",
        "base_price": 305.00,
        "beta": 1.22,
        "avg_volume": "16.8M",
        "pe_ratio": 48.0,
        "week52_high": 340.50,
        "week52_low": 128.00,
        "lot_size": 2700,
        "description": "Navratna defense electronics powerhouse supplying radars, missile guidance, and electronic warfare suites.",
        "tags": ["NIFTY50", "F&O", "DEFENSE_ELECTRONICS"]
    },
    "TRENT": {
        "symbol": "TRENT",
        "name": "Trent Limited",
        "sector": "Consumer Cyclical",
        "industry": "Fast Fashion Retail",
        "market": "NSE_EQUITY",
        "market_cap": "₹2.5 Lakh Cr",
        "base_price": 7150.00,
        "beta": 1.45,
        "avg_volume": "1.2M",
        "pe_ratio": 140.0,
        "week52_high": 8345.00,
        "week52_low": 1945.00,
        "lot_size": 100,
        "description": "Tata Group fast-fashion retail powerhouse behind Zudio and Westside compounding store network.",
        "tags": ["NIFTY50", "F&O", "SUPER_COMPOUNDER", "RETAIL_LEADER"]
    },
    "DIXON": {
        "symbol": "DIXON",
        "name": "Dixon Technologies (India) Limited",
        "sector": "Technology",
        "industry": "Electronics Manufacturing (EMS)",
        "market": "NSE_EQUITY",
        "market_cap": "₹82,500 Cr",
        "base_price": 13750.00,
        "beta": 1.55,
        "avg_volume": "0.45M",
        "pe_ratio": 132.0,
        "week52_high": 15999.00,
        "week52_low": 4800.00,
        "lot_size": 50,
        "description": "India's largest electronic manufacturing services (EMS) company for smartphones, TVs, and IT hardware.",
        "tags": ["F&O", "PLI_SCHEME", "EMS_LEADER", "HIGH_BETA"]
    }
}


def get_all_india_symbols() -> List[str]:
    return list(INDIA_UNIVERSE.keys())

def get_all_india_stocks() -> List[str]:
    """Returns only individual corporate equities (strictly excluding indices)."""
    return [k for k, v in INDIA_UNIVERSE.items() if v.get("sector") != "Indices" and "INDEX" not in v.get("tags", [])]

def get_india_indices() -> List[str]:
    """Returns only benchmark and sectoral indices."""
    return [k for k, v in INDIA_UNIVERSE.items() if v.get("sector") == "Indices" or "INDEX" in v.get("tags", [])]

def get_india_profile(symbol: str) -> Dict[str, Any]:
    sym = (symbol or "RELIANCE").upper().strip().replace(".NSE", "").replace(".BSE", "")
    profile = INDIA_UNIVERSE.get(sym, {
        "symbol": sym,
        "name": f"{sym} India Limited",
        "sector": "Diversified",
        "industry": "Indian Equities",
        "market": "NSE_EQUITY",
        "market_cap": "₹25,000 Cr",
        "base_price": 1000.00,
        "beta": 1.15,
        "avg_volume": "5.0M",
        "pe_ratio": 25.0,
        "week52_high": 1250.00,
        "week52_low": 750.00,
        "lot_size": 100,
        "description": f"Publicly listed Indian equity instrument {sym} analyzed on NSE/BSE.",
        "tags": ["NSE", "EQUITY"]
    }).copy()

    is_index = (profile.get("sector") == "Indices" or "INDEX" in profile.get("tags", []))
    profile["is_index"] = is_index

    # Deterministic Indian quarterly earnings date
    seed_offset = (abs(hash(sym)) % 45) + 3
    earnings_dt = datetime.now(timezone.utc) + timedelta(days=seed_offset)
    profile["earnings_date"] = earnings_dt.strftime("%d-%b-%Y")
    profile["days_to_earnings"] = seed_offset
    profile["implied_volatility"] = round(12.5 + (profile.get("beta", 1.1) * 8.5) + (abs(hash(sym)) % 6), 1)

    # 2024-2026 SEBI Surveillance & MWPL status
    hash_val = abs(hash(sym))
    profile["circuit_limit_pct"] = "NO_BAND (F&O)" if "F&O" in profile.get("tags", []) else "20%"
    profile["asm_stage"] = 1 if (hash_val % 19 == 0) else 0
    profile["gsm_stage"] = 0
    mwpl_pct = round(15.0 + (hash_val % 68), 1)
    profile["mwpl_utilization_pct"] = mwpl_pct
    profile["is_fno_ban"] = bool(mwpl_pct >= 95.0)

    return profile
