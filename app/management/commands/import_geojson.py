"""
Management command: import_geojson
==================================
Mengimport data geometri (polygon) dari file GeoJSON ke kolom `geom`
pada model Wilayah, dicocokkan berdasarkan kode_wilayah (kode BPS).

Cara pakai:
    python manage.py import_geojson --file path/ke/file.geojson
    python manage.py import_geojson --file path/ke/file.geojson --tipe Provinsi
    python manage.py import_geojson --file path/ke/file.geojson --field-kode ADM1_PCODE --field-nama NAME_1

Sumber GeoJSON Indonesia:
    Provinsi   : https://raw.githubusercontent.com/superpikar/indonesia-geojson/master/indonesia-prov.geojson
    Kabupaten  : https://raw.githubusercontent.com/superpikar/indonesia-geojson/master/indonesia.geojson
"""

import json
import urllib.request
from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from app.models import Wilayah


class Command(BaseCommand):
    help = 'Import geometri polygon dari GeoJSON ke kolom geom pada tabel Wilayah'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', '-f',
            type=str,
            help='Path ke file GeoJSON lokal, atau URL http(s)://...',
        )
        parser.add_argument(
            '--url',
            type=str,
            help='URL GeoJSON (alternatif jika tidak pakai --file)',
        )
        parser.add_argument(
            '--tipe',
            type=str,
            default=None,
            help='Filter tipe wilayah yang akan diupdate: Provinsi | Kabupaten | Kota',
        )
        parser.add_argument(
            '--field-kode',
            type=str,
            default='kode_wilayah',
            help='Nama field properties di GeoJSON yang berisi kode wilayah BPS (default: kode_wilayah)',
        )
        parser.add_argument(
            '--field-nama',
            type=str,
            default='nama_wilayah',
            help='Nama field properties di GeoJSON yang berisi nama wilayah (default: nama_wilayah)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulasi tanpa menyimpan ke database',
        )

    def handle(self, *args, **options):
        sumber = options.get('file') or options.get('url')
        if not sumber:
            raise CommandError(
                'Masukkan path file dengan --file atau URL dengan --url.\n'
                'Contoh URL provinsi:\n'
                '  python manage.py import_geojson --url '
                'https://raw.githubusercontent.com/superpikar/indonesia-geojson/master/indonesia-prov.geojson'
            )

        field_kode = options['field_kode']
        field_nama = options['field_nama']
        tipe_filter = options.get('tipe')
        dry_run = options['dry_run']

        # ── Baca GeoJSON ──
        self.stdout.write(f'📂 Membaca GeoJSON dari: {sumber}')
        try:
            if sumber.startswith('http://') or sumber.startswith('https://'):
                with urllib.request.urlopen(sumber) as r:
                    geojson = json.loads(r.read())
            else:
                with open(sumber, encoding='utf-8') as f:
                    geojson = json.load(f)
        except Exception as e:
            raise CommandError(f'Gagal membaca GeoJSON: {e}')

        features = geojson.get('features', [])
        self.stdout.write(f'✅ {len(features)} feature ditemukan dalam GeoJSON.\n')

        # ── Proses tiap feature ──
        cocok = 0
        gagal = 0
        tidak_ada = 0

        for feat in features:
            props = feat.get('properties', {})
            kode  = str(props.get(field_kode, '')).strip()
            nama  = str(props.get(field_nama, '')).strip()
            geom_raw = feat.get('geometry')

            if not geom_raw:
                self.stdout.write(self.style.WARNING(f'  ⚠️  Fitur "{nama}" tidak punya geometry, dilewati.'))
                gagal += 1
                continue

            # konversi ke GEOSGeometry
            try:
                geom = GEOSGeometry(json.dumps(geom_raw), srid=4326)
                # pastikan bentuknya MultiPolygon
                if isinstance(geom, Polygon):
                    geom = MultiPolygon(geom)
                elif not isinstance(geom, MultiPolygon):
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠️  Geometry "{nama}" bukan Polygon/MultiPolygon ({geom.geom_type}), dilewati.'
                    ))
                    gagal += 1
                    continue
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ⚠️  Gagal parse geometry "{nama}": {e}'))
                gagal += 1
                continue

            # Cari Wilayah di DB berdasarkan kode_wilayah
            qs = Wilayah.objects.filter(kode_wilayah=kode)
            if tipe_filter:
                qs = qs.filter(tipe_wilayah=tipe_filter)

            if not qs.exists():
                # coba cocokkan dengan nama (fallback)
                qs = Wilayah.objects.filter(nama_wilayah__icontains=nama)
                if tipe_filter:
                    qs = qs.filter(tipe_wilayah=tipe_filter)

            if not qs.exists():
                self.stdout.write(
                    self.style.WARNING(f'  🔍 Tidak ditemukan di DB: kode={kode!r}, nama={nama!r}')
                )
                tidak_ada += 1
                continue

            for w in qs:
                if not dry_run:
                    w.geom = geom
                    w.save(update_fields=['geom'])
                self.stdout.write(
                    self.style.SUCCESS(f'  ✅ {"[DRY RUN] " if dry_run else ""}Update: {w.nama_wilayah} ({w.kode_wilayah})')
                )
                cocok += 1

        # ── Ringkasan ──
        self.stdout.write('\n' + '─' * 50)
        self.stdout.write(self.style.SUCCESS(f'✅  Berhasil diupdate : {cocok} wilayah'))
        self.stdout.write(self.style.WARNING(f'🔍  Tidak ditemukan di DB : {tidak_ada} feature'))
        self.stdout.write(self.style.ERROR  (f'❌  Gagal parse geometry : {gagal} feature') if gagal else '')
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN — tidak ada yang disimpan ke database.'))
