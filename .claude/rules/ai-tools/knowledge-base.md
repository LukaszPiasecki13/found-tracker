---
paths: ["docs/**/*.md", "CONTEXT.md", "PRODUCT.md", "**/CONTEXT.md"]
description: Konwencje bazy wiedzy dla agentów - reguły edycji dokumentów w docs/. Schemat metadanych, warstwy i limity żyją w skillu knowledge-base. Ładowane automatycznie przy pracy na dokumentach w docs/.
---

# Baza wiedzy — konwencje

Minimum egzekwowane przy każdej edycji dokumentu. **Tu nie ma schematu metadanych,
modelu warstw ani limitów rozmiaru** — mają jedno źródło prawdy w skillu `knowledge-base`
(wywołaj go zamiast odtwarzać konwencję z pamięci):

| Co | Gdzie |
|---|---|
| Front-matter: pola, `status`, `type`, kody walidatora | skill `knowledge-base`, plik `METADATA.md` |
| Warstwy L0–L4, limity rozmiaru | skill `knowledge-base`, plik `ARCHITECTURE.md` |
| Szablony dokumentów i ADR | skill `knowledge-base`, katalog `templates/` |

Zasady niezależne od schematu:

- Sprzeczność między dokumentami rozstrzyga warstwa wyższa i **jest defektem** — zgłoś ją
  jako otwarty punkt, nie wybieraj po cichu.
- **Plan (L3) nigdy nie opisuje stanu systemu**; stan opisuje L2 z linkami do kodu.

## Reguły edycji

1. **Jeden fakt — jedno miejsce.** Wszędzie indziej link `plik.md#kotwica`.
2. **Twierdzenie normatywne ma źródło** (kod, ADR, dowód L4). Bez źródła → w treści
   `> **[HIPOTEZA]** … Podstawa: …`.
3. **Decyzja idzie do ADR**, nie do planu. Warunki łącznie: nieodwracalna,
   nieoczywista, był realny wybór. Format ADR ustala reguła `architecture-decisions`.
4. **Nowe pojęcie domenowe → `CONTEXT.md` natychmiast**, z listą `_Unikać_`.
5. **Nic nie kasujesz** — zastąpiony lub zamknięty dokument zostaje w repo, z
   dopiskiem w treści i linkiem do następcy (konwencję lokalizacji wybiera projekt).
6. **Zmiana nagłówka zrywa kotwice** — napraw linkujące dokumenty w tym commicie.
7. **Nowy dokument → wpis w `docs/00_KNOWLEDGE-MAP.md`** w tym samym commicie.
8. **Zmiana kodu z `applies_to`** → aktualizacja dokumentu i nowe `last_reviewed`,
   w tym samym commicie co kod.
9. **`last_reviewed` podbija ten, kto sprawdził treść wobec rzeczywistości** — nie ten,
   kto poprawił literówkę.
10. **Nomenklatura statusu zależy od typu.** Zwykłe dokumenty: front-matter `status: draft/current`.
    ADR-y (`type: decision`): front-matter `status: Proposed/Accepted`.
    Brak sekcji `## Status` w treści — informacja żyje w metadanych.

## Przed zamknięciem zadania

Uruchom walidator (`kb_validate.py --root . --strict`). Projekt dostaje go jako hook
pre-commit `kb-validate` z repozytorium ai-tools (patrz `.pre-commit-hooks.yaml`) albo kopią
przez `python <ai-tools>/scripts/install.py --target . --validator`. Plik poza strukturą
bazy wyłączasz flagą `--exclude <glob>`.
