from .models import Inventario, Movimiento


def descontar_stock(producto, cantidad, usuario, origen_id, origen_tipo='venta', notas=None):
    """
    Descuenta stock del producto. Lanza ValueError si no hay suficiente stock.
    """
    inventario, _ = Inventario.objects.get_or_create(producto=producto)

    if inventario.stock_actual < cantidad:
        raise ValueError(
            f'Stock insuficiente para {producto.nombre}. '
            f'Stock actual: {inventario.stock_actual}, solicitado: {cantidad}.'
        )

    stock_antes              = inventario.stock_actual
    inventario.stock_actual -= cantidad
    inventario.save(update_fields=['stock_actual', 'ultima_actualizacion'])

    Movimiento.objects.create(
        producto      = producto,
        usuario       = usuario,
        tipo          = 'salida',
        cantidad      = cantidad,
        stock_antes   = stock_antes,
        stock_despues = inventario.stock_actual,
        origen_tipo   = origen_tipo,
        origen_id     = origen_id,
        notas         = notas,
    )
    return inventario


def aumentar_stock(producto, cantidad, usuario, origen_tipo, origen_id, notas=None):
    """
    Aumenta el stock del producto y registra el movimiento.
    """
    inventario, _            = Inventario.objects.get_or_create(producto=producto)
    stock_antes              = inventario.stock_actual
    inventario.stock_actual += cantidad
    inventario.save(update_fields=['stock_actual', 'ultima_actualizacion'])

    Movimiento.objects.create(
        producto      = producto,
        usuario       = usuario,
        tipo          = 'entrada',
        cantidad      = cantidad,
        stock_antes   = stock_antes,
        stock_despues = inventario.stock_actual,
        origen_tipo   = origen_tipo,
        origen_id     = origen_id,
        notas         = notas,
    )
    return inventario


def ajustar_stock(producto, cantidad_nueva, usuario, notas=None):
    """
    Ajuste manual: el almacenero corrige el stock real al valor exacto.
    """
    inventario, _           = Inventario.objects.get_or_create(producto=producto)
    stock_antes             = inventario.stock_actual
    inventario.stock_actual = cantidad_nueva
    inventario.save(update_fields=['stock_actual', 'ultima_actualizacion'])

    Movimiento.objects.create(
        producto      = producto,
        usuario       = usuario,
        tipo          = 'ajuste',
        cantidad      = abs(cantidad_nueva - stock_antes),
        stock_antes   = stock_antes,
        stock_despues = cantidad_nueva,
        origen_tipo   = 'ajuste_manual',
        notas         = notas,
    )
    return inventario