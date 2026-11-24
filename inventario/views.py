
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import MateriaPrima, MovimientoStock, Proveedor, Producto, Produccion
from .forms import MateriaPrimaForm, MovimientoStockForm, ProveedorForm, ProduccionForm
import csv
from urllib.parse import urlencode
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date
from django.db.models import Count, DecimalField, F, Max, Prefetch, Q, Sum
from django.core.paginator import Paginator
from django.db.models.functions import TruncMonth


# Función auxiliar para comprobar si el usuario es "Gerente" (Staff)
def es_gerente(user):
    return user.is_staff


@login_required(login_url='login')
def panel_principal(request):
    # Control de acceso según tipo de usuario (staff vs operario)
    if not request.user.is_staff:
        return redirect('consumos')

    materias_primas = MateriaPrima.objects.all()

    # Filtro de materia prima seleccionada desde el template
    materia_id = request.GET.get("materia", "")
    if not materia_id.isdigit():
        materia_id = ""
    materia_seleccionada = materias_primas.filter(pk=materia_id).first() if materia_id else None

    # Resumen general y alertas globales
    resumen = []
    alertas_criticas = []

    for mp in materias_primas:
        stock = mp.stock_actual
        alerta = stock <= mp.stock_minimo

        if alerta:
            alertas_criticas.append(mp)

        resumen.append({
            'id_materia': mp.id,
            'nombre': mp.nombre,
            'variedad': mp.variedad if mp.variedad else 'Sin variedad',
            'stock': stock,
            'unidad': mp.get_unidad_medida_display(),
            'stock_minimo': mp.stock_minimo,
            'alerta': alerta,
        })

    # Tarjetas según el filtro
    unidad_stock = "Kg"
    if materia_seleccionada:
        stock_total = materia_seleccionada.stock_actual
        alertas_visibles = (
            [materia_seleccionada]
            if materia_seleccionada.stock_actual <= materia_seleccionada.stock_minimo
            else []
        )
    else:
        stock_total = materias_primas.aggregate(t=Sum("stock_actual"))["t"] or Decimal("0")
        alertas_visibles = alertas_criticas

    ultimos_movimientos = MovimientoStock.objects.all()
    if materia_seleccionada:
        ultimos_movimientos = ultimos_movimientos.filter(materia_prima=materia_seleccionada)
    ultimos_movimientos = ultimos_movimientos.order_by('-fecha')[:10]

    # Gráfico: ingresos y consumos por mes (últimos 12 meses)
    movs = MovimientoStock.objects.filter(fecha__gte=timezone.now() - timedelta(days=365))
    if materia_seleccionada:
        movs = movs.filter(materia_prima=materia_seleccionada)

    datos = defaultdict(lambda: {"INGRESO": Decimal("0"), "CONSUMO": Decimal("0")})
    for mov in movs:
        mes = timezone.localtime(mov.fecha).strftime("%Y-%m")
        datos[mes][mov.tipo] += mov.cantidad

    meses = sorted(datos)
    grafico = {
        "labels": [f"{m[5:]}/{m[:4]}" for m in meses],
        "ingresos": [float(datos[m]["INGRESO"]) for m in meses],
        "consumos": [float(datos[m]["CONSUMO"]) for m in meses],
        "unidad": "Kg",
    }

    # Consumo del mes actual
    ahora = timezone.localtime()
    consumos_mes_qs = MovimientoStock.objects.filter(
        tipo="CONSUMO", fecha__year=ahora.year, fecha__month=ahora.month
    )
    if materia_seleccionada:
        consumos_mes_qs = consumos_mes_qs.filter(materia_prima=materia_seleccionada)
    consumo_mes = consumos_mes_qs.aggregate(t=Sum("cantidad"))["t"] or Decimal("0")

    # Producciones y ventas
    suma_ventas = Sum(
        F("cantidad") * F("precio_unitario"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    producciones = Produccion.objects.all()
    if materia_seleccionada:
        usadas = MovimientoStock.objects.filter(
            materia_prima=materia_seleccionada, produccion__isnull=False
        ).values("produccion_id")
        producciones = producciones.filter(pk__in=usadas)

    producciones_mes = producciones.filter(fecha__year=ahora.year, fecha__month=ahora.month)
    cant_producciones_mes = producciones_mes.count()
    ventas_mes = producciones_mes.aggregate(t=suma_ventas)["t"] or Decimal("0")
    ventas_total = producciones.aggregate(t=suma_ventas)["t"] or Decimal("0")

    contexto = {
        'productos': resumen,
        'stock_total': stock_total,
        'unidad_stock': unidad_stock,
        'alertas': alertas_visibles,
        'cant_alertas': len(alertas_visibles),
        'movimientos': ultimos_movimientos,
        'materias': materias_primas.order_by("nombre"),
        'materia_id': materia_id,
        'materia_seleccionada': materia_seleccionada,
        'grafico': grafico,
        'consumo_mes': consumo_mes,
        'seccion': 'panel',
        'producciones_mes': cant_producciones_mes,
        'ventas_mes': ventas_mes,
        'ventas_total': ventas_total,
    }

    return render(request, 'inventario/panelprincipal.html', contexto)


# Registrar Nueva Materia Prima (Catálogo)
@login_required(login_url='login')
def registrar_materia_prima(request):
    if request.method == "POST":
        formulario = MateriaPrimaForm(request.POST)
        if formulario.is_valid():
            with transaction.atomic():
                materia = formulario.save(commit=False)
                cantidad_inicial = formulario.cleaned_data.get("cantidad_inicial") or Decimal("0.00")

                # Asignamos el stock inicial a la materia prima
                materia.stock_actual = cantidad_inicial
                materia.save()

                # Creamos el movimiento automático en el historial
                if cantidad_inicial > 0:
                    MovimientoStock.objects.create(
                        materia_prima=materia,
                        tipo="INGRESO",
                        cantidad=cantidad_inicial,
                        precio_unitario=formulario.cleaned_data["precio_unitario"],
                        observaciones="Stock inicial al registrar la materia prima",
                    )

            messages.success(
                request,
                f"Se registró «{materia}». Cargale stock desde Registro de Ingresos.",
            )
            return redirect("inventariostock")
    else:
        formulario = MateriaPrimaForm()

    return render(request, "inventario/registrarmateriaprima.html", {"formulario": formulario})


# Registrar Movimiento de Stock (Ingresos / Consumos)
@login_required(login_url='login')
def registrar_movimiento(request):
    if request.method == 'POST':
        formulario = MovimientoStockForm(request.POST)

        if formulario.is_valid():
            # El modelo mantiene la responsabilidad de actualizar el stock.
            formulario.save()
            messages.success(request, '¡Movimiento de stock registrado correctamente!')
            return redirect('panelprincipal')
    else:
        formulario = MovimientoStockForm()

    return render(
        request,
        'inventario/registrarmovimiento.html',
        {'formulario': formulario}
    )


def _fecha(valor):
    try:
        return parse_date(valor)
    except ValueError:
        return None


def _filtrar_por_fechas(request, queryset):
    """Aplica el rango desde/hasta (inclusive) del GET."""
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")

    if _fecha(desde):
        queryset = queryset.filter(fecha__date__gte=_fecha(desde))
    if _fecha(hasta):
        queryset = queryset.filter(fecha__date__lte=_fecha(hasta))

    return queryset, desde, hasta


# Vista del Historial General
@login_required(login_url='login')
def historial_general(request):
    tipo = request.GET.get("tipo", "")
    if tipo not in ("ingreso", "consumo"):
        tipo = ""

    base, desde, hasta = _filtrar_por_fechas(request, MovimientoStock.objects.all())
    cant_ingresos = base.filter(tipo="INGRESO").count()
    cant_consumos = base.filter(tipo="CONSUMO").count()

    movimientos = base.select_related(
        "materia_prima", "proveedor", "produccion__producto"
    ).order_by("-fecha")

    if tipo == "ingreso":
        movimientos = movimientos.filter(tipo="INGRESO")
    elif tipo == "consumo":
        movimientos = movimientos.filter(tipo="CONSUMO")

    pagina = Paginator(movimientos, 25).get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    fechas = {k: v for k, v in (("desde", desde), ("hasta", hasta)) if v}

    return render(request, "inventario/historialgeneral.html", {
        "pagina": pagina,
        "tipo": tipo,
        "desde": desde,
        "hasta": hasta,
        "cant_ingresos": cant_ingresos,
        "cant_consumos": cant_consumos,
        "cant_todos": cant_ingresos + cant_consumos,
        "querystring": params.urlencode(),
        "qs_fechas": urlencode(fechas),
        "total": pagina.paginator.count,
    })


# Vista de Informes Mensuales
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]


def _rango_mes(valor):
    """Devuelve (primer día del mes, primer día del mes siguiente)."""
    try:
        anio, mes = (int(x) for x in valor.split("-"))
        inicio = date(anio, mes, 1)
    except (ValueError, AttributeError):
        inicio = timezone.localdate().replace(day=1)

    fin = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
    return inicio, fin


def _datos_reporte(valor):
    inicio, fin = _rango_mes(valor)
    tz = timezone.get_current_timezone()
    ini_dt = timezone.make_aware(datetime.combine(inicio, time.min), tz)
    fin_dt = timezone.make_aware(datetime.combine(fin, time.min), tz)

    en_mes = Q(fecha__gte=ini_dt, fecha__lt=fin_dt)
    despues = Q(fecha__gte=fin_dt)
    cero = Decimal("0")

    # Una sola consulta con todos los totales por materia prima
    totales = {
        f["materia_prima_id"]: f
        for f in MovimientoStock.objects.order_by().values("materia_prima_id").annotate(
            ing=Sum("cantidad", filter=Q(tipo="INGRESO") & en_mes),
            con=Sum("cantidad", filter=Q(tipo="CONSUMO") & en_mes),
            ing_post=Sum("cantidad", filter=Q(tipo="INGRESO") & despues),
            con_post=Sum("cantidad", filter=Q(tipo="CONSUMO") & despues),
            n=Count("id", filter=en_mes),
        )
    }

    filas = []
    for m in MateriaPrima.objects.order_by("nombre"):
        t = totales.get(m.id, {})

        ing = Decimal(str(t.get("ing") or 0))
        con = Decimal(str(t.get("con") or 0))
        ing_post = Decimal(str(t.get("ing_post") or 0))
        con_post = Decimal(str(t.get("con_post") or 0))

        posterior = ing_post - con_post
        cierre = m.stock_actual - posterior
        precio_unitario = m.precio_referencia

        filas.append({
            "materia": m,
            "unidad": m.unidad_medida,
            "inicial": cierre - ing + con,
            "ingresos": ing,
            "consumos": con,
            "final": cierre,
            "critica": cierre <= m.stock_minimo,
            "n": t.get("n") or 0,
            "precio_referencia": precio_unitario,
        })

    compras_qs = (
        MovimientoStock.objects.filter(tipo="INGRESO").filter(en_mes)
        .order_by()
        .values(
            "proveedor__nombre",
            "materia_prima__nombre",
            "materia_prima__variedad",
            "materia_prima__unidad_medida",
        )
        .annotate(
            total=Sum("cantidad"),
            veces=Count("id"),
            precio_total=Sum(
                F("cantidad") * F("precio_unitario"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        )
        .order_by("proveedor__nombre", "materia_prima__nombre")
    )

    compras = []
    for c in compras_qs:
        compras.append({
            "proveedor__nombre": c["proveedor__nombre"],
            "materia_prima__nombre": c["materia_prima__nombre"],
            "materia_prima__variedad": c["materia_prima__variedad"],
            "materia_prima__unidad_medida": c["materia_prima__unidad_medida"],
            "total": Decimal(str(c["total"] or 0)),
            "veces": c["veces"],
            "precio_total": c["precio_total"] or Decimal("0"),
        })

    ing_kg = sum((f["ingresos"] for f in filas), cero)
    con_kg = sum((f["consumos"] for f in filas), cero)
    extra = _datos_extra(inicio, fin, ini_dt, fin_dt)

    return {
        "mes_valor": inicio.strftime("%Y-%m"),
        "mes_nombre": f"{MESES[inicio.month - 1]} de {inicio.year}",
        "mes_anterior": (inicio - timedelta(days=1)).strftime("%Y-%m"),
        "mes_siguiente": fin.strftime("%Y-%m"),
        "hay_siguiente": fin <= timezone.localdate(),
        "filas": filas,
        "compras": compras,
        "ing_kg": ing_kg,
        "con_kg": con_kg,
        "balance_kg": ing_kg - con_kg,
        "movimientos": sum(f["n"] for f in filas),
        "criticas_cierre": sum(1 for f in filas if f["critica"]),
        "generado": timezone.localtime(),
        **extra,
    }


def _importe():
    return Sum(
        F("cantidad") * F("precio_unitario"),
        output_field=DecimalField(max_digits=14, decimal_places=2)
    )


def _datos_extra(inicio, fin, ini_dt, fin_dt):
    cero = Decimal("0")

    stock_total = MateriaPrima.objects.aggregate(t=Sum("stock_actual"))["t"] or cero
    consumo_mes = (
        MovimientoStock.objects.filter(tipo="CONSUMO", fecha__gte=ini_dt, fecha__lt=fin_dt)
        .aggregate(t=Sum("cantidad"))["t"] or cero
    )

    # Producciones y ventas del mes del informe
    producciones = Produccion.objects.filter(fecha__gte=ini_dt, fecha__lt=fin_dt)
    producciones_mes = producciones.count()
    ventas_mes = producciones.aggregate(t=_importe())["t"] or cero

    # Comparativo de los últimos 12 meses
    meses, y, m = [], inicio.year, inicio.month
    for _ in range(12):
        meses.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    meses.reverse()
    desde = date(meses[0][0], meses[0][1], 1)

    def por_mes(qs):
        filas = qs.annotate(mes=TruncMonth("fecha")).values("mes").annotate(
            t=_importe()
        ).order_by("mes")
        return {f["mes"].strftime("%Y-%m"): f["t"] or cero for f in filas}

    pagado = por_mes(MovimientoStock.objects.filter(
        tipo="INGRESO", fecha__date__gte=desde, fecha__date__lt=fin
    ))
    vendido = por_mes(Produccion.objects.filter(
        fecha__date__gte=desde, fecha__date__lt=fin
    ))

    comparativo = []
    for y, m in meses:
        clave = f"{y}-{m:02d}"
        c, v = pagado.get(clave, cero), vendido.get(clave, cero)
        comparativo.append({
            "mes": f"{m:02d}/{y}",
            "compras": c,
            "ventas": v,
            "diferencia": v - c
        })

    return {
        "stock_total": stock_total,
        "consumo_mes": consumo_mes,
        "stock_menos_produccion": stock_total - consumo_mes,
        "producciones_mes": producciones_mes,
        "ventas_mes": ventas_mes,
        "comparativo": comparativo,
        "grafico_comparativo": {
            "labels": [c["mes"] for c in comparativo],
            "compras": [float(c["compras"]) for c in comparativo],
            "ventas": [float(c["ventas"]) for c in comparativo],
        },
        "historial_mes": (
            MovimientoStock.objects.filter(fecha__gte=ini_dt, fecha__lt=fin_dt)
            .select_related("materia_prima", "proveedor").order_by("-fecha")
        ),
    }


@login_required(login_url='login')
@user_passes_test(es_gerente, login_url='/')
def reportes(request):
    datos = _datos_reporte(request.GET.get("mes", ""))
    datos["seccion"] = "reportes"
    datos["imprimir"] = request.GET.get("imprimir") == "1"
    datos["base_template"] = "inventario/base.html"
    return render(request, "inventario/reportes.html", datos)


def _num_csv(x):
    """Número con coma decimal y 2 decimales, para Excel/LibreOffice en español."""
    if x is None or x == "":
        return ""
    return f"{Decimal(str(x)):.2f}".replace(".", ",")


@login_required(login_url='login')
@user_passes_test(es_gerente, login_url='/')
def reportes_csv(request):
    d = _datos_reporte(request.GET.get("mes", ""))
    n = _num_csv

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="informe-{d["mes_valor"]}.csv"'
    resp.write("\ufeff")
    w = csv.writer(resp, delimiter=";", quoting=csv.QUOTE_ALL)

    w.writerow(["Informe mensual CAUQUEVA", d["mes_nombre"]])
    w.writerow([])
    w.writerow(["RESUMEN"])
    w.writerow(["Stock total acumulado (Kg)", n(d["stock_total"])])
    w.writerow(["Stock total menos lo producido (Kg)", n(d["stock_menos_produccion"])])
    w.writerow(["Consumos y producción (Kg)", n(d["con_kg"])])
    w.writerow(["Movimientos", d["movimientos"]])
    w.writerow(["Materias primas críticas al cierre", d["criticas_cierre"]])
    w.writerow(["Producciones del mes", d["producciones_mes"]])
    w.writerow(["Ventas del mes ($)", n(d["ventas_mes"])])
    w.writerow([])
    w.writerow(["MATERIAS PRIMAS"])
    w.writerow([
        "Materia prima", "Unidad", "Stock inicial", "Ingresos",
        "Consumos", "Stock final", "Estado"
    ])

    for f in d["filas"]:
        w.writerow([
            f["materia"], f["unidad"], n(f["inicial"]), n(f["ingresos"]),
            n(f["consumos"]), n(f["final"]),
            "Crítica" if f["critica"] else "Normal"
        ])

    w.writerow([])
    w.writerow(["COMPRAS POR PROVEEDOR"])
    w.writerow(["Proveedor", "Materia prima", "Unidad", "Cantidad", "Ingresos", "Total ($)"])

    for c in d["compras"]:
        w.writerow([
            c["proveedor__nombre"] or "Sin proveedor",
            c["materia_prima__nombre"],
            c["materia_prima__unidad_medida"],
            n(c["total"]),
            c["veces"],
            n(c["precio_total"])
        ])

    w.writerow([])
    w.writerow(["COMPARATIVO MENSUAL: PAGADO EN MATERIA PRIMA VS VENTAS POR PRODUCCIÓN ($)"])
    w.writerow(["Mes", "Pagado en materia prima", "Ventas por producción", "Diferencia"])

    for c in d["comparativo"]:
        w.writerow([c["mes"], n(c["compras"]), n(c["ventas"]), n(c["diferencia"])])

    w.writerow([])
    w.writerow(["HISTORIAL DE MOVIMIENTOS DEL MES"])
    w.writerow([
        "Fecha y hora", "Operación", "Materia prima", "Cantidad (Kg)",
        "Precio por Kg ($)", "Total ($)", "Proveedor", "Observaciones"
    ])

    for mov in d["historial_mes"]:
        if mov.proveedor:
            proveedor_str = mov.proveedor.nombre
            if getattr(mov.proveedor, 'es_externo', False):
                proveedor_str += " (externo)"
        else:
            proveedor_str = "—"

        precio_u = getattr(mov, 'precio_unitario', None)
        total_mov = getattr(mov, 'total', None)

        w.writerow([
            timezone.localtime(mov.fecha).strftime("%d/%m/%Y %H:%M"),
            "Ingreso" if mov.tipo == "INGRESO" else "Consumo",
            mov.materia_prima,
            n(mov.cantidad),
            n(precio_u) if precio_u is not None else "",
            n(total_mov) if total_mov is not None else "",
            proveedor_str,
            mov.observaciones or "",
        ])

    return resp


# Solo el gerente puede ver la lista general del inventario
@login_required(login_url='login')
@user_passes_test(es_gerente, login_url='/consumos/')
def listar_inventario(request):
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    if estado not in {"criticas", "normales"}:
        estado = ""

    todas_las_materias = MateriaPrima.objects.all()
    total = todas_las_materias.count()
    normales = todas_las_materias.filter(
        stock_actual__gt=F("stock_minimo")
    ).count()
    criticas = todas_las_materias.filter(
        stock_actual__lte=F("stock_minimo")
    ).count()

    materias = todas_las_materias
    if q:
        materias = materias.filter(
            Q(nombre__icontains=q) | Q(variedad__icontains=q)
        )
    if estado == "criticas":
        materias = materias.filter(stock_actual__lte=F("stock_minimo"))
    elif estado == "normales":
        materias = materias.filter(stock_actual__gt=F("stock_minimo"))

    materias = materias.order_by("nombre", "variedad")

    return render(
        request,
        "inventario/inventariostock.html",
        {
            "materias": materias,
            "total": total,
            "normales": normales,
            "criticas": criticas,
            "q": q,
            "estado": estado,
        },
    )


@login_required(login_url='login')
def alertas_stock(request):
    materias_primas = MateriaPrima.objects.all()
    lista_alertas = []

    for mp in materias_primas:
        if mp.stock_actual <= mp.stock_minimo:
            deficit = mp.stock_minimo - mp.stock_actual

            lista_alertas.append({
                'nombre': mp.nombre,
                'variedad': mp.variedad if mp.variedad else '',
                'stock_actual': mp.stock_actual,
                'stock_minimo': mp.stock_minimo,
                'deficit': deficit,
                'unidad': mp.get_unidad_medida_display()
            })

    return render(request, 'inventario/alertas.html', {
        'alertas': lista_alertas
    })


# Operaciones con consumo de materias primas
@login_required(login_url='login')
def consumos(request):
    producto_id = request.GET.get("producto", "")
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")

    producciones = Produccion.objects.select_related("producto").prefetch_related(
        "consumos__materia_prima"
    )

    if producto_id.isdigit():
        producciones = producciones.filter(producto_id=producto_id)
    if _fecha(desde):
        producciones = producciones.filter(fecha__date__gte=_fecha(desde))
    if _fecha(hasta):
        producciones = producciones.filter(fecha__date__lte=_fecha(hasta))

    suma_total = Sum(
        F("cantidad") * F("precio_unitario"),
        output_field=DecimalField(max_digits=14, decimal_places=2)
    )

    ahora = timezone.localtime()
    del_mes = Produccion.objects.filter(
        fecha__year=ahora.year, fecha__month=ahora.month
    )

    pagina = Paginator(producciones, 20).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "inventario/consumos.html", {
        "pagina": pagina,
        "productos": Producto.objects.order_by("nombre"),
        "producto_id": producto_id,
        "desde": desde,
        "hasta": hasta,
        "total_periodo": producciones.count(),
        "ventas_periodo": producciones.aggregate(t=suma_total)["t"] or Decimal("0"),
        "del_mes": del_mes.count(),
        "ventas_mes": del_mes.aggregate(t=suma_total)["t"] or Decimal("0"),
        "querystring": params.urlencode(),
    })


@login_required(login_url='login')
def registrar_consumo(request):
    if request.method == "POST":
        formulario = ProduccionForm(request.POST)

        if formulario.is_valid():
            d = formulario.cleaned_data

            try:
                produccion, materias = Produccion.registrar(
                    d["producto"],
                    d["cantidad"],
                    d["fecha"],
                    d["observaciones"],
                )
            except ValidationError as error:
                formulario.add_error(None, error)
            else:
                messages.success(
                    request,
                    f"Se registró la producción de {produccion.cantidad} × "
                    f"{produccion.producto}. Ventas: ${produccion.total:,.2f}.",
                )
                return redirect("consumos")

    else:
        formulario = ProduccionForm()

    productos = {
        str(p.id): {
            "precio": float(p.precio),
            "ingredientes": [
                {
                    "nombre": str(i.materia_prima),
                    "por_unidad": float(i.cantidad_por_unidad),
                    "stock": float(i.materia_prima.stock_actual),
                }
                for i in p.ingredientes.all()
            ],
        }
        for p in Producto.objects.filter(activo=True).prefetch_related(
            "ingredientes__materia_prima"
        )
    }

    return render(
        request,
        "inventario/registrarconsumo.html",
        {
            "formulario": formulario,
            "productos": productos,
        },
    )


# Operaciones con proveedor
@login_required(login_url='login')
@user_passes_test(es_gerente, login_url='/')
def proveedores(request):
    q = request.GET.get("q", "").strip()
    ingresos = MovimientoStock.objects.filter(tipo="INGRESO").select_related("materia_prima")

    lista = Proveedor.objects.annotate(
        num_ingresos=Count("movimientostock", filter=Q(movimientostock__tipo="INGRESO")),
        ultimo_ingreso=Max("movimientostock__fecha", filter=Q(movimientostock__tipo="INGRESO")),
    ).prefetch_related(
        "materias_primas",
        Prefetch("movimientostock_set", queryset=ingresos, to_attr="ingresos_cargados"),
    )

    if q:
        lista = lista.filter(Q(nombre__icontains=q) | Q(telefono__icontains=q) | Q(email__icontains=q))
    lista = list(lista.order_by("nombre"))

    for p in lista:
        declaradas = {str(m) for m in p.materias_primas.all()}
        entregadas = {str(mov.materia_prima) for mov in p.ingresos_cargados}
        p.materias = sorted(declaradas | entregadas)

    return render(request, "inventario/proveedores.html", {
        "proveedores": lista,
        "q": q,
        "total": Proveedor.objects.count(),
    })


@login_required(login_url='login')
@user_passes_test(es_gerente, login_url='/')
def crear_proveedor(request):
    if request.method == "POST":
        formulario = ProveedorForm(request.POST)
        if formulario.is_valid():
            proveedor = formulario.save()
            messages.success(request, f"Se registró al proveedor «{proveedor}».")
            return redirect("proveedores")
    else:
        formulario = ProveedorForm()

    return render(request, "inventario/formularioproveedor.html", {
        "formulario": formulario, "titulo": "Nuevo proveedor",
    })


@login_required(login_url='login')
@user_passes_test(es_gerente, login_url='/')
def editar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == "POST":
        formulario = ProveedorForm(request.POST, instance=proveedor)
        if formulario.is_valid():
            formulario.save()
            messages.success(request, f"Se actualizaron los datos de «{proveedor}».")
            return redirect("proveedores")
    else:
        formulario = ProveedorForm(instance=proveedor)

    return render(request, "inventario/formularioproveedor.html", {
        "formulario": formulario, "titulo": f"Editar proveedor: {proveedor}",
    })


@login_required(login_url='login')
@user_passes_test(es_gerente, login_url='/')
@require_POST
def eliminar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    nombre = proveedor.nombre
    # Los movimientos históricos se conservan (el proveedor queda en blanco).
    proveedor.delete()
    messages.success(request, f"Se eliminó al proveedor «{nombre}».")
    return redirect("proveedores")


# Funciones del historial: exportar y editar

@login_required(login_url='login')
def exportar_historial(request):
    movimientos = MovimientoStock.objects.select_related(
        "materia_prima", "proveedor"
    ).order_by("-fecha")

    # Aplicamos los mismos filtros que tenga el usuario en la interfaz
    materia_id = request.GET.get("materia")
    tipo = (request.GET.get("tipo") or "").upper()

    if materia_id and materia_id.isdigit():
        movimientos = movimientos.filter(materia_prima_id=materia_id)
    if tipo in ("INGRESO", "CONSUMO"):
        movimientos = movimientos.filter(tipo=tipo)

    movimientos, _, _ = _filtrar_por_fechas(request, movimientos)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="historial_movimientos.csv"'
    response.write("\ufeff")

    writer = csv.writer(response, delimiter=";", quoting=csv.QUOTE_ALL)

    writer.writerow([
        "Fecha y Hora",
        "Tipo de Movimiento",
        "Materia Prima",
        "Variedad",
        "Cantidad",
        "Unidad",
        "Precio Unitario ($)",
        "Proveedor",
        "Observaciones"
    ])

    f_num = _num_csv

    for mov in movimientos:
        fecha_str = timezone.localtime(mov.fecha).strftime("%d/%m/%Y %H:%M")
        proveedor_str = mov.proveedor.nombre if mov.proveedor else "—"
        precio_u = getattr(mov, "precio_unitario", None)

        writer.writerow([
            fecha_str,
            mov.get_tipo_display() if hasattr(mov, "get_tipo_display") else mov.tipo,
            mov.materia_prima.nombre,
            mov.materia_prima.variedad or "—",
            f_num(mov.cantidad),
            mov.materia_prima.unidad_medida,
            f_num(precio_u),
            proveedor_str,
            mov.observaciones or "",
        ])

    return response


# Vista para modificar movimiento (solo gerente)
@login_required(login_url='login')
@user_passes_test(es_gerente, login_url='/')
def editar_movimiento(request, id):
    movimiento = get_object_or_404(MovimientoStock, id=id)

    if request.method == "POST":
        formulario = MovimientoStockForm(request.POST, instance=movimiento)
        if formulario.is_valid():
            try:
                formulario.save()
            except ValidationError as error:
                formulario.add_error(None, error)
            else:
                messages.success(request, "Movimiento actualizado correctamente.")
                return redirect('historial')
    else:
        formulario = MovimientoStockForm(instance=movimiento)

    return render(request, "inventario/registrarproducto.html", {
        "formulario": formulario,
        "titulo_formulario": f"Editar Movimiento #{movimiento.id}"
    })
