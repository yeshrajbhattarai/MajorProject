from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospitals', '0022_backfill_medical_record_meta_for_finalized_records'),
    ]

    operations = [
        migrations.AddField(
            model_name='nursequeueitem',
            name='finalized_record_history',
            field=models.JSONField(blank=True, default=list),
        ),
    ]