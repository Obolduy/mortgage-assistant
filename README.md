# Ипотечный ассистент

Бэкенд ассистента ипотечного банка. Проект к воркшопам второго модуля профессии
«LLM-разработчик» на Хекслете.

Архитектура и решения: [docs/architecture.md](docs/architecture.md), [docs/adr/](docs/adr/).

## Эталон по встречам

После каждой встречи здесь появляется тег с решением домашнего задания: `workshop-1`,
`workshop-2` и так далее.

```sh
git clone https://github.com/Obolduy/mortgage-assistant.git
cd mortgage-assistant
git fetch --tags

# начать следующий шаг с эталона
git checkout -b my-work workshop-1

# сравнить свое решение с эталоном
git diff workshop-1 -- app/
```

## Что есть в тегах

`workshop-1`:

- Каркас на FastAPI: типизированные настройки, пул соединений, структурные логи.
- Postgres с pgvector и Temporal в Docker Compose.
- Миграции SQL-файлами и свой раннер.
- Проверки живости и готовности.
- Таблица кредитов с пятью тестовыми кредитами.
- Калькулятор в целых копейках: график, досрочное погашение (сократить срок или платеж), смена
  даты платежа.
- `GET /loans/{id}` и `GET /loans/{id}/schedule`.

`workshop-2-start` – код, который разбираем на второй встрече, с него начинается домашка:

- Клиент модели: повторы и таймаут живут в HTTP-клиенте, у прогона агента свой общий таймаут.
- Агент на OpenAI Agents SDK с инструментами `get_loan`, `get_schedule`,
  `simulate_early_repayment`. Номер кредита приходит из контекста клиента, модель его не выбирает.
- Контракт ответа `AssistantAnswer` и `POST /ask`.
- Бюджет ходов агента: исчерпан – вопрос уходит сотруднику.

`workshop-2` – решение домашки после второй встречи:

- Разбор грязного JSON от модели и повтор с текстом ошибки, без повторного вызова инструментов.
- Проверка сумм в ответе: каждая должна найтись в результатах инструментов, иначе повтор, потом
  сотрудник.
- Порог уверенности: ниже порога ответ помечается для сотрудника.
- Таблица задач с ключом идемпотентности.
- Заявление на смену даты платежа – процесс в Temporal: проверка правил, ожидание сотрудника,
  решение через update с валидатором. Инструменты агента для проверки и подачи заявления.

`workshop-3-start` – код, который разбираем на третьей встрече:

- Документы банка в `data/`: договор, регламент, правила досрочки, тарифы, скан справки, заявление
  клиента. Пересобрать: `make dataset`.
- Разбор PDF, DOCX и XLSX в блоки, нормализация (колонтитулы, переносы, пробелы), нарезка на чанки с
  метаданными: раздел, страница, лист, строка, код программы.
- Скан без текстового слоя получает отказ с причиной.
- Посмотреть чанки файла: `make chunks FILE=data/credit_agreement.pdf`.

## Запуск

Нужны Python 3.12, [uv](https://docs.astral.sh/uv/) и Docker. Для `POST /ask` – локальная модель:
[LM Studio](https://lmstudio.ai/) с `gemma-4-e4b-it` на `http://localhost:1234`.

```sh
cp .env.example .env   # порт 5434 занят? поменяйте PG_PORT и DATABASE_URL
make install           # зависимости из uv.lock
make infra             # Postgres с pgvector и Temporal
make migrate           # повторный запуск напишет «Новых миграций нет»
make api               # http://localhost:8000/docs
make worker            # воркер Temporal для заявлений
```

```sh
make lint
make test   # тестам нужна поднятая база с миграциями, модель не нужна
```

## Как проверить себя

- `make test` и `make lint` зеленые.
- Повторный `make migrate` ничего не применяет.
- `GET /health/ready` отвечает 200 и версией `vector`.
- `docker compose -p mortgage-assistant stop db`: `/health/live` – 200, `/health/ready` – 503.
- Без `DATABASE_URL` приложение не стартует.
- `GET /loans/1/schedule`: первый платеж 5 505 431 копейка (55 054,31 ₽).

## Деньги

Все суммы – целые копейки, ставка – базисные пункты: 12% годовых = `1200`. Почему так –
[ADR-0001](docs/adr/0001-agent-stack.md).

## Вопрос ассистенту

```sh
curl -s localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"loan_id": 1, "question": "После 12-го платежа внесу 500 000 и уменьшу платеж. Какой будет платеж?"}'
```

## Заявление на смену даты платежа

```sh
curl -s -X POST localhost:8000/applications/payment-day -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: my-key-1' -d '{"loan_id": 3, "new_day": 20}'
curl -s localhost:8000/jobs/<id>
curl -s -X POST localhost:8000/applications/<id>/decision -H 'Content-Type: application/json' \
  -d '{"approve": true}'
```

История процесса – в веб-интерфейсе Temporal: http://localhost:8233.
