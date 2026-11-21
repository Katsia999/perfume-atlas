from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Brand(models.Model):
    name = models.CharField("название", max_length=100, unique=True)
    aliases = models.TextField("варианты написания", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "бренд"
        verbose_name_plural = "бренды"

    def __str__(self):
        return self.name


class Family(models.Model):
    name = models.CharField("название", max_length=100, unique=True)
    description = models.TextField("описание", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "семейство"
        verbose_name_plural = "семейства"

    def __str__(self):
        return self.name


class Note(models.Model):
    name = models.CharField("название", max_length=100, unique=True)
    aliases = models.TextField("варианты написания", blank=True)
    description = models.TextField("описание", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "нота"
        verbose_name_plural = "ноты"

    def __str__(self):
        return self.name


class SourcedEntry(models.Model):
    description = models.TextField("краткое описание")
    source_url = models.URLField("ссылка на источник", max_length=500)
    verified_on = models.DateField("дата проверки источника")
    is_published = models.BooleanField("опубликовано", default=False)

    class Meta:
        abstract = True


class Fragrance(SourcedEntry):
    brand = models.ForeignKey(Brand, models.PROTECT, verbose_name="бренд")
    name = models.CharField("название", max_length=150)
    version = models.CharField("версия", max_length=80, help_text="Например, Eau de Parfum.")
    family = models.ForeignKey(Family, models.PROTECT, verbose_name="семейство")
    family_from_source = models.BooleanField(
        "семейство указано в источнике",
        default=False,
        help_text="Оставьте пустым для редакционной категории.",
    )
    pyramid_source_url = models.URLField(
        "источник уровней пирамиды",
        max_length=500,
        blank=True,
        help_text="Оставьте пустым, если уровни взяты из основной ссылки.",
    )
    pyramid_verified_on = models.DateField("дата проверки пирамиды", blank=True, null=True)
    notes = models.ManyToManyField(Note, through="FragranceNote", verbose_name="ноты", blank=True)

    class Meta:
        ordering = ["brand__name", "name", "version"]
        verbose_name = "версия аромата"
        verbose_name_plural = "версии ароматов"
        constraints = [
            models.UniqueConstraint(
                fields=["brand", "name", "version"], name="unique_fragrance_version"
            ),
        ]

    def __str__(self):
        return f"{self.brand} {self.name} · {self.version}"


class FragrancePerformance(models.Model):
    class Kind(models.TextChoices):
        LONGEVITY = "longevity", "Стойкость"
        SILLAGE = "sillage", "Шлейф"

    class Level(models.TextChoices):
        SHORT = "short", "Низкая"
        MEDIUM = "medium", "Средняя"
        LONG = "long", "Высокая"
        LIGHT = "light", "Лёгкий"
        MODERATE = "moderate", "Умеренный"
        STRONG = "strong", "Заметный"

    fragrance = models.ForeignKey(
        Fragrance, models.CASCADE, related_name="performance", verbose_name="версия аромата",
    )
    kind = models.CharField("характеристика", max_length=9, choices=Kind)
    level = models.CharField(
        "значение для поиска", max_length=8, choices=Level, blank=True,
        help_text="Оставьте пустым для стойкости, выраженной только в часах.",
    )
    description = models.TextField("что сообщает производитель")
    source_url = models.URLField("ссылка на источник", max_length=500)
    verified_on = models.DateField("дата проверки источника")

    class Meta:
        ordering = ["kind"]
        verbose_name = "стойкость или шлейф"
        verbose_name_plural = "стойкость и шлейф"
        constraints = [
            models.UniqueConstraint(fields=["fragrance", "kind"], name="unique_fragrance_performance_kind"),
            models.CheckConstraint(
                condition=(
                    models.Q(kind="longevity", level__in=("", "short", "medium", "long"))
                    | models.Q(kind="sillage", level__in=("light", "moderate", "strong"))
                ),
                name="valid_fragrance_performance_kind_level",
                violation_error_message="Выберите значение, которое относится к указанной характеристике.",
            ),
            models.CheckConstraint(
                condition=~models.Q(description="") & ~models.Q(source_url=""),
                name="fragrance_performance_requires_evidence",
            ),
        ]

    def __str__(self):
        return self.get_kind_display()


class WearOption(models.TextChoices):
    SPRING = "spring", "Весна"
    SUMMER = "summer", "Лето"
    AUTUMN = "autumn", "Осень"
    WINTER = "winter", "Зима"
    ALL_YEAR = "all_year", "Круглый год"
    DAY = "day", "День"
    EVENING = "evening", "Вечер"
    LIGHT = "light", "Лёгкий"


SEASONS = (WearOption.SPRING, WearOption.SUMMER, WearOption.AUTUMN, WearOption.WINTER)


class FragranceWear(models.Model):
    class Kind(models.TextChoices):
        SEASON = "season", "Сезон"
        TIME = "time", "Время суток"
        LIGHTNESS = "lightness", "Характер звучания"

    class Basis(models.TextChoices):
        BRAND = "brand", "Рекомендация бренда"
        ATLAS = "atlas", "Рекомендация Атласа"
        PROFILE = "profile", "Оценка профиля Атласом"

    fragrance = models.ForeignKey(
        Fragrance, models.CASCADE, related_name="wear", verbose_name="версия аромата",
    )
    kind = models.CharField("характеристика", max_length=9, choices=Kind)
    options = ArrayField(models.CharField(max_length=8, choices=WearOption), verbose_name="значения")
    basis = models.CharField("основание", max_length=7, choices=Basis)
    description = models.TextField("пояснение")
    source_url = models.URLField("ссылка на источник", max_length=500)
    verified_on = models.DateField("дата проверки источника")

    class Meta:
        ordering = ["kind"]
        verbose_name = "основание для подбора"
        verbose_name_plural = "когда носить и лёгкость звучания"
        constraints = [
            models.UniqueConstraint(fields=["fragrance", "kind"], name="unique_fragrance_wear_kind"),
            models.CheckConstraint(
                condition=(
                    models.Q(kind="season", basis__in=("brand", "atlas"))
                    & (models.Q(options=["all_year"]) | models.Q(options__contained_by=SEASONS, options__len__range=(1, 3)))
                    | models.Q(kind="time", basis__in=("brand", "atlas"),
                               options__contained_by=("day", "evening"), options__len__range=(1, 2))
                    | models.Q(kind="lightness", basis="profile", options=["light"])
                ),
                name="valid_fragrance_wear_options",
                violation_error_message="Значения и основание должны соответствовать характеристике.",
            ),
            models.CheckConstraint(
                condition=~models.Q(description="") & ~models.Q(source_url=""),
                name="fragrance_wear_requires_evidence",
            ),
        ]

    def clean(self):
        super().clean()
        if self.options and len(self.options) != len(set(self.options)):
            raise ValidationError({"options": "Уберите повторяющиеся значения."})

    @property
    def option_labels(self):
        return [WearOption(option).label for option in self.options]


class FragranceNote(models.Model):
    class Level(models.TextChoices):
        TOP = "top", "Верхняя"
        HEART = "heart", "Сердце"
        BASE = "base", "База"

    fragrance = models.ForeignKey(Fragrance, models.CASCADE, verbose_name="аромат")
    note = models.ForeignKey(Note, models.PROTECT, verbose_name="нота")
    level = models.CharField(
        "уровень пирамиды", max_length=5, choices=Level, blank=True, default=""
    )

    class Meta:
        verbose_name = "нота аромата"
        verbose_name_plural = "ноты аромата"
        constraints = [
            models.UniqueConstraint(fields=["fragrance", "note"], name="unique_fragrance_note"),
            models.CheckConstraint(
                condition=models.Q(level__in=("", "top", "heart", "base")),
                name="valid_fragrance_note_level",
            ),
        ]

    def __str__(self):
        return str(self.note)


class FragranceCharacter(models.Model):
    fragrance = models.ForeignKey(
        Fragrance, models.CASCADE, related_name="character_labels", verbose_name="версия аромата"
    )
    label = models.CharField("оттенок", max_length=40, help_text="Например, «Древесный».")
    position = models.PositiveSmallIntegerField("порядок показа", default=1)

    class Meta:
        ordering = ["position", "label"]
        verbose_name = "оттенок характера"
        verbose_name_plural = "характер аромата"
        constraints = [
            models.UniqueConstraint(
                fields=["fragrance", "label"], name="unique_fragrance_character"
            ),
        ]

    def __str__(self):
        return self.label


class FragranceRating(models.Model):
    fragrance = models.ForeignKey(
        Fragrance, models.CASCADE, related_name="ratings", verbose_name="версия аромата"
    )
    visitor_id = models.UUIDField("идентификатор посетителя", editable=False)
    value = models.PositiveSmallIntegerField(
        "оценка", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    class Meta:
        verbose_name = "оценка аромата"
        verbose_name_plural = "оценки ароматов"
        constraints = [
            models.UniqueConstraint(
                fields=["fragrance", "visitor_id"], name="unique_fragrance_visitor_rating"
            ),
            models.CheckConstraint(
                condition=models.Q(value__range=(1, 5)), name="valid_fragrance_rating_value"
            ),
        ]


class Material(SourcedEntry):
    class Kind(models.TextChoices):
        ARTICLE = "article", "Статья"
        VIDEO = "video", "Видео"
        NEWS = "news", "Новость"

    kind = models.CharField("тип", max_length=7, choices=Kind)
    title = models.CharField("заголовок", max_length=200)
    body = models.TextField("текст статьи", blank=True)
    published_on = models.DateField("дата публикации в источнике", null=True, blank=True)
    notes = models.ManyToManyField(Note, verbose_name="темы по нотам", blank=True)
    families = models.ManyToManyField(Family, verbose_name="темы по семействам", blank=True)

    class Meta:
        ordering = ["kind", "title"]
        verbose_name = "материал"
        verbose_name_plural = "материалы"
        constraints = [
            models.UniqueConstraint(fields=["kind", "title"], name="unique_material_title"),
            models.CheckConstraint(
                condition=models.Q(kind__in=("article", "video", "news")),
                name="valid_material_kind",
            ),
            models.CheckConstraint(
                condition=~models.Q(kind="news") | models.Q(published_on__isnull=False),
                name="news_requires_publication_date",
                violation_error_message="Для новости укажите дату публикации в источнике.",
            ),
        ]

    def __str__(self):
        return self.title
