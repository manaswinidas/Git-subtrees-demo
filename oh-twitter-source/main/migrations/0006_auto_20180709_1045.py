# Generated by Django 2.0.5 on 2018-07-09 10:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0005_auto_20180709_1025'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='datasourcemember',
            name='token_expires',
        ),
        migrations.AlterField(
            model_name='datasourcemember',
            name='last_submitted',
            field=models.DateTimeField(default='2018-07-02 10:45:47+00:00'),
        ),
        migrations.AlterField(
            model_name='datasourcemember',
            name='last_updated',
            field=models.DateTimeField(default='2018-07-02 10:45:47+00:00'),
        ),
    ]