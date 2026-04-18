from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospitals', '0014_alter_lab_lab_type_choices'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='custom_field_schema',
            field=models.JSONField(blank=True, default=list, help_text='JSON list of extra fields for this lab.'),
        ),
        migrations.AddField(
            model_name='labrequest',
            name='custom_field_values',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='medicalrecordmeta',
            name='custom_field_values',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]