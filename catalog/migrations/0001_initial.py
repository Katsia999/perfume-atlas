import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Brand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='название')),
                ('aliases', models.TextField(blank=True, verbose_name='варианты написания')),
            ],
            options={
                'verbose_name': 'бренд',
                'verbose_name_plural': 'бренды',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Family',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='название')),
                ('description', models.TextField(blank=True, verbose_name='описание')),
            ],
            options={
                'verbose_name': 'семейство',
                'verbose_name_plural': 'семейства',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Note',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='название')),
                ('aliases', models.TextField(blank=True, verbose_name='варианты написания')),
                ('description', models.TextField(blank=True, verbose_name='описание')),
            ],
            options={
                'verbose_name': 'нота',
                'verbose_name_plural': 'ноты',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Fragrance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.TextField(verbose_name='краткое описание')),
                ('source_url', models.URLField(max_length=500, verbose_name='ссылка на источник')),
                ('verified_on', models.DateField(verbose_name='дата проверки источника')),
                ('is_published', models.BooleanField(default=False, verbose_name='опубликовано')),
                ('name', models.CharField(max_length=150, verbose_name='название')),
                ('version', models.CharField(help_text='Например, Eau de Parfum.', max_length=80, verbose_name='версия')),
                ('family_from_source', models.BooleanField(default=False, help_text='Оставьте пустым для редакционной категории.', verbose_name='семейство указано в источнике')),
                ('brand', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='catalog.brand', verbose_name='бренд')),
                ('family', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='catalog.family', verbose_name='семейство')),
            ],
            options={
                'verbose_name': 'версия аромата',
                'verbose_name_plural': 'версии ароматов',
                'ordering': ['brand__name', 'name', 'version'],
            },
        ),
        migrations.CreateModel(
            name='FragranceNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.CharField(blank=True, choices=[('top', 'Верхняя'), ('heart', 'Сердце'), ('base', 'База')], default='', max_length=5, verbose_name='уровень пирамиды')),
                ('fragrance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='catalog.fragrance', verbose_name='аромат')),
                ('note', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='catalog.note', verbose_name='нота')),
            ],
            options={
                'verbose_name': 'нота аромата',
                'verbose_name_plural': 'ноты аромата',
            },
        ),
        migrations.AddField(
            model_name='fragrance',
            name='notes',
            field=models.ManyToManyField(blank=True, through='catalog.FragranceNote', to='catalog.note', verbose_name='ноты'),
        ),
        migrations.CreateModel(
            name='Material',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.TextField(verbose_name='краткое описание')),
                ('source_url', models.URLField(max_length=500, verbose_name='ссылка на источник')),
                ('verified_on', models.DateField(verbose_name='дата проверки источника')),
                ('is_published', models.BooleanField(default=False, verbose_name='опубликовано')),
                ('kind', models.CharField(choices=[('article', 'Статья'), ('video', 'Видео'), ('news', 'Новость')], max_length=7, verbose_name='тип')),
                ('title', models.CharField(max_length=200, verbose_name='заголовок')),
                ('body', models.TextField(blank=True, verbose_name='текст статьи')),
                ('published_on', models.DateField(blank=True, null=True, verbose_name='дата публикации в источнике')),
                ('families', models.ManyToManyField(blank=True, to='catalog.family', verbose_name='темы по семействам')),
                ('notes', models.ManyToManyField(blank=True, to='catalog.note', verbose_name='темы по нотам')),
            ],
            options={
                'verbose_name': 'материал',
                'verbose_name_plural': 'материалы',
                'ordering': ['kind', 'title'],
                'constraints': [models.UniqueConstraint(fields=('kind', 'title'), name='unique_material_title'), models.CheckConstraint(condition=models.Q(('kind__in', ('article', 'video', 'news'))), name='valid_material_kind'), models.CheckConstraint(condition=models.Q(models.Q(('kind', 'news'), _negated=True), ('published_on__isnull', False), _connector='OR'), name='news_requires_publication_date', violation_error_message='Для новости укажите дату публикации в источнике.')],
            },
        ),
        migrations.AddConstraint(
            model_name='fragrancenote',
            constraint=models.UniqueConstraint(fields=('fragrance', 'note'), name='unique_fragrance_note'),
        ),
        migrations.AddConstraint(
            model_name='fragrancenote',
            constraint=models.CheckConstraint(condition=models.Q(('level__in', ('', 'top', 'heart', 'base'))), name='valid_fragrance_note_level'),
        ),
        migrations.AddConstraint(
            model_name='fragrance',
            constraint=models.UniqueConstraint(fields=('brand', 'name', 'version'), name='unique_fragrance_version'),
        ),
    ]
