# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-10-25 14:36
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('test_app', '0001_create_table'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='a',
            name='null_field',
        ),
    ]