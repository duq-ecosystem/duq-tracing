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
