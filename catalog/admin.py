from django import forms
from django.contrib import admin

from .models import (
    Brand, Family, Fragrance, FragranceCharacter, FragranceNote, FragrancePerformance, FragranceWear,
    Material, Note, WearOption,
)

admin.site.site_header = "Атлас ароматов"
admin.site.site_title = "Атлас ароматов"
admin.site.index_title = "Управление базой знаний"


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    search_fields = ("name", "aliases")


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    search_fields = ("name", "aliases")


class FragranceNoteInline(admin.TabularInline):
    model = FragranceNote
    autocomplete_fields = ("note",)
    extra = 1


class FragranceCharacterInline(admin.TabularInline):
    model = FragranceCharacter
    extra = 1


class FragrancePerformanceInline(admin.StackedInline):
    model = FragrancePerformance
    extra = 0
    max_num = 2


class FragranceWearForm(forms.ModelForm):
    options = forms.MultipleChoiceField(
        label="Значения", choices=WearOption.choices, widget=forms.CheckboxSelectMultiple,
        help_text="Отметьте значения для выбранной характеристики. «Круглый год» выбирается отдельно.",
    )

    class Meta:
        model = FragranceWear
        fields = "__all__"


class FragranceWearInline(admin.StackedInline):
    model = FragranceWear
    form = FragranceWearForm
    extra = 0
    max_num = 3


@admin.register(Fragrance)
class FragranceAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "brand", "family", "is_published", "verified_on")
    list_filter = ("family", "brand", "is_published")
    list_select_related = ("brand", "family")
    search_fields = ("name", "version", "brand__name", "brand__aliases", "notes__name")
    inlines = (FragranceWearInline, FragrancePerformanceInline, FragranceCharacterInline, FragranceNoteInline)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "published_on", "is_published", "verified_on")
    list_filter = ("kind", "is_published")
    search_fields = ("title", "description")
    filter_horizontal = ("notes", "families")
