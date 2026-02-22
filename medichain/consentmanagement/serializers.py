from rest_framework import serializers
from .models import ConsentRequest

class ConsentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentRequest
        fields = '__all__'