import pandas as pd
from io import BytesIO
from decimal import Decimal, InvalidOperation
from django.db import transaction
from .models import Wilayah, NamaVariabel, Data

KOLOM_METADATA = ['nama_wilayah', 'tipe_wilayah', 'kode_wilayah', 'tahun']

MAPPING_NAMA_VARIABEL = {
    'dbh_pajak': 'DBH Pajak',
    'dbh_sda': 'DBH SDA',
    'dbh_lainnya': 'DBH Lainnya',
    'dau_block_grant': 'DAU Block Grant',
    'dau_earmark': 'DAU Earmark',
    'dak_fisik': 'DAK Fisik',
    'dak_nonfisik': 'DAK Non-Fisik',
    'hibah': 'Hibah',
    'did_reguler': 'DID Reguler',
    'dana_desa': 'Dana Desa',
}


# def baca_file(file_obj, ekstensi: str) -> pd.DataFrame:
#     """Baca file CSV atau Excel dan kembalikan sebagai DataFrame."""
#     ekstensi = ekstensi.lower().lstrip('.')
#     if ekstensi == 'csv':
#         df = pd.read_csv(file_obj, dtype=str)
#     elif ekstensi in ('xlsx', 'xls'):
#         df = pd.read_excel(file_obj, dtype=str)
#     elif ekstensi == 'json':
#         df = pd.read_json(file_obj, dtype=str)
#     else:
#         raise ValueError(f"Format file '{ekstensi}' tidak didukung. Gunakan CSV, Excel, atau JSON.")
#     return df


def baca_file(file_obj, ekstensi: str) -> pd.DataFrame:
    ekstensi = ekstensi.lower().lstrip('.')
    
    if ekstensi == 'csv':
        import csv, io
        content = file_obj.read()
        # Cek header mentah sebelum pandas membaca
        header_raw = next(csv.reader(io.StringIO(content.decode('utf-8'))))
        duplikat = [k for k in header_raw if header_raw.count(k) > 1]
        if duplikat:
            raise ValueError(
                f"Terdapat nama kolom yang sama: {', '.join(set(duplikat))}. "
                f"Setiap kolom variabel harus memiliki nama yang unik."
            )
        df = pd.read_csv(io.BytesIO(content), dtype=str)

    elif ekstensi in ('xlsx', 'xls'):
        content = file_obj.read()
        df = pd.read_excel(io.BytesIO(content), dtype=str)
        duplikat = [k for k in df.columns if list(df.columns).count(k) > 1]
        if duplikat:
            raise ValueError(
                f"Terdapat nama kolom yang sama: {', '.join(set(duplikat))}. "
                f"Setiap kolom variabel harus memiliki nama yang unik."
            )

    elif ekstensi == 'json':
        df = pd.read_json(file_obj, dtype=str)

    else:
        raise ValueError(f"Format file '{ekstensi}' tidak didukung.")
    
    return df

def validasi_kolom(df: pd.DataFrame) -> list[str]:
    errors = []
    kolom_wajib = ['nama_wilayah', 'tipe_wilayah', 'tahun']
    for k in kolom_wajib:
        if k not in df.columns:
            errors.append(f"Kolom wajib '{k}' tidak ditemukan di file.")

    kolom_duplikat = df.columns[df.columns.duplicated()].tolist()
    if kolom_duplikat:
        errors.append(
            f"Terdapat nama kolom yang sama: {', '.join(kolom_duplikat)}. "
            f"Setiap kolom variabel harus memiliki nama yang unik."
        )

    return errors


def validasi_kolom(df: pd.DataFrame) -> list[str]:

    errors = []
    kolom_wajib = ['nama_wilayah', 'tipe_wilayah', 'tahun']
    for k in kolom_wajib:
        if k not in df.columns:
            errors.append(f"Kolom wajib '{k}' tidak ditemukan di file.")

    # ── Cek kolom duplikat di file CSV ──
    kolom_duplikat = df.columns[df.columns.duplicated()].tolist()
    if kolom_duplikat:
        errors.append(f"Kolom duplikat ditemukan di file: {', '.join(kolom_duplikat)}. Setiap kolom harus unik.")

    # ── Cek nama variabel duplikat di database ──
    from .models import NamaVariabel
    kolom_variabel = [k for k in df.columns if k not in KOLOM_METADATA]
    nama_akan_disimpan = [
        MAPPING_NAMA_VARIABEL.get(k, k.replace('_', ' ').title())
        for k in kolom_variabel
    ]
    duplikat_antar_kolom = [
        nama for nama in nama_akan_disimpan
        if nama_akan_disimpan.count(nama) > 1
    ]
    if duplikat_antar_kolom:
        errors.append(
            f"Beberapa kolom akan menghasilkan nama variabel yang sama: "
            f"{', '.join(set(duplikat_antar_kolom))}. Periksa MAPPING_NAMA_VARIABEL."
        )

    return errors

def get_or_create_wilayah(nama: str, tipe: str, kode: str | None) -> Wilayah:
    """Ambil atau buat objek Wilayah. Gunakan nama+tipe sebagai kunci unik."""
    wilayah, created = Wilayah.objects.get_or_create(
        nama_wilayah=nama.strip(),
        tipe_wilayah=tipe.strip(),
        defaults={'kode_wilayah': kode.strip() if kode and str(kode).strip() else None}
    )
    return wilayah


def get_or_create_variabel(nama_kolom: str) -> NamaVariabel:
    """Ambil atau buat NamaVariabel dari nama kolom CSV."""
    nama_tampil = MAPPING_NAMA_VARIABEL.get(nama_kolom, nama_kolom.replace('_', ' ').title())
    variabel, created = NamaVariabel.objects.get_or_create(
        nama_variabel=nama_tampil,
    )
    return variabel


def parse_nilai(nilai_str: str) -> Decimal | None:
    """Parse string angka menjadi Decimal. Kembalikan None jika kosong/invalid."""
    if pd.isna(nilai_str) or str(nilai_str).strip() in ('', 'nan', 'None', '-'):
        return None
    # Hapus karakter non-numerik kecuali titik dan minus
    cleaned = str(nilai_str).replace(',', '').replace(' ', '').strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


@transaction.atomic
def import_dataframe(df: pd.DataFrame) -> dict:
    """
    Proses utama: unpivot DataFrame dan simpan ke database.
    Kembalikan dict berisi statistik hasil import.
    """
    errors = validasi_kolom(df)
    if errors:
        raise ValueError('\n'.join(errors))

    kolom_variabel = [k for k in df.columns if k not in KOLOM_METADATA]

    if not kolom_variabel:
        raise ValueError("Tidak ditemukan kolom variabel di file. Pastikan ada kolom selain nama_wilayah, tipe_wilayah, kode_wilayah, dan tahun.")

    stats = {
        'total_baris': len(df),
        'wilayah_baru': 0,
        'variabel_baru': 0,
        'data_dibuat': 0,
        'data_diupdate': 0,
        'data_dilewati': 0,
        'errors': [],
    }

    # Cache variabel agar tidak query berulang
    cache_variabel: dict[str, NamaVariabel] = {}

    for idx, row in df.iterrows():
        nomor_baris = idx + 2  # +2 karena header di baris 1, index mulai 0

        nama_wil = str(row.get('nama_wilayah', '')).strip()
        tipe_wil = str(row.get('tipe_wilayah', '')).strip()
        kode_wil = row.get('kode_wilayah', None)

        if not nama_wil or not tipe_wil:
            stats['errors'].append(f"Baris {nomor_baris}: nama_wilayah atau tipe_wilayah kosong, dilewati.")
            stats['data_dilewati'] += len(kolom_variabel)
            continue

        # Validasi tipe_wilayah
        tipe_valid = ['Negara', 'Provinsi', 'Kabupaten', 'Kota']
        if tipe_wil not in tipe_valid:
            stats['errors'].append(
                f"Baris {nomor_baris}: tipe_wilayah '{tipe_wil}' tidak valid (harus salah satu dari {tipe_valid})."
            )
            stats['data_dilewati'] += len(kolom_variabel)
            continue

        try:
            wilayah_sebelum = Wilayah.objects.filter(nama_wilayah=nama_wil, tipe_wilayah=tipe_wil).exists()
            wilayah = get_or_create_wilayah(nama_wil, tipe_wil, str(kode_wil) if kode_wil else None)
            if not wilayah_sebelum:
                stats['wilayah_baru'] += 1
        except Exception as e:
            stats['errors'].append(f"Baris {nomor_baris}: Gagal memproses wilayah '{nama_wil}' - {e}")
            continue


        tahun_str = str(row.get('tahun', '')).strip()
        try:
            tahun = int(float(tahun_str))
        except (ValueError, TypeError):
            stats['errors'].append(f"Baris {nomor_baris}: Nilai tahun '{tahun_str}' tidak valid, dilewati.")
            stats['data_dilewati'] += len(kolom_variabel)
            continue

        for nama_kolom in kolom_variabel:
            if nama_kolom not in cache_variabel:
                variabel_sebelum = NamaVariabel.objects.filter(
                    nama_variabel=MAPPING_NAMA_VARIABEL.get(nama_kolom, nama_kolom)
                ).exists()
                cache_variabel[nama_kolom] = get_or_create_variabel(nama_kolom)
                if not variabel_sebelum:
                    stats['variabel_baru'] += 1

            variabel = cache_variabel[nama_kolom]
            nilai = parse_nilai(row.get(nama_kolom))

            if nilai is None:
                stats['data_dilewati'] += 1
                continue

            obj, created = Data.objects.update_or_create(
                wilayah=wilayah,
                variabel_data=variabel,
                tahun=tahun,
                defaults={'nilai': nilai}
            )
            if created:
                stats['data_dibuat'] += 1
            else:
                stats['data_diupdate'] += 1

    return stats