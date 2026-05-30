# Playwright: выгрузка статей Дзен

## Установка (один раз)

```powershell
cd C:\Users\kash-\Python_kash\Cursor\AIKIVAVIORA_v.3_Cursor
pip install -r tools\requirements-scrape.txt
python -m playwright install chromium
```

## Как пользоваться

1. Откройте статью на Дзене → **Поделиться → Скопировать ссылку** (формат `https://dzen.ru/a/...`).
2. Запустите:

```powershell
python tools\dzen_playwright_export.py "https://dzen.ru/a/XXXX" -o "G:\3_Дзен\...\слот\statiia.md"
```

3. **Первый запуск** — откроется окно Chrome. Если попросит вход — войдите в Яндекс. Сессия сохранится в `05data/playwright_dzen_profile/`.
4. Повторные запуски можно с `--headless` (без окна), если уже залогинены.

## Проверено

- Статья: `https://dzen.ru/a/agn86z3LoXbDuwvM`
- Результат: ~71 блок, ~11 000 символов → `.md`
- Тест: `03experiments/dzen_scrape/agn86z3LoXbDuwvM.md`
- Канон G: `4_AIKIVAVIORA_база-RAG/модуль 1.3 - .../4F_10-00_.../statiia_1530_roditel_pomoshchnik_praktika_1_3.md`

## Не работает

| URL | Почему |
|-----|--------|
| `dzen.ru/id/...` | это канал, не статья |
| `requests` без браузера | SSO-заглушка |

## Дальше

После накопления `.md` на G: — `python tools/ingest_from_g.py` (когда сделаем полный ingest).
