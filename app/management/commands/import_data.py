import os
from django.core.management.base import BaseCommand, CommandError
from app.resources import baca_file, import_dataframe 


class Command(BaseCommand):
    help = 'Import data dari file CSV, Excel, atau JSON ke database'

    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            type=str,
            help='Path ke file yang akan diimport (CSV, XLSX, atau JSON)'
        )

    def handle(self, *args, **options):
        file_path = options['file_path']

        if not os.path.exists(file_path):
            raise CommandError(f"File tidak ditemukan: {file_path}")

        ekstensi = os.path.splitext(file_path)[1]
        self.stdout.write(f"Membaca file: {file_path}")

        try:
            with open(file_path, 'rb') as f:
                df = baca_file(f, ekstensi)

            self.stdout.write(f"  → {len(df)} baris ditemukan, memproses...")
            stats = import_dataframe(df)

            self.stdout.write(self.style.SUCCESS(
                f"\n   Import selesai!"
                f"\n   Data baru      : {stats['data_dibuat']}"
                f"\n   Data diupdate  : {stats['data_diupdate']}"
                f"\n   Data dilewati  : {stats['data_dilewati']}"
                f"\n   Wilayah baru   : {stats['wilayah_baru']}"
                f"\n   Variabel baru  : {stats['variabel_baru']}"
            ))

            if stats['errors']:
                self.stdout.write(self.style.WARNING(f"\n⚠ {len(stats['errors'])} peringatan:"))
                for err in stats['errors']:
                    self.stdout.write(self.style.WARNING(f"  - {err}"))

        except ValueError as e:
            raise CommandError(f"Error validasi: {e}")
        except Exception as e:
            raise CommandError(f"Error tidak terduga: {e}")