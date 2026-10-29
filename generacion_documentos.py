import csv
import io
import re
import unicodedata
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# --- Paleta Azul Oscuro ---
PRIMARIO = colors.HexColor("#0F172A")
TEXTO = colors.HexColor("#111827")
GRIS = colors.HexColor("#6B7280")
LINEA = colors.HexColor("#E5E7EB")
FONDO_SUAVE = colors.HexColor("#F8F9FA")

CARPETAS = {"venta": "Ventas", "compra": "Compras", "egreso": "Egresos", "contable": "Contables"}
PREFIJOS = {"venta": "VEN", "compra": "COM", "egreso": "EGR", "contable": "CD"}
AVISO = "Documento de soporte interno; no es factura electrónica."

def moneda(x):
    try: return f"${float(x):,.0f}"
    except: return "$0"

def fecha_hora(iso):
    if not iso: return ""
    try: d = datetime.fromisoformat(str(iso)[:19])
    except: return str(iso)
    sufijo = "a. m." if d.hour < 12 else "p. m."
    hora = d.hour % 12 or 12
    return f"{d:%d/%m/%Y} {hora:02d}:{d:%M} {sufijo}"

def solo_fecha(iso):
    try: return f"{datetime.fromisoformat(str(iso)[:19]):%d/%m/%Y}"
    except: return str(iso or "")

def slug(texto, maximo=40):
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-")
    return t[:maximo].strip("-")

def formatear_numero(tipo, numero):
    try: n = int(numero)
    except: return str(numero)
    return f"{PREFIJOS.get(tipo, 'DOC')}-{n:06d}"

def nombre_archivo(numero, fecha_iso, tercero):
    base = f"{numero}_{str(fecha_iso)[:10]}_"
    resto = 80 - len(base) - len(".pdf")
    return f"{base}{slug(tercero, resto) or 'Sin-tercero'}.pdf"

def _p(texto, estilo): return Paragraph(escape(str(texto if texto is not None else "")), estilo)

def _estilos():
    base = getSampleStyleSheet()["Normal"]
    normal = ParagraphStyle("n", parent=base, fontName="Helvetica", fontSize=9.5, leading=12.5, textColor=TEXTO)
    return {
        "n": normal, "b": ParagraphStyle("b", parent=normal, fontName="Helvetica-Bold"),
        "peq": ParagraphStyle("peq", parent=normal, fontSize=8, leading=10, textColor=GRIS),
        "tab": ParagraphStyle("tab", parent=normal, fontSize=8.5, leading=10.5),
        "tabb": ParagraphStyle("tabb", parent=normal, fontName="Helvetica-Bold", fontSize=8.5, leading=10.5),
        "emp": ParagraphStyle("emp", parent=normal, fontName="Helvetica-Bold", fontSize=13, leading=16),
        "titulo": ParagraphStyle("titulo", parent=normal, fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=PRIMARIO, alignment=TA_RIGHT),
        "num": ParagraphStyle("num", parent=normal, fontName="Helvetica-Bold", fontSize=11, alignment=TA_RIGHT),
        "der": ParagraphStyle("der", parent=normal, alignment=TA_RIGHT),
        "derb": ParagraphStyle("derb", parent=normal, fontName="Helvetica-Bold", alignment=TA_RIGHT),
        "total": ParagraphStyle("total", parent=normal, fontName="Helvetica-Bold", fontSize=12, leading=15, alignment=TA_RIGHT, textColor=PRIMARIO),
    }

def _canvas_con_pie(pie, marca):
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._paginas = []
        def showPage(self):
            self._paginas.append(dict(self.__dict__))
            self._startPage()
        def save(self):
            total = len(self._paginas)
            for estado in self._paginas:
                self.__dict__.update(estado)
                self._extras(total)
                super().showPage()
            super().save()
        def _extras(self, total):
            ancho, alto = self._pagesize
            self.saveState()
            self.setStrokeColor(LINEA)
            self.setLineWidth(0.6)
            self.line(2 * cm, 1.9 * cm, ancho - 2 * cm, 1.9 * cm)
            self.setFont("Helvetica", 7.5)
            self.setFillColor(GRIS)
            self.drawString(2 * cm, 1.4 * cm, pie[:120])
            self.drawRightString(ancho - 2 * cm, 1.4 * cm, f"Página {self._pageNumber} de {total}")
            self.restoreState()
            if marca:
                self.saveState()
                self.setFillColor(colors.Color(0.05, 0.09, 0.16, alpha=0.13))
                self.setFont("Helvetica-Bold", 96)
                self.translate(ancho / 2, alto / 2)
                self.rotate(40)
                self.drawCentredString(0, 0, marca)
                self.restoreState()
    return NumberedCanvas

def _documento(buf, titulo, pie, marca=None, apaisado=False):
    tam = landscape(letter) if apaisado else letter
    doc = SimpleDocTemplate(buf, pagesize=tam, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=2.4 * cm, title=titulo, author="SIVAE")
    return doc, _canvas_con_pie(pie, marca)

def _encabezado(est, empresa, titulo, numero, ancho):
    emp = empresa or {}
    izq = [_p(emp.get("nombre", ""), est["emp"])]
    if emp.get("nit"): izq.append(_p(f"NIT {emp['nit']}", est["peq"]))
    ubic = " · ".join(x for x in [emp.get("direccion"), emp.get("ciudad"), emp.get("telefono")] if x)
    if ubic: izq.append(_p(ubic, est["peq"]))
    der = [_p(titulo, est["titulo"])]
    if numero: der.append(_p(f"N.º {numero}", est["num"]))
    t = Table([[izq, der]], colWidths=[ancho * 0.55, ancho * 0.45])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return [t, Spacer(1, 6), HRFlowable(width="100%", thickness=2, color=PRIMARIO, spaceAfter=8)]

def _bloque_datos(est, izquierda, derecha, ancho):
    def col(pares): return [Paragraph(f"<b>{escape(k)}:</b> {escape(str(v))}", est["n"]) for k, v in pares if v not in (None, "")]
    t = Table([[col(izquierda), col(derecha)]], colWidths=[ancho * 0.55, ancho * 0.45])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return t

def _tabla(est, encabezados, filas, anchos, derecha=(), total_fila=None):
    st_h = ParagraphStyle("h", parent=est["tabb"], textColor=colors.white)
    st_hd = ParagraphStyle("hd", parent=st_h, alignment=TA_RIGHT)
    datos = [[Paragraph(escape(str(h)), st_hd if i in derecha else st_h) for i, h in enumerate(encabezados)]]
    for fila in filas:
        datos.append([Paragraph(escape(str(c)), ParagraphStyle("c", parent=est["tab"], alignment=TA_RIGHT if i in derecha else 0)) for i, c in enumerate(fila)])
    if total_fila:
        datos.append([Paragraph(escape(str(c)), ParagraphStyle("ct", parent=est["tabb"], alignment=TA_RIGHT if i in derecha else 0)) for i, c in enumerate(total_fila)])
    t = Table(datos, colWidths=anchos, repeatRows=1)
    estilo = [("BACKGROUND", (0, 0), (-1, 0), PRIMARIO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINEA),
              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if total_fila: estilo += [("LINEABOVE", (0, -1), (-1, -1), 1, PRIMARIO), ("BACKGROUND", (0, -1), (-1, -1), FONDO_SUAVE)]
    t.setStyle(TableStyle(estilo))
    return t

def pdf_comprobante(datos, estado="emitido", copia=False):
    est = _estilos()
    tipo = datos.get("tipo", "venta")
    numero = datos.get("numero", "")
    ancho = letter[0] - 4 * cm
    marca = "ANULADO" if estado == "anulado" else ("COPIA" if copia else None)
    buf = io.BytesIO()
    doc, cv = _documento(buf, f"COMPROBANTE {numero}", f"{AVISO}  ·  {numero}", marca)
    historia = _encabezado(est, datos.get("empresa"), f"COMPROBANTE DE {tipo.upper()}", numero, ancho)
    fecha = fecha_hora(datos.get("fecha"))
    
    if tipo == "venta":
        c = datos.get("cliente") or {}
        ciudad = ", ".join(x for x in [c.get("ciudad"), c.get("pais")] if x)
        historia.append(_bloque_datos(est, [("Cliente", c.get("nombre") or "Cliente general"), ("Documento", c.get("documento")), ("Dirección", c.get("direccion")), ("Ciudad", ciudad), ("Responsable de IVA", c.get("responsable_iva"))], [("Fecha", fecha), ("Forma de pago", str(datos.get("forma_pago", "")).capitalize()), ("Vendedor", datos.get("vendedor"))], ancho))
        historia.append(Spacer(1, 10))
        filas = [[i.get("cantidad"), i.get("descripcion"), moneda(i.get("precio_unitario")), f"{float(i.get('descuento_pct') or 0):g} %", moneda(i.get("total"))] for i in datos.get("items", [])]
        historia.append(_tabla(est, ["Cant.", "Descripción", "Precio unit.", "Desc.", "Total"], filas, [1.5 * cm, ancho - 1.5 * cm - 3.2 * cm - 2 * cm - 3.3 * cm, 3.2 * cm, 2 * cm, 3.3 * cm], derecha=(0, 2, 3, 4)))
        etiqueta = "Total neto"
    elif tipo == "compra":
        p = datos.get("proveedor") or {}
        historia.append(_bloque_datos(est, [("Proveedor", p.get("nombre")), ("NIT", p.get("nit")), ("Factura del proveedor", datos.get("factura"))], [("Fecha", fecha), ("Forma de pago", str(datos.get("forma_pago", "")).capitalize()), ("Vence", solo_fecha(datos.get("vence_en")) if datos.get("vence_en") else None), ("Registrado por", datos.get("registrado_por"))], ancho))
        historia.append(Spacer(1, 10))
        filas = [[i.get("cantidad"), i.get("descripcion"), moneda(i.get("costo_unitario")), moneda(i.get("total"))] for i in datos.get("items", [])]
        historia.append(_tabla(est, ["Cant.", "Descripción", "Costo unit.", "Total"], filas, [1.5 * cm, ancho - 1.5 * cm - 3.5 * cm - 3.5 * cm, 3.5 * cm, 3.5 * cm], derecha=(0, 2, 3)))
        etiqueta = "Total compra"
    else:
        p = datos.get("proveedor") or {}
        historia.append(_bloque_datos(est, [("Proveedor", p.get("nombre")), ("NIT", p.get("nit")), ("Factura del proveedor", datos.get("factura")), ("Compra", datos.get("compra_numero"))], [("Fecha", fecha), ("Medio de pago", str(datos.get("medio", "")).capitalize()), ("Referencia", datos.get("referencia")), ("Registrado por", datos.get("registrado_por"))], ancho))
        historia.append(Spacer(1, 10))
        filas = [["Saldo antes del pago", moneda(datos.get("saldo_anterior"))], ["Valor pagado", moneda(datos.get("valor"))], ["Saldo después del pago", moneda(datos.get("saldo_nuevo"))]]
        historia.append(_tabla(est, ["Concepto", "Valor"], filas, [ancho - 5 * cm, 5 * cm], derecha=(1,)))
        etiqueta = "Valor pagado"
    
    historia.append(Spacer(1, 12))
    total = datos.get("valor") if tipo == "egreso" else datos.get("total")
    historia.append(Table([[_p(etiqueta + ":", est["derb"]), _p(moneda(total), est["total"])]], colWidths=[ancho - 5 * cm, 5 * cm]))
    doc.build(historia, canvasmaker=cv)
    return buf.getvalue()

def pdf_asiento(asiento, empresa=None, estado="emitido"):
    est = _estilos()
    ancho = letter[0] - 4 * cm
    numero = asiento.get("numero_texto") or f"CD-{int(asiento.get('numero', 0)):06d}"
    marca = "ANULADO" if estado == "anulado" else None
    buf = io.BytesIO()
    doc, cv = _documento(buf, f"Comprobante contable {numero}", f"{AVISO}  ·  {numero}", marca)
    historia = _encabezado(est, empresa or asiento.get("empresa"), "COMPROBANTE CONTABLE", numero, ancho)
    historia.append(_bloque_datos(est, [("Descripción", asiento.get("descripcion")), ("Origen", str(asiento.get("origen_tipo", "")).replace("_", " "))], [("Fecha", fecha_hora(asiento.get("fecha")))], ancho))
    historia.append(Spacer(1, 10))
    lineas = asiento.get("lineas", [])
    filas = [[l.get("cuenta"), l.get("detalle") or "", moneda(l.get("debito")) if l.get("debito") else "", moneda(l.get("credito")) if l.get("credito") else ""] for l in lineas]
    td = sum(float(l.get("debito") or 0) for l in lineas); tc = sum(float(l.get("credito") or 0) for l in lineas)
    historia.append(_tabla(est, ["Cuenta", "Detalle", "Débito", "Crédito"], filas, [6 * cm, ancho - 6 * cm - 6 * cm, 3 * cm, 3 * cm], derecha=(2, 3), total_fila=["Totales", "", moneda(td), moneda(tc)]))
    doc.build(historia, canvasmaker=cv)
    return buf.getvalue()

def pdf_de_item(item, copia=False):
    if item["tipo"] == "contable": return pdf_asiento(item["datos"], item["datos"].get("empresa"), estado=item.get("estado", "emitido"))
    return pdf_comprobante(item["datos"], estado=item.get("estado", "emitido"), copia=copia)

def zip_comprobantes(empresa_nombre, items):
    raiz = slug(empresa_nombre, 40) or "Empresa"
    ordenados = sorted(items, key=lambda i: (str(i["fecha"]), str(i["numero"])))
    buf = io.BytesIO()
    indice = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for it in ordenados:
            fecha = str(it["fecha"])
            numero_fmt = it["numero"] if "-" in str(it["numero"]) else formatear_numero(it["tipo"], it["numero"])
            ruta = f"{raiz}/{fecha[:4]}/{fecha[5:7]}/{CARPETAS[it['tipo']]}/{nombre_archivo(numero_fmt, fecha, it['tercero'])}"
            z.writestr(ruta, pdf_de_item(it))
            indice.append([numero_fmt, CARPETAS[it["tipo"]][:-1].lower(), solo_fecha(fecha), it["tercero"] or "", f"{float(it['total'] or 0):.2f}", it.get("estado", "emitido"), ruta])
        z.writestr(f"{raiz}/indice.csv", csv_bytes(["numero", "tipo", "fecha", "tercero", "total", "estado", "archivo"], indice))
    return buf.getvalue()

def csv_bytes(columnas, filas):
    salida = io.StringIO()
    w = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    w.writerow(columnas); w.writerows(filas)
    return ("\ufeff" + salida.getvalue()).encode("utf-8")

def indice_csv(items):
    ordenados = sorted(items, key=lambda i: (str(i["fecha"]), str(i["numero"])))
    filas = [[i["numero"], i["tipo"], solo_fecha(i["fecha"]), i["tercero"] or "", f"{float(i['total'] or 0):.2f}", i.get("estado", "emitido")] for i in ordenados]
    return csv_bytes(["numero", "tipo", "fecha", "tercero", "total", "estado"], filas)
