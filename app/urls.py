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

# ── Daftar endpoint yang tersedia ──────────────────────────────────
#
#  GET /api/wilayah/                         → semua wilayah
#  GET /api/wilayah/?tipe_wilayah=Kota       → filter per tipe
#  GET /api/wilayah/?search=banda            → cari nama
#
#  GET /api/variabel/                        → semua variabel
#
#  GET /api/data/                            → semua data (paginasi 100)
#  GET /api/data/?tahun=2024                 → filter tahun
#  GET /api/data/?tahun_dari=2020&tahun_sampai=2024
#  GET /api/data/?wilayah_id=uuid1,uuid2
#  GET /api/data/?variabel_id=uuid1,uuid2
#  GET /api/data/?wilayah__tipe_wilayah=Kota
#
#  GET /api/data/pivot/                      → format pivot (untuk chart/tabel)
#  GET /api/data/pivot/?tahun=2024&wilayah__tipe_wilayah=Kota
#
#  GET /api/data/tahun-tersedia/             → ['2014','2015',...,'2024']
 