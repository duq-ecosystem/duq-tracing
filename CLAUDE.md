# ⛔⛔⛔ ЗАПРЕТ ЛОКАЛЬНОГО ТЕСТИРОВАНИЯ ⛔⛔⛔

## КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:
- Запускать docker контейнеры локально
- Создавать .venv локально  
- Запускать pytest/go test локально
- Создавать локальные БД
- Запускать сервисы локально
- pip install / go build локально
- ЛЮБОЕ локальное тестирование

## ВСЕ ТЕСТИРОВАНИЕ ТОЛЬКО НА VPS

### Сервер:
```
IP: 90.156.230.49
SSH: ssh root@90.156.230.49
```

### Docker Сервисы (АКТУАЛЬНО):
```
cd /opt/duq-deploy && ./deploy.sh deploy

duq-core         -> :8081
duq-gateway      -> :8082  <- uses duq-tracing
duq-admin        -> :5000
duq-postgres     -> :5432
duq-redis        -> :6379  <- трейсы в Redis
```

### duq-tracing Usage
This is a shared library used by:
- duq (Python) - via `duq.tracing` module
- duq-gateway (Go) - via local module dependency

### Деплой:
```bash
# duq-tracing встроен в Docker образы при сборке
# Изменения в tracing требуют пересборки gateway:

rsync -avz --exclude='.git' /home/danny/Documents/projects/duq-tracing/go/ root@90.156.230.49:/opt/duq-deploy/duq-gateway/duq-tracing/
ssh root@90.156.230.49 "cd /opt/duq-deploy && docker compose build duq-gateway && docker compose up -d duq-gateway"
```

## НАРУШЕНИЕ = НЕМЕДЛЕННОЕ ПРЕКРАЩЕНИЕ РАБОТЫ

## ⛔ TDD Обязательно (Superpowers)

**Superpowers установлен глобально** — TDD-enforcement активен автоматически.

### Red-Green-Refactor

```
НИ ОДНОЙ СТРОКИ PRODUCTION КОДА БЕЗ ПАДАЮЩЕГО ТЕСТА!
```

**Цикл разработки:**
1. **RED** — Напиши падающий тест, запусти, убедись что падает правильно
2. **GREEN** — Напиши минимальный код чтобы тест прошёл
3. **REFACTOR** — Улучши код, держа тесты зелёными

**Правила:**
- Написал код до теста? **Удали**. Начни заново с теста.
- Тест сразу прошёл? Он ничего не тестирует. Исправь.
- Не можешь объяснить почему тест упал? Тест плохой.
- "Потом добавлю тесты" = технический долг

### Superpowers Workflow

Skills активируются автоматически:
- `brainstorming` — перед началом фичи
- `writing-plans` — планирование задач
- `test-driven-development` — при написании кода
- `systematic-debugging` — при отладке
- `verification-before-completion` — перед завершением

### Покрытие

- Минимум: 80%
- Каждая новая функция — покрыта тестами
- Каждый баг-фикс — сначала тест воспроизводящий баг

### Команды

```bash
# Python (pytest)
pytest
pytest --cov
pytest -x --tb=short  # Stop on first failure

# Kotlin (Gradle)
./gradlew test
./gradlew test --tests "ClassName"
./gradlew jacocoTestReport
```
