"""
Management command: import_geom_kabkota
=========================================
Import geometri Kabupaten/Kota Indonesia dari geoBoundaries (ADM2).
Pencocokan dilakukan berdasarkan NAMA (fuzzy: strip prefix "Kab." / "Kota " / dll.)
karena geoBoundaries tidak menyertakan kode BPS.

Cara pakai:
    python manage.py import_geom_kabkota
    python manage.py import_geom_kabkota --dry-run
    python manage.py import_geom_kabkota --verbose
"""

import json, re, unicodedata, urllib.request
from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from app.models import Wilayah

URL = (
    'https://github.com/wmgeolab/geoBoundaries/raw/main/'
    'releaseData/gbOpen/IDN/ADM2/geoBoundaries-IDN-ADM2.geojson'
)


def normalisasi(nama: str) -> str:
    """Normalkan nama wilayah untuk pencocokan fuzzy."""
    nama = nama.lower()
    nama = unicodedata.normalize('NFD', nama)
    nama = ''.join(c for c in nama if unicodedata.category(c) != 'Mn')  # strip aksen
    # hapus prefix umum
    for prefix in ('kab. ', 'kabupaten ', 'kota ', 'administrasi ', 'kepulauan '):
        if nama.startswith(prefix):
            nama = nama[len(prefix):]
    nama = re.sub(r'\s+', ' ', nama).strip()
    return nama


class Command(BaseCommand):
    help = 'Import geometri Kabupaten/Kota dari geoBoundaries (name-matching)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Simulasi tanpa simpan ke database')
        parser.add_argument('--verbose', '-v2', action='store_true',
                            help='Tampilkan detail semua proses')
        parser.add_argument('--only-null', action='store_true', default=True,
                            help='Hanya update wilayah yang geom-nya NULL (default: True)')

    def handle(self, *args, **options):
        dry_run  = options['dry_run']
        verbose  = options['verbose']
        only_null = options['only_null']

        # ── Download GeoJSON ──
        self.stdout.write('📡 Mengunduh geoBoundaries ADM2 Indonesia...')
        try:
            with urllib.request.urlopen(URL, timeout=60) as r:
                raw = r.read()
            geojson = json.loads(raw)
        except Exception as e:
            raise CommandError(f'Gagal mengunduh: {e}')

        features = geojson.get('features', [])
        self.stdout.write(f'✅ {len(features)} feature ADM2 ditemukan.\n')

        # Bangun lookup: norma_nama → list[feature]
        lookup: dict[str, list] = {}
        for feat in features:
            nama_geo = feat.get('properties', {}).get('shapeName', '')
            key = normalisasi(nama_geo)
            lookup.setdefault(key, []).append(feat)

        # ── Ambil wilayah dari DB ──
        qs = Wilayah.objects.filter(tipe_wilayah__in=['Kota', 'Kabupaten'])
        if only_null:
            qs = qs.filter(geom__isnull=True)

        total = qs.count()
        self.stdout.write(f'🗂️  {total} wilayah akan diproses.\n')

        cocok = 0
        tidak_cocok = []
        gagal = 0

        for w in qs:
            key_db = normalisasi(w.nama_wilayah)

            # coba exact match dulu
            matches = lookup.get(key_db, [])

            # fallback: partial match (cari key yang mengandung key_db atau sebaliknya)
            if not matches:
                for k, v in lookup.items():
                    if key_db in k or k in key_db:
                        matches = v
                        if verbose:
                            self.stdout.write(
                                self.style.WARNING(f'  ~~ Partial match: "{w.nama_wilayah}" → "{k}"')
                            )
                        break

            if not matches:
                tidak_cocok.append(w.nama_wilayah)
                if verbose:
                    self.stdout.write(self.style.WARNING(f'  🔍 Tidak cocok: {w.nama_wilayah} ({w.kode_wilayah})'))
                continue

            # Ambil feature pertama yang cocok & parse geom
            # Jika ada beberapa feature (multiple polygons), gabung jadi MultiPolygon
            all_polys = []
            for feat in matches:
                geom_raw = feat.get('geometry')
                if not geom_raw:
                    continue
                try:
                    g = GEOSGeometry(json.dumps(geom_raw), srid=4326)
                    if isinstance(g, Polygon):
                        all_polys.append(g)
                    elif isinstance(g, MultiPolygon):
                        all_polys.extend(list(g))
                except Exception as e:
                    gagal += 1
                    self.stdout.write(self.style.WARNING(f'  ⚠️ Parse gagal ({w.nama_wilayah}): {e}'))

            if not all_polys:
                gagal += 1
                continue

            geom = MultiPolygon(all_polys, srid=4326)

            if not dry_run:
                w.geom = geom
                w.save(update_fields=['geom'])

            cocok += 1
            if verbose or (cocok % 20 == 0):
                self.stdout.write(self.style.SUCCESS(
                    f'  ✅ {"[DRY RUN] " if dry_run else ""}({cocok}/{total}) {w.nama_wilayah}'
                ))

        # ── Ringkasan ──
        self.stdout.write('\n' + '─' * 55)
        self.stdout.write(self.style.SUCCESS(f'✅  Berhasil update : {cocok} wilayah'))
        self.stdout.write(self.style.WARNING(f'🔍  Tidak cocok     : {len(tidak_cocok)} wilayah'))
        self.stdout.write(self.style.ERROR  (f'❌  Gagal parse     : {gagal}') if gagal else '')

        if tidak_cocok:
            self.stdout.write('\n--- Wilayah tidak ditemukan di geoBoundaries ---')
            for n in tidak_cocok[:20]:
                self.stdout.write(f'  · {n}')
            if len(tidak_cocok) > 20:
                self.stdout.write(f'  ... dan {len(tidak_cocok)-20} lainnya')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN — tidak ada yang disimpan.'))
