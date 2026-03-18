from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WilayahViewSet, NamaVariabelViewSet, DataViewSet

router = DefaultRouter()
router.register('wilayah', WilayahViewSet, basename='wilayah')
router.register('variabel', NamaVariabelViewSet, basename='variabel')
router.register('data', DataViewSet, basename='data')

urlpatterns = [
    path('api/', include(router.urls)),
]