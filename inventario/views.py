from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import MateriaPrima, MovimientoStock,Proveedor
from .forms import MateriaPrimaForm,MovimientoStockForm, ProveedorForm,ConsumoForm
import csv 
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.utils.dateparse import parse_date
from django.db.models import Count, Max, Prefetch, Q, Sum
from django.core.paginator import Paginator


A_KG = {"KG": Decimal("1"), "TN": Decimal("1000")}
# Función auxiliar para comprobar si el usuario es "Gerente" (Staff)
def es_gerente(user):
    return user.is_staff

# Vista del Panel Principal
@login_required(login_url='login')
def panel_principal(request):
    materias_primas = MateriaPrima.objects.all()

    resumen = []
    stock_total_kilos = Decimal("0")
    alertas_criticas = []  # ahora es una lista de materias primas, no un número

    for mp in materias_primas:
        stock = mp.stock_actual
        # Solo se suma en kg lo que se mide en KG o TN (las "UN" no son kilos)
        if mp.unidad_medida in A_KG:
            stock_total_kilos += stock * A_KG[mp.unidad_medida]
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

    ultimos_movimientos = MovimientoStock.objects.all().order_by('-fecha')[:10]

    # --- Gráfico: ingresos y consumos por mes (últimos 12 meses) ---
    materia_id = request.GET.get("materia", "")
    if not materia_id.isdigit():
        materia_id = ""

    movs = MovimientoStock.objects.filter(
        fecha__gte=timezone.now() - timedelta(days=365)
    ).select_related("materia_prima")
    unidad_grafico = "Kg"
    if materia_id:
        movs = movs.filter(materia_prima_id=materia_id)
        elegida = materias_primas.filter(pk=materia_id).first()
        if elegida:
            unidad_grafico = elegida.get_unidad_medida_display()

    datos = defaultdict(lambda: {"INGRESO": 0.0, "CONSUMO": 0.0})
    for mov in movs:
        if materia_id:
            factor = Decimal("1")  # una sola materia: se muestra en su propia unidad
        else:
            factor = A_KG.get(mov.materia_prima.unidad_medida)
            if factor is None:
                continue
        mes = timezone.localtime(mov.fecha).strftime("%Y-%m")
        datos[mes][mov.tipo] += float(mov.cantidad * factor)

    meses = sorted(datos)
    grafico = {
        "labels": [f"{m[5:]}/{m[:4]}" for m in meses],
        "ingresos": [datos[m]["INGRESO"] for m in meses],
        "consumos": [datos[m]["CONSUMO"] for m in meses],
        "unidad": unidad_grafico,
    }

    # --- Consumo del mes actual, en kg ---
    ahora = timezone.localtime()
    consumo_mes = Decimal("0")
    consumos = MovimientoStock.objects.filter(
        tipo="CONSUMO", fecha__year=ahora.year, fecha__month=ahora.month
    ).select_related("materia_prima")
    for mov in consumos:
        factor = A_KG.get(mov.materia_prima.unidad_medida)
        if factor:
            consumo_mes += mov.cantidad * factor

    contexto = {
        'productos': resumen,
        'stock_total': stock_total_kilos,
        'alertas': alertas_criticas,             # lista para la tabla
        'cant_alertas': len(alertas_criticas),   # número para la tarjeta
        'movimientos': ultimos_movimientos,
        'materias': materias_primas.order_by("nombre"),
        'materia_id': materia_id,
        'grafico': grafico,
        'consumo_mes': consumo_mes,
        'seccion': 'panel',
    }

    return render(request, 'inventario/panelprincipal.html', contexto)

# Registrar Nueva Materia Prima (Catálogo)
@login_required(login_url='login')
def registrar_materia_prima(request):
    if request.method == "POST":
        formulario = MateriaPrimaForm(request.POST)
        if formulario.is_valid():
            materia = formulario.save()  # nace con stock 0
            messages.success(
                request,
                f"Se registró «{materia}». Cargale stock desde Registro de Ingresos.",
            )
            return redirect("inventario_stock")
    else:
        formulario = MateriaPrimaForm()

    return render(request, "inventario/registrarmateriaprima.html", {"formulario": formulario})

# Registrar Movimiento de Stock (Ingresos / Consumos)
@login_required(login_url='login')
def registrar_movimiento(request):
    if request.method == 'POST':
        formulario = MovimientoStockForm(request.POST)
        if formulario.is_valid():
            # commit=False pausa el guardado para que podamos hacer la matemática primero
            movimiento = formulario.save(commit=False)
            materia = movimiento.materia_prima
            
            if movimiento.tipo == 'INGRESO':
                materia.stock_actual += movimiento.cantidad
                
            elif movimiento.tipo == 'CONSUMO':
                # Validación fundamental: evitar consumos fantasma
                if movimiento.cantidad > materia.stock_actual:
                    messages.error(request, f"Stock insuficiente. Solo quedan {materia.stock_actual} Kg de {materia.nombre}.")
                    return render(request, 'inventario/registrarproducto.html', {
                        'formulario': formulario,
                        'titulo_formulario': 'Registrar Movimiento'
                    })
                materia.stock_actual -= movimiento.cantidad
            #guardamos los cambios en la base de datos
            materia.save()
            movimiento.save()
            
            messages.success(request, '¡Movimiento de stock registrado correctamente!')
            return redirect('panelprincipal') # Acá podrías redirigir a 'historial' si lo preferís
    else:
        formulario = MovimientoStockForm()
        
    return render(request, 'inventario/registrarproducto.html', {
        'formulario': formulario, 
        'titulo_formulario': 'Registrar Movimiento de Stock'
    })

# Vista del Historial General (Todos los movimientos)
@login_required(login_url='login')
def historial_general(request):
    # .all() trae todo. 
    # .select_related() optimiza la carga de las tablas relacionadas.
    # .order_by('-fecha') garantiza el orden: del más reciente al más viejo.
    movimientos = MovimientoStock.objects.all().select_related(
        'materia_prima', 
        'proveedor'
    ).order_by('-fecha')
    
    return render(request, 'inventario/historialgeneral.html', {
        'movimientos': movimientos
    })

# Vista de Informes Mensuales 
A_KG = {"KG": Decimal("1"), "TN": Decimal("1000")}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


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
        ing = t.get("ing") or cero
        con = t.get("con") or cero
        posterior = (t.get("ing_post") or cero) - (t.get("con_post") or cero)
        # Stock al cierre del mes = stock de hoy menos lo que se movió después
        cierre = m.stock_actual - posterior
        filas.append({
            "materia": m,
            "unidad": m.unidad_medida,
            "inicial": cierre - ing + con,
            "ingresos": ing,
            "consumos": con,
            "final": cierre,
            "critica": cierre <= m.stock_minimo,
            "n": t.get("n") or 0,
        })

    compras = (
        MovimientoStock.objects.filter(tipo="INGRESO").filter(en_mes)
        .order_by()
        .values("proveedor__nombre", "materia_prima__nombre", "materia_prima__variedad",
                "materia_prima__unidad_medida")
        .annotate(total=Sum("cantidad"), veces=Count("id"))
        .order_by("proveedor__nombre", "materia_prima__nombre")
    )

    # Totales generales en kg (las unidades "UN" no se pueden sumar como kg)
    ing_kg = sum((f["ingresos"] * A_KG[f["unidad"]] for f in filas if f["unidad"] in A_KG), cero)
    con_kg = sum((f["consumos"] * A_KG[f["unidad"]] for f in filas if f["unidad"] in A_KG), cero)

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
        "hay_unidades": any(f["unidad"] not in A_KG for f in filas),
        "criticas_cierre": sum(1 for f in filas if f["critica"]),
        "generado": timezone.localtime(),
    }


def reportes(request):
    datos = _datos_reporte(request.GET.get("mes", ""))
    datos["seccion"] = "reportes"
    return render(request, "inventario/reportes.html", datos)


def reportes_csv(request):
    d = _datos_reporte(request.GET.get("mes", ""))
    n = lambda x: str(x).replace(".", ",")  # coma decimal para Excel en español

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="informe-{d["mes_valor"]}.csv"'
    resp.write("\ufeff")  # para que Excel respete los acentos
    w = csv.writer(resp, delimiter=";")

    w.writerow(["Informe mensual CAUQUEVA", d["mes_nombre"]])
    w.writerow([])
    w.writerow(["MATERIAS PRIMAS"])
    w.writerow(["Materia prima", "Unidad", "Stock inicial", "Ingresos", "Consumos", "Stock final", "Estado"])
    for f in d["filas"]:
        w.writerow([f["materia"], f["unidad"], n(f["inicial"]), n(f["ingresos"]),
                    n(f["consumos"]), n(f["final"]), "Crítica" if f["critica"] else "Normal"])
    w.writerow([])
    w.writerow(["COMPRAS POR PROVEEDOR"])
    w.writerow(["Proveedor", "Materia prima", "Unidad", "Cantidad", "Ingresos"])
    for c in d["compras"]:
        w.writerow([c["proveedor__nombre"] or "Sin proveedor", c["materia_prima__nombre"],
                    c["materia_prima__unidad_medida"], n(c["total"]), c["veces"]])
    return resp


def listar_inventario(request):
    # 1. Traemos todas las materias primas activas desde la base de datos
    materias_primas = MateriaPrima.objects.all()
    
    lista_inventario = []

    # 2. Recorremos cada producto para evaluar su stock real y su alerta
    for mp in materias_primas:
        stock = mp.stock_actual
        # Comparamos si el stock actual es menor o igual al mínimo permitido
        alerta = stock <= mp.stock_minimo

        lista_inventario.append({
            'id_materia': mp.id,
            'nombre': mp.nombre,
            'variedad': mp.variedad if mp.variedad else 'Sin variedad',
            'stock': stock,
            'unidad': mp.get_unidad_medida_display(), # Muestra 'Kg', 'Tn', etc.
            'stock_minimo': mp.stock_minimo,
            'alerta': alerta # Variable booleana (True/False) para el diseño rojo/verde
        })

    contexto = {
        'productos': lista_inventario
    }
    
    # Renderiza el HTML específico de esta sección
    return render(request, 'inventario/inventariostock.html', contexto)


def alertas_stock(request):
    # Traemos todas las materias primas activas
    materias_primas = MateriaPrima.objects.all()
    lista_alertas = []

    for mp in materias_primas:
        # Filtramos solo las que están en estado crítico
        if mp.stock_actual <= mp.stock_minimo:
            # Calculamos la diferencia exacta para mostrar el déficit
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
    
def _fecha(valor):
    try:
        return parse_date(valor)
    except ValueError:
        return None

#operaciones con consumo de materias primas
@login_required(login_url='login')
def consumos(request):
    materia_id = request.GET.get("materia", "")
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")

    movimientos = MovimientoStock.objects.filter(tipo="CONSUMO").select_related("materia_prima")
    if materia_id.isdigit():
        movimientos = movimientos.filter(materia_prima_id=materia_id)
    if _fecha(desde):
        movimientos = movimientos.filter(fecha__date__gte=_fecha(desde))
    if _fecha(hasta):
        movimientos = movimientos.filter(fecha__date__lte=_fecha(hasta))

    # Total consumido por materia prima (cada una en su propia unidad)
    resumen = (
        movimientos.values("materia_prima__nombre", "materia_prima__variedad", "materia_prima__unidad_medida")
        .annotate(total=Sum("cantidad"), veces=Count("id"))
        .order_by("materia_prima__nombre")
    )

    ahora = timezone.localtime()
    del_mes = MovimientoStock.objects.filter(
        tipo="CONSUMO", fecha__year=ahora.year, fecha__month=ahora.month
    ).count()

    pagina = Paginator(movimientos, 20).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "inventario/consumos.html", {
        "pagina": pagina,
        "resumen": resumen,
        "materias": MateriaPrima.objects.order_by("nombre"),
        "materia_id": materia_id,
        "desde": desde,
        "hasta": hasta,
        "total_periodo": movimientos.count(),
        "del_mes": del_mes,
        "querystring": params.urlencode(),
    })


def registrar_consumo(request):
    if request.method == "POST":
        formulario = ConsumoForm(request.POST)
        if formulario.is_valid():
            mov = formulario.save()
            messages.success(
                request,
                f"Se registró el consumo de {mov.cantidad:g} {mov.materia_prima.unidad_medida} de {mov.materia_prima}.",
            )
            return redirect("consumos")
    else:
        formulario = ConsumoForm()

    stocks = {
        str(m.id): {"stock": float(m.stock_actual), "unidad": m.unidad_medida}
        for m in MateriaPrima.objects.all()
    }
    return render(request, "inventario/registrarconsumo.html", {"formulario": formulario, "stocks": stocks})

#Operaciones con proveedor

@login_required(login_url='login')
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
        lista = lista.filter(Q(nombre__icontains=q) | Q(telefono__icontains=q))
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
    
    
    