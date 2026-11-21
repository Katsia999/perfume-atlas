import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FragranceCharacter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(help_text='Например, «Древесный».', max_length=40, verbose_name='оттенок')),
                ('position', models.PositiveSmallIntegerField(default=1, verbose_name='порядок показа')),
                ('fragrance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='character_labels', to='catalog.fragrance', verbose_name='версия аромата')),
            ],
            options={
                'verbose_name': 'оттенок характера',
                'verbose_name_plural': 'характер аромата',
                'ordering': ['position', 'label'],
                'constraints': [models.UniqueConstraint(fields=('fragrance', 'label'), name='unique_fragrance_character')],
            },
        ),
        migrations.CreateModel(
            name='FragranceRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visitor_id', models.UUIDField(editable=False, verbose_name='идентификатор посетителя')),
                ('value', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='оценка')),
                ('fragrance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ratings', to='catalog.fragrance', verbose_name='версия аромата')),
            ],
            options={
                'verbose_name': 'оценка аромата',
                'verbose_name_plural': 'оценки ароматов',
                'constraints': [models.UniqueConstraint(fields=('fragrance', 'visitor_id'), name='unique_fragrance_visitor_rating'), models.CheckConstraint(condition=models.Q(('value__range', (1, 5))), name='valid_fragrance_rating_value')],
            },
        ),
    ]
