# ============================================================
#  SISTEMA DE GESTIÓN ADMINISTRATIVA · multiempresa  (SIVAE v1.1)
# ============================================================
from secrets import token_hex
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from supabase import create_client
import generacion_documentos as gd

st.set_page_config(page_title="Sistema de gestión administrativa", page_icon="💎", layout="wide")
SUPABASE_URL = "https://tqgmapwcknhdydjkbdtj.supabase.co"
ZONA = "America/Bogota"

VINO, VINO_OSCURO = "#8B1E3F", "#6E1731"
MARFIL, MARFIL_OSC = "#F7F4EF", "#EDE7DD"
TEXTO, GRIS, LINEA = "#1F2430", "#6B7280", "#E0D9CD"
GRIS_CALIDO = "#B9AE9D"

ROLES = {"gerente": "Gerente", "administrador": "Administrador", "contable": "Contable / Financiero", "ventas": "Ventas"}
TODOS = list(ROLES)
PAGINAS = {
    "🏠 Inicio y Gráficos": TODOS, "📦 Inventario": TODOS, "💰 Registrar Venta (POS)": ["gerente", "administrador", "ventas"],
    "➕ Agregar Producto": ["gerente", "administrador"], "🛒 Compras y proveedores": ["gerente", "administrador", "contable"],
    "💳 Cuentas por pagar": ["gerente", "administrador", "contable"], "📊 Soporte Contable": ["gerente", "administrador", "contable"],
    "📚 Contabilidad": ["gerente", "administrador", "contable"], "📄 Comprobantes y descargas": TODOS,
    "👥 Equipo": ["gerente"], "⚙️ Panel Administrador": ["gerente", "administrador"],
}

def get_sb():
    if "sb" not in st.session_state: st.session_state["sb"] = create_client(SUPABASE_URL, st.secrets["SUPABASE_KEY"])
    return st.session_state["sb"]
sb = get_sb()

st.markdown(f"""
<style>
    .stApp {{ background-color: {MARFIL} !important; color: {TEXTO}; }}
    [data-testid="stSidebar"] {{ background-color: {MARFIL_OSC} !important; border-right: 1px solid {LINEA}; }}
    h1 {{ color: {TEXTO} !important; font-weight: 700; }}
    h2, h3 {{ color: {VINO} !important; }}
    div[data-testid="stMetric"] {{ background: #FFFFFF; padding: 16px 18px; border-radius: 12px; border: 1px solid {LINEA}; border-left: 4px solid {VINO}; }}
    div[data-testid="stMetric"] label {{ color: {GRIS} !important; }}
    div.stButton > button, div.stFormSubmitButton > button, div.stDownloadButton > button {{ background-color: {VINO} !important; color: #FFFFFF !important; border: 1px solid {VINO} !important; border-radius: 8px; font-weight: 600; }}
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {{ background-color: {VINO_OSCURO} !important; }}
    .stTextInput input, .stNumberInput input, .stDateInput input, .stTextArea textarea {{ background-color: #FFFFFF !important; color: {TEXTO} !important; border: 1px solid {LINEA} !important; }}
    div[data-baseweb="select"] > div {{ background-color: #FFFFFF !important; border: 1px solid {LINEA} !important; }}
    [data-testid="stExpander"] {{ background-color: #FFFFFF; border: 1px solid {LINEA}; border-radius: 10px; }}
    .stTabs [data-baseweb="tab"] {{ color: {GRIS}; }}
    .stTabs [aria-selected="true"] {{ color: {VINO} !important; }}
</style>
""", unsafe_allow_html=True)

def ahora_co(): return datetime.now(ZoneInfo(ZONA))
def hoy_co(): return ahora_co().date()
def dinero(x): return f"${float(x):,.0f}"
def msg_error(e): return getattr(e, "message", None) or str(e)

def estilo_fig(fig, alto=360):
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=alto, margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=-0.2), font=dict(color=TEXTO))
    fig.update_xaxes(gridcolor=LINEA); fig.update_yaxes(gridcolor=LINEA); return fig

def cargar(tabla):
    filas, ini = [], 0
    while True:
        r = sb.table(tabla).select("*").order("id").range(ini, ini + 999).execute()
        bloque = r.data or []
        filas += bloque
        if len(bloque) < 1000: break
        ini += 1000
    return pd.DataFrame(filas)

def inventario():
    df = cargar("Inventario")
    if df.empty: return pd.DataFrame(columns=["id", "nombre", "categoria", "precio", "costo", "stock"])
    if "nombre" not in df.columns and "producto" in df.columns: df = df.rename(columns={"producto": "nombre"})
    for c in ["nombre", "categoria"]:
        if c not in df.columns: df[c] = ""
    for c in ["precio", "costo", "stock"]:
        if c not in df.columns: df[c] = 0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df

def ventas():
    cols = ["fecha", "dia", "producto", "cantidad", "total", "costo_total"]
    df = cargar("Ventas")
    if df.empty: return pd.DataFrame({c: [] for c in cols}).assign(fecha=pd.to_datetime([]), dia=pd.to_datetime([]))
    raw = df["fecha"].astype(str)
    if raw.str.contains(r"(?:Z|[+-]\d{2}(?::?\d{2})?)$", regex=True).all(): df["fecha"] = pd.to_datetime(raw, utc=True).dt.tz_convert(ZONA).dt.tz_localize(None)
    else: df["fecha"] = pd.to_datetime(raw)
    df["dia"] = df["fecha"].dt.normalize()
    for c in ["cantidad", "total", "costo_unitario"]: df[c] = pd.to_numeric(df.get(c, 0), errors="coerce").fillna(0)
    df["costo_total"] = df["cantidad"] * df["costo_unitario"]
    return df

def gastos():
    df = cargar("Gastos")
    if df.empty: return pd.DataFrame({"fecha": pd.to_datetime([]), "tipo": [], "concepto": [], "monto": []})
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.normalize()
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0)
    return df

def equipo(): return pd.DataFrame(sb.table("miembros").select("*").order("creado_en").execute().data or [])

def filtrar(df, col, ini, fin):
    if df.empty: return df
    return df[(df[col] >= pd.Timestamp(ini)) & (df[col] <= pd.Timestamp(fin))]

def resumen(v, g, ini, fin):
    vv, gg = filtrar(v, "dia", ini, fin), filtrar(g, "fecha", ini, fin)
    ingresos = vv["total"].sum() if not vv.empty else 0; costo = vv["costo_total"].sum() if not vv.empty else 0
    fijos = gg.loc[gg["tipo"] == "Fijo", "monto"].sum() if not gg.empty else 0
    variables = gg.loc[gg["tipo"] == "Variable", "monto"].sum() if not gg.empty else 0
    bruta = ingresos - costo; neta = bruta - fijos - variables; n = len(vv)
    return {"Ingresos": ingresos, "Costo de ventas": costo, "Utilidad bruta": bruta, "Gastos fijos": fijos, "Gastos variables": variables, "Gastos totales": costo + fijos + variables, "Utilidad neta": neta, "Margen neto (%)": (neta / ingresos * 100) if ingresos else 0, "N.º de ventas": n, "Ticket promedio": (ingresos / n) if n else 0}

def periodos(opcion, hoy):
    if opcion == "Hoy vs ayer": return (hoy, hoy), (hoy - timedelta(1), hoy - timedelta(1))
    if opcion == "Últimos 7 días vs 7 anteriores": return (hoy - timedelta(6), hoy), (hoy - timedelta(13), hoy - timedelta(7))
    if opcion == "Mes actual vs mes anterior":
        ini = hoy.replace(day=1); fin_prev = ini - timedelta(1); ini_prev = fin_prev.replace(day=1); dias = (hoy - ini).days
        return (ini, hoy), (ini_prev, min(ini_prev + timedelta(dias), fin_prev))
    ini, fin = st.session_state["rango_personal"]; largo = (fin - ini).days
    return (ini, fin), (ini - timedelta(largo + 1), ini - timedelta(1))

def por_mes(df, col, rango, fecha, filtro=None):
    if df.empty: return pd.Series(0.0, index=rango)
    d = df if filtro is None else df[filtro(df)]
    if d.empty: return pd.Series(0.0, index=rango)
    return d.groupby(d[fecha].dt.to_period("M"))[col].sum().reindex(rango, fill_value=0.0)

def tendencia_mensual(v, g, meses=6):
    rango = pd.period_range(end=pd.Timestamp(hoy_co()).to_period("M"), periods=meses, freq="M")
    df = pd.DataFrame({"Ingresos": por_mes(v, "total", rango, "dia"), "Costo de ventas": por_mes(v, "costo_total", rango, "dia"), "Gastos fijos": por_mes(g, "monto", rango, "fecha", lambda d: d["tipo"] == "Fijo"), "Gastos variables": por_mes(g, "monto", rango, "fecha", lambda d: d["tipo"] == "Variable")})
    df["Utilidad neta"] = df["Ingresos"] - df["Costo de ventas"] - df["Gastos fijos"] - df["Gastos variables"]
    df.index = df.index.strftime("%b %Y"); return df

def serie_diaria(v, ini, fin):
    dias = pd.date_range(ini, fin); s = filtrar(v, "dia", ini, fin)
    if s.empty: return [0.0] * len(dias)
    return s.groupby("dia")["total"].sum().reindex(dias, fill_value=0.0).tolist()

def usuario_actual():
    try: return sb.auth.get_session().user if sb.auth.get_session() else None
    except: return None

def cargar_perfil(uid
