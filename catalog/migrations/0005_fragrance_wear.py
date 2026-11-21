import django.contrib.postgres.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0004_fragrance_performance'),
    ]

    operations = [
        migrations.CreateModel(
            name='FragranceWear',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('season', 'Сезон'), ('time', 'Время суток'), ('lightness', 'Характер звучания')], max_length=9, verbose_name='характеристика')),
                ('options', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(choices=[('spring', 'Весна'), ('summer', 'Лето'), ('autumn', 'Осень'), ('winter', 'Зима'), ('all_year', 'Круглый год'), ('day', 'День'), ('evening', 'Вечер'), ('light', 'Лёгкий')], max_length=8), size=None, verbose_name='значения')),
                ('basis', models.CharField(choices=[('brand', 'Рекомендация бренда'), ('atlas', 'Рекомендация Атласа'), ('profile', 'Оценка профиля Атласом')], max_length=7, verbose_name='основание')),
                ('description', models.TextField(verbose_name='пояснение')),
                ('source_url', models.URLField(max_length=500, verbose_name='ссылка на источник')),
                ('verified_on', models.DateField(verbose_name='дата проверки источника')),
                ('fragrance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wear', to='catalog.fragrance', verbose_name='версия аромата')),
            ],
            options={
                'verbose_name': 'основание для подбора',
                'verbose_name_plural': 'когда носить и лёгкость звучания',
                'ordering': ['kind'],
                'constraints': [models.UniqueConstraint(fields=('fragrance', 'kind'), name='unique_fragrance_wear_kind'), models.CheckConstraint(condition=models.Q(models.Q(('basis__in', ('brand', 'atlas')), ('kind', 'season'), models.Q(('options', ['all_year']), models.Q(('options__contained_by', ('spring', 'summer', 'autumn', 'winter')), ('options__len__range', (1, 3))), _connector='OR')), models.Q(('basis__in', ('brand', 'atlas')), ('kind', 'time'), ('options__contained_by', ('day', 'evening')), ('options__len__range', (1, 2))), models.Q(('basis', 'profile'), ('kind', 'lightness'), ('options', ['light'])), _connector='OR'), name='valid_fragrance_wear_options', violation_error_message='Значения и основание должны соответствовать характеристике.'), models.CheckConstraint(condition=models.Q(models.Q(('description', ''), _negated=True), models.Q(('source_url', ''), _negated=True)), name='fragrance_wear_requires_evidence')],
            },
        ),
    ]
