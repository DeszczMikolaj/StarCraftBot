# 06. Testy, jakość kodu, zależności

**Cel:** sprawdzić zmiany przed commitem i bezpiecznie dodać lub zaktualizować bibliotekę.

## Testy

Testy jednostkowe nie potrzebują gry i trwają około sekundy:

```bash
uv run pytest
```

Testy integracyjne startują prawdziwą grę, więc uruchamia się je tam, gdzie jest
zainstalowana. W Dockerze trwają około 40 sekund:

```bash
docker compose run --rm sc2 pytest -m sc2
```

Te same testy działają na kliencie Windows z [runbooka 02](02-klient-windows.md). Trwają
tam około 80 sekund i otwierają okna gry:

```bash
uv run pytest -m sc2
```

| Plik | Co sprawdza |
|------|-------------|
| `tests/test_observation.py` | Skalowanie i obcinanie wektora obserwacji, odwracalność. |
| `tests/test_reward.py` | Składniki nagrody i nagrodę końcową. |
| `tests/test_qlearning.py` | Dyskretyzację, regułę aktualizacji Q, maski, epsilon, zapis i odczyt tablicy. |
| `tests/test_agents_and_runner.py` | Agentów odniesienia, pętlę epizodów (także równoległą i po awarii gry), przedział Wilsona. |
| `tests/test_env_integration.py` | Prawdziwą grę: stan początkowy, skutki akcji, limit czasu, powtórkę. |

Uruchom testy integracyjne po każdej zmianie w `src/scbot/env/`.

## Styl kodu

```bash
uv run ruff check .
```

```bash
uv run ruff format .
```

Pierwsza komenda zgłasza błędy, druga formatuje pliki. Obie powinny przejść bez uwag
przed commitem.

## Dodanie lub aktualizacja biblioteki

1. Dodaj zależność (zapisuje ją w `pyproject.toml` i aktualizuje `uv.lock`):

   ```bash
   uv add nazwa-biblioteki
   ```

2. Odśwież `requirements.txt`, który jest generowany z pliku blokady:

   ```bash
   uv run python scripts/export_requirements.py
   ```

   Skrypt wywołuje `uv export` i dopisuje adresy indeksów PyTorch, bez których `pip` nie
   znajdzie wersji `+cu126` i `+cpu`. Nie edytuj tego pliku ręcznie.

3. Przebuduj obraz, żeby kontener miał te same wersje:

   ```bash
   docker compose build sc2
   ```

4. Uruchom oba zestawy testów i zacommituj razem `pyproject.toml`, `uv.lock`
   i `requirements.txt`.

Źródłem prawdy o wersjach jest `uv.lock`. `requirements.txt` istnieje dla osób, które
wolą `pip`.

## PyTorch na różnych platformach

`pyproject.toml` wybiera wariant PyTorch według systemu: na Windows wersję z CUDA 12.6
(trening na karcie graficznej), na Linuksie, czyli w kontenerze, wersję CPU. Model A nie
używa sieci, więc w kontenerze karta nie jest potrzebna. Jeżeli DQN lub PPO mają się
uczyć w kontenerze na GPU, trzeba zmienić indeks dla Linuksa w sekcji `[tool.uv.sources]`
i uruchamiać kontener z dostępem do karty.

## Przed commitem

- [ ] `uv run ruff check .` i `uv run ruff format .` bez uwag
- [ ] `uv run pytest` przechodzi
- [ ] `docker compose run --rm sc2 pytest -m sc2` przechodzi, jeśli zmiana dotyka `src/scbot/env/`
- [ ] nowe zachowanie ma test, a zmiana interfejsu jest opisana w `docs/`
