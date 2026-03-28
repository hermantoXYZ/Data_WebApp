import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.gis.serializers.geojson import Serializer as GeoJSONSerializer
from .models import Wilayah, NamaVariabel, Data


def peta_view(request):
    """Halaman utama: peta geospasial Indonesia."""
    tipe_wilayah = request.GET.get('tipe', 'Provinsi')
    wilayah_list = Wilayah.objects.filter(tipe_wilayah=tipe_wilayah).order_by('nama_wilayah')
    tahun_list   = list(Data.objects.values_list('tahun', flat=True).distinct().order_by('tahun'))
    variabel_list = NamaVariabel.objects.all().order_by('nama_variabel')

    context = {
        'wilayah_list':  wilayah_list,
        'tahun_list':    tahun_list,
        'variabel_list': variabel_list,
        'tipe_aktif':    tipe_wilayah,
    }
    return render(request, 'peta.html', context)


def data_wilayah_json(request, wilayah_id):
    """
    AJAX: semua data variabel untuk satu wilayah.
    Dipanggil saat user klik polygon di peta.
    """
    wilayah = get_object_or_404(Wilayah, id=wilayah_id)
    tahun   = request.GET.get('tahun')

    qs = (
        Data.objects
        .filter(wilayah=wilayah)
        .select_related('variabel_data')
        .order_by('tahun', 'variabel_data__nama_variabel')
    )
    if tahun:
        qs = qs.filter(tahun=tahun)

    data = [
        {
            'tahun':    row.tahun,
            'variabel': row.variabel_data.nama_variabel,
            'deskripsi': row.variabel_data.deskripsi or '',
            'nilai':    float(row.nilai),
        }
        for row in qs
    ]

    return JsonResponse({
        'wilayah': wilayah.nama_wilayah,
        'tipe':    wilayah.tipe_wilayah,
        'kode':    wilayah.kode_wilayah,
        'data':    data,
    })


def wilayah_list_json(request):
    """
    AJAX: daftar wilayah + GeoJSON geometry untuk Leaflet.js.
    Jika kolom geom masih kosong, geojson.features akan kosong.
    """
    tipe = request.GET.get('tipe', 'Provinsi')
    qs   = Wilayah.objects.filter(tipe_wilayah=tipe).order_by('nama_wilayah')

    # Wilayah yang punya geom → serialisasi ke GeoJSON
    qs_dengan_geom = qs.exclude(geom__isnull=True)

    geojson = {'type': 'FeatureCollection', 'features': []}
    if qs_dengan_geom.exists():
        s = GeoJSONSerializer()
        raw = s.serialize(
            qs_dengan_geom,
            geometry_field='geom',
            fields=['nama_wilayah', 'tipe_wilayah', 'kode_wilayah'],
        )
        raw_dict = json.loads(raw)
        # Tambahkan 'id' ke setiap feature.properties
        for i, w in enumerate(qs_dengan_geom):
            raw_dict['features'][i]['properties']['id'] = str(w.id)
        geojson = raw_dict

    # Daftar sederhana (untuk sidebar)
    wilayah_simple = list(
        qs.values('id', 'nama_wilayah', 'kode_wilayah', 'tipe_wilayah')
    )
    for w in wilayah_simple:
        w['id'] = str(w['id'])

    return JsonResponse({
        'geojson': geojson,
        'wilayah': wilayah_simple,
    })
