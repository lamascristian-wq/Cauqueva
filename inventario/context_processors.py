from .models import MateriaPrima

def notificaciones_stock(request):
    # Si el usuario no está logueado, no mostramos nada
    if not request.user.is_authenticated:
        return {}
        
    materias_primas = MateriaPrima.objects.all()
    alertas = []
    
    for mp in materias_primas:
        if mp.stock_actual <= mp.stock_minimo:
            alertas.append(mp)
            
    return {
        'total_alertas': len(alertas),
        # Mandamos solo las 5 primeras alertas para no hacer un menú gigante
        'alertas_recientes': alertas[:5] 
    }