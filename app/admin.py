import os
from django import forms
from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.urls import path
from django.utils.html import format_html
from .models import Wilayah, NamaVariabel, Data
from .resources import baca_file, import_dataframe 

class ImportDataForm(forms.Form):
    FORMAT_CHOICES = [
        ('csv', 'CSV (.csv)'),
        ('xlsx', 'Excel (.xlsx / .xls)'),
        ('json', 'JSON (.json)'),
    ]

    file = forms.FileField(
        label='Pilih File',
        help_text='Maksimal ukuran file: 10 MB',
        widget=forms.FileInput(attrs={'accept': '.csv,.xlsx,.xls,.json'})
    )
    mode_update = forms.BooleanField(
        label='Update data yang sudah ada',
        required=False,
        initial=True,
        help_text='Jika dicentang, nilai yang sudah ada akan di-overwrite. Jika tidak, baris duplikat akan dilewati.'
    )

    def clean_file(self):
        f = self.cleaned_data['file']
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ('.csv', '.xlsx', '.xls', '.json'):
            raise forms.ValidationError('Format file tidak didukung. Gunakan CSV, Excel (.xlsx/.xls), atau JSON.')
        if f.size > 10 * 1024 * 1024:  # 10 MB
            raise forms.ValidationError('Ukuran file melebihi batas 10 MB.')
        return f


@admin.register(Wilayah)
class WilayahAdmin(admin.ModelAdmin):
    list_display = ('nama_wilayah', 'tipe_wilayah', 'kode_wilayah')
    list_filter = ('tipe_wilayah',)
    search_fields = ('nama_wilayah', 'kode_wilayah')
    ordering = ('tipe_wilayah', 'nama_wilayah')


@admin.register(NamaVariabel)
class NamaVariabelAdmin(admin.ModelAdmin):
    list_display = ('nama_variabel', 'deskripsi')
    search_fields = ('nama_variabel',)


@admin.register(Data)
class DataAdmin(admin.ModelAdmin):
    list_display = ('wilayah', 'variabel_data', 'tahun', 'nilai_formatted')
    list_filter = ('tahun', 'wilayah__tipe_wilayah', 'variabel_data')
    search_fields = ('wilayah__nama_wilayah', 'variabel_data__nama_variabel')
    ordering = ('wilayah__nama_wilayah', 'tahun', 'variabel_data__nama_variabel')
    autocomplete_fields = ['wilayah', 'variabel_data']

    change_list_template = 'admin/data_change_list.html'

    def nilai_formatted(self, obj):
        return f"{obj.nilai:,.2f}"
    nilai_formatted.short_description = 'Nilai'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import/', self.admin_site.admin_view(self.import_view), name='data_import'),
            path('template/', self.admin_site.admin_view(self.download_template), name='data_template'),
        ]
        return custom_urls + urls

    def import_view(self, request):
        """View untuk halaman import data."""
        if request.method == 'POST':
            form = ImportDataForm(request.POST, request.FILES)
            if form.is_valid():
                file_obj = request.FILES['file']
                ekstensi = os.path.splitext(file_obj.name)[1]

                try:
                    df = baca_file(file_obj, ekstensi)
                    stats = import_dataframe(df)

                    pesan = (
                        f" Import selesai! "
                        f"{stats['data_dibuat']} data baru, "
                        f"{stats['data_diupdate']} diupdate, "
                        f"{stats['data_dilewati']} dilewati. "
                        f"({stats['wilayah_baru']} wilayah baru, "
                        f"{stats['variabel_baru']} variabel baru)"
                    )
                    self.message_user(request, pesan, messages.SUCCESS)

                    if stats['errors']:
                        for err in stats['errors'][:10]:  # Batasi 10 error pertama
                            self.message_user(request, err, messages.WARNING)
                        if len(stats['errors']) > 10:
                            self.message_user(
                                request,
                                f"... dan {len(stats['errors']) - 10} error lainnya.",
                                messages.WARNING
                            )

                    return redirect('admin:app_data_changelist')  # Ganti 'yourapp' dengan nama app kamu

                except ValueError as e:
                    self.message_user(request, f"❌ Error: {e}", messages.ERROR)
                except Exception as e:
                    self.message_user(request, f"❌ Terjadi kesalahan: {e}", messages.ERROR)
        else:
            form = ImportDataForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Import Data dari File',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/data_import.html', context)

    def download_template(self, request):
        """Download template CSV kosong."""
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="template_import_data.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'nama_wilayah', 'tipe_wilayah', 'kode_wilayah', 'tahun',
            'dbh_pajak', 'dbh_sda', 'dbh_lainnya',
            'dau_block_grant', 'dau_earmark',
            'dak_fisik', 'dak_nonfisik',
            'hibah', 'did_reguler', 'dana_desa'
        ])

        writer.writerow([
            'Kota Contoh', 'Kota', '12345', '2024',
            '1000000', '2000000', '0',
            '500000000', '0',
            '300000000', '200000000',
            '0', '50000000', '75000000'
        ])
        return response