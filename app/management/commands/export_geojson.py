"""
Management command: export_geojson
===================================
Export data geometry dari MySQL ke file GeoJSON statis.
Gunakan command ini DI LOCAL MACHINE sebelum deploy ke hosting.

File hasil export:
    static/geojson/provinsi.geojson
    static/geojson/kabkota.geojson

Cara pakai:
    python manage.py export_geojson
    python manage.py export_geojson --tipe Provinsi
    python manage.py export_geojson --tipe KabKota
"""

import json
import os
from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = 'Export geometry dari MySQL ke file GeoJSON statis (tanpa GDAL)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tipe',
            choices=['Provinsi', 'KabKota', 'Negara', 'Semua'],
            default='Semua',
            help='Tipe wilayah yang diekspor (default: Semua)',
        )

    def handle(self, *args, **options):
        tipe = options['tipe']
        geojson_dir = os.path.join(settings.BASE_DIR, 'static', 'geojson')
        os.makedirs(geojson_dir, exist_ok=True)

        if tipe in ('Negara', 'Semua'):
            self._export_tipe('Negara', geojson_dir)

        if tipe in ('Provinsi', 'Semua'):
            self._export_tipe('Provinsi', geojson_dir)

        if tipe in ('KabKota', 'Semua'):
            self._export_kabkota(geojson_dir)

        self.stdout.write(self.style.SUCCESS('\n✅ Export selesai!'))
        self.stdout.write(f'📁 File tersimpan di: {geojson_dir}')

    def _export_tipe(self, tipe_wilayah, out_dir):
        """Export satu tipe wilayah ke file GeoJSON."""
        filename = 'provinsi.geojson'
        out_path = os.path.join(out_dir, filename)

        self.stdout.write(f'\n📡 Export {tipe_wilayah}...')

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    id,
                    nama_wilayah,
                    tipe_wilayah,
                    kode_wilayah,
                    ST_AsGeoJSON(geom, 6) as geojson_geom
                FROM app_wilayah
                WHERE tipe_wilayah = %s
                  AND geom IS NOT NULL
                ORDER BY nama_wilayah
            """, [tipe_wilayah])
            rows = cursor.fetchall()

        features = []
        for row in rows:
            wilayah_id, nama, tipe, kode, geojson_str = row
            if not geojson_str:
                continue
            try:
                geometry = json.loads(geojson_str)
            except (json.JSONDecodeError, TypeError):
                self.stdout.write(self.style.WARNING(f'  ⚠️ Skip {nama}: geometry tidak valid'))
                continue

            features.append({
                'type': 'Feature',
                'geometry': geometry,
                'properties': {
                    'id': wilayah_id,
                    'nama_wilayah': nama,
                    'tipe_wilayah': tipe,
                    'kode_wilayah': kode,
                },
            })

        geojson_data = {
            'type': 'FeatureCollection',
            'features': features,
        }

        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, ensure_ascii=False, separators=(',', ':'))

        size_kb = os.path.getsize(out_path) / 1024
        self.stdout.write(self.style.SUCCESS(
            f'  ✅ {len(features)} {tipe_wilayah} → {filename} ({size_kb:.1f} KB)'
        ))


    def _export_kabkota(self, out_dir):
        """Export Kabupaten + Kota ke satu file GeoJSON."""
        filename = 'kabkota.geojson'
        out_path = os.path.join(out_dir, filename)

        self.stdout.write('\n📡 Export Kabupaten/Kota...')

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    id,
                    nama_wilayah,
                    tipe_wilayah,
                    kode_wilayah,
                    ST_AsGeoJSON(geom, 6) as geojson_geom
                FROM app_wilayah
                WHERE tipe_wilayah IN ('Kabupaten', 'Kota')
                  AND geom IS NOT NULL
                ORDER BY nama_wilayah
            """)
            rows = cursor.fetchall()

        features = []
        for row in rows:
            wilayah_id, nama, tipe, kode, geojson_str = row
            if not geojson_str:
                continue
            try:
                geometry = json.loads(geojson_str)
            except (json.JSONDecodeError, TypeError):
                self.stdout.write(self.style.WARNING(f'  ⚠️ Skip {nama}: geometry tidak valid'))
                continue

            features.append({
                'type': 'Feature',
                'geometry': geometry,
                'properties': {
                    'id': wilayah_id,
                    'nama_wilayah': nama,
                    'tipe_wilayah': tipe,
                    'kode_wilayah': kode,
                },
            })

        geojson_data = {
            'type': 'FeatureCollection',
            'features': features,
        }

        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, ensure_ascii=False, separators=(',', ':'))

        size_kb = os.path.getsize(out_path) / 1024
        self.stdout.write(self.style.SUCCESS(
            f'  ✅ {len(features)} Kabupaten/Kota → {filename} ({size_kb:.1f} KB)'
        ))
