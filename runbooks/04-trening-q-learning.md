# 04. Trening Q-Learning

**Cel:** wytrenować Model A (tabelaryczny Q-Learning) przeciw wbudowanej SI, podejrzeć
postęp i w razie potrzeby wznowić przerwany trening.

**Wymagania:** zbudowany obraz ([runbook 01](01-srodowisko-docker.md)) i zielona
diagnostyka ([runbook 03](03-pierwsza-gra.md)).

Opis algorytmu, dyskretyzacji stanu i formatu tablicy jest w
[docs/model-a-q-learning.md](../docs/model-a-q-learning.md).

## Kroki

### 1. Uruchom trening

```bash
docker compose run --rm sc2 python -m scbot.train_q --run-name q_baseline --difficulty Easy --episodes 500 --epsilon-decay-episodes 350 --num-envs 12
```

Trening od razu zaczyna grać. Pierwszy wiersz potwierdza ustawienia, kolejne to
ukończone gry:

```text
run: runs/q_baseline | map=Simple64 opponent=Easy | state space: 7200 states | decision interval 1.43 s of game time | 12 game(s) in parallel
ep    1/500 Tie     return=+1.124 eps=1.00 game=20.0min wall=  60s marines=143 states= 147 win1=0%
ep    2/500 Victory return=+2.100 eps=1.00 game=14.2min wall=  42s marines=137 states= 147 win2=50%
```

| Pole | Znaczenie |
|------|-----------|
| `ep 2/500` | Numer gry i docelowa liczba gier w tym runie. |
| `Victory` / `Defeat` / `Tie` | Wynik. `Tie` to limit czasu gry. |
| `return` | Suma nagród w grze. |
| `eps` | Epsilon: udział losowych akcji w tej grze. |
| `game` / `wall` | Czas gry i czas rzeczywisty. |
| `marines` | Wyszkoleni Marines. |
| `states` | Liczba stanów w tablicy Q. |
| `winN` | Odsetek wygranych w ostatnich N grach (okno do 20). |

### 2. Dobierz parametry

| Opcja | Domyślnie | Znaczenie |
|-------|-----------|-----------|
| `--run-name` | `q_baseline` | Nazwa katalogu w `runs/`. Jeden trening to jedna nazwa. |
| `--episodes` | 200 | Docelowa **łączna** liczba gier w runie. |
| `--num-envs` | 1 | Gry prowadzone jednocześnie na jednej tablicy Q. |
| `--difficulty` | `VeryEasy` | Poziom wbudowanej SI. |
| `--alpha` | 0,1 | Współczynnik uczenia. |
| `--gamma` | 0,99 | Dyskonto na interwał decyzyjny (1,43 s gry). |
| `--epsilon-start`, `--epsilon-end` | 1,0 i 0,05 | Eksploracja na początku i po wygaszeniu. |
| `--epsilon-decay-episodes` | 150 | Przez ile gier epsilon liniowo maleje. |
| `--initial-q` | 0 | Wartość początkowa nieodwiedzonych par stan-akcja. |
| `--seed` | 0 | Ziarno agenta. Gra numer `n` dostaje ziarno `seed + n`. |
| `--checkpoint-every` | 25 | Co ile gier zapisać numerowaną kopię tablicy. |
| `--replay-every` | 50 | Co ile gier zapisać powtórkę (0 wyłącza). |
| `--log-steps-every` | 10 | Co która decyzja trafia z odczytami do `steps.jsonl` (0 wyłącza). |
| `--wait-intervals` | 7 | Ile interwałów trwa czekanie po `NO_OP` ([docs/srodowisko.md](../docs/srodowisko.md#punkty-decyzyjne)). |

Opcje środowiska (`--map`, `--max-game-minutes`, `--game-step`, `--decision-interval`)
są takie same jak w `scbot.play`. Pełna lista: `python -m scbot.train_q --help`.

**Ile gier naraz.** Jedna gra zajmuje około 1,5 rdzenia i 0,5–0,8 GB pamięci. Na maszynie
z 24 wątkami i 16 GB dla Dockera 12 gier naraz dawało około 11 ukończonych gier na
minutę. Zacznij od liczby rdzeni fizycznych podzielonej przez 1,5.

### 3. Podglądaj postęp

W drugim terminalu:

```bash
docker compose up tensorboard
```

Otwórz <http://localhost:6006>. Najważniejsze wykresy:

| Wykres | Co pokazuje |
|--------|-------------|
| `episode/win` | 1 dla wygranej, 0 w pozostałych przypadkach. Włącz wygładzanie. |
| `episode/return` | Suma nagród w grze. |
| `reward/*` | Rozbicie nagrody na składniki. |
| `action_share/*` | Udział każdej akcji w decyzjach. |
| `agent/epsilon`, `agent/q_states` | Eksploracja i rozmiar tablicy. |
| `game/*` | Marines, SCV, koszary, wartość zniszczeń i strat. |

TensorBoard zatrzymasz przez Ctrl+C, a kontener usuniesz komendą `docker compose down`.

### 4. Przerwij i wznów

Ctrl+C przerywa trening. Tablica jest zapisywana po każdej ukończonej grze i dodatkowo
w chwili przerwania. Wznowienie:

```bash
docker compose run --rm sc2 python -m scbot.train_q --run-name q_baseline --resume --episodes 500 --num-envs 12 --difficulty Easy
```

- `--episodes` to nadal docelowa łączna liczba gier. Żeby dograć kolejne 300 gier po
  ukończonych 500, podaj `--episodes 800`.
- Hiperparametry agenta (`--alpha`, `--gamma`, epsilon) są wczytywane z zapisanej tablicy.
  Podane przy `--resume` są ignorowane.
- Opcje środowiska (`--difficulty`, `--map`, `--num-envs`, `--wait-intervals`) trzeba podać
  ponownie. Nie są zapisywane w tablicy.

## Co powstaje

Wszystko trafia do `runs/<run-name>/`:

| Plik | Zawartość |
|------|-----------|
| `qtable.npz` | Aktualna tablica Q. Ten plik podajesz w `--model`. |
| `checkpoints/qtable_ep00025.npz` | Kopie tablicy co 25 gier. |
| `config.json` | Ustawienia środowiska, agenta i dyskretyzacji. |
| `episodes.csv` | Jeden wiersz na grę: wynik, nagrody, akcje, statystyki końcowe. |
| `steps.jsonl` | Surowe odczyty z gry dla co 10. decyzji. |
| `tb/` | Logi TensorBoard. |
| `replays/ep00050.SC2Replay` | Powtórki co 50 gier. |

Przy grach równoległych epizody są numerowane w kolejności startu i w tej kolejności
zapisywane, więc numer w `episodes.csv`, `steps.jsonl`, nazwie powtórki i checkpointu
oznacza tę samą grę.

## Nie edytuj kodu środowiska w trakcie treningu

Kod jest podmontowany do kontenera z dysku. Działający trening ma go już w pamięci, ale
proces gry uruchomiony ponownie po awarii pojedynczej gry wczyta pliki w **bieżącej**
wersji. Zmiana w `src/scbot/env/` w trakcie treningu może więc sprawić, że część gier
rozegra się na innych zasadach niż reszta (zdarzyło się to w treningu v1, patrz
[docs/wyniki.md](../docs/wyniki.md)). Jeśli chcesz pracować nad kodem podczas długiego
treningu, rób to w osobnej kopii repozytorium (`git worktree`).

## Weryfikacja

- Trening kończy się wierszem `done: N episodes finished, ...`.
- `runs/<run-name>/episodes.csv` ma N wierszy z danymi.
- Wytrenowaną tablicę da się ocenić: [runbook 05](05-ewaluacja-i-powtorki.md).

## Czego się spodziewać

Wyniki referencyjnych treningów, razem z czasem trwania, są w
[docs/wyniki.md](../docs/wyniki.md). W początkowej fazie (epsilon bliski 1) agent gra
niemal losowo i odsetek wygranych odpowiada agentowi losowemu. Poprawa pojawia się
dopiero, gdy epsilon wyraźnie spadnie.
