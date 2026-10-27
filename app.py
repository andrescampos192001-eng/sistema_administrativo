# ============================================================
#  SISTEMA DE GESTIÓN ADMINISTRATIVA · multiempresa
#  Streamlit + Supabase (Auth + seguridad por filas)
# ============================================================
from secrets import token_hex
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Sistema de gestión administrativa", page_icon="💎", layout="wide")

SUPABASE_URL = "https://tqgmapwcknhdydjkbdtj.supabase.co"
ZONA = "America/Bogota"

AZUL, AZUL_CLARO, AZUL_OSCURO = "#3b82f6", "#60a5fa", "#1e3a8a"
GRIS, GRIS_CLARO = "#64748b", "#cbd5e1"

ROLES = {
    "gerente": "Gerente",
    "administrador": "Administrador",
    "contable": "Contable / Financiero",
    "ventas": "Ventas",
}
TODOS = list(ROLES)
PAGINAS = {
    "🏠 Inicio y Gráficos": TODOS,
    "📦 Inventario": TODOS,
    "💰 Registrar Venta (POS)": ["gerente", "administrador", "ventas"],
    "➕ Agregar Producto": ["gerente", "administrador"],
    "📊 Soporte Contable": ["gerente", "administrador", "contable"],
    "👥 Equipo": ["gerente"],
    "⚙️ Panel Administrador": ["gerente", "administrador"],
}

# ------------------------------------------------------------
#  Conexión: UN cliente por sesión de navegador (nunca compartido)
# ------------------------------------------------------------
def get_sb():
    if "sb" not in st.session_state:
        st.session_state["sb"] = create_client(SUPABASE_URL, st.secrets["SUPABASE_KEY"])
    return st.session_state["sb"]


sb = get_sb()

# ------------------------------------------------------------
#  Estilos
# ------------------------------------------------------------
st.markdown(
    f"""
<style>
    .stApp {{ background-color: #0b0f19 !important; color: #e5e7eb; }}
    [data-testid="stSidebar"] {{ background-color: #05070c !important; border-right: 1px solid #1f2937; }}
    h1 {{ color: #f1f5f9 !important; font-weight: 700; letter-spacing: .3px; }}
    h2, h3 {{ color: {AZUL_CLARO} !important; }}
    div[data-testid="stMetric"] {{
        background: linear-gradient(145deg, #111827, #0f172a);
        padding: 16px 18px; border-radius: 12px;
        border: 1px solid #1f2a44; border-left: 4px solid {AZUL};
    }}
    div[data-testid="stMetric"] label {{ color: {GRIS_CLARO} !important; }}
    div.stButton > button, div.stFormSubmitButton > button, div.stDownloadButton > button {{
        background-color: {AZUL_OSCURO} !important; color: #fff !important;
        border: 1px solid {AZUL} !important; border-radius: 8px; font-weight: 600;
    }}
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {{ background-color: {AZUL} !important; }}
    .stTextInput input, .stNumberInput input, .stDateInput input, .stTextArea textarea {{
        background-color: #111827 !important; color: #e5e7eb !important; border: 1px solid #1f2a44 !important;
    }}
    div[data-baseweb="select"] > div {{ background-color: #111827 !important; border: 1px solid #1f2a44 !important; }}
    [data-testid="stExpander"] {{ background-color: #0f172a; border: 1px solid #1f2a44; border-radius: 10px; }}
    .stTabs [data-baseweb="tab"] {{ color: {GRIS_CLARO}; }}
    .stTabs [aria-selected="true"] {{ color: {AZUL_CLARO} !important; }}
    hr {{ border-color: #1f2937; }}
</style>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
#  Utilidades
# ------------------------------------------------------------
def ahora_co():
    """Fecha y hora actuales de Colombia (el servidor de Streamlit usa UTC)."""
    return datetime.now(ZoneInfo(ZONA))


def hoy_co():
    return ahora_co().date()


def dinero(x):
    return f"${x:,.0f}"


def msg_error(e):
    return getattr(e, "message", None) or str(e)


def variacion(actual, anterior):
    if not anterior:
        return None
    return (actual - anterior) / abs(anterior) * 100


def estilo_fig(fig, alto=360):
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=alto, margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=-0.2), font=dict(color=GRIS_CLARO),
    )
    fig.update_xaxes(gridcolor="#1f2937")
    fig.update_yaxes(gridcolor="#1f2937")
    return fig


# ------------------------------------------------------------
#  Datos (siempre filtrados por la base de datos según el usuario)
#  Sin caché compartida: así nunca se mezcla información entre empresas.
# ------------------------------------------------------------
def cargar(tabla):
    filas, ini = [], 0
    while True:
        r = sb.table(tabla).select("*").order("id").range(ini, ini + 999).execute()
        bloque = r.data or []
        filas += bloque
        if len(bloque) < 1000:
            break
        ini += 1000
    return pd.DataFrame(filas)


def inventario():
    df = cargar("Inventario")
    if df.empty:
        return pd.DataFrame(columns=["id", "nombre", "categoria", "precio", "costo", "stock"])
    if "nombre" not in df.columns and "producto" in df.columns:
        df = df.rename(columns={"producto": "nombre"})
    for c in ["nombre", "categoria"]:
        if c not in df.columns:
            df[c] = ""
    for c in ["precio", "costo", "stock"]:
        if c not in df.columns:
            df[c] = 0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def ventas():
    cols = ["fecha", "dia", "producto", "cantidad", "total", "costo_total"]
    df = cargar("Ventas")
    if df.empty:
        return pd.DataFrame({c: [] for c in cols}).assign(
            fecha=pd.to_datetime([]), dia=pd.to_datetime([]))
    raw = df["fecha"].astype(str)
    con_zona = raw.str.contains(r"(?:Z|[+-]\d{2}(?::?\d{2})?)$", regex=True).all()
    if con_zona:
        df["fecha"] = pd.to_datetime(raw, utc=True).dt.tz_convert(ZONA).dt.tz_localize(None)
    else:
        df["fecha"] = pd.to_datetime(raw)
    df["dia"] = df["fecha"].dt.normalize()
    for c in ["cantidad", "total", "costo_unitario"]:
        df[c] = pd.to_numeric(df.get(c, 0), errors="coerce").fillna(0)
    df["costo_total"] = df["cantidad"] * df["costo_unitario"]
    return df


def gastos():
    df = cargar("Gastos")
    if df.empty:
        return pd.DataFrame({"fecha": pd.to_datetime([]), "tipo": [], "concepto": [], "monto": []})
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.normalize()
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0)
    return df


def equipo():
    r = sb.table("miembros").select("*").order("creado_en").execute()
    return pd.DataFrame(r.data or [])


def filtrar(df, col, ini, fin):
    if df.empty:
        return df
    return df[(df[col] >= pd.Timestamp(ini)) & (df[col] <= pd.Timestamp(fin))]


def resumen(v, g, ini, fin):
    vv, gg = filtrar(v, "dia", ini, fin), filtrar(g, "fecha", ini, fin)
    ingresos = vv["total"].sum() if not vv.empty else 0
    costo = vv["costo_total"].sum() if not vv.empty else 0
    fijos = gg.loc[gg["tipo"] == "Fijo", "monto"].sum() if not gg.empty else 0
    variables = gg.loc[gg["tipo"] == "Variable", "monto"].sum() if not gg.empty else 0
    bruta = ingresos - costo
    neta = bruta - fijos - variables
    n = len(vv)
    return {
        "Ingresos": ingresos, "Costo de ventas": costo, "Utilidad bruta": bruta,
        "Gastos fijos": fijos, "Gastos variables": variables,
        "Gastos totales": costo + fijos + variables, "Utilidad neta": neta,
        "Margen neto (%)": (neta / ingresos * 100) if ingresos else 0,
        "N.º de ventas": n, "Ticket promedio": (ingresos / n) if n else 0,
    }


def periodos(opcion, hoy):
    if opcion == "Hoy vs ayer":
        return (hoy, hoy), (hoy - timedelta(1), hoy - timedelta(1))
    if opcion == "Últimos 7 días vs 7 anteriores":
        return (hoy - timedelta(6), hoy), (hoy - timedelta(13), hoy - timedelta(7))
    if opcion == "Mes actual vs mes anterior":
        ini = hoy.replace(day=1)
        fin_prev = ini - timedelta(1)
        ini_prev = fin_prev.replace(day=1)
        dias = (hoy - ini).days
        return (ini, hoy), (ini_prev, min(ini_prev + timedelta(dias), fin_prev))
    ini, fin = st.session_state["rango_personal"]
    largo = (fin - ini).days
    return (ini, fin), (ini - timedelta(largo + 1), ini - timedelta(1))


def por_mes(df, col, rango, fecha, filtro=None):
    if df.empty:
        return pd.Series(0.0, index=rango)
    d = df if filtro is None else df[filtro(df)]
    if d.empty:
        return pd.Series(0.0, index=rango)
    return d.groupby(d[fecha].dt.to_period("M"))[col].sum().reindex(rango, fill_value=0.0)


def tendencia_mensual(v, g, meses=6):
    rango = pd.period_range(end=pd.Timestamp(hoy_co()).to_period("M"), periods=meses, freq="M")
    df = pd.DataFrame({
        "Ingresos": por_mes(v, "total", rango, "dia"),
        "Costo de ventas": por_mes(v, "costo_total", rango, "dia"),
        "Gastos fijos": por_mes(g, "monto", rango, "fecha", lambda d: d["tipo"] == "Fijo"),
        "Gastos variables": por_mes(g, "monto", rango, "fecha", lambda d: d["tipo"] == "Variable"),
    })
    df["Utilidad neta"] = df["Ingresos"] - df["Costo de ventas"] - df["Gastos fijos"] - df["Gastos variables"]
    df.index = df.index.strftime("%b %Y")
    return df


def serie_diaria(v, ini, fin):
    dias = pd.date_range(ini, fin)
    s = filtrar(v, "dia", ini, fin)
    if s.empty:
        return [0.0] * len(dias)
    return s.groupby("dia")["total"].sum().reindex(dias, fill_value=0.0).tolist()


# ------------------------------------------------------------
#  Autenticación
# ------------------------------------------------------------
def usuario_actual():
    try:
        ses = sb.auth.get_session()  # renueva el token si venció
        return ses.user if ses else None
    except Exception:
        return None


def cargar_perfil(uid):
    r = (sb.table("miembros")
         .select("rol,nombre,empresa_id,activo,empresas(nombre)")
         .eq("user_id", uid).execute())
    return r.data[0] if r.data else None


def cerrar_sesion():
    try:
        sb.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()


def pantalla_acceso():
    _, centro, _ = st.columns([1, 1.4, 1])
    with centro:
        st.write("")
        st.markdown("## 💎 Sistema de gestión administrativa")
        st.caption("Inventario, ventas y contabilidad para tu empresa")
        t1, t2 = st.tabs(["Ingresar", "Crear cuenta"])

        with t1:
            with st.form("login"):
                correo = st.text_input("Correo electrónico")
                clave = st.text_input("Contraseña", type="password")
                enviar = st.form_submit_button("Ingresar", use_container_width=True)
            if enviar:
                ok = False
                try:
                    sb.auth.sign_in_with_password({"email": correo.strip(), "password": clave})
                    ok = True
                except Exception as e:
                    if "not confirmed" in msg_error(e).lower():
                        st.error("Debes confirmar tu correo antes de ingresar. Revisa tu bandeja de entrada.")
                    else:
                        st.error("Correo o contraseña incorrectos.")
                if ok:
                    st.rerun()

        with t2:
            with st.form("registro"):
                correo = st.text_input("Correo electrónico", key="reg_correo")
                clave = st.text_input("Contraseña (mínimo 8 caracteres)", type="password", key="reg_clave")
                clave2 = st.text_input("Repite la contraseña", type="password", key="reg_clave2")
                enviar = st.form_submit_button("Crear cuenta", use_container_width=True)
            if enviar:
                if "@" not in correo or "." not in correo:
                    st.error("Escribe un correo válido.")
                elif len(clave) < 8:
                    st.error("La contraseña debe tener al menos 8 caracteres.")
                elif clave != clave2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    ok = False
                    try:
                        res = sb.auth.sign_up({"email": correo.strip(), "password": clave})
                        if res.session:
                            ok = True
                        else:
                            st.success("Cuenta creada. Confirma tu correo desde el mensaje que te enviamos "
                                       "y luego ingresa.")
                    except Exception as e:
                        st.error(msg_error(e))
                    if ok:
                        st.rerun()


def pantalla_onboarding(user):
    _, centro, _ = st.columns([1, 1.4, 1])
    with centro:
        st.write("")
        st.markdown("## Bienvenido")
        st.caption(f"Sesión iniciada como {user.email}")
        t1, t2 = st.tabs(["🏢 Crear mi empresa", "🔑 Unirme con código"])

        with t1:
            st.caption("Serás el gerente de la empresa y podrás invitar a tu equipo.")
            with st.form("crear_empresa"):
                empresa = st.text_input("Nombre de la empresa")
                nombre = st.text_input("Tu nombre")
                enviar = st.form_submit_button("Crear empresa", use_container_width=True)
            if enviar:
                ok = False
                try:
                    sb.rpc("crear_empresa", {"p_nombre": empresa, "p_nombre_usuario": nombre}).execute()
                    ok = True
                except Exception as e:
                    st.error(msg_error(e))
                if ok:
                    st.rerun()

        with t2:
            st.caption("Pide al gerente de tu empresa un código de invitación.")
            with st.form("unirse"):
                codigo = st.text_input("Código de invitación")
                nombre = st.text_input("Tu nombre", key="nombre_union")
                enviar = st.form_submit_button("Unirme a la empresa", use_container_width=True)
            if enviar:
                ok = False
                try:
                    sb.rpc("unirse_con_invitacion", {"p_codigo": codigo, "p_nombre_usuario": nombre}).execute()
                    ok = True
                except Exception as e:
                    st.error(msg_error(e))
                if ok:
                    st.rerun()

        if st.button("Cerrar sesión"):
            cerrar_sesion()
            st.rerun()


user = usuario_actual()
if user is None:
    pantalla_acceso()
    st.stop()

perfil = cargar_perfil(user.id)
if perfil is None:
    pantalla_onboarding(user)
    st.stop()
if not perfil["activo"]:
    st.error("Tu cuenta fue desactivada por el gerente de la empresa.")
    if st.button("Cerrar sesión"):
        cerrar_sesion()
        st.rerun()
    st.stop()

rol = perfil["rol"]
empresa_nombre = (perfil.get("empresas") or {}).get("nombre", "")

# ------------------------------------------------------------
#  Menú lateral (según el rol)
# ------------------------------------------------------------
st.sidebar.markdown(f"## 💎 {empresa_nombre}")
st.sidebar.caption(f"👤 {perfil['nombre'] or user.email} · {ROLES[rol]}")
st.sidebar.caption(f"📅 {ahora_co():%d/%m/%Y} · 🕒 {ahora_co():%I:%M %p}")
menu = st.sidebar.radio(
    "MENÚ", [p for p, roles in PAGINAS.items() if rol in roles], label_visibility="collapsed")
if st.sidebar.button("🔒 Cerrar sesión"):
    cerrar_sesion()
    st.rerun()

if "carrito" not in st.session_state:
    st.session_state["carrito"] = []
if "msg" in st.session_state:
    st.success(st.session_state.pop("msg"))

# ============================================================
#  INICIO
# ============================================================
if menu == "🏠 Inicio y Gráficos":
    st.title(empresa_nombre or "Inicio")
    st.subheader("Dashboard gerencial")

    inv, v, g = inventario(), ventas(), gastos()
    hoy = hoy_co()
    mes = resumen(v, g, hoy.replace(day=1), hoy)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Modelos de productos", len(inv))
    c2.metric("🧮 Unidades en stock", f"{int(inv['stock'].sum()):,}")
    if rol == "ventas":
        c3.metric("💰 Mis ventas del mes", dinero(mes["Ingresos"]))
        c4.metric("🧾 N.º de ventas del mes", mes["N.º de ventas"])
    else:
        c3.metric("💰 Ingresos del mes", dinero(mes["Ingresos"]))
        c4.metric("📈 Utilidad neta del mes", dinero(mes["Utilidad neta"]))

    st.write("")
    izq, der = st.columns(2)
    with izq:
        st.markdown("### Ingresos de los últimos 30 días")
        ini = hoy - timedelta(29)
        dias = pd.date_range(ini, hoy)
        fig = go.Figure(go.Scatter(x=dias, y=serie_diaria(v, ini, hoy), mode="lines", fill="tozeroy",
                                   line=dict(color=AZUL_CLARO, width=2.5),
                                   fillcolor="rgba(59,130,246,0.15)"))
        st.plotly_chart(estilo_fig(fig), use_container_width=True)
    with der:
        st.markdown("### Productos más vendidos (mes)")
        vm = filtrar(v, "dia", hoy.replace(day=1), hoy)
        if vm.empty:
            st.info("Aún no hay ventas registradas este mes.")
        else:
            top = vm.groupby("producto")["total"].sum().nlargest(5).sort_values()
            fig = go.Figure(go.Bar(x=top.values, y=top.index, orientation="h", marker_color=AZUL))
            st.plotly_chart(estilo_fig(fig), use_container_width=True)

    if rol != "ventas":
        vm = filtrar(v, "dia", hoy.replace(day=1), hoy)
        if not vm.empty and "vendedor_id" in vm.columns:
            st.markdown("### Ventas por persona del equipo (mes)")
            eq = equipo()
            nombres = dict(zip(eq["user_id"], eq["nombre"].fillna(eq["correo"]))) if not eq.empty else {}
            vm = vm.assign(vendedor=vm["vendedor_id"].map(nombres).fillna("Sin asignar"))
            por = vm.groupby("vendedor")["total"].sum().sort_values()
            fig = go.Figure(go.Bar(x=por.values, y=por.index, orientation="h", marker_color=AZUL_CLARO))
            st.plotly_chart(estilo_fig(fig, 300), use_container_width=True)

    bajos = inv[inv["stock"] <= 5]
    if not bajos.empty:
        st.warning(f"⚠️ {len(bajos)} producto(s) con stock bajo (≤ 5 unidades).")
        st.dataframe(bajos[["nombre", "stock"]], use_container_width=True, hide_index=True)

# ============================================================
#  AGREGAR PRODUCTO
# ============================================================
elif menu == "➕ Agregar Producto":
    st.title("➕ Agregar producto")
    with st.form("nuevo_producto", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre del producto")
        categoria = c2.text_input("Categoría")
        c3, c4, c5 = st.columns(3)
        costo = c3.number_input("Costo unitario ($)", min_value=0.0, step=100.0)
        precio = c4.number_input("Precio de venta ($)", min_value=0.0, step=100.0)
        stock = c5.number_input("Stock inicial", min_value=0, step=1)
        enviar = st.form_submit_button("Guardar producto")
    if enviar:
        if not nombre.strip():
            st.error("El nombre es obligatorio.")
        else:
            try:
                sb.table("Inventario").insert({
                    "nombre": nombre.strip(), "categoria": categoria.strip(),
                    "costo": costo, "precio": precio, "stock": int(stock)}).execute()
                st.success(f"Producto «{nombre}» guardado.")
            except Exception as e:
                st.error(msg_error(e))

# ============================================================
#  INVENTARIO
# ============================================================
elif menu == "📦 Inventario":
    st.title("📦 Inventario")
    inv = inventario()
    if inv.empty:
        st.info("No hay productos registrados.")
    else:
        buscar = st.text_input("🔎 Buscar producto")
        vista = inv[inv["nombre"].str.contains(buscar, case=False, na=False)] if buscar else inv
        vista = vista.drop(columns=[c for c in ["empresa_id"] if c in vista.columns])
        c1, c2, c3 = st.columns(3)
        c1.metric("Modelos", len(vista))
        c2.metric("Unidades", f"{int(vista['stock'].sum()):,}")
        if rol == "ventas":
            vista = vista.drop(columns=["costo"])
        else:
            c3.metric("Valor del inventario (costo)", dinero((vista["costo"] * vista["stock"]).sum()))
        st.dataframe(vista, use_container_width=True, hide_index=True)

# ============================================================
#  PUNTO DE VENTA
# ============================================================
elif menu == "💰 Registrar Venta (POS)":
    st.title("💰 Registrar venta")
    inv = inventario()
    disp = inv[inv["stock"] > 0]

    with st.expander("👤 Datos del cliente", expanded=True):
        c1, c2 = st.columns(2)
        cliente = c1.text_input("Nombre y apellido")
        doc = c2.text_input("Documento de identidad")
        direccion = st.text_input("Dirección")
        c3, c4, c5 = st.columns(3)
        ciudad = c3.text_input("Ciudad")
        pais = c4.text_input("País", value="Colombia")
        iva = c5.selectbox("¿Responsable de IVA?", ["No", "Sí"])

    st.subheader("🛍️ Carrito y ajustes")
    if disp.empty:
        st.warning("No hay productos con stock disponible.")
    else:
        c_prod, c_cant, c_desc = st.columns(3)
        nombre_sel = c_prod.selectbox("Producto", disp["nombre"].tolist())
        fila = disp[disp["nombre"] == nombre_sel].iloc[0]
        ya = sum(l["cantidad"] for l in st.session_state["carrito"] if l["id"] == int(fila["id"]))
        maximo = int(fila["stock"]) - ya
        c_prod.caption(f"Precio: {dinero(fila['precio'])} · Disponible: {maximo}")
        cantidad = c_cant.number_input("Cantidad", min_value=1, max_value=max(maximo, 1), value=1)
        desc_op = c_desc.selectbox("Descuento (%)", [0, 5, 10, 15, 20, "Personalizado"])
        desc = c_desc.number_input("Descuento personalizado (%)", 0.0, 100.0, 0.0) \
            if desc_op == "Personalizado" else float(desc_op)

        if st.button("Agregar a la factura"):
            if maximo < 1:
                st.error("Ya agregaste todo el stock disponible de este producto.")
            else:
                st.session_state["carrito"].append({
                    "id": int(fila["id"]), "producto": nombre_sel, "cantidad": int(cantidad),
                    "precio": float(fila["precio"]), "descuento": float(desc),
                    "total": round(cantidad * float(fila["precio"]) * (1 - desc / 100), 2)})
                st.rerun()

    st.write("---")
    carrito = st.session_state["carrito"]
    if carrito:
        st.dataframe(pd.DataFrame(carrito)[["producto", "cantidad", "precio", "descuento", "total"]],
                     use_container_width=True, hide_index=True)
    total_neto = sum(l["total"] for l in carrito)
    st.markdown(f"### 🧾 Total neto a pagar: {dinero(total_neto)}")

    b1, b2, _ = st.columns([1, 1, 3])
    if b1.button("Vaciar carrito"):
        st.session_state["carrito"] = []
        st.rerun()
    if b2.button("✅ Confirmar venta", disabled=not carrito):
        ok = False
        try:
            res = sb.rpc("registrar_venta", {
                "p_cliente": {"cliente": cliente, "documento": doc, "direccion": direccion,
                              "ciudad": ciudad, "pais": pais, "responsable_iva": iva},
                "p_items": [{"id": l["id"], "cantidad": l["cantidad"], "descuento": l["descuento"]}
                            for l in carrito]}).execute()
            st.session_state["carrito"] = []
            st.session_state["msg"] = (f"Venta registrada por {dinero(float(res.data))}. "
                                       "Inventario e ingresos actualizados.")
            ok = True
        except Exception as e:
            st.error(msg_error(e))
        if ok:
            st.rerun()

# ============================================================
#  SOPORTE CONTABLE
# ============================================================
elif menu == "📊 Soporte Contable":
    st.title("📊 Soporte contable")
    v, g = ventas(), gastos()
    hoy = hoy_co()
    tab1, tab2, tab3 = st.tabs(["📈 Análisis comparativo", "🧾 Registrar gasto", "📒 Libro de movimientos"])

    with tab1:
        opcion = st.selectbox("Comparar", ["Mes actual vs mes anterior", "Hoy vs ayer",
                                           "Últimos 7 días vs 7 anteriores", "Rango personalizado"])
        if opcion == "Rango personalizado":
            st.session_state["rango_personal"] = (hoy.replace(day=1), hoy)
            r = st.date_input("Rango", value=(hoy.replace(day=1), hoy))
            if isinstance(r, tuple) and len(r) == 2:
                st.session_state["rango_personal"] = r
        (a_ini, a_fin), (p_ini, p_fin) = periodos(opcion, hoy)
        st.caption(f"Actual: {a_ini:%d/%m/%Y} – {a_fin:%d/%m/%Y}  ·  Anterior: {p_ini:%d/%m/%Y} – {p_fin:%d/%m/%Y}")

        act, ant = resumen(v, g, a_ini, a_fin), resumen(v, g, p_ini, p_fin)

        def tarjeta(col, nombre, inverso=False):
            var = variacion(act[nombre], ant[nombre])
            col.metric(nombre, dinero(act[nombre]),
                       delta=None if var is None else f"{var:+.1f}%",
                       delta_color="inverse" if inverso else "normal")

        m = st.columns(4)
        tarjeta(m[0], "Ingresos")
        tarjeta(m[1], "Utilidad bruta")
        tarjeta(m[2], "Gastos totales", inverso=True)
        tarjeta(m[3], "Utilidad neta")
        m2 = st.columns(4)
        tarjeta(m2[0], "Gastos fijos", inverso=True)
        tarjeta(m2[1], "Gastos variables", inverso=True)
        tarjeta(m2[2], "Costo de ventas", inverso=True)
        m2[3].metric("Margen neto", f"{act['Margen neto (%)']:.1f}%",
                     delta=f"{act['Margen neto (%)'] - ant['Margen neto (%)']:+.1f} pp")

        st.markdown("### Detalle comparativo")
        filas = []
        for k in ["Ingresos", "Costo de ventas", "Utilidad bruta", "Gastos fijos", "Gastos variables",
                  "Gastos totales", "Utilidad neta", "Ticket promedio"]:
            var = variacion(act[k], ant[k])
            filas.append({"Indicador": k, "Actual": dinero(act[k]), "Anterior": dinero(ant[k]),
                          "Diferencia": dinero(act[k] - ant[k]),
                          "Variación": "—" if var is None else f"{var:+.1f}%"})
        filas.append({"Indicador": "N.º de ventas", "Actual": act["N.º de ventas"], "Anterior": ant["N.º de ventas"],
                      "Diferencia": act["N.º de ventas"] - ant["N.º de ventas"], "Variación": "—"})
        st.dataframe(pd.DataFrame(filas).astype(str), use_container_width=True, hide_index=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Ingresos por día: actual vs anterior")
            sa, sp = serie_diaria(v, a_ini, a_fin), serie_diaria(v, p_ini, p_fin)
            x = list(range(1, len(sa) + 1))
            fig = go.Figure()
            fig.add_scatter(x=x, y=sa, name="Actual", line=dict(color=AZUL_CLARO, width=3))
            fig.add_scatter(x=x, y=sp[:len(x)], name="Anterior", line=dict(color=GRIS, width=2, dash="dash"))
            fig.update_xaxes(title="Día del período")
            st.plotly_chart(estilo_fig(fig), use_container_width=True)
        with c2:
            st.markdown("### Estructura de egresos (actual)")
            valores = [act["Costo de ventas"], act["Gastos fijos"], act["Gastos variables"]]
            if sum(valores) == 0:
                st.info("Sin egresos en el período.")
            else:
                fig = go.Figure(go.Pie(labels=["Costo de ventas", "Gastos fijos", "Gastos variables"],
                                       values=valores, hole=0.55,
                                       marker=dict(colors=[AZUL, AZUL_OSCURO, GRIS])))
                st.plotly_chart(estilo_fig(fig), use_container_width=True)

        st.markdown("### Tendencia de los últimos 6 meses")
        t = tendencia_mensual(v, g)
        fig = go.Figure()
        fig.add_bar(x=t.index, y=t["Ingresos"], name="Ingresos", marker_color=AZUL)
        fig.add_bar(x=t.index, y=t["Costo de ventas"] + t["Gastos fijos"] + t["Gastos variables"],
                    name="Egresos totales", marker_color=GRIS)
        fig.add_scatter(x=t.index, y=t["Utilidad neta"], name="Utilidad neta",
                        line=dict(color="#e2e8f0", width=3))
        fig.update_layout(barmode="group")
        st.plotly_chart(estilo_fig(fig, 400), use_container_width=True)
        st.dataframe(t.round(0).style.format("${:,.0f}"), use_container_width=True)

        gg = filtrar(g, "fecha", a_ini, a_fin)
        if not gg.empty:
            st.markdown("### Gastos del período por concepto")
            tabla = gg.groupby(["tipo", "concepto"])["monto"].sum().reset_index().sort_values("monto", ascending=False)
            tabla["monto"] = tabla["monto"].map(dinero)
            st.dataframe(tabla, use_container_width=True, hide_index=True)

    with tab2:
        st.caption("El costo de la mercancía vendida se calcula solo con cada venta. "
                   "Aquí registra gastos como arriendo, servicios, nómina (fijos) o empaques, envíos y comisiones (variables).")
        with st.form("nuevo_gasto", clear_on_submit=True):
            c1, c2 = st.columns(2)
            fecha_g = c1.date_input("Fecha", value=hoy, max_value=hoy)
            tipo_g = c2.selectbox("Tipo", ["Fijo", "Variable"])
            c3, c4 = st.columns(2)
            concepto = c3.text_input("Concepto (ej. Arriendo, Empaques)")
            monto = c4.number_input("Monto ($)", min_value=0.0, step=1000.0)
            enviar = st.form_submit_button("Registrar gasto")
        if enviar:
            if not concepto.strip() or monto <= 0:
                st.error("Indica un concepto y un monto mayor que 0.")
            else:
                try:
                    sb.table("Gastos").insert({"fecha": str(fecha_g), "tipo": tipo_g,
                                               "concepto": concepto.strip(), "monto": monto}).execute()
                    st.success("Gasto registrado.")
                except Exception as e:
                    st.error(msg_error(e))

    with tab3:
        eq = equipo()
        nombres = dict(zip(eq["user_id"], eq["nombre"].fillna(eq["correo"]))) if not eq.empty else {}
        st.markdown("### Ventas")
        if v.empty:
            st.info("Sin ventas registradas.")
        else:
            vt = v.sort_values("fecha", ascending=False).copy()
            if "vendedor_id" in vt.columns:
                vt["vendedor"] = vt["vendedor_id"].map(nombres).fillna("—")
            vt = vt.drop(columns=[c for c in ["empresa_id", "vendedor_id", "dia"] if c in vt.columns])
            st.dataframe(vt, use_container_width=True, hide_index=True)
        st.markdown("### Gastos")
        if g.empty:
            st.info("Sin gastos registrados.")
        else:
            gt = g.sort_values("fecha", ascending=False)
            gt = gt.drop(columns=[c for c in ["empresa_id", "registrado_por"] if c in gt.columns])
            st.dataframe(gt, use_container_width=True, hide_index=True)

# ============================================================
#  EQUIPO (solo gerente)
# ============================================================
elif menu == "👥 Equipo":
    st.title("👥 Equipo de trabajo")
    eq = equipo()
    if not eq.empty:
        vista = eq.assign(rol=eq["rol"].map(ROLES), activo=eq["activo"].map({True: "Sí", False: "No"}))
        st.dataframe(vista[["nombre", "correo", "rol", "activo"]], use_container_width=True, hide_index=True)

    st.markdown("### Cambiar rol o desactivar a una persona")
    otros = eq[eq["user_id"] != user.id] if not eq.empty else eq
    if otros.empty:
        st.info("Aún no hay otras personas en tu equipo. Invítalas con un código.")
    else:
        opciones = {f"{r['nombre'] or '—'} · {r['correo']}": r for _, r in otros.iterrows()}
        sel = opciones[st.selectbox("Persona", list(opciones))]
        c1, c2 = st.columns(2)
        nuevo_rol = c1.selectbox("Rol", list(ROLES), index=list(ROLES).index(sel["rol"]),
                                 format_func=lambda r: ROLES[r])
        activo = c2.checkbox("Cuenta activa", value=bool(sel["activo"]))
        if st.button("Guardar cambios"):
            try:
                sb.table("miembros").update({"rol": nuevo_rol, "activo": activo}).eq("user_id", sel["user_id"]).execute()
                st.session_state["msg"] = "Cambios guardados."
                st.rerun()
            except Exception as e:
                st.error(msg_error(e))

    st.markdown("### Invitar a una persona")
    st.caption("Genera un código, compártelo con la persona y que lo use en «Unirme con código». "
               "Vence a los 7 días y sirve una sola vez.")
    rol_inv = st.selectbox("Rol de la persona invitada", list(ROLES), index=3,
                           format_func=lambda r: ROLES[r])
    if st.button("Generar código"):
        codigo = token_hex(4).upper()
        try:
            sb.table("invitaciones").insert({"codigo": codigo, "rol": rol_inv}).execute()
            st.success("Código generado. Cópialo y envíalo:")
            st.code(codigo)
        except Exception as e:
            st.error(msg_error(e))

    pend = sb.table("invitaciones").select("codigo,rol,vence_en").eq("usada", False).execute().data or []
    if pend:
        st.markdown("#### Invitaciones pendientes")
        dfp = pd.DataFrame(pend)
        dfp["rol"] = dfp["rol"].map(ROLES)
        st.dataframe(dfp, use_container_width=True, hide_index=True)

# ============================================================
#  PANEL ADMINISTRADOR
# ============================================================
elif menu == "⚙️ Panel Administrador":
    st.title("⚙️ Panel administrador")
    inv = inventario()
    st.markdown("### Ajustar stock o eliminar producto")
    if inv.empty:
        st.info("No hay productos.")
    else:
        sel = st.selectbox("Producto", inv["nombre"].tolist())
        f = inv[inv["nombre"] == sel].iloc[0]
        nuevo = st.number_input("Nuevo stock", min_value=0, value=int(f["stock"]))
        c1, c2 = st.columns(2)
        if c1.button("Guardar stock"):
            try:
                sb.table("Inventario").update({"stock": int(nuevo)}).eq("id", int(f["id"])).execute()
                st.session_state["msg"] = "Stock actualizado."
                st.rerun()
            except Exception as e:
                st.error(msg_error(e))
        if c2.button("🗑️ Eliminar producto"):
            try:
                sb.table("Inventario").delete().eq("id", int(f["id"])).execute()
                st.session_state["msg"] = "Producto eliminado."
                st.rerun()
            except Exception as e:
                st.error(msg_error(e))
    st.markdown("### Descargas")
    d1, d2, d3 = st.columns(3)
    d1.download_button("Inventario (CSV)", inventario().to_csv(index=False).encode(), "inventario.csv")
    d2.download_button("Ventas (CSV)", ventas().to_csv(index=False).encode(), "ventas.csv")
    d3.download_button("Gastos (CSV)", gastos().to_csv(index=False).encode(), "gastos.csv")
