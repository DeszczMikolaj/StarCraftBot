# Model A: tabelaryczny Q-Learning

Punkt odniesienia dla modeli z sieciami neuronowymi. Nie ma tu sieci: wartości akcji są
zapisane w tablicy, a ciągła obserwacja jest najpierw sprowadzana do niewielkiej liczby
dyskretnych stanów. Kod: `src/scbot/agents/qlearning.py`.

## Algorytm

Po każdej decyzji agent dostaje przejście (stan `s`, akcja `a`, nagroda `r`, następny
stan `s'`) i poprawia jedną komórkę tablicy:

```text
Q(s, a) ← Q(s, a) + α · ( r + γ^Δt · max_a' Q(s', a') − Q(s, a) )
```

- Maksimum liczone jest tylko po akcjach **dostępnych** w `s'` (maska akcji).
- `Δt` to czas między decyzjami w interwałach decyzyjnych (`intervals_elapsed`). Kroki
  środowiska mają różną długość, więc dyskonto zależy od czasu gry, a nie od liczby kroków.
- Gdy gra kończy się wygraną lub przegraną, cel to samo `r`. Gdy gra została ucięta
  limitem czasu, cel nadal zawiera wartość następnego stanu.
- Stan, którego jeszcze nie ma w tablicy, ma wartość początkową `initial_q` (domyślnie 0).

Wybór akcji jest ε-zachłanny: z prawdopodobieństwem ε losowa akcja spośród dostępnych,
w przeciwnym razie dostępna akcja o najwyższym Q. Remisy i stany nieznane rozstrzyga
losowanie. Epsilon maleje liniowo z liczbą ukończonych gier.

## Dyskretyzacja stanu

Z 24 cech obserwacji tablica używa ośmiu. Każda jest dzielona progami na koszyki; stan
to krotka numerów koszyków (`DEFAULT_BINS`).

| Cecha | Progi | Koszyki | Uzasadnienie progów |
|-------|-------|---------|---------------------|
| `minerals` | 50, 100, 150, 400 | 5 | Koszt SCV i Marine, magazynu, koszar, Command Center |
| `supply_left` | 2, 6 | 3 | Brak miejsca, mało, zapas |
| `workers` | 14, 20 | 3 | Start, nasycenie minerałów, limit na bazę |
| `barracks` | 1, 3, 5 | 4 | Brak, 1–2, 3–4, 5 i więcej |
| `marines` | 1, 8, 16, 30 | 5 | Brak armii do dużej armii |
| `army_attacking` | 0,5 | 2 | Obrona albo atak |
| `enemy_near_base` | 1 | 2 | Czy baza jest atakowana |
| `townhalls` | 2 | 2 | Jedna baza albo więcej |

Razem 5 · 3 · 3 · 4 · 5 · 2 · 2 · 2 = **7200 stanów** po 8 akcji. W praktyce odwiedzana
jest niewielka część: po 500 grach treningowych w tablicy były 932 stany.

Wartość dokładnie równa progowi trafia do wyższego koszyka (50 minerałów to już koszyk
„stać na SCV"). Obserwacja jest typu `float32`, więc przed porównaniem z progiem wartości
są zaokrąglane. Bez tego jeden Marine, zapisany jako 0,01 w `float32` (czyli
0,0099999998), trafiałby do koszyka „brak armii".

Tablica jest słownikiem `stan → 8 wartości`. Trzyma tylko odwiedzone stany, więc
zwiększenie liczby koszyków nie zajmuje pamięci z góry, ale wydłuża uczenie.

### Własna dyskretyzacja

```python
from scbot.agents.qlearning import BinSpec, StateDiscretizer, TabularQAgent

discretizer = StateDiscretizer(
    [
        BinSpec("minerals", (50, 150, 400)),
        BinSpec("marines", (1, 10, 25)),
        BinSpec("army_attacking", (0.5,)),
    ]
)
agent = TabularQAgent(discretizer=discretizer)
```

Progi podaje się w surowych jednostkach gry. Nazwy cech pochodzą z tabeli w
[srodowisko.md](srodowisko.md). Dyskretyzacja jest zapisywana razem z tablicą, więc
wczytana tablica zawsze używa progów, z którymi powstała. Skrypt `train_q` używa
dyskretyzacji domyślnej.

## Hiperparametry

| Parametr | Domyślnie | Opcja `train_q` |
|----------|-----------|-----------------|
| α, współczynnik uczenia | 0,1 | `--alpha` |
| γ, dyskonto na interwał (1,43 s gry) | 0,99 | `--gamma` |
| ε początkowe i końcowe | 1,0 i 0,05 | `--epsilon-start`, `--epsilon-end` |
| Liczba gier, przez które ε maleje | 150 | `--epsilon-decay-episodes` |
| Wartość początkowa Q | 0 | `--initial-q` |

Przy γ = 0,99 na interwał nagroda oddalona o 100 interwałów (143 s gry) liczy się
z wagą 0,37. Agent patrzy więc około dwóch i pół minuty do przodu. Nagroda końcowa za
wygraną wpływa wprost tylko na decyzje z ostatnich minut gry, a wcześniejszymi kierują
nagrody pomocnicze.

## Plik tablicy

`qtable.npz` to archiwum NumPy bez `pickle`, więc można je bezpiecznie przekazywać
między osobami.

| Tablica | Kształt | Zawartość |
|---------|---------|-----------|
| `states` | (N, 8) `int16` | Numery koszyków odwiedzonych stanów |
| `q` | (N, 8) `float64` | Wartości Q dla każdej akcji |
| `visits` | (N, 8) `int64` | Liczba aktualizacji każdej pary stan-akcja |
| `meta` | napis JSON | Hiperparametry, progi koszyków, nazwy akcji, liczba gier i aktualizacji |

Przykład odczytu i podglądu najczęściej odwiedzanych stanów:

```python
import numpy as np

from scbot.agents.qlearning import TabularQAgent
from scbot.env.actions import ACTION_NAMES

agent = TabularQAgent.load("runs/q_baseline/qtable.npz")
print(agent.episodes, "gier,", len(agent.q), "stanów")

for state in sorted(agent.q, key=lambda s: -agent.visits[s].sum())[:5]:
    print(agent.discretizer.describe(state))
    for name, value, count in zip(ACTION_NAMES, agent.q[state], agent.visits[state]):
        if count:
            print(f"    {name:<20} Q={value:+.4f}  n={count}")
```

Tablica wytrenowana na innej liście akcji nie zostanie wczytana (`TabularQAgent.load`
zgłosi błąd), bo kolumny odpowiadają akcjom.

## Trening równoległy

Przy `--num-envs N` jedna tablica uczy się z N gier naraz. Aktualizacje wykonuje proces
główny, po jednej, w kolejności napływania odpowiedzi z gier. Reguła uczenia jest ta sama
co przy jednej grze; zmienia się tylko kolejność przejść, bo przeplatają się przejścia
z różnych gier. Epsilon zależy od liczby ukończonych gier, więc N gier startujących razem
gra z tym samym ε.

## Ograniczenia

- **Zlewanie stanów.** Bardzo różne sytuacje trafiają do jednego koszyka (np. każda armia
  powyżej 30 Marines). Tablica nie rozróżni tego, czego nie rozróżniają koszyki.
- **Krótki horyzont.** Wygrana jest daleko od większości decyzji. Zachowanie w pierwszych
  minutach gry kształtują głównie nagrody pomocnicze.
- **Mała przewaga działania nad czekaniem.** Wartości „zrób teraz" i „poczekaj" są
  z natury bliskie. Dlatego `NO_OP` jest w środowisku rozciągnięte w czasie
  ([srodowisko.md](srodowisko.md#punkty-decyzyjne)); pomiary są w [wyniki.md](wyniki.md).
- **Brak uogólniania.** Każdy stan uczy się osobno. To główny powód, dla którego Model B
  zastępuje tablicę siecią.

Wyniki treningów: [wyniki.md](wyniki.md). Jak uruchomić trening:
[runbook 04](../runbooks/04-trening-q-learning.md).
