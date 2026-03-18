from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from .models import Wilayah, NamaVariabel, Data
from .serializers import WilayahSerializer, NamaVariabelSerializer, DataSerializer


class WilayahViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wilayah.objects.all().order_by('tipe_wilayah', 'nama_wilayah')
    serializer_class = WilayahSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['tipe_wilayah']
    search_fields = ['nama_wilayah', 'kode_wilayah']


class NamaVariabelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NamaVariabel.objects.all().order_by('nama_variabel')
    serializer_class = NamaVariabelSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['nama_variabel']


class DataViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DataSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['tahun', 'wilayah__tipe_wilayah']
    search_fields = ['wilayah__nama_wilayah', 'variabel_data__nama_variabel']

    def get_queryset(self):
        qs = Data.objects.select_related('wilayah', 'variabel_data')

        # Filter: ?wilayah_id=uuid1,uuid2
        wilayah_ids = self.request.query_params.get('wilayah_id')
        if wilayah_ids:
            qs = qs.filter(wilayah__id__in=wilayah_ids.split(','))

        # Filter: ?variabel_id=uuid1,uuid2
        variabel_ids = self.request.query_params.get('variabel_id')
        if variabel_ids:
            qs = qs.filter(variabel_data__id__in=variabel_ids.split(','))

        # Filter: ?tahun_dari=2020&tahun_sampai=2024
        tahun_dari = self.request.query_params.get('tahun_dari')
        tahun_sampai = self.request.query_params.get('tahun_sampai')
        if tahun_dari:
            qs = qs.filter(tahun__gte=int(tahun_dari))
        if tahun_sampai:
            qs = qs.filter(tahun__lte=int(tahun_sampai))

        return qs.order_by('wilayah__nama_wilayah', 'tahun', 'variabel_data__nama_variabel')

    @action(detail=False, methods=['get'], url_path='pivot')
    def pivot(self, request):
        qs = self.get_queryset()

        pivot_map = {}
        for row in qs:
            key = (str(row.wilayah.id), row.tahun)
            if key not in pivot_map:
                pivot_map[key] = {
                    'wilayah_id': str(row.wilayah.id),
                    'wilayah': row.wilayah.nama_wilayah,
                    'tipe_wilayah': row.wilayah.tipe_wilayah,
                    'kode_wilayah': row.wilayah.kode_wilayah,
                    'tahun': row.tahun,
                }
            key_variabel = row.variabel_data.nama_variabel.lower().replace(' ', '_')
            pivot_map[key][key_variabel] = float(row.nilai)

        hasil = sorted(pivot_map.values(), key=lambda x: (x['wilayah'], x['tahun']))
        return Response(hasil)

    @action(detail=False, methods=['get'], url_path='tahun-tersedia')
    def tahun_tersedia(self, request):
        tahun_list = (
            Data.objects.values_list('tahun', flat=True)
            .distinct()
            .order_by('tahun')
        )
        return Response(list(tahun_list))