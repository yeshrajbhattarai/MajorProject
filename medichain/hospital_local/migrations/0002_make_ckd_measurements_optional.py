from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital_local', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='medicalrecord',
            name='blood_pressure_systolic',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='medicalrecord',
            name='blood_pressure_diastolic',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='medicalrecord',
            name='cholesterol',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='medicalrecord',
            name='blood_glucose',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='medicalrecord',
            name='heart_rate',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='medicalrecord',
            name='ecg_result',
            field=models.CharField(blank=True, choices=[('normal', 'Normal'), ('st_t_abnormality', 'ST-T abnormality'), ('lvh', 'LVH')], max_length=32, null=True),
        ),
    ]