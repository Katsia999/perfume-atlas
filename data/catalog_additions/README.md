# Пополнение каталога от 21 ноября 2026 года

В партии 20 новых версий. У каждой есть 4–5 качественных меток характера, верхние ноты, ноты сердца и базовые ноты. Метки и краткие описания составлены «Атласом» по страницам брендов. Ноты распределены по уровням, которые опубликовал производитель для конкретной концентрации.

| Бренд | Версии |
| --- | --- |
| Fragonard | Santal Cardamome EDP, Grenade Pivoine EDP, Juste un Baiser EDT, Fleur de Citronnier EDT, Grain de Soleil EDP |
| Molinard | Habanita EDP, Santal Insolent EDP, Vanille EDP, Rose EDP, Figue EDP |
| Maison Margiela | REPLICA By the Fireplace EDT, REPLICA Jazz Club EDT, REPLICA Lazy Sunday Morning EDT, REPLICA Beach Walk EDT, REPLICA Autumn Vibes EDT |
| L’Occitane en Provence | Cédrat EDT, Cèdre Gingembre EDT, Fleurs de Cerisier EDT, Néroli Orchidée EDT, Verveine EDT |

В [fragrances.csv](fragrances.csv) у каждой версии есть `source_url`, дата проверки и редакционное примечание `evidence_note`. Пустое поле `pyramid_source_url` означает, что описание и уровни взяты из одного источника. Для нескольких региональных карточек L’Occitane бренд приводит разные подборки нот. В каталоге показана одна явно подписанная разбивка из указанной версии сайта. Расхождения записаны в примечаниях. [Cèdre Gingembre, ОАЭ](https://ae.loccitane.com/en/cedre-gingembre-cap-cedrat-eau-de-toilette/20ET050HCR25.html) · [Cèdre Gingembre, США](https://www.loccitane.com/en-us/cedre-gingembre-%28formerly-cap-cedrat%29--eau-de-toilette-20ET050HCR25.html) · [Verveine, США](https://www.loccitane.com/en-us/verbena-eau-de-toilette-15ET075VB26.html) · [Verveine, ОАЭ](https://ae.loccitane.com/en/verveine-verbena-eau-de-toilette/15ET075VB26.html)

## Загрузка данных

Выполните после миграций и загрузки основного набора.

```powershell
.\.venv\Scripts\python.exe manage.py import_catalog_additions
```

Команда обрабатывает всю партию в одной транзакции. Она находит версию по бренду, названию и концентрации, переиспользует справочник нот и проверяет наличие всех трёх уровней. При повторном запуске команда обновляет совпавшие карточки и связи. Для другой партии передайте `--file путь-к-CSV`. Используйте `|` для нескольких меток или нот. Значение `source` в `family_origin` означает, что семейство указал производитель. Значение `catalog` обозначает семейство, выбранное для навигации в «Атласе».

## Официальные фотографии

Для каждого флакона записаны страница производителя (`photo_source_url`), адрес снимка (`image_url`), условия использования (`terms_url`), имя и размеры файла. Снимки показываются из `.local/official-bottle-photos/` по записям `.local/official-bottle-photos.json`. Эти два элемента нужны для переноса фотографий на другой локальный стенд. Права на фото сохраняются за правообладателями. Набор снимков используется для локального учебного показа и исключён из Git. [Иллюстрации проекта](../../MEDIA.md#официальные-фотографии-для-локального-показа)
