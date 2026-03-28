from django.urls import path
from . import views

urlpatterns = [
    # Halaman utama: peta geospasial
    path('', views.peta_view, name='peta'),

    # AJAX: data semua variabel untuk satu wilayah (dipanggil saat klik peta)
    path('data/wilayah/<uuid:wilayah_id>/', views.data_wilayah_json, name='data-wilayah'),

    # AJAX: daftar wilayah untuk dropdown/filter
    path('wilayah/list/', views.wilayah_list_json, name='wilayah-list'),
]
