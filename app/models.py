from django.db import models  


class Wilayah(models.Model):
    choices_tipe_wilayah = [
        ('Negara', 'Negara'),
        ('Provinsi', 'Provinsi'),
        ('Kabupaten', 'Kabupaten'),
        ('Kota', 'Kota'),
    ]

    nama_wilayah = models.CharField(max_length=255)
    tipe_wilayah = models.CharField(max_length=50, choices=choices_tipe_wilayah)
    kode_wilayah = models.CharField(max_length=20, unique=True, blank=True, null=True)

    def __str__(self):
        return self.nama_wilayah

    class Meta:
        verbose_name = 'Wilayah'
        verbose_name_plural = 'Wilayah'
        ordering = ['tipe_wilayah', 'nama_wilayah']


class NamaVariabel(models.Model):
    nama_variabel = models.CharField(max_length=255, unique=True)
    deskripsi = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nama_variabel

    class Meta:
        verbose_name = 'Nama Variabel'
        verbose_name_plural = 'Nama Variabel'
        ordering = ['nama_variabel']


class Data(models.Model):
    wilayah = models.ForeignKey(Wilayah, on_delete=models.CASCADE, db_index=True)
    variabel_data = models.ForeignKey(NamaVariabel, on_delete=models.CASCADE, db_index=True)
    tahun = models.IntegerField(db_index=True)
    nilai = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        unique_together = ('wilayah', 'variabel_data', 'tahun')
        verbose_name = 'Data'
        verbose_name_plural = 'Data'
        ordering = ['wilayah', 'tahun', 'variabel_data']

    def __str__(self):
        return f"{self.wilayah.nama_wilayah} ({self.tahun}) - {self.variabel_data.nama_variabel}"