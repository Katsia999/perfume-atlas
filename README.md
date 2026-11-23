# Атлас ароматов

**Курсовая работа Беляевой Екатерины Викторовны, группа СДП-ИИ-241**

«Атлас ароматов» — база знаний по парфюмерии на Django и PostgreSQL. В каталоге собраны карточки ароматов с пирамидами нот, рекомендациями по сезону и времени суток и ссылками на источники. Поиск по слову, фразе или предложению исправляет распространённые опечатки и находит ароматы, статьи, видео и новости. Подбор по нотам показывает, какие предпочтения совпали. Каталог и материалы можно пополнять через Django Admin. [Демонстрационные данные и источники](data/demo/README.md) · [Графика и видео](MEDIA.md)

## 1. Установить программы на Windows

Для локального запуска без Docker нужны Python, PostgreSQL и PowerShell. Инструкция проверена с Python 3.11.9 и PostgreSQL 17.5. При стандартной установке PostgreSQL должен работать как служба Windows. Запомните пароль роли `postgres` и порт сервера, обычно `5432`. [Python для Windows](https://www.python.org/downloads/windows/) · [PostgreSQL для Windows и pgAdmin](https://www.postgresql.org/download/windows/)

## 2. Создать роль и базу в pgAdmin

1. Подключитесь к локальному серверу под ролью `postgres`. При регистрации сервера в **Servers → Register → Server** укажите на вкладке **Connection** адрес `127.0.0.1`, порт установки, **Maintenance database** `postgres` и **Username** `postgres`.
2. В **Login/Group Roles → Create → Login/Group Role** задайте имя `perfume_app`, пароль на вкладке **Definition** и включите **Can login?** на вкладке **Privileges**. [Настройки роли](https://www.pgadmin.org/docs/pgadmin4/latest/role_dialog.html)
3. В **Databases → Create → Database** задайте имя `perfume_atlas` и владельца `perfume_app`. На вкладке **Definition** выберите **Encoding** `UTF8`, **Template** `template0`, **Locale Provider** `ICU` и **ICU Locale** `ru-RU`. Эти параметры позволяют PostgreSQL учитывать регистр кириллицы при поиске. [Настройки базы](https://www.pgadmin.org/docs/pgadmin4/latest/database_dialog.html)

Альтернативный способ через `psql`. Подключитесь под администратором к базе `postgres` и выполните команды по очереди. Команда `\password` запросит новый пароль роли.

```sql
CREATE ROLE perfume_app LOGIN;
\password perfume_app
CREATE DATABASE perfume_atlas OWNER perfume_app TEMPLATE template0
  ENCODING 'UTF8' LOCALE_PROVIDER icu ICU_LOCALE 'ru-RU';
```

## 3. Установить зависимости и настроить подключение

Откройте PowerShell в каталоге исходников.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -c "from secrets import token_urlsafe; print(token_urlsafe(48))"
notepad .env
```

Пример настроек для базы из предыдущего шага. [Файл .env.example](.env.example)

```dotenv
DJANGO_SECRET_KEY=
POSTGRES_DB=perfume_atlas
POSTGRES_USER=perfume_app
POSTGRES_PASSWORD=
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

Вставьте сгенерированный ключ в `DJANGO_SECRET_KEY`, а пароль роли приложения в `POSTGRES_PASSWORD`. Если выбрали другие имя базы, роль или порт, укажите их в `.env`. Для пароля с пробелами по краям или знаком `#` используйте кавычки. Файл `.env` исключён из Git.

## 4. Применить миграции, загрузить данные и запустить Django

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py import_demo
.\.venv\Scripts\python.exe manage.py import_articles
.\.venv\Scripts\python.exe manage.py import_profiles
.\.venv\Scripts\python.exe manage.py import_pyramids
.\.venv\Scripts\python.exe manage.py import_catalog_additions
.\.venv\Scripts\python.exe manage.py import_performance
.\.venv\Scripts\python.exe manage.py import_wear
.\.venv\Scripts\python.exe manage.py train_intent
.\.venv\Scripts\python.exe manage.py prepare_semantic_search
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

`createsuperuser` создаёт учётную запись для входа в Django Admin. При повторном запуске используйте созданную учётную запись. Если порт `8000` занят, укажите свободный порт в команде и в адресах для браузера. Сервер предназначен для локального запуска. [Главная](http://127.0.0.1:8000/) · [Django Admin](http://127.0.0.1:8000/admin/)

В чистой базе после импорта доступны 60 версий ароматов 13 брендов, 19 статей, 12 видео и 12 новостей. На главной из раздела «Из журнала» открываются списки каждого типа. Импорты обновляют записи по ключам из файлов. На существующем стенде повторный `import_demo` запускайте перед `import_pyramids`, чтобы финальная разбивка нот учитывала уточнения. Стойкость, шлейф и рекомендации загружаются после импорта всех версий ароматов. [Основной набор](data/demo/README.md) · [Характер, пирамиды и свойства](data/card_profiles/README.md) · [Дополнительные версии](data/catalog_additions/README.md)

В **База знаний → Материалы → Добавить материал** заполните тип, заголовок, описание, ссылку и дату проверки. Для новости укажите дату публикации в источнике. Отметка **Опубликовано** открывает доступ к записи и добавляет её в поиск. Метки характера, ноты, рекомендации, стойкость и шлейф редактируются в форме версии аромата. Ссылки и даты сверки хранятся рядом со сведениями, к которым относятся.

### Журнал

В разделе **Из журнала** на главной выберите статьи, видео или новости. Попробуйте запросы «Gucci Flora», «ваниль с карамелью» или «свежие новости». В материалах с роликом нажмите **Воспроизвести видео** либо перейдите к оригиналу. Подробные тексты статей, подписи, источники и ссылки на видео хранятся в JSON. [Статьи](http://127.0.0.1:8000/search/?kind=article) · [Видео](http://127.0.0.1:8000/search/?kind=video) · [Новости](http://127.0.0.1:8000/search/?kind=news) · [Файлы статей](data/articles/)

## 5. Воспроизвести проверки

После миграций, импорта и обучения выполните во втором окне PowerShell.

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe manage.py verify_search
```

`verify_search` обращается к работающему сайту и сверяет карточки в выдаче с выборками PostgreSQL. Проверяются исправления, типы результатов, период новостей, подбор и условия по нотам и свойствам. Для сервера на другом порту передайте, например, `--port 8001`. В pgAdmin таблицы доступны в **Databases → perfume_atlas → Schemas → public → Tables**.

Для ручной проверки введите «бергамт». Сайт предложит исправление «бергамот». Запрос «хочу стойкие духи с ванилью и лёгким шлейфом» на демонстрационном наборе даёт L’Occitane Néroli Orchidée EDT с объяснением совпадений. В подборе отметьте «Ваниль» и «Сандал». Версии с двумя совпадениями появятся перед версиями с одним. [Поиск с опечаткой](http://127.0.0.1:8000/search/?q=%D0%B1%D0%B5%D1%80%D0%B3%D0%B0%D0%BC%D1%82) · [Подбор по нотам](http://127.0.0.1:8000/selection/)

## Как обучается модель и работает поиск

Команда `train_intent` обучает классификатор на размеченных запросах, выводит Macro‑F1 на отложенной выборке и сохраняет модель в `.local/query-intent.joblib`. Классификатор помогает поднять в выдаче подходящий тип результата. [Размеченные запросы](data/search/queries.csv) · [Команда обучения](catalog/management/commands/train_intent.py)

Для поиска по смыслу при первой установке выполните `manage.py prepare_semantic_search`. Команда скачает около 131 МБ с Hugging Face, сверит SHA-256 и подготовит векторы фрагментов опубликованных записей. Затем сайт обрабатывает запросы на процессоре без подключения к интернету. Для переноса можно скопировать каталог `.local/rubert-mini-frida/`. Пока модель не загружена, поиск использует совпадения слов и проверяемые свойства. [Модель ruBERT-mini-FRIDA](https://huggingface.co/sergeyzh/rubert-mini-frida) · [Версия ONNX](https://huggingface.co/amekhrishvili/rubert-mini-frida-onnx)

Попробуйте «Хочу пахнуть как свежевыстиранные простыни» или «Куда пшикнуть пробник, чтобы понять, брать ли флакон?». Для свободного описания сайт сравнивает вектор запроса с текстами карточек и материалов, учитывает общие слова и показывает до пяти близких записей с подходящими фрагментами. Указанные ноты, исключения и выбранный тип ограничивают подбор. Если к ванили добавить бюджет, выдача объяснит, что в базе нет цен. После правки в админке новые тексты участвуют в ближайшем поиске. [Попробовать поиск](http://127.0.0.1:8000/search/) · [Код сравнения фрагментов](catalog/semantic.py)

## Как устроен CSV-импорт

`import_demo` читает шесть CSV из `data/demo`. Сначала загружаются справочники, затем версии ароматов, связи с нотами и материалы. В базе версия определяется по бренду, названию и концентрации, а материал по типу и заголовку. Ошибка в CSV отменяет изменения всего запуска команды. Для другого набора передайте `manage.py import_demo --directory путь`. [Файлы основного набора](data/demo/) · [Код импорта](catalog/management/commands/import_demo.py)
