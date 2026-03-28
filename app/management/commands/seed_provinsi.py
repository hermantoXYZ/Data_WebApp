"""
Management command: seed_provinsi
==================================
Mengambil data 38 Provinsi Indonesia dari GeoJSON BIG (via GitHub) dan
LANGSUNG membuat record Wilayah baru sekaligus mengisi kolom geom-nya.

Berguna jika tabel Wilayah belum punya record dengan tipe_wilayah='Provinsi'.

Cara pakai:
    python manage.py seed_provinsi
    python manage.py seed_provinsi --dry-run
"""

import json
import urllib.request
from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from app.models import Wilayah

URL_PROVINSI = (
    'https://raw.githubusercontent.com/ardian28/GeoJson-Indonesia-38-Provinsi'
    '/main/Provinsi/38%20Provinsi%20Indonesia%20-%20Provinsi.json'
)


class Command(BaseCommand):
    help = 'Seed 38 Provinsi Indonesia ke tabel Wilayah + isi kolom geom'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Simulasi tanpa menyimpan ke database')
        parser.add_argument('--update', action='store_true',
                            help='Update record yang sudah ada (berdasarkan kode_wilayah)')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        update  = options['update']

        self.stdout.write(f'📂 Mengambil data dari GitHub BIG ...')
        try:
            with urllib.request.urlopen(URL_PROVINSI) as r:
                geojson = json.loads(r.read())
        except Exception as e:
            raise CommandError(f'Gagal mengambil GeoJSON: {e}')

        features = geojson.get('features', [])
        self.stdout.write(f'✅ {len(features)} provinsi ditemukan.\n')

        dibuat = 0
        diupdate = 0
        gagal = 0

        for feat in features:
            props    = feat.get('properties', {})
            kode     = str(props.get('KODE_PROV', '')).strip()
            nama     = str(props.get('PROVINSI', '')).strip()
            geom_raw = feat.get('geometry')

            if not geom_raw:
                self.stdout.write(self.style.WARNING(f'  ⚠️ {nama}: geometry kosong, dilewati'))
                gagal += 1
                continue

            try:
                geom = GEOSGeometry(json.dumps(geom_raw), srid=4326)
                if isinstance(geom, Polygon):
                    geom = MultiPolygon(geom)
                elif not isinstance(geom, MultiPolygon):
                    self.stdout.write(self.style.WARNING(f'  ⚠️ {nama}: geometry bukan Polygon ({geom.geom_type})'))
                    gagal += 1
                    continue
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ⚠️ {nama}: gagal parse geometry — {e}'))
                gagal += 1
                continue

            # Cek apakah sudah ada di DB
            existing = Wilayah.objects.filter(kode_wilayah=kode, tipe_wilayah='Provinsi').first()

            if existing:
                if update:
                    if not dry_run:
                        existing.geom = geom
                        existing.save(update_fields=['geom'])
                    self.stdout.write(self.style.SUCCESS(
                        f'  🔄 {"[DRY RUN] " if dry_run else ""}Update: {existing.nama_wilayah} ({kode})'
                    ))
                    diupdate += 1
                else:
                    self.stdout.write(self.style.WARNING(
                        f'  ⏭️  Skip (sudah ada): {existing.nama_wilayah} ({kode}) — pakai --update untuk overwrite'
                    ))
            else:
                if not dry_run:
                    Wilayah.objects.create(
                        nama_wilayah=nama,
                        tipe_wilayah='Provinsi',
                        kode_wilayah=kode,
                        geom=geom,
                    )
                self.stdout.write(self.style.SUCCESS(
                    f'  ✅ {"[DRY RUN] " if dry_run else ""}Buat baru: {nama} ({kode})'
                ))
                dibuat += 1

        self.stdout.write('\n' + '─' * 50)
        self.stdout.write(self.style.SUCCESS(f'✅  Dibuat baru : {dibuat} provinsi'))
        self.stdout.write(self.style.WARNING(f'🔄  Diupdate   : {diupdate} provinsi'))
        self.stdout.write(self.style.ERROR  (f'❌  Gagal      : {gagal} provinsi') if gagal else '')
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN — tidak ada yang disimpan.'))
