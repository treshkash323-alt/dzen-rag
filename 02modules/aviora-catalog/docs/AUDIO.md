# Аудио в Aviora Catalog (v0.3.13)

## Форматы

`.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.wma`, `.opus`

## UI

1. Откройте аудио в дереве слева — **плеер** и поле транскрипта.
2. **Транскрипт** — распознавание речи; **фиолетовая полоса под лентой** (как Scan), % и «часть N из M». Пока идёт — можно листать каталог; не закрывать окно сервера.
3. Чип **audio** в поиске — только аудиофайлы (после Scan).
4. **Студия → Тексты** — папка `05data/aviora_audio_transcripts/`.

## Установка (один раз)

В PowerShell:

```powershell
cd backend
.\.venv\Scripts\pip install -r requirements.txt
```

Установите **ffmpeg** и добавьте в PATH (для части форматов):  
https://ffmpeg.org/download.html

Перезапустите сервер :8002. В подвале UI: `whisper` в health.

## Настройки (.env)

```
WHISPER_MODEL=small
WHISPER_LANGUAGE=ru
WHISPER_DEVICE=cpu
WHISPER_COMPUTE=int8
MAX_AUDIO_TRANSCRIBE_MB=1024
WHISPER_CHUNK_SEC=600
WHISPER_CHUNK_MINUTES=15
```

Длинные записи (как 1.5 ч) обрабатываются **по частям** (~10 мин) через ffmpeg.

Первый запуск скачивает модель (несколько сотен МБ).

## Индекс

После транскрипции текст попадает в индекс (без полного Scan). Для всех файлов — **Scan** после пакетной обработки.

## Чат

Вопросы по **тексту транскрипта** в индексе; сам MP3 в LLM не отправляется.
