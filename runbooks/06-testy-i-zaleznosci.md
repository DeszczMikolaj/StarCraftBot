# 06. Testy, jakość kodu, zależności

**Cel:** sprawdzić zmiany przed commitem i bezpiecznie dodać lub zaktualizować bibliotekę.

## Testy

Testy jednostkowe nie potrzebują gry i trwają około sekundy:

```bash
uv run pytest
```

Testy integracyjne startują prawdziwą grę, więc uruchamia się je tam, gdzie jest
zainstalowana. W Dockerze trwają około minuty:

```bash
docker compose run --rm sc2 pytest -m sc2
```

Te same testy działają na kliencie Windows z [runbooka 02](02-klient-windows.md). Trwają
tam około półtorej minuty i otwierają okna gry:

```bash
uv run pytest -m sc2
```

| Plik | Co sprawdza |
|------|-------------|
| `tests/test_observation.py` | Skalowanie i obcinanie wektora obserwacji, odwracalność. |
| `tests/test_reward.py` | Składniki nagrody i nagrodę końcową. |
| `tests/test_qlearning.py` | Dyskretyzację, regułę aktualizacji Q, maski, epsilon, zapis i odczyt tablicy. |
| `tests/test_agents_and_runner.py` | Agentów odniesienia, pętlę epizodów (także równoległą i po awarii gry), przedział Wilsona. |
| `tests/test_env_integration.py` | Prawdziwą grę: stan początkowy, skutki akcji, limit czasu, powtórkę, zgodność z wrapperem `RecordEpisodeStatistics` z Gymnasium. |

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

## Typy

Każda funkcja ma adnotacje typów, a mypy sprawdza je tak jak kompilator w Javie: przed
uruchomieniem i bez gry. Pierwsze uruchomienie trwa około pół minuty, bo mypy buduje
pamięć podręczną w `.mypy_cache/`; kolejne trwają około sekundy.

```bash
uv run mypy
```

Sprawdza `src/`, `tests/`, `scripts/` i `examples/`. Poprawny wynik:

```text
Success: no issues found in 38 source files
```

Przykłady tego, co wyłapuje. Wywołanie `env.step("ATTACK")` zamiast numeru akcji daje

```text
<plik>:<linia>: error: Argument 1 to "step" of "SC2MacroEnv" has incompatible type "str"; expected "int"  [arg-type]
```

a literówka w kluczu `info`, np. `info["action_maks"]`:

```text
<plik>:<linia>: error: TypedDict "StepInfo" has no key "action_maks"  [typeddict-item]
<plik>:<linia>: note: Did you mean "action_mask"?
```

Ustawienia są w `pyproject.toml`, w sekcji `[tool.mypy]`:

- `strict = true`: każda funkcja musi mieć typy parametrów i wyniku, a funkcja o
  zadeklarowanym typie nie może zwracać wartości nieznanego typu (`Any`).
- `platform = "linux"`: kod jest sprawdzany tak, jak działa w kontenerze, więc wynik jest
  ten sam na Windows i na Linuksie.

### Odpowiedniki z Javy

| Java | Python w tym projekcie | Przykład |
|------|------------------------|----------|
| interfejs implementowany jawnie | klasa abstrakcyjna (`ABC`), po której się dziedziczy | `Agent` w `agents/base.py`, `TabularQAgent(Agent)` |
| interfejs bez `implements` | `Protocol`: pasuje każda klasa, która ma wymienione metody | `AsyncEnv` w `runner.py`; pasują do niego `SC2MacroEnv` i testowy `FakeEnv` |
| `enum` | `IntEnum` | `MacroAction` w `env/actions.py` |
| `record` | `@dataclass(frozen=True)` | `EnvConfig` w `config.py`, `StepRecord` w `runner.py` |
| `record`, ale pola czyta się kluczem-napisem | `TypedDict`: w działaniu zwykły `dict`, mypy zna klucze i typy wartości | `StepInfo` i `GameSummary` w `env/info.py` |
| `@Nullable Integer` | `int \| None` | `seed: int \| None = None` |
| `List<Integer>`, `Map<String, Double>` | `list[int]`, `dict[str, float]` | |
| rzutowanie `(StepData) obj` | `cast(StepData, obj)` | odbiór odpowiedzi z procesu gry w `env/sc2_env.py` |
| `Object` | `Any`: wyłącza sprawdzanie dla tej wartości | `options: dict[str, Any]` w `reset` |

Dwie różnice, o których łatwo zapomnieć:

- **Typy nie działają w czasie wykonania.** Interpreter ich nie sprawdza, a `cast` niczego
  nie konwertuje ani nie weryfikuje. Błędny typ wyłapie tylko mypy.
- **Nie ma przeciążania metod.** Jedna nazwa to jedna metoda; warianty robi się
  parametrami z wartościami domyślnymi.

### Czego mypy nie sprawdzi

- **Kluczy słowników, których klucze pochodzą z listy.** Same klucze `info` są
  sprawdzane (`StepInfo`), ale w środku `info["raw"]`, `info["reward_components"]`
  i `info["game_summary"]["action_counts"]` to zwykłe `dict[str, float]` albo
  `dict[str, int]`: ich klucze to nazwy z `FEATURE_NAMES`, `REWARD_COMPONENTS`
  i `ACTION_NAMES`, a kod zwykle przechodzi po nich pętlą. Literówka w
  `info["raw"]["minerlas"]` wyjdzie dopiero w działaniu, jako `KeyError`. Tak samo
  słowniki zapisywane do CSV i JSON (`run_logging.py`, `evaluate.py`).
- **Kształtu tablic numpy.** Typ mówi „tablica", ale nie „wektor długości 24".
- **Części właściwości python-sc2.** Właściwości z pamięcią podręczną na jedną klatkę gry
  (np. `expansion_locations_list`) mypy widzi jako typ `Never`, więc ich użycia nie
  sprawdza. W `env/macro.py` dwa takie miejsca mają `cast` przywracający zadeklarowany
  typ.

Jedyne `type: ignore` w projekcie są przy `reset` i `step` w `env/sc2_env.py`. Gymnasium
deklaruje tam `info` jako `dict[str, Any]`, a mypy nie uznaje `TypedDict` za podtyp
`dict`, choć w działaniu nim jest. Komentarz nad tymi metodami opisuje to w kodzie.

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
- [ ] `uv run mypy` bez uwag
- [ ] `uv run pytest` przechodzi
- [ ] `docker compose run --rm sc2 pytest -m sc2` przechodzi, jeśli zmiana dotyka `src/scbot/env/`
- [ ] nowe zachowanie ma test, a zmiana interfejsu jest opisana w `docs/`
