"""
Management command: seed_all_countries
=========================================
Download data semua negara di dunia dari Natural Earth (via GitHub),
simpan ke static/geojson/negara.geojson (menggantikan file lama yang hanya Indonesia),
dan buat/update record Wilayah tipe 'Negara' di database untuk setiap negara.

CATATAN:
  - Hanya negara saja (tipe_wilayah='Negara')
  - Provinsi/Kab/Kota tetap hanya Indonesia (sudah di-seed terpisah)
  - Negara Indonesia tetap ada, kode_wilayah='ID'

Cara pakai (jalankan di LOCAL sebelum deploy):
    python manage.py seed_all_countries
    python manage.py seed_all_countries --dry-run
    python manage.py seed_all_countries --skip-geojson   # hanya update DB, skip file GeoJSON
"""

import json
import os
import urllib.request
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from app.models import Wilayah

# ─────────────────────────────────────────────────────────────────────────────
# Source: Natural Earth 110m Admin-0 Countries (via GitHub CDN)
# File berukuran ~900 KB — cukup ringan untuk semua negara dunia (250 negara)
# Resolusi 110m = cukup untuk tampilan peta dunia / perbandingan antar negara
# ─────────────────────────────────────────────────────────────────────────────
URL_WORLD = (
    'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/'
    'master/geojson/ne_110m_admin_0_countries.geojson'
)

# Fallback: jika URL di atas mati, coba mirror ini
URL_WORLD_FALLBACK = (
    'https://raw.githubusercontent.com/datasets/geo-countries/'
    'master/data/countries.geojson'
)


class Command(BaseCommand):
    help = (
        'Download semua negara di dunia dari Natural Earth → '
        'static/geojson/negara.geojson + buat/update record Wilayah tipe Negara'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulasi tanpa menyimpan apapun ke DB atau file',
        )
        parser.add_argument(
            '--skip-geojson',
            action='store_true',
            help='Hanya update DB, tidak menulis file GeoJSON',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Hapus semua record Wilayah tipe Negara sebelum insert ulang',
        )

    def handle(self, *args, **options):
        dry_run      = options['dry_run']
        skip_geojson = options['skip_geojson']
        do_reset     = options['reset']

        geojson_dir = os.path.join(settings.BASE_DIR, 'static', 'geojson')
        os.makedirs(geojson_dir, exist_ok=True)
        out_path = os.path.join(geojson_dir, 'negara.geojson')

        # ── 1. Download GeoJSON dunia ─────────────────────────────────────────
        self.stdout.write('📡 Mengunduh data negara dunia dari Natural Earth…')
        raw = self._download(URL_WORLD) or self._download(URL_WORLD_FALLBACK)
        if not raw:
            raise CommandError(
                'Gagal mengunduh data dari kedua URL. Periksa koneksi internet.'
            )

        features_raw = raw.get('features', [])
        self.stdout.write(f'   → {len(features_raw)} negara ditemukan di sumber.')

        # ── 2. Normalisasi field nama & ISO dari Natural Earth ────────────────
        # Natural Earth pakai property: NAME, ISO_A2, ISO_A3, ADM0_A3, SOVEREIGNT
        normalized = []
        for feat in features_raw:
            props = feat.get('properties') or {}
            geom  = feat.get('geometry')
            if not geom:
                continue

            nama  = (
                props.get('NAME') or
                props.get('SOVEREIGNT') or
                props.get('name') or
                props.get('ADMIN') or
                'Unknown'
            )
            # Natural Earth: ISO_A2_EH lebih lengkap untuk kasus France, Norway, dll.
            iso2 = (
                props.get('ISO_A2_EH') or
                props.get('ISO_A2') or
                props.get('iso_a2') or
                props.get('ISO2') or
                ''
            ).strip()
            iso3 = (
                props.get('ISO_A3') or
                props.get('ISO_A3_EH') or
                props.get('iso_a3') or
                props.get('ADM0_A3') or
                ''
            ).strip()

            # Bersihkan nilai '-99' dan '-1' yang berarti 'tidak ada kode' di Natural Earth
            if iso2 in ('-99', '-1', '-9'):
                iso2 = ''
            if iso3 in ('-99', '-1', '-9'):
                iso3 = ''

            # Untuk France overseas / Norway: coba ambil dari FIPS_10 sebagai ISO2 fallback
            if not iso2 and iso3:
                iso2 = props.get('FIPS_10', '').strip()
                if iso2 in ('-99', '-1', '-9', ''):
                    iso2 = ''

            # Gunakan ISO_A2 sebagai kode_wilayah utama; fallback ke ISO_A3
            kode = iso2 if iso2 else iso3

            normalized.append({
                'nama'  : nama,
                'kode'  : kode,
                'iso2'  : iso2,
                'iso3'  : iso3,
                'geom'  : geom,
            })

        self.stdout.write(f'   → {len(normalized)} negara berhasil dinormalisasi.')

        # ── 3. Optional reset ─────────────────────────────────────────────────
        if do_reset and not dry_run:
            deleted, _ = Wilayah.objects.filter(tipe_wilayah='Negara').delete()
            self.stdout.write(self.style.WARNING(
                f'   🗑️  {deleted} record Wilayah Negara dihapus (reset).'
            ))

        # ── 4. Upsert record Wilayah di DB ────────────────────────────────────
        self.stdout.write('\n🗄️  Memproses record Wilayah di database…')
        created_count = 0
        updated_count = 0
        skipped_count = 0
        id_map = {}   # kode → wilayah_id  (untuk build GeoJSON)

        for entry in normalized:
            nama = entry['nama']
            kode = entry['kode']

            if not kode:
                # Tidak bisa simpan tanpa kode unik → lewati
                self.stdout.write(self.style.WARNING(
                    f'   ⚠️  Lewati "{nama}" — tidak ada kode ISO.'
                ))
                skipped_count += 1
                continue

            if dry_run:
                existing = Wilayah.objects.filter(
                    tipe_wilayah='Negara', kode_wilayah=kode
                ).first()
                status = 'UPDATE' if existing else 'CREATE'
                self.stdout.write(f'   [DRY RUN] {status}: {nama} ({kode})')
                id_map[kode] = existing.id if existing else 0
                continue

            obj, created = Wilayah.objects.update_or_create(
                tipe_wilayah='Negara',
                kode_wilayah=kode,
                defaults={'nama_wilayah': nama},
            )
            id_map[kode] = obj.id

            if created:
                created_count += 1
                self.stdout.write(f'   ✅ [BARU]    {nama} ({kode}) id={obj.id}')
            else:
                updated_count += 1
                self.stdout.write(f'   🔄 [UPDATE]  {nama} ({kode}) id={obj.id}')

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'\n📊 Ringkasan DB → '
                f'Baru: {created_count}  |  Update: {updated_count}  |  '
                f'Lewati (no kode): {skipped_count}'
            ))

        # ── 5. Build GeoJSON output ───────────────────────────────────────────
        if skip_geojson:
            self.stdout.write('\nℹ️  --skip-geojson aktif, file GeoJSON tidak ditulis.')
            return

        self.stdout.write('\n🗺️  Menyusun file GeoJSON dunia…')
        features_out = []
        for entry in normalized:
            kode = entry['kode']
            if not kode:
                continue
            wilayah_id = id_map.get(kode, 0)

            features_out.append({
                'type'    : 'Feature',
                'geometry': entry['geom'],
                'properties': {
                    'id'           : wilayah_id,
                    'nama_wilayah' : entry['nama'],
                    'tipe_wilayah' : 'Negara',
                    'kode_wilayah' : kode,
                    'iso2'         : entry['iso2'],
                    'iso3'         : entry['iso3'],
                },
            })

        geojson_out = {'type': 'FeatureCollection', 'features': features_out}

        # ── 6. Simpan ke file ─────────────────────────────────────────────────
        if not dry_run:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(geojson_out, f, ensure_ascii=False, separators=(',', ':'))
            size_kb = os.path.getsize(out_path) / 1024
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Tersimpan → static/geojson/negara.geojson '
                f'({size_kb:.1f} KB, {len(features_out)} negara)'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'\n[DRY RUN] — Tidak ada yang disimpan. '
                f'{len(features_out)} feature siap ditulis ke negara.geojson.'
            ))

    # ─────────────────────────────────────────────────────────────────────────
    def _download(self, url):
        """Download JSON dari URL, kembalikan dict atau None jika gagal."""
        try:
            self.stdout.write(f'   Mencoba: {url}')
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.loads(r.read())
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'   ⚠️  Gagal: {exc}'))
            return None
