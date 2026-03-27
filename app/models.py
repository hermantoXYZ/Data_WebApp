import uuid
from django.contrib.gis.db import models

class Wilayah(models.Model):
    choices_tipe_wilayah = [
        ('Negara', 'Negara'),
        ('Provinsi', 'Provinsi'),
        ('Kabupaten', 'Kabupaten'),
        ('Kota', 'Kota'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nama_wilayah = models.CharField(max_length=255)
    tipe_wilayah = models.CharField(max_length=50, choices=choices_tipe_wilayah)
    kode_wilayah = models.CharField(max_length=20, unique=True, blank=True, null=True)
    geom = models.MultiPolygonField(srid=4326, blank=True, null=True)   

    def __str__(self):
        return self.nama_wilayah

class NamaVariabel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nama_variabel = models.CharField(max_length=255)
    deskripsi = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nama_variabel

class Data(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wilayah = models.ForeignKey(Wilayah, on_delete=models.CASCADE)
    variabel_data = models.ForeignKey(NamaVariabel, on_delete=models.CASCADE)
    tahun = models.IntegerField()
    nilai = models.DecimalField(max_digits=15, decimal_places=2)
    
    class Meta:
        unique_together = ('wilayah', 'variabel_data', 'tahun')

    def __str__(self):
        return f"{self.wilayah.nama_wilayah} ({self.tahun}) - {self.variabel_data.nama_variabel}"