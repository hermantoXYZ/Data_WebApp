"""
Management command: seed_kabkota
==================================
Seed data Kabupaten/Kota Indonesia ke tabel Wilayah beserta geometrinya,
diambil langsung dari geoBoundaries ADM2 (terhubung ke Provinsi via kode BPS).

Cara pakai:
    python manage.py seed_kabkota
    python manage.py seed_kabkota --dry-run
    python manage.py seed_kabkota --update     # overwrite geom yang sudah ada
    python manage.py seed_kabkota --verbose    # tampilkan semua detail

Catatan:
    Data kode BPS kabupaten/kota digunakan dari field shapeName di geoBoundaries.
    Karena geoBoundaries tidak memiliki kode BPS, kode dibuat otomatis dari
    kode provinsi + urutan (tidak 100% akurat tetapi cukup untuk peta).
"""

import json
import re
import unicodedata
import urllib.request
from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from app.models import Wilayah

# geoBoundaries ADM2 Indonesia
URL_ADM2 = (
    'https://github.com/wmgeolab/geoBoundaries/raw/main/'
    'releaseData/gbOpen/IDN/ADM2/geoBoundaries-IDN-ADM2.geojson'
)

# Mapping shapeName provinsi di geoBoundaries → kode BPS provinsi
# Digunakan untuk membuat kode_wilayah kabkota secara otomatis
PROV_KODE_MAP = {
    'Aceh': '11', 'Sumatera Utara': '12', 'Sumatera Barat': '13',
    'Riau': '14', 'Jambi': '15', 'Sumatera Selatan': '16',
    'Bengkulu': '17', 'Lampung': '18', 'Kepulauan Bangka Belitung': '19',
    'Kepulauan Riau': '21', 'DKI Jakarta': '31', 'Jawa Barat': '32',
    'Jawa Tengah': '33', 'Daerah Istimewa Yogyakarta': '34',
    'Jawa Timur': '35', 'Banten': '36', 'Bali': '51',
    'Nusa Tenggara Barat': '52', 'Nusa Tenggara Timur': '53',
    'Kalimantan Barat': '61', 'Kalimantan Tengah': '62',
    'Kalimantan Selatan': '63', 'Kalimantan Timur': '64',
    'Kalimantan Utara': '65', 'Sulawesi Utara': '71',
    'Sulawesi Tengah': '72', 'Sulawesi Selatan': '73',
    'Sulawesi Tenggara': '74', 'Gorontalo': '75', 'Sulawesi Barat': '76',
    'Maluku': '81', 'Maluku Utara': '82', 'Papua Barat': '92',
    'Papua': '91',
}


def normalisasi(nama: str) -> str:
    nama = nama.lower().strip()
    nama = unicodedata.normalize('NFD', nama)
    nama = ''.join(c for c in nama if unicodedata.category(c) != 'Mn')
    for prefix in ('kab. ', 'kabupaten ', 'kota ', 'administrasi ', 'kepulauan ',
                   'kab.', 'kab '):
        if nama.startswith(prefix):
            nama = nama[len(prefix):]
            break
    nama = re.sub(r'\s+', ' ', nama).strip()
    return nama


def deteksi_tipe(nama_raw: str) -> str:
    """Deteksi apakah Kabupaten atau Kota dari nama asli."""
    nama_lower = nama_raw.lower()
    if nama_lower.startswith('kota ') or nama_lower.startswith('administrasi '):
        return 'Kota'
    return 'Kabupaten'


class Command(BaseCommand):
    help = 'Seed Kabupaten/Kota Indonesia ke tabel Wilayah beserta geometrinya'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Simulasi tanpa simpan ke database')
        parser.add_argument('--update', action='store_true',
                            help='Update geom untuk record yang sudah ada')
        parser.add_argument('--verbose', action='store_true',
                            help='Tampilkan semua detail proses')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        update  = options['update']
        verbose = options['verbose']

        # ── Download GeoJSON ADM2 ──
        self.stdout.write('📡 Mengunduh geoBoundaries ADM2 Indonesia...')
        self.stdout.write(f'   {URL_ADM2}\n')
        try:
            with urllib.request.urlopen(URL_ADM2, timeout=120) as r:
                raw = r.read()
            geojson = json.loads(raw)
        except Exception as e:
            raise CommandError(f'Gagal mengunduh GeoJSON: {e}')

        features = geojson.get('features', [])
        self.stdout.write(f'✅ {len(features)} feature ADM2 ditemukan.\n')

        # ── Bangun lookup provinsi dari DB ──
        provinsi_db = {
            w.kode_wilayah: w
            for w in Wilayah.objects.filter(tipe_wilayah='Provinsi')
        }
        self.stdout.write(f'🗺️  {len(provinsi_db)} Provinsi ditemukan di database.\n')

        dibuat   = 0
        diupdate = 0
        skip     = 0
        gagal    = 0
        kode_counter: dict[str, int] = {}  # untuk generate kode unik per provinsi

        for feat in features:
            props    = feat.get('properties', {})
            nama_raw = str(props.get('shapeName', '')).strip()
            prov_raw = str(props.get('shapeGroup', '') or
                          props.get('ADM1_NAME', '') or '').strip()
            geom_raw = feat.get('geometry')

            if not nama_raw:
                gagal += 1
                continue

            # Deteksi tipe
            tipe = deteksi_tipe(nama_raw)

            # Parse geometry
            if not geom_raw:
                if verbose:
                    self.stdout.write(self.style.WARNING(f'  ⚠️ {nama_raw}: geometry kosong, dilewati'))
                gagal += 1
                continue

            try:
                geom = GEOSGeometry(json.dumps(geom_raw), srid=4326)
                if isinstance(geom, Polygon):
                    geom = MultiPolygon(geom)
                elif not isinstance(geom, MultiPolygon):
                    if verbose:
                        self.stdout.write(self.style.WARNING(
                            f'  ⚠️ {nama_raw}: geom bukan Polygon ({geom.geom_type}), dilewati'))
                    gagal += 1
                    continue
            except Exception as e:
                if verbose:
                    self.stdout.write(self.style.WARNING(f'  ⚠️ {nama_raw}: gagal parse — {e}'))
                gagal += 1
                continue

            # Generate kode_wilayah (2-digit kode prov + 2-digit urut)
            kode_prov = None
            for prov_name, kode in PROV_KODE_MAP.items():
                if prov_name.lower() in prov_raw.lower() or prov_raw.lower() in prov_name.lower():
                    kode_prov = kode
                    break

            if kode_prov is None:
                # Coba dari nama kabkota sendiri untuk beberapa kasus khusus
                if verbose:
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠️ {nama_raw}: provinsi tidak dikenali ({prov_raw!r}), kode dibuat tanpa prefix'))
                kode_prov = '00'

            kode_counter[kode_prov] = kode_counter.get(kode_prov, 0) + 1
            kode_kabkota = f"{kode_prov}{kode_counter[kode_prov]:02d}"

            # Cek apakah sudah ada di DB (berdasarkan nama + tipe)
            existing = Wilayah.objects.filter(
                nama_wilayah__iexact=nama_raw,
                tipe_wilayah=tipe
            ).first()

            if not existing:
                # Coba juga tanpa prefix (misal "Kab. Bogor" vs "Bogor")
                nama_norm = normalisasi(nama_raw).title()
                existing = Wilayah.objects.filter(
                    nama_wilayah__icontains=nama_norm,
                    tipe_wilayah=tipe
                ).first()

            if existing:
                if update:
                    if not dry_run:
                        existing.geom = geom
                        existing.save(update_fields=['geom'])
                    diupdate += 1
                    if verbose:
                        self.stdout.write(self.style.SUCCESS(
                            f'  🔄 {"[DRY] " if dry_run else ""}Update: {existing.nama_wilayah}'))
                else:
                    skip += 1
                    if verbose:
                        self.stdout.write(
                            f'  ⏭️  Skip: {existing.nama_wilayah} — pakai --update')
            else:
                if not dry_run:
                    Wilayah.objects.create(
                        nama_wilayah=nama_raw,
                        tipe_wilayah=tipe,
                        kode_wilayah=kode_kabkota,
                        geom=geom,
                    )
                dibuat += 1
                if verbose or (dibuat % 50 == 0):
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✅ {"[DRY] " if dry_run else ""}({dibuat}) {tipe}: {nama_raw} [{kode_kabkota}]'))

        # ── Ringkasan ──
        self.stdout.write('\n' + '─' * 60)
        self.stdout.write(self.style.SUCCESS(f'✅  Dibuat baru  : {dibuat} kabupaten/kota'))
        self.stdout.write(self.style.WARNING(f'🔄  Diupdate     : {diupdate} kabupaten/kota'))
        self.stdout.write(self.style.WARNING(f'⏭️   Di-skip      : {skip} kabupaten/kota'))
        if gagal:
            self.stdout.write(self.style.ERROR(f'❌  Gagal        : {gagal} feature'))
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN — tidak ada yang disimpan ke database.'))
