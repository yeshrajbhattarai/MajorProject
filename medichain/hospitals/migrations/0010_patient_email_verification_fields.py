from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospitals', '0009_alter_hospitaluser_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='patient',
            name='email_verified',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='patient',
            name='email_verify_otp',
            field=models.CharField(blank=True, max_length=6, null=True),
        ),
        migrations.AddField(
            model_name='patient',
            name='email_verify_otp_expiry',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
