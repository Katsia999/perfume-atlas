# Пополнение каталога

## Партия от 21 ноября 2026 года

В партии 20 новых версий. У каждой есть 4–5 качественных меток характера, верхние ноты, ноты сердца и базовые ноты. Метки и краткие описания составлены «Атласом» по страницам брендов. Ноты распределены по уровням, которые опубликовал производитель для конкретной концентрации.

| Бренд | Версии |
| --- | --- |
| Fragonard | Santal Cardamome EDP, Grenade Pivoine EDP, Juste un Baiser EDT, Fleur de Citronnier EDT, Grain de Soleil EDP |
| Molinard | Habanita EDP, Santal Insolent EDP, Vanille EDP, Rose EDP, Figue EDP |
| Maison Margiela | REPLICA By the Fireplace EDT, REPLICA Jazz Club EDT, REPLICA Lazy Sunday Morning EDT, REPLICA Beach Walk EDT, REPLICA Autumn Vibes EDT |
| L’Occitane en Provence | Cédrat EDT, Cèdre Gingembre EDT, Fleurs de Cerisier EDT, Néroli Orchidée EDT, Verveine EDT |

В [fragrances.csv](fragrances.csv) у каждой версии есть `source_url`, дата проверки и редакционное примечание `evidence_note`. Пустое поле `pyramid_source_url` означает, что описание и уровни взяты из одного источника. Для нескольких региональных карточек L’Occitane бренд приводит разные подборки нот. В каталоге показана одна явно подписанная разбивка из указанной версии сайта. Расхождения записаны в примечаниях. [Cèdre Gingembre, ОАЭ](https://ae.loccitane.com/en/cedre-gingembre-cap-cedrat-eau-de-toilette/20ET050HCR25.html) · [Cèdre Gingembre, США](https://www.loccitane.com/en-us/cedre-gingembre-%28formerly-cap-cedrat%29--eau-de-toilette-20ET050HCR25.html) · [Verveine, США](https://www.loccitane.com/en-us/verbena-eau-de-toilette-15ET075VB26.html) · [Verveine, ОАЭ](https://ae.loccitane.com/en/verveine-verbena-eau-de-toilette/15ET075VB26.html)

## Партия от 22 ноября 2026 года

Добавлены 20 версий пяти брендов. У 19 указаны все три уровня, у каждой версии сохранены четыре метки характера, источник и редакционные рекомендации по сезону и времени суток. [Рекомендации](../card_profiles/wear.csv)

| Бренд | Версии |
| --- | --- |
| Gucci | Flora Gorgeous Gardenia, Gorgeous Jasmine, Gorgeous Magnolia, Gorgeous Orchid и Guilty Pour Femme в Eau de Parfum |
| Victoria’s Secret | Bombshell, Bombshell Intense, Tease, Tease Glam, Tease Crème Cloud, Tease Cocoa Soirée и Tease Strawberry Bisou в Eau de Parfum |
| Valentino | Donna Born in Roma, Donna Born in Roma Intense, Donna Born in Roma Coral Fantasy, Donna Born in Roma Green Stravaganza и Uomo Born in Roma Intense в Eau de Parfum, Uomo Born in Roma Coral Fantasy в Eau de Toilette |
| Yves Saint Laurent | Libre Eau de Parfum |
| Lancôme | Idôle Eau de Parfum |

У лимитированной **Tease Glam Eau de Parfum** есть общий проверенный список из трёх нот. Уровни оставлены открытыми из-за расхождений между справочниками и продавцами. Для **Bombshell** выбрана подписанная разбивка актуальной страницы Victoria’s Secret, а расхождение со старым пресс-китом записано в CSV. У **Bombshell Intense** и **Libre** ссылки на данные об уровнях сохранены отдельно от описания товара. [Tease Glam · Parfumo](https://www.parfumo.com/Perfumes/Victoria_s_Secret/tease-glam-eau-de-parfum) · [Tease Glam · Fragrantica](https://www.fragrantica.com/perfume/Victoria-s-Secret/Tease-Glam-63625.html) · [Bombshell · Victoria’s Secret](https://www.victoriassecret.com/us/vs/beauty/fragrances-bombshell-shop)

## Загрузка данных

Выполните после миграций и загрузки основного набора.

```powershell
.\.venv\Scripts\python.exe manage.py import_catalog_additions
```

Команда обрабатывает файл в одной транзакции. Она находит версию по бренду, названию и концентрации, переиспользует справочник нот и проверяет метки характера. Для исключений с неполной пирамидой заполните поле `notes` общим списком подтверждённых нот, а в `evidence_note` объясните выбор источника и уровней. При повторном запуске команда обновляет совпавшие карточки и связи. Для другой партии передайте `--file путь-к-CSV`. Используйте `|` для нескольких меток или нот. Значение `source` в `family_origin` означает, что семейство указал производитель. Значение `catalog` обозначает семейство, выбранное для навигации в «Атласе».

## Официальные фотографии

Для каждого доступного снимка записаны страница публикации (`photo_source_url`), адрес снимка (`image_url`), условия правообладателя (`terms_url`), имя и размеры файла. Снимки показываются из `.local/official-bottle-photos/` по записям `.local/official-bottle-photos.json`. Эти два элемента нужны для переноса фотографий на другой локальный стенд. Права на фото сохраняются за правообладателями. Набор снимков используется для локального учебного показа и исключён из Git.

Во второй партии локальные фото есть для 15 версий. Снимок **Flora Gorgeous Gardenia** взят со страницы премии The Fragrance Foundation и подписан на карточке. Для Tease Glam и ещё четырёх версий Gucci используются иллюстрации семейств. [Фото Gorgeous Gardenia](https://fragrance.org/award/gucci-flora-gorgeous-gardenia-eau-de-parfum/) · [Иллюстрации проекта](../../MEDIA.md#официальные-фотографии-для-локального-показа)
