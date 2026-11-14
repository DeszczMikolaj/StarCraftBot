# 03. Pierwsza gra i diagnostyka

**Cel:** rozegrać jedną pełną grę i zobaczyć na ekranie, co środowisko odczytuje z gry
i jakie akcje wykonuje bot. To najszybszy test całego stosu: start gry, obserwacje, akcje
makro, nagrody.

**Wymagania:** zbudowany obraz ([runbook 01](01-srodowisko-docker.md)).

## Kroki

### 1. Sprawdź środowisko

```bash
docker compose run --rm sc2 python -m scbot.doctor
```

Każdy wiersz powinien zaczynać się od `[  ok]`, a na końcu ma być `Environment is ready.`
Z opcją `--launch` diagnostyka dodatkowo startuje grę na 20 decyzji.

### 2. Zagraj agentem skryptowym

```bash
docker compose run --rm sc2 python -m scbot.play --agent scripted --difficulty VeryEasy --replay replays/pierwsza_gra.SC2Replay
```

Agent skryptowy to ręcznie napisana kolejność budowy (SCV, magazyny, koszary, Marines,
atak grupą). Nie uczy się. Służy do sprawdzenia, że zestaw akcji makro pozwala wygrać.

Przykładowy fragment wyjścia:

```text
map=Simple64 opponent=VeryEasy agent=scripted decision interval 32 game loops (1.43 s of game time)
starting StarCraft II...
[00:00] #0     min=50 supply=12 cap=15 scv=12 cc=1 depots=0 rax=0 marines=0 enemy=0 killed=0 lost=0 | action=TRAIN_SCV reward=+0.0010 | can: NO_OP,TRAIN_SCV
[01:01] #10    min=145 supply=16 cap=23 scv=16 cc=1 depots=1 rax=0 marines=0 enemy=0 killed=0 lost=0 | action=NO_OP reward=+0.0000 | can: NO_OP,TRAIN_SCV,BUILD_SUPPLY_DEPOT
[01:51] #20    min=510 supply=17 cap=23 scv=16 cc=1 depots=1 rax=2 marines=0 enemy=0 killed=0 lost=0 | action=BUILD_BARRACKS reward=+0.0000 | can: NO_OP,TRAIN_SCV,BUILD_SUPPLY_DEPOT,BUILD_BARRACKS,TRAIN_MARINE
[03:27] #50    min=150 supply=33 cap=54 scv=16 cc=2 depots=3 rax=4 marines=14 enemy=0 killed=0 lost=0 | action=TRAIN_MARINE reward=+0.0000 | can: NO_OP,BUILD_BARRACKS,TRAIN_MARINE,ATTACK
[04:22] #70    min=90 supply=51 cap=62 scv=24 cc=2 depots=4 rax=4 marines=21 enemy=8 killed=750 lost=100 | action=NO_OP reward=+0.0040 | can: NO_OP,RETREAT
...
result:        Victory
game time:     5.5 min (103 decisions)
wall time:     12.2 s
return:        +1.375
reward parts:  marines_trained=0.074, workers_trained=0.021, value_killed=0.285, value_lost=-0.005, terminal=1
actions:       NO_OP=43, TRAIN_SCV=19, BUILD_SUPPLY_DEPOT=11, BUILD_BARRACKS=5, TRAIN_MARINE=23, EXPAND=1, ATTACK=1, RETREAT=0
not executed:  0
replay:        replays/pierwsza_gra.SC2Replay
```

Czas rzeczywisty zależy od obciążenia maszyny: 12 s na wolnej maszynie, a przy treningu
działającym w tle nawet 30 s.

### 3. Odczytaj wynik

Każdy wiersz to jedna decyzja (drukowana co 10., zmienisz to opcją `--print-every`).
Odstępy czasu między decyzjami są nierówne, bo agent jest pytany tylko wtedy, gdy ma
wybór ([docs/srodowisko.md](../docs/srodowisko.md#punkty-decyzyjne)).

| Fragment | Znaczenie |
|----------|-----------|
| `[03:27]` | Czas gry. |
| `#50` | Numer decyzji w tej grze. |
| `min`, `supply`, `cap`, `scv`, `cc`, `depots`, `rax`, `marines` | Surowe odczyty: minerały, populacja zajęta i limit, SCV, Command Center, magazyny, koszary, Marines. |
| `enemy`, `killed`, `lost` | Widoczne jednostki wroga, wartość zniszczonych jednostek wroga i wartość strat własnych (w surowcach). |
| `action` | Akcja makro wybrana w tej decyzji. |
| `reward` | Nagroda za okres od poprzedniej decyzji. |
| `can:` | Akcje dostępne w tej chwili (maska akcji). |

Podsumowanie na końcu podaje wynik gry, sumę nagród z rozbiciem na składniki, liczbę
użyć każdej akcji oraz `not executed`, czyli ile razy wybrana akcja nie mogła zostać
wykonana.

## Warianty

Agent losowy (wybiera równomiernie spośród dostępnych akcji):

```bash
docker compose run --rm sc2 python -m scbot.play --agent random --difficulty VeryEasy
```

Zapisana tablica Q ([runbook 04](04-trening-q-learning.md)):

```bash
docker compose run --rm sc2 python -m scbot.play --agent q --model runs/q_baseline/qtable.npz --difficulty Easy
```

Pełny log gry i python-sc2 (przydatny, gdy gra nie startuje):

```bash
docker compose run --rm -e SCBOT_DEBUG=1 sc2 python -m scbot.play --agent scripted
```

Lista wszystkich opcji:

```bash
docker compose run --rm sc2 python -m scbot.play --help
```

## Weryfikacja

- Gra kończy się wierszem `result:` z wartością `Victory`, `Defeat` albo `Tie` (limit czasu).
- Odczyty rosną sensownie: minerały i liczba SCV na początku, potem magazyny i koszary.
- Plik powtórki istnieje pod podaną ścieżką.
