import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0003_fragrance_pyramid_sources'),
    ]

    operations = [
        migrations.CreateModel(
            name='FragrancePerformance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('longevity', 'Стойкость'), ('sillage', 'Шлейф')], max_length=9, verbose_name='характеристика')),
                ('level', models.CharField(blank=True, choices=[('short', 'Низкая'), ('medium', 'Средняя'), ('long', 'Высокая'), ('light', 'Лёгкий'), ('moderate', 'Умеренный'), ('strong', 'Заметный')], help_text='Оставьте пустым для стойкости, выраженной только в часах.', max_length=8, verbose_name='значение для поиска')),
                ('description', models.TextField(verbose_name='что сообщает производитель')),
                ('source_url', models.URLField(max_length=500, verbose_name='ссылка на источник')),
                ('verified_on', models.DateField(verbose_name='дата проверки источника')),
                ('fragrance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='performance', to='catalog.fragrance', verbose_name='версия аромата')),
            ],
            options={
                'verbose_name': 'стойкость или шлейф',
                'verbose_name_plural': 'стойкость и шлейф',
                'ordering': ['kind'],
                'constraints': [models.UniqueConstraint(fields=('fragrance', 'kind'), name='unique_fragrance_performance_kind'), models.CheckConstraint(condition=models.Q(models.Q(('kind', 'longevity'), ('level__in', ('', 'short', 'medium', 'long'))), models.Q(('kind', 'sillage'), ('level__in', ('light', 'moderate', 'strong'))), _connector='OR'), name='valid_fragrance_performance_kind_level', violation_error_message='Выберите значение, которое относится к указанной характеристике.'), models.CheckConstraint(condition=models.Q(models.Q(('description', ''), _negated=True), models.Q(('source_url', ''), _negated=True)), name='fragrance_performance_requires_evidence')],
            },
        ),
    ]
