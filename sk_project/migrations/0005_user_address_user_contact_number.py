# Generated by Django 5.1.2 on 2024-10-16 11:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sk_project', '0004_user_profile_picture'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='contact_number',
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
    ]