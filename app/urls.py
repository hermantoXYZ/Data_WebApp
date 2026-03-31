from django.urls import path
from . import views

urlpatterns = [
    path('', views.peta_view, name='peta'),
    path('data/wilayah/<int:wilayah_id>/', views.data_wilayah_json, name='data-wilayah'),
    path('wilayah/list/', views.wilayah_list_json, name='wilayah-list'),
]
