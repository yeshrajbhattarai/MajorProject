from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospitals', '0028_merge_20260519_1756'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patient',
            name='gov_id_type',
            field=models.CharField(blank=True, choices=[('aadhar', 'Aadhar Card'), ('voter', 'Voter ID')], max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='patient',
            name='gov_id_number',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='patient',
            name='gov_id_hash',
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
    ]
