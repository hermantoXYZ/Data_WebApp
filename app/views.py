import json
import os
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.conf import settings
from .models import Wilayah, NamaVariabel, Data


_GEOJSON_CACHE = {}

def _load_geojson(tipe: str) -> dict:
    cache_key_map = {
        'Provinsi':  'provinsi',
        'Kabupaten': 'kabkota',
        'Kota':      'kabkota',
        'Negara':    'negara',
    }
    cache_key = cache_key_map.get(tipe, 'provinsi')

    if cache_key not in _GEOJSON_CACHE:
        filename = f'{cache_key}.geojson'
        path = os.path.join(settings.BASE_DIR, 'static', 'geojson', filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                _GEOJSON_CACHE[cache_key] = json.load(f)
        except FileNotFoundError:
            _GEOJSON_CACHE[cache_key] = {'type': 'FeatureCollection', 'features': []}

    return _GEOJSON_CACHE[cache_key]


def peta_view(request):
    tipe_wilayah  = request.GET.get('tipe', 'Provinsi')
    wilayah_list  = Wilayah.objects.filter(tipe_wilayah=tipe_wilayah).order_by('nama_wilayah')
    tahun_list    = list(Data.objects.values_list('tahun', flat=True).distinct().order_by('tahun'))
    variabel_list = NamaVariabel.objects.all().order_by('nama_variabel')

    context = {
        'wilayah_list':  wilayah_list,
        'tahun_list':    tahun_list,
        'variabel_list': variabel_list,
        'tipe_aktif':    tipe_wilayah,
    }
    return render(request, 'peta.html', context)


def data_wilayah_json(request, wilayah_id):
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
            'tahun':     row.tahun,
            'variabel':  row.variabel_data.nama_variabel,
            'deskripsi': row.variabel_data.deskripsi or '',
            'nilai':     float(row.nilai),
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
    tipe = request.GET.get('tipe', 'Provinsi')

    geojson = _load_geojson(tipe)

    qs = Wilayah.objects.filter(tipe_wilayah=tipe).order_by('nama_wilayah')

    kode_to_wilayah = {w.kode_wilayah: w for w in qs if w.kode_wilayah}

    geojson_copy = {
        'type': 'FeatureCollection',
        'features': [],
    }
    for feature in geojson.get('features', []):
        props = feature.get('properties', {})
        kode  = props.get('kode_wilayah')
        feat_tipe = props.get('tipe_wilayah', '')
        if feat_tipe != tipe:
            continue
        if kode and kode in kode_to_wilayah:
            props = dict(props)
            props['id'] = kode_to_wilayah[kode].id

        geojson_copy['features'].append({
            'type':       'Feature',
            'geometry':   feature['geometry'],
            'properties': props,
        })

    wilayah_simple = list(qs.values('id', 'nama_wilayah', 'kode_wilayah', 'tipe_wilayah'))

    return JsonResponse({
        'geojson': geojson_copy,
        'wilayah': wilayah_simple,
    })
