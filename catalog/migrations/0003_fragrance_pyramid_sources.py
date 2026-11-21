from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_fragrance_character_and_rating'),
    ]

    operations = [
        migrations.AddField(
            model_name='fragrance',
            name='pyramid_source_url',
            field=models.URLField(blank=True, help_text='Оставьте пустым, если уровни взяты из основной ссылки.', max_length=500, verbose_name='источник уровней пирамиды'),
        ),
        migrations.AddField(
            model_name='fragrance',
            name='pyramid_verified_on',
            field=models.DateField(blank=True, null=True, verbose_name='дата проверки пирамиды'),
        ),
    ]
