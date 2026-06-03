# Безопасность Aviora Catalog (локальный MVP)

> API рассчитан на **localhost** (порт 8002). Не выставляйте в интернет без доработок.

## Что сделано

| Риск | Мера |
|------|------|
| Path traversal | Все пути через `resolve_path` — только под `CATALOG_ROOT` |
| Секреты в редакторе | Blacklist `.env`, `*.pem`, `id_rsa`; `.env` — banner + read-only |
| Overwrite | Backup `*.bak` для md/txt/изображений |
| Zip slip | Extract проверяет `relative_to(CATALOG_ROOT)` |
| DoS файл | `MAX_UPLOAD_MB`, `MAX_FILE_READ_MB`, `MAX_IMAGE_DIM` |
| CORS | localhost:8002 по умолчанию |
| Ключи в git | `.env` не коммитить; в `/health` нет значения ключа |
| Весь диск | `ALLOW_FULL_DISK` **не** реализован |

## Ограничения MVP

- Нет аутентификации на API
- Read-only — переключатель UI + env `READ_ONLY_MODE`
- Удаление → `.trash/` внутри корня

## Перед публикацией

1. HTTPS + reverse proxy + API key
2. Rate limiting
3. CORS только на свой домен

## Проверка

```powershell
git ls-files "**/.env"
```

Должно быть пусто.
