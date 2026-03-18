# Panduan Import Data CSV ke Django

## Struktur yang Telah Dibuat

Saya telah membuat management command untuk mengimport data CSV Anda ke database Django. Berikut struktur direktorinya:

```
app/
├── management/
│   ├── __init__.py
│   └── commands/
│       ├── __init__.py
│       └── import_csv.py
```

## Cara Menggunakan

### 1. Jalankan Migration (jika belum)
Pastikan tabel database sudah dibuat:
```bash
python manage.py migrate
```

### 2. Import Data dari CSV
Jalankan command import dengan path file CSV:
```bash
python manage.py import_csv data_ekonomi.csv
```

Atau dengan path absolut:
```bash
python manage.py import_csv /Users/andihermanto/Documents/WebApp/DATA_app/data_ekonomi.csv
```

## Apa yang Dilakukan Command Ini

1. **Membaca file CSV** - Membaca semua baris dari file CSV Anda
2. **Membuat Variabel** - Secara otomatis membuat NamaVariabel untuk semua kolom data (dbh_pajak, dbh_sda, dll)
3. **Membuat/Update Wilayah** - Membuat record Wilayah berdasarkan kode_wilayah
4. **Import Data** - Membuat record Data untuk setiap kombinasi wilayah, variabel, dan tahun

## Fitur-Fitur

✅ **Automatic Wilayah Creation** - Wilayah dibuat otomatis jika belum ada
✅ **Skip Zero Values** - Nilai 0 atau kosong akan di-skip
✅ **Update Support** - Data yang sudah ada akan di-update jika di-import ulang
✅ **Error Handling** - Error pada baris tertentu tidak akan menghentikan seluruh proses
✅ **Progress Report** - Menampilkan jumlah baris yang berhasil diimport

## Struktur Data yang Diimport

### Wilayah
- `nama_wilayah` - Nama wilayah (contoh: "Kota Banda Aceh")
- `tipe_wilayah` - Tipe wilayah (Negara, Provinsi, Kabupaten, Kota)
- `kode_wilayah` - Kode unik wilayah

### NamaVariabel (Otomatis dibuat)
- dbh_pajak
- dbh_sda
- dbh_lainnya
- dau_block_grant
- dau_earmark
- dak_fisik
- dak_nonfisik
- hibah
- did_reguler
- dana_desa

### Data
Berisi nilai untuk setiap kombinasi:
- wilayah (FK)
- variabel_data (FK)
- tahun
- nilai

## Contoh Output

```
✓ Import selesai!
  Total baris diproses: 50
  Baris yang di-skip: 0
```

## Troubleshooting

### File tidak ditemukan
- Pastikan path ke CSV file benar
- Gunakan path absolut jika path relatif tidak bekerja

### Encoding error
- File CSV harus menggunakan encoding UTF-8
- Jika ada error encoding, buka file CSV dengan text editor dan save sebagai UTF-8

### Nilai tidak sesuai
- Pastikan kolom di CSV sesuai dengan nama yang diharapkan
- Nilai harus berupa angka (akan dikonversi ke Decimal)
