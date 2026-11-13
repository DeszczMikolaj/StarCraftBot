# Rozwijanie projektu

Jak dodać własnego agenta, cechę obserwacji, akcję makro albo składnik nagrody, nie psując
pracy pozostałych osób.

## Zasady wspólne

- Wektor obserwacji i lista akcji to **wspólny kontrakt** wszystkich modeli. Nowe pozycje
  dopisuj **na końcu**. Zmiana kolejności lub usunięcie pozycji unieważnia zapisane
  tablice Q i wytrenowane sieci.
- Każda zmiana w `src/scbot/env/` wymaga przejścia testów integracyjnych
  (`docker compose run --rm sc2 pytest -m sc2`).
- Kod, komentarze i komunikaty commitów są po angielsku. Dokumentacja i runbooki po polsku.
- Przed commitem: [runbook 06](../runbooks/06-testy-i-zaleznosci.md).

## Nowy agent (DQN, PPO)

Są dwie drogi. Wybierz tę, która pasuje do biblioteki, z której korzystasz.

### Droga 1: interfejs `Agent`

Tak jest zrobiony Q-Learning. Implementujesz klasę z `agents/base.py`, a pętlę gier,
gry równoległe, logi i ewaluację dostajesz z `runner.run_episodes`.

```python
from scbot.agents.base import Agent


class DQNAgent(Agent):
    name = "dqn"

    def act(self, obs, action_mask, *, explore):
        # zwróć numer akcji; action_mask[a] mówi, czy akcja a jest teraz dostępna
        ...

    def observe(
        self, obs, action, reward, next_obs, next_action_mask, terminated, intervals_elapsed=1.0
    ):
        # jedno przejście: dopisz do bufora powtórek, wykonaj krok uczenia
        ...

    def end_episode(self):
        # koniec gry treningowej: np. zmniejsz epsilon, zsynchronizuj sieć docelową
        ...
```

Uwagi:

- `observe` dostaje przejścia z wielu gier na przemian, gdy trening jest równoległy.
  Bufor powtórek to znosi bez zmian. Algorytm, który potrzebuje całych trajektorii
  w kolejności (PPO), powinien iść drogą 2 albo grupować przejścia po swojej stronie.
- `terminated` jest `False`, gdy gra została tylko ucięta limitem czasu. Wtedy cel uczenia
  nadal powinien doliczać wartość następnego stanu.
- Kroki mają różną długość. `intervals_elapsed` mówi, ile interwałów decyzyjnych minęło
  między `obs` a `next_obs`. Wartość następnego stanu dyskontuj przez
  `gamma ** intervals_elapsed`; w buforze powtórek wystarczy zapisać tę liczbę obok
  przejścia. Przy drodze 2 jest ona w `info["intervals_elapsed"]`.
- Wzorcem skryptu treningowego jest `train_q.py`: tworzy agenta, listę środowisk i woła
  `run_episodes` z funkcjami `on_step` i `on_episode`.
- Żeby agent był dostępny w `play` i `evaluate`, dopisz go w `cli_common.py`
  (`AGENT_CHOICES` i `build_agent`).

### Droga 2: bezpośrednio Gymnasium

`SC2MacroEnv` jest zwykłym środowiskiem Gymnasium z przestrzenią `Box(24)` i
`Discrete(8)`, więc można je podać bibliotece takiej jak Stable Baselines 3. Maskę akcji
zwraca `env.action_masks()` w konwencji sb3-contrib (`MaskablePPO`). Przykład pętli:
[`examples/random_gym_loop.py`](../examples/random_gym_loop.py).

Tej drogi nie testowaliśmy jeszcze z żadną biblioteką uczenia. Stable Baselines 3 nie
jest w zależnościach projektu; dodanie opisuje [runbook 06](../runbooks/06-testy-i-zaleznosci.md).

## Nowa cecha obserwacji

1. Dopisz `Feature(nazwa, skala, opis)` **na końcu** listy `FEATURES` w
   `env/observation.py`. Skalę dobierz tak, żeby typowe wartości wypadały w [0, 1].
2. Dodaj odczyt o tej samej nazwie w `MacroBot._read_raw` (`env/bot.py`). Brak odczytu
   skończy się wyjątkiem `KeyError` przy pierwszej decyzji.
3. Zaktualizuj tabelę w [srodowisko.md](srodowisko.md).

Długość wektora (`OBS_DIM`) zmienia się sama. Tablica Q używa tylko cech wymienionych
w swojej dyskretyzacji, więc dopisanie cechy na końcu jej nie psuje. Sieci neuronowe
trzeba wytrenować od nowa, bo zmienia się rozmiar wejścia.

## Nowa akcja makro

1. Dopisz pozycję **na końcu** `MacroAction` w `env/actions.py`.
2. W `env/macro.py` dodaj warunek dostępności w `available_actions` i wykonanie
   w `execute`.
3. Dodaj test integracyjny, który wykonuje akcję w grze i sprawdza skutek.
4. Zaktualizuj tabelę w [srodowisko.md](srodowisko.md).

Zmiana liczby akcji unieważnia zapisane tablice Q: `TabularQAgent.load` odmówi wczytania
tablicy z inną listą akcji.

Przykład: rafineria i jednostki na gaz. Potrzebne będą akcje `BUILD_REFINERY`
i np. `BUILD_FACTORY`, a w `housekeeping` nic nie trzeba zmieniać, bo
`distribute_workers` sam obsadza rafinerie.

## Nowy składnik nagrody

1. Dodaj licznik narastający w `RewardCounters` (`env/reward.py`) i jego wagę
   w `RewardConfig` (`config.py`), a potem powiąż je w słowniku `_WEIGHT_NAMES`.
2. Wypełnij licznik w `MacroBot._reward_counters` (`env/bot.py`).
3. Dodaj przypadek w `tests/test_reward.py`.

Składnik sam trafi do `info["reward_components"]`, do `episodes.csv` i do TensorBoard.

## Inna mapa lub przeciwnik

Mapę wybiera `--map` (pole `EnvConfig.map_name`). Obraz Dockera zawiera paczki `Melee`,
`Ladder2019Season3` oraz starsze paczki sezonowe dostarczane z grą. Listę nazw pokaże:

```bash
docker compose run --rm sc2 python -m scbot.doctor --list-maps
```

Rozmieszczanie budynków testowaliśmy tylko na `Simple64`. Na innej mapie zacznij od
`scbot.play --agent scripted --map <nazwa>` i sprawdź, czy koszary i magazyny powstają.

Poziom wbudowanej SI wybiera `--difficulty`.

## Wskazówki do diagnozowania

- `SCBOT_DEBUG=1` włącza pełny log gry i python-sc2.
- Wyjątek w kodzie bota wraca do procesu głównego jako `SC2EnvError` z oryginalnym
  tracebackiem.
- `steps.jsonl` w katalogu runu zawiera surowe odczyty co 20. decyzję. To najszybszy
  sposób, żeby zobaczyć, co agent faktycznie widział.
