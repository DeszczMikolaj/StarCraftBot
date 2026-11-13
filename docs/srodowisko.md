# Środowisko: obserwacje, akcje, nagroda

`SC2MacroEnv` (`src/scbot/env/sc2_env.py`) to środowisko zgodne z interfejsem
[Gymnasium](https://gymnasium.farama.org/). Jeden epizod to jedna gra 1v1 Terran kontra
Terran z wbudowaną SI. Jeden krok to jedna decyzja makro. Środowisko przechodzi
`gymnasium.utils.env_checker.check_env` bez ostrzeżeń.

## Minimalny przykład

Działający plik: [`examples/random_gym_loop.py`](../examples/random_gym_loop.py).

```python
import numpy as np

from scbot.config import EnvConfig
from scbot.env import SC2MacroEnv


def main() -> None:
    rng = np.random.default_rng(0)
    env = SC2MacroEnv(EnvConfig(difficulty="VeryEasy", max_game_minutes=5))
    try:
        obs, info = env.reset(seed=0)
        finished = False
        while not finished:
            action = rng.choice(np.flatnonzero(info["action_mask"]))
            obs, reward, terminated, truncated, info = env.step(action)
            finished = terminated or truncated
        print(info["episode"]["result"])
    finally:
        env.close()


if __name__ == "__main__":  # wymagane: gra działa w osobnym procesie
    main()
```

## Czas

| Pojęcie | Wartość domyślna | Parametr |
|---------|------------------|----------|
| Pętla gry | 1/22,4 s czasu gry (prędkość „Faster") | stała gry |
| Krok bota | 8 pętli gry | `EnvConfig.game_step` |
| Interwał decyzyjny | 4 kroki bota = 32 pętle = 1,43 s czasu gry | `EnvConfig.decision_interval` |
| Czekanie po `NO_OP` | do 7 interwałów = 10 s | `EnvConfig.wait_intervals` |
| Wymuszona decyzja | po 42 interwałach = 60 s bez decyzji | `EnvConfig.max_idle_intervals` |
| Limit gry | 20 minut czasu gry | `EnvConfig.max_game_minutes` |

Między decyzjami warstwa skryptowa działa w każdym kroku bota (co 8 pętli). Gra nie biegnie
w czasie rzeczywistym, chyba że ustawisz `realtime=True`.

### Punkty decyzyjne

Stan gry jest sprawdzany co interwał, ale agent jest pytany o akcję tylko wtedy, gdy ma
co wybierać (`env/decision_points.py`):

1. **Brak pytania, gdy jedyną dostępną akcją jest `NO_OP`.** Gra biegnie dalej, aż coś
   stanie się możliwe.
2. **`NO_OP` znaczy „czekaj".** Następne pytanie pada, gdy stanie się dostępna akcja,
   której nie było w chwili wyboru `NO_OP`, albo po 10 sekundach gry. Opcje, z których
   agent właśnie zrezygnował, nie przerywają czekania.
3. **Po 60 sekundach bez decyzji** pytanie jest wymuszane, nawet jeśli nic nie da się
   zrobić.

Kroki środowiska mają więc różną długość. `info["intervals_elapsed"]` podaje, ile
interwałów minęło od poprzedniej decyzji: co najmniej 1 w zwykłym kroku, 0 w pierwszej
obserwacji, a w ostatnim kroku gry może to być ułamek, bo gra kończy się w dowolnej chwili.
Nagroda za krok obejmuje cały ten okres. Agent powinien dyskontować wartość następnego
stanu przez `gamma ** intervals_elapsed`, a nie przez samo `gamma`.

**Skąd ta konstrukcja.** W pierwszej wersji agent był pytany co interwał. W zapisanych
odczytach z treningu 51% decyzji miało dostępne wyłącznie `NO_OP`, a łącznie 74% decyzji
kończyło się `NO_OP`. Czekanie jednego interwału kosztowało tylko jeden czynnik
dyskontowy, więc wartość `NO_OP` różniła się od wartości najlepszej akcji o około 1%,
czyli mniej niż szum estymacji. Tablica Q nie potrafiła odróżnić „zrób teraz" od
„poczekaj". Szczegóły i liczby są w [wyniki.md](wyniki.md).

Podsumowanie etapu 1 podawało jako przykład decyzję „co 8–10 kroków gry". Interwał
32 pętli i pozostałe wartości zmienia się w `EnvConfig`; interwał także z linii poleceń
(`--game-step`, `--decision-interval`).

## Obserwacja

Wektor `float32` o długości 24. Każda pozycja to surowy odczyt z gry podzielony przez
skalę, obcięty do przedziału [0, 2]. Typowe wartości mieszczą się w [0, 1]. Kolejność
definiuje lista `FEATURES` w `env/observation.py`.

| # | Cecha | Skala | Znaczenie |
|---|-------|-------|-----------|
| 0 | `minerals` | 1000 | Niewydane minerały |
| 1 | `vespene` | 1000 | Niewydany gaz |
| 2 | `supply_used` | 200 | Zajęta populacja |
| 3 | `supply_cap` | 200 | Limit populacji |
| 4 | `supply_left` | 20 | Wolna populacja |
| 5 | `workers` | 50 | Żywe SCV |
| 6 | `idle_workers` | 10 | SCV bez rozkazów |
| 7 | `townhalls` | 4 | Ukończone Command Center |
| 8 | `townhalls_pending` | 2 | Command Center zlecone lub w budowie |
| 9 | `supply_depots` | 20 | Ukończone magazyny |
| 10 | `supply_depots_pending` | 4 | Magazyny zlecone lub w budowie |
| 11 | `barracks` | 8 | Ukończone koszary |
| 12 | `barracks_pending` | 4 | Koszary zlecone lub w budowie |
| 13 | `barracks_idle` | 8 | Ukończone koszary z pustą kolejką |
| 14 | `marines` | 100 | Żywi Marines |
| 15 | `marines_pending` | 16 | Marines w produkcji |
| 16 | `army_supply` | 100 | Populacja zajęta przez armię |
| 17 | `army_attacking` | 1 | 1, gdy armia jest w trybie ataku, 0 w obronie |
| 18 | `enemy_units_visible` | 50 | Widoczne teraz jednostki wroga |
| 19 | `enemy_structures_known` | 20 | Budynki wroga widoczne lub zapamiętane |
| 20 | `enemy_near_base` | 20 | Jednostki wroga w promieniu 15 od naszych budynków |
| 21 | `value_killed` | 5000 | Wartość zniszczonych jednostek i budynków wroga (minerały + gaz) |
| 22 | `value_lost` | 5000 | Wartość własnych strat |
| 23 | `game_minutes` | 20 | Czas gry w minutach |

Odczyty uwzględniają mgłę wojny: o przeciwniku wiemy tylko to, co widzą nasze jednostki.

Surowe wartości tych samych cech są w `info["raw"]` (słownik nazwa → wartość). Funkcje
`to_vector` i `to_raw` przeliczają w obie strony.

Gaz jest w obserwacji, choć obecne akcje go nie używają (bot nie buduje rafinerii), więc
ta pozycja jest zawsze zerem.

## Akcje

Przestrzeń dyskretna, 8 akcji (`MacroAction` w `env/actions.py`). Numer akcji to indeks
kolumny w tablicy Q i wyjścia sieci.

| # | Akcja | Dostępna, gdy | Co robi warstwa skryptowa |
|---|-------|---------------|---------------------------|
| 0 | `NO_OP` | zawsze | Nic. Agent czeka do 10 s gry albo do pojawienia się nowej opcji (patrz „Punkty decyzyjne"). |
| 1 | `TRAIN_SCV` | jest bezczynne Command Center, stać nas (50 minerałów, 1 populacji), SCV żywych i w produkcji jest mniej niż limit | Każde bezczynne Command Center zaczyna szkolić jednego SCV. |
| 2 | `BUILD_SUPPLY_DEPOT` | 100 minerałów, limit populacji poniżej 200, w budowie mniej niż 2 magazyny | Najbliższy wolny SCV buduje magazyn przy głównej bazie. |
| 3 | `BUILD_BARRACKS` | 150 minerałów, jest ukończony magazyn, koszar razem z budowanymi mniej niż 6, w budowie mniej niż 2 | SCV buduje koszary przed główną bazą. |
| 4 | `TRAIN_MARINE` | są bezczynne koszary, stać nas (50 minerałów, 1 populacji) | Każde bezczynne koszary zaczynają szkolić jednego Marine. |
| 5 | `EXPAND` | 400 minerałów, baz razem z budowanymi mniej niż 3, żadna baza nie jest w budowie | SCV stawia Command Center na najbliższej wolnej ekspansji. |
| 6 | `ATTACK` | armia jest w obronie, ma co najmniej jedną jednostkę, minęło 30 s gry od ostatniej zmiany trybu | Armia przechodzi w tryb ataku. |
| 7 | `RETREAT` | armia jest w ataku, minęło 30 s gry od ostatniej zmiany trybu | Armia wraca do bazy i przechodzi w tryb obrony. |

Limit SCV to mniejsza z wartości: 44 łącznie i 20 na każde ukończone Command Center.
Akcje budowy (2, 3, 5) wymagają dodatkowo żywego SCV i przynajmniej jednego Command
Center. Wszystkie progi są w `MacroConfig` (`config.py`).

### Maska akcji

`info["action_mask"]` to tablica 8 wartości logicznych: `True` tam, gdzie akcję da się
teraz wykonać. Wybranie akcji spoza maski nie jest błędem. Akcja nie zostanie wykonana,
a kolejny krok zwróci `info["last_action_executed"] == False`. Metoda
`env.action_masks()` zwraca tę samą maskę w konwencji biblioteki sb3-contrib.

### Co skrypt robi sam, bez decyzji agenta

W każdym kroku bota (`MacroExecutor.housekeeping`):

- **Armia w trybie ataku** idzie na najbliższy znany budynek wroga. Gdy żadnego nie zna,
  idzie na pozycję startową wroga, a gdy ta jest pusta, sprawdza po kolei ekspansje.
- **Armia w trybie obrony** stoi w punkcie zbiórki przed bazą i atakuje jednostki wroga,
  które podejdą na 15 jednostek odległości do naszych budynków.
- **Co 8 kroków bota:** bezczynni SCV wracają do wydobycia, przerwane budowy dostają
  nowego SCV, magazyny są opuszczane, żeby nie blokowały przejścia.

Armia to wszystkie jednostki poza SCV i MULE.

## Nagroda

Nagroda za krok to suma składników naliczonych od poprzedniej decyzji
(`env/reward.py`, wagi w `RewardConfig`):

| Składnik | Waga domyślna | Kiedy |
|----------|---------------|-------|
| `terminal` | +1 wygrana, −1 przegrana, 0 remis | Raz, na końcu gry |
| `marines_trained` | +0,002 za jednostkę | Marine ukończył szkolenie |
| `workers_trained` | +0,001 za jednostkę | SCV ukończył szkolenie |
| `value_killed` | +0,0001 za punkt wartości | Zniszczono jednostkę lub budynek wroga |
| `value_lost` | −0,00005 za punkt wartości | Stracono własną jednostkę lub budynek |

Wartość to koszt jednostki w minerałach i gazie, liczony przez grę. Rozbicie nagrody na
składniki jest w `info["reward_components"]`, a sumy za całą grę w
`info["episode"]["reward_totals"]`.

Skala orientacyjna: w wygranej grze agenta skryptowego z VeryEasy składniki pomocnicze
dały razem około +0,36, a nagroda końcowa +1.

## Koniec epizodu

| Wynik gry | `terminated` | `truncated` | Nagroda końcowa |
|-----------|--------------|-------------|-----------------|
| `Victory` | `True` | `False` | +1 |
| `Defeat` | `True` | `False` | −1 |
| `Tie` (limit czasu) | `False` | `True` | 0 |

Remis traktujemy jako ucięcie epizodu, a nie stan końcowy: Q-Learning nadal dolicza
wartość kolejnego stanu.

Ostatni krok zwraca dodatkowo `info["result"]` i `info["episode"]` z podsumowaniem gry:
wynik, suma nagród, liczba decyzji, czas gry, liczba użyć każdej akcji, liczba akcji
niewykonanych, wynik punktowy gry, zebrane minerały, liczba wyszkolonych Marines i SCV.

## Słownik `info`

| Klucz | Typ | Zawartość |
|-------|-----|-----------|
| `raw` | `dict[str, float]` | Surowe odczyty wszystkich cech |
| `action_mask` | `ndarray[bool]`, 8 | Dostępne akcje |
| `reward_components` | `dict[str, float]` | Składniki nagrody za ostatni krok |
| `last_action_executed` | `bool` | Czy poprzednia akcja została wykonana |
| `game_loop` | `int` | Numer pętli gry |
| `intervals_elapsed` | `float` | Interwały decyzyjne od poprzedniej decyzji |
| `decision` | `int` | Numer decyzji w epizodzie |
| `result`, `episode` | `str`, `dict` | Tylko w ostatnim kroku |

## Konfiguracja

`EnvConfig` (`config.py`) zbiera wszystko, co definiuje środowisko:

| Pole | Domyślnie | Znaczenie |
|------|-----------|-----------|
| `map_name` | `"Simple64"` | Nazwa mapy z katalogu `Maps` gry |
| `difficulty` | `"VeryEasy"` | Poziom wbudowanej SI |
| `game_step` | 8 | Pętle gry na krok bota |
| `decision_interval` | 4 | Kroki bota w jednym interwale decyzyjnym |
| `wait_intervals` | 7 | Ile interwałów trwa czekanie po `NO_OP` |
| `max_idle_intervals` | 42 | Po ilu interwałach bez decyzji pytanie jest wymuszane |
| `max_game_minutes` | 20 | Limit czasu gry |
| `realtime` | `False` | Gra w tempie człowieka (podgląd w kliencie Windows) |
| `start_timeout_s` | 240 | Czas na start gry do pierwszej decyzji |
| `step_timeout_s` | 120 | Czas na odpowiedź gry na jedną akcję |
| `macro` | `MacroConfig()` | Limity i odległości warstwy skryptowej |
| `reward` | `RewardConfig()` | Wagi nagrody |

## Wiele gier naraz

`reset` i `step` to wysłanie żądania i czekanie na odpowiedź. Obie połowy są dostępne
osobno: `reset_async` / `step_async` wysyłają żądanie, `collect` odbiera odpowiedź,
a `connection` można przekazać do `multiprocessing.connection.wait`, żeby dowiedzieć się,
która gra odpowiedziała pierwsza. Tak działa `runner.run_episodes`, z którego korzystają
`train_q` i `evaluate`. W zwykłym użyciu wystarczy `reset` i `step`.

## Mapa

`Simple64` to mała mapa dla dwóch graczy z paczki `Melee`. W 20-minutowych grach
rozegranych na jednej bazie zebrane minerały zatrzymywały się na 10 800, a liczba
wyszkolonych Marines na około 143. Dłuższa gra wymaga więc drugiej bazy (`EXPAND`).
