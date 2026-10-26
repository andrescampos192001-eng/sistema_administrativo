# ============================================================
#  Sistema de gestión administrativa
#  Streamlit + Supabase
# ============================================================
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from supabase import create_client

st.set_page_config(page_title=Sistema de gestión administrativa", page_icon="💎", layout="wide")

SUPABASE_URL = "https://tqgmapwcknhdydjkbdtj.supabase.co"
ZONA = "America/Bogota"

# Paleta: azul oscuro, grises y negro
AZUL, AZUL_CLARO, AZUL_OSCURO = "#3b82f6", "#60a5fa", "#1e3a8a"
GRIS, GRIS_CLARO = "#64748b", "#cbd5e1"
ROJO_SUAVE = "#94a3b8"


# ------------------------------------------------------------
#  Conexión
# ------------------------------------------------------------
@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, st.secrets["SUPABASE_KEY"])


sb = get_supabase()

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
def dinero(x):
    return f"${x:,.0f}"


def variacion(actual, anterior):
    """Variación porcentual; None si no hay base de comparación."""
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


@st.cache_data(ttl=15)
def cargar(tabla):
    r = sb.table(tabla).select("*").execute()
    return pd.DataFrame(r.data or [])


def refrescar():
    st.cache_data.clear()


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
    df["fecha"] = pd.to_datetime(df["fecha"], utc=True).dt.tz_convert(ZONA).dt.tz_localize(None)
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
    """Devuelve (periodo actual, periodo anterior comparable)."""
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
    rango = pd.period_range(end=pd.Timestamp(date.today()).to_period("M"), periods=meses, freq="M")
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
#  Menú lateral
# ------------------------------------------------------------
st.sidebar.markdown("## 💎 BRI RODRÍGUEZ")
st.sidebar.caption("Sistema de gestión administrativa")
menu = st.sidebar.radio(
    "MENÚ",
    ["🏠 Inicio y Gráficos", "➕ Agregar Producto", "📦 Inventario",
     "💰 Registrar Venta (POS)", "📊 Soporte Contable", "⚙️ Panel Administrador"],
    label_visibility="collapsed",
)

if "carrito" not in st.session_state:
    st.session_state["carrito"] = []
if "msg" in st.session_state:
    st.success(st.session_state.pop("msg"))

# ============================================================
#  INICIO
# ============================================================
if menu == "🏠 Inicio y Gráficos":
    st.title("JOYERÍA BISUTERÍA BRI RODRÍGUEZ")
    st.subheader("Dashboard gerencial automatizado")

    inv, v, g = inventario(), ventas(), gastos()
    hoy = date.today()
    mes = resumen(v, g, hoy.replace(day=1), hoy)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Modelos de productos", len(inv))
    c2.metric("🧮 Unidades en stock", f"{int(inv['stock'].sum()):,}")
    c3.metric("💰 Ingresos del mes", dinero(mes["Ingresos"]))
    c4.metric("📈 Utilidad neta del mes", dinero(mes["Utilidad neta"]))

    st.write("")
    izq, der = st.columns(2)
    with izq:
        st.markdown("### Ingresos de los últimos 30 días")
        ini = hoy - timedelta(29)
        dias = pd.date_range(ini, hoy)
        vals = serie_diaria(v, ini, hoy)
        fig = go.Figure(go.Scatter(x=dias, y=vals, mode="lines", fill="tozeroy",
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
        if st.form_submit_button("Guardar producto"):
            if not nombre.strip():
                st.error("El nombre es obligatorio.")
            else:
                sb.table("Inventario").insert({
                    "nombre": nombre.strip(), "categoria": categoria.strip(),
                    "costo": costo, "precio": precio, "stock": int(stock)}).execute()
                refrescar()
                st.success(f"Producto «{nombre}» guardado.")

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
        c1, c2, c3 = st.columns(3)
        c1.metric("Modelos", len(vista))
        c2.metric("Unidades", f"{int(vista['stock'].sum()):,}")
        c3.metric("Valor del inventario (costo)", dinero((vista["costo"] * vista["stock"]).sum()))
        st.dataframe(vista, use_container_width=True, hide_index=True)

# ============================================================
#  PUNTO DE VENTA (automatiza inventario + ingresos)
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
        ya = sum(l["cantidad"] for l in st.session_state["carrito"] if l["id"] == fila["id"])
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
                    "precio": float(fila["precio"]), "costo": float(fila["costo"]),
                    "descuento": desc,
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
        # 1) validar stock actual
        errores = []
        stocks = {}
        for l in carrito:
            actual = sb.table("Inventario").select("stock").eq("id", l["id"]).execute().data
            stocks[l["id"]] = actual[0]["stock"] if actual else 0
        pedido = {}
        for l in carrito:
            pedido[l["id"]] = pedido.get(l["id"], 0) + l["cantidad"]
        for pid, cant in pedido.items():
            if stocks[pid] < cant:
                errores.append(f"Stock insuficiente (ID {pid}): hay {stocks[pid]}, pides {cant}.")
        if errores:
            for e in errores:
                st.error(e)
        else:
            # 2) registrar ventas (ingreso) y 3) descontar inventario
            for l in carrito:
                sb.table("Ventas").insert({
                    "cliente": cliente, "documento": doc, "direccion": direccion,
                    "ciudad": ciudad, "pais": pais, "responsable_iva": iva,
                    "producto_id": l["id"], "producto": l["producto"], "cantidad": l["cantidad"],
                    "precio_unitario": l["precio"], "costo_unitario": l["costo"],
                    "descuento_pct": l["descuento"], "total": l["total"]}).execute()
            for pid, cant in pedido.items():
                sb.table("Inventario").update({"stock": stocks[pid] - cant}).eq("id", pid).execute()
            st.session_state["carrito"] = []
            refrescar()
            st.session_state["msg"] = f"Venta registrada por {dinero(total_neto)}. Inventario e ingresos actualizados."
            st.rerun()

# ============================================================
#  SOPORTE CONTABLE
# ============================================================
elif menu == "📊 Soporte Contable":
    st.title("📊 Soporte contable")
    v, g = ventas(), gastos()
    hoy = date.today()
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
            fecha_g = c1.date_input("Fecha", value=hoy)
            tipo_g = c2.selectbox("Tipo", ["Fijo", "Variable"])
            c3, c4 = st.columns(2)
            concepto = c3.text_input("Concepto (ej. Arriendo, Empaques)")
            monto = c4.number_input("Monto ($)", min_value=0.0, step=1000.0)
            if st.form_submit_button("Registrar gasto"):
                if not concepto.strip() or monto <= 0:
                    st.error("Indica un concepto y un monto mayor que 0.")
                else:
                    sb.table("Gastos").insert({"fecha": str(fecha_g), "tipo": tipo_g,
                                               "concepto": concepto.strip(), "monto": monto}).execute()
                    refrescar()
                    st.success("Gasto registrado.")

    with tab3:
        st.markdown("### Ventas")
        st.dataframe(v.sort_values("fecha", ascending=False) if not v.empty else v,
                     use_container_width=True, hide_index=True)
        st.markdown("### Gastos")
        st.dataframe(g.sort_values("fecha", ascending=False) if not g.empty else g,
                     use_container_width=True, hide_index=True)

# ============================================================
#  PANEL ADMINISTRADOR
# ============================================================
elif menu == "⚙️ Panel Administrador":
    st.title("⚙️ Panel administrador")
    pin_real = st.secrets.get("ADMIN_PIN")
    if not pin_real:
        st.warning("Define ADMIN_PIN en los secretos de la app para habilitar este panel.")
    else:
        pin = st.text_input("PIN de administrador", type="password")
        if pin == str(pin_real):
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
                    sb.table("Inventario").update({"stock": int(nuevo)}).eq("id", int(f["id"])).execute()
                    refrescar()
                    st.session_state["msg"] = "Stock actualizado."
                    st.rerun()
                if c2.button("🗑️ Eliminar producto"):
                    sb.table("Inventario").delete().eq("id", int(f["id"])).execute()
                    refrescar()
                    st.session_state["msg"] = "Producto eliminado."
                    st.rerun()
            st.markdown("### Descargas")
            d1, d2, d3 = st.columns(3)
            d1.download_button("Inventario (CSV)", inventario().to_csv(index=False).encode(), "inventario.csv")
            d2.download_button("Ventas (CSV)", ventas().to_csv(index=False).encode(), "ventas.csv")
            d3.download_button("Gastos (CSV)", gastos().to_csv(index=False).encode(), "gastos.csv")
        elif pin:
            st.error("PIN incorrecto.")
