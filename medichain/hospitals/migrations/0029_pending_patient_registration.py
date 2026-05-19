from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('hospitals', '0011_alter_patient_gov_id_fields_for_self_registration'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingPatientRegistration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('full_name', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('phone', models.CharField(max_length=10)),
                ('password_hash', models.CharField(max_length=255)),
                ('otp', models.CharField(max_length=6)),
                ('otp_expiry', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'pending_patient_registrations',
            },
        ),
    ]
