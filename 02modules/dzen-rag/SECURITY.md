# Безопасность Dzen RAG (локальный MVP)

> API рассчитан на **localhost** (разработка и сдача ДЗ-7). Не выставляйте порт 8001 в интернет без доработок ниже.

## Что уже сделано

| Риск | Мера |
|------|------|
| Утечка ключей в git | `backend/.env` в `.gitignore`; в репозитории только `.env.example` |
| Path traversal при upload | Имя файла: `Path(filename).name` (без `../`) |
| Произвольные типы файлов | Только `.pdf`, `.txt`, `.md` |
| DoS большим файлом | Лимит размера upload (`RAG_MAX_UPLOAD_MB`, по умолчанию 25 МБ) |
| DoS длинным вопросом | Лимит длины `query` (8000 символов) |
| Произвольный ingest с диска | `POST /ingest` — путь только **внутри** `RAG_SOURCE_PATH` |
| XSS во фронте | `escapeHtml()` для текста сообщений и источников |
| Ключ в `/health` | Только флаги `llm_*_configured`, не значение ключа |
| Ошибки LLM | В ответе тип исключения, не полный traceback |

## Ограничения (осознанно для ДЗ)

- **Нет аутентификации** — любой, кто достучится до API, может `/upload`, `/ingest`, `/chat`.
- **CORS** по умолчанию — origins `127.0.0.1` / `localhost` на порту API; для отладки можно задать `RAG_CORS_ORIGINS=*` (не для продакшена).
- **LM Studio / DeepSeek** — URL и ключи из `.env`; не указывайте внутренние URL компании в `LM_STUDIO_BASE_URL` без необходимости.
- **Индекс Chroma** на диске — не шифруется; не кладите в индекс персональные данные третьих лиц.

## Перед публикацией в сеть

1. API-ключ + reverse proxy + HTTPS  
2. Auth (API key header или OAuth) на `/upload`, `/ingest`, `/chat`  
3. Rate limiting  
4. CORS только на свой домен фронта  
5. Не отдавать `source_path` / `index_path` в публичном `/health` (или отдельный internal endpoint)

## Публичный git push

1. Прочитать `PUBLIC_RELEASE.md` в корне репозитория  
2. Запустить `scripts/check-public-push.ps1`  
3. Убедиться, что в remote нет индекса Chroma и материалов PDF канала  

## Проверка перед сдачей

```powershell
# .env не в индексе git
git ls-files "**/.env"

# Должно быть пусто
```

Скрин `.env` для Google Doc — **замазать** `DEEPSEEK_API_KEY`.
