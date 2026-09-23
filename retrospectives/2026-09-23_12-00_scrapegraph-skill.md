# Ретро: установка скила ScrapeGraphAI (just-scrape)

**Дата:** 2026-09-23 12:00
**Длительность:** ~10 минут
**План:** —

## 1. Задача

Найти на GitHub скил ScrapeGraphAI и установить его в проект.

## 2. Как решал

Поиск через GitHub code search `org:ScrapeGraphAI filename:SKILL.md` → официальный скил `ScrapeGraphAI/just-scrape/skills/just-scrape` (коммит `a3d179f`). Сторонние копии (реестры, форки) отбросил. Аудит по `prompts/setup/08-skills-install.md`: один SKILL.md, без скриптов, без curl/wget наружу, без rm, без чтения `.env` самим скилом → безопасно. Установлен локально в `.claude/skills/just-scrape/`, `.just-scrape/` (папка вывода CLI) добавлена в `.gitignore`.

## 3. Решил?

- [ ] Да, полностью
- [x] Частично: скил установлен; сам CLI `just-scrape` (npm) и ключ `SGAI_API_KEY` не ставились — это решение пользователя (платный API).
- [ ] Нет: почему

## 4. Что можно было лучше

Сразу искать в официальной организации — поиск по всему GitHub выдаёт десятки копий.

## 5. Как было / как стало

- **Было:** скила ScrapeGraphAI нет.
- **Стало:** `.claude/skills/just-scrape/SKILL.md` (официальный, MIT).

## Follow-up (если нужно)

- Решить, нужен ли ScrapeGraphAI API (платный, кредиты) для коллекторов с пометкой «нужен ресерч»; если да — `npm i -g just-scrape` + `SGAI_API_KEY` в `.env`.
