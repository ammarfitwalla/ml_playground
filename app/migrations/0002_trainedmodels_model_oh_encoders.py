# Generated by Django 3.2.14 on 2022-09-03 12:21

from django.db import migrations
import django.utils.timezone
import picklefield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainedmodels',
            name='model_oh_encoders',
            field=picklefield.fields.PickledObjectField(default=django.utils.timezone.now, editable=False),
            preserve_default=False,
        ),
    ]