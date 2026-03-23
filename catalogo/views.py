from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import CategoriaProducto, SubcategoriaProducto, Producto
from .serializers import CategoriaSerializer, SubcategoriaSerializer, ProductoSerializer


class CategoriaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Lista todas las categorías
        categorias = CategoriaProducto.objects.all()
        serializer = CategoriaSerializer(categorias, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Crea una categoría nueva
        serializer = CategoriaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SubcategoriaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subcategorias = SubcategoriaProducto.objects.all()
        serializer    = SubcategoriaSerializer(subcategorias, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = SubcategoriaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Filtra por activo=True por defecto
        productos  = Producto.objects.filter(activo=True)
        serializer = ProductoSerializer(productos, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ProductoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductoDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            producto   = Producto.objects.get(pk=pk)
            serializer = ProductoSerializer(producto)
            return Response(serializer.data)
        except Producto.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        # Edita un producto existente
        try:
            producto   = Producto.objects.get(pk=pk)
            serializer = ProductoSerializer(producto, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Producto.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        # No borra el producto, solo lo desactiva
        try:
            producto        = Producto.objects.get(pk=pk)
            producto.activo = False
            producto.save()
            return Response({'mensaje': 'Producto desactivado'})
        except Producto.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)