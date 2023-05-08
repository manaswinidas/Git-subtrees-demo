# Generated by Django 2.1.1 on 2018-10-17 17:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_auto_20180827_0818'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='datasourcemember',
            name='scope',
        ),
        migrations.RemoveField(
            model_name='datasourcemember',
            name='token_type',
        ),
        migrations.AddField(
            model_name='datasourcemember',
            name='access_token_secret',
            field=models.CharField(max_length=512, null=True),
        ),
        migrations.AlterField(
            model_name='datasourcemember',
            name='last_submitted',
            field=models.DateTimeField(default='2018-10-10 17:35:34+00:00'),
        ),
        migrations.AlterField(
            model_name='datasourcemember',
            name='last_updated',
            field=models.DateTimeField(default='2018-10-10 17:35:34+00:00'),
        ),
    ]
