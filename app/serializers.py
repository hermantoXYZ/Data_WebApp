from rest_framework import serializers
from .models import Wilayah, NamaVariabel, Data


class WilayahSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wilayah
        fields = ['id', 'nama_wilayah', 'tipe_wilayah', 'kode_wilayah']


class NamaVariabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = NamaVariabel
        fields = ['id', 'nama_variabel', 'deskripsi']


class DataSerializer(serializers.ModelSerializer):
    wilayah = WilayahSerializer(read_only=True)
    variabel_data = NamaVariabelSerializer(read_only=True)

    class Meta:
        model = Data
        fields = ['id', 'wilayah', 'variabel_data', 'tahun', 'nilai']


class DataPivotSerializer(serializers.Serializer):
    wilayah = serializers.CharField(source='wilayah__nama_wilayah')
    tipe_wilayah = serializers.CharField(source='wilayah__tipe_wilayah')
    kode_wilayah = serializers.CharField(source='wilayah__kode_wilayah')
    tahun = serializers.IntegerField()