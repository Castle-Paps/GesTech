from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import CategoriaProducto, SubcategoriaProducto, Producto
from .serializers import CategoriaSerializer, SubcategoriaSerializer, ProductoSerializer


# ── Categorías ────────────────────────────────────────────────────────────────

class CategoriaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        categorias = CategoriaProducto.objects.all()
        serializer = CategoriaSerializer(categorias, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CategoriaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoriaDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return CategoriaProducto.objects.get(pk=pk), None
        except CategoriaProducto.DoesNotExist:
            return None, Response(
                {'error': 'Categoría no encontrada'}, status=status.HTTP_404_NOT_FOUND
            )

    def get(self, request, pk):
        categoria, err = self._get(pk)
        if err: return err
        return Response(CategoriaSerializer(categoria).data)

    def patch(self, request, pk):
        categoria, err = self._get(pk)
        if err: return err
        serializer = CategoriaSerializer(categoria, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """
        Elimina la categoría solo si no tiene productos asociados.
        Si tiene subcategorías, las elimina en cascada (definido en el modelo).
        """
        categoria, err = self._get(pk)
        if err: return err

        if categoria.producto_set.exists():
            return Response(
                {'error': 'No se puede eliminar: hay productos asociados a esta categoría.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        categoria.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Subcategorías ─────────────────────────────────────────────────────────────

class SubcategoriaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Lista subcategorías. Filtra con ?categoria_id=N"""
        qs = SubcategoriaProducto.objects.select_related('categoria').all()
        categoria_id = request.query_params.get('categoria_id')
        if categoria_id:
            qs = qs.filter(categoria_id=categoria_id)
        return Response(SubcategoriaSerializer(qs, many=True).data)

    def post(self, request):
        serializer = SubcategoriaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SubcategoriaDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return SubcategoriaProducto.objects.get(pk=pk), None
        except SubcategoriaProducto.DoesNotExist:
            return None, Response(
                {'error': 'Subcategoría no encontrada'}, status=status.HTTP_404_NOT_FOUND
            )

    def get(self, request, pk):
        sub, err = self._get(pk)
        if err: return err
        return Response(SubcategoriaSerializer(sub).data)

    def patch(self, request, pk):
        sub, err = self._get(pk)
        if err: return err
        serializer = SubcategoriaSerializer(sub, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Elimina subcategoría solo si no tiene productos asociados."""
        sub, err = self._get(pk)
        if err: return err

        if Producto.objects.filter(subcategoria=sub).exists():
            return Response(
                {'error': 'No se puede eliminar: hay productos asociados a esta subcategoría.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        sub.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Productos ─────────────────────────────────────────────────────────────────

class ProductoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Lista productos activos por defecto.
        Filtros opcionales:
        ?activo=false          → solo inactivos
        ?activo=all            → todos (activos e inactivos)
        ?categoria_id=N
        ?subcategoria_id=N
        ?es_servicio=true|false
        ?buscar=texto          → busca en nombre, sku, marca, modelo
        """
        activo_param = request.query_params.get('activo', 'true').lower()

        if activo_param == 'all':
            qs = Producto.objects.all()
        elif activo_param == 'false':
            qs = Producto.objects.filter(activo=False)
        else:
            qs = Producto.objects.filter(activo=True)

        # Filtros adicionales
        categoria_id    = request.query_params.get('categoria_id')
        subcategoria_id = request.query_params.get('subcategoria_id')
        es_servicio     = request.query_params.get('es_servicio')
        buscar          = request.query_params.get('buscar')

        if categoria_id:
            qs = qs.filter(categoria_id=categoria_id)
        if subcategoria_id:
            qs = qs.filter(subcategoria_id=subcategoria_id)
        if es_servicio is not None:
            qs = qs.filter(es_servicio=(es_servicio.lower() == 'true'))
        if buscar:
            qs = (
                qs.filter(nombre__icontains=buscar)  |
                qs.filter(sku__icontains=buscar)      |
                qs.filter(marca__icontains=buscar)    |
                qs.filter(modelo__icontains=buscar)
            )

        serializer = ProductoSerializer(qs.select_related('categoria', 'subcategoria'), many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ProductoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductoDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return Producto.objects.select_related('categoria', 'subcategoria').get(pk=pk), None
        except Producto.DoesNotExist:
            return None, Response(
                {'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND
            )

    def get(self, request, pk):
        producto, err = self._get(pk)
        if err: return err
        return Response(ProductoSerializer(producto).data)

    def put(self, request, pk):
        producto, err = self._get(pk)
        if err: return err
        serializer = ProductoSerializer(producto, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        """Edición parcial: permite actualizar solo los campos enviados."""
        producto, err = self._get(pk)
        if err: return err
        serializer = ProductoSerializer(producto, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Soft-delete: desactiva el producto sin borrarlo de la BD."""
        producto, err = self._get(pk)
        if err: return err
        producto.activo = False
        producto.save(update_fields=['activo'])
        return Response({'mensaje': 'Producto desactivado'})


class ReactivarProductoView(APIView):
    """Reactiva un producto previamente desactivado."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            producto = Producto.objects.get(pk=pk, activo=False)
        except Producto.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado o ya está activo'},
                status=status.HTTP_404_NOT_FOUND
            )
        producto.activo = True
        producto.save(update_fields=['activo'])
        return Response(ProductoSerializer(producto).data)