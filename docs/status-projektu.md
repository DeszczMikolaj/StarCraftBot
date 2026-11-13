# Status projektu względem założeń

Stan na 13 listopada 2026. Odnosi się do dwóch dokumentów zespołu: wstępnych założeń
projektu („Porównanie trzech podejść do uczenia agentów gry StarCraft II") oraz
podsumowania etapu 1 po rozmowie z prowadzącym.

## Lista „To-Do" na kolejne spotkanie (Proof of Concept)

| Wymaganie | Stan | Gdzie |
|-----------|------|-------|
| Repozytorium z `requirements.txt` obejmującym python-sc2 i PyTorch | Zrobione. `pip` poprawnie rozwiązuje plik (`--dry-run` na Windows); pełnej instalacji przez `pip` nie wykonywaliśmy, bo na co dzień używamy `uv`. | `requirements.txt` (generowany z `uv.lock`), `pyproject.toml` |
| Środowisko uruchamia grę bez interfejsu graficznego | Zrobione i sprawdzone | Obraz Dockera z linuksowym SC2 4.10, [runbook 01](../runbooks/01-srodowisko-docker.md) |
| Klasa środowiska: w każdej klatce decyzyjnej zwraca wektor obserwacji i przyjmuje jedną dyskretną akcję makro (Terran vs Terran) | Zrobione i sprawdzone | `SC2MacroEnv`, [srodowisko.md](srodowisko.md) |
| Klasyczny Q-Learning uruchomiony w grze, podejmuje akcje na podstawie tablicy Q | Zrobione i sprawdzone | `agents/qlearning.py`, [model-a-q-learning.md](model-a-q-learning.md) |
| Logowanie poprawnych odczytów z gry | Zrobione i sprawdzone | `scbot.play` (na ekran), `steps.jsonl`, `episodes.csv`, TensorBoard |

„Sprawdzone" oznacza: przechodzi testy integracyjne z prawdziwą grą i zostało uruchomione
ręcznie w kontenerze. Wyniki liczbowe są w [wyniki.md](wyniki.md).

## Podział zadań

| Osoba | Model | Część wspólna | Stan części wspólnej |
|-------|-------|---------------|----------------------|
| Mikołaj | A: tabelaryczny Q-Learning | Integracja API: python-sc2 z grą headless | Gotowa: proces gry, protokół, środowisko Gymnasium, gry równoległe |
| Robert | B: DQN | Przestrzeń obserwacji i nagród | Wersja minimalna: 24 cechy, nagroda końcowa i cztery składniki pomocnicze. Do rozwinięcia. |
| Piotr | C: PPO | Warstwa skryptowa (makro) | Wersja minimalna: 8 akcji, same Marines, prosta obsługa armii. Do rozwinięcia. |

Wersje minimalne powstały po to, żeby baseline dało się uruchomić od początku do końca.
Ich autorzy mogą je zmieniać w granicach opisanych w [rozwijanie.md](rozwijanie.md).

## Założenia upraszczające z dokumentu projektowego

| Założenie | Stan |
|-----------|------|
| 1v1, wszystkie boty grają Terranami | Tak. Przeciwnik wbudowany też jest Terranem. |
| 1–2 mapy o prostym układzie | Jedna: `Simple64`. Druga do wyboru; obraz zawiera 68 map. |
| Decyzje na poziomie makro, wykonanie w warstwie skryptowej wspólnej dla botów | Tak. |
| Obserwacja jako wektor cech liczbowych | Tak, 24 cechy. Uproszczonej minimapy nie ma. |
| python-sc2 (BurnySC2), PyTorch | burnysc2 7.3.0, PyTorch 2.14.1. |
| Logowanie eksperymentów (TensorBoard / W&B) | TensorBoard oraz pliki CSV i JSONL. |

## Odstępstwa i rzeczy do uzgodnienia w zespole

- **Częstość decyzji.** Podsumowanie etapu 1 podaje przykład „co 8–10 kroków gry".
  Środowisko sprawdza grę co 32 pętle (1,43 s), ale pyta agenta tylko wtedy, gdy ma on
  wybór, a `NO_OP` oznacza czekanie do 10 s. Kroki mają więc różną długość. Uzasadnienie
  w [srodowisko.md](srodowisko.md#punkty-decyzyjne). Parametry są konfigurowalne, ale
  wszystkie modele powinny używać tych samych wartości.
- **Minimalny czas rozkazu dla armii** (30 s gry) nie wynika z dokumentów. Został dodany,
  bo bez niego eksploracja była nieskuteczna.
- **Rezerwacja minerałów na zlecone budynki** też nie wynika z dokumentów. Bez niej
  rozkazy budowy mogły przepadać, gdy agent wydał pieniądze przed dojściem SCV.
- **Ograniczenia w masce akcji**, które wynikły z treningów: `EXPAND` jest oferowane
  tylko dla miejsca po naszej stronie mapy, na którym da się budować, a magazyn tylko
  wtedy, gdy zapas populacji jest poniżej 16. Uzasadnienie i pomiary są
  w [wyniki.md](wyniki.md).
- **Wersja gry.** Headless działa na linuksowej wersji 4.10, starszej niż klient Windows.
- **Brak gazu.** Bot nie buduje rafinerii ani jednostek innych niż Marine. Rozszerzenie
  listy akcji jest opisane w [rozwijanie.md](rozwijanie.md).

## Czego jeszcze nie ma

| Element z założeń | Uwagi |
|-------------------|-------|
| Model B (DQN) i Model C (PPO) | Etap 3. Interfejs agenta i środowisko są gotowe. |
| Turniej każdy z każdym | Wymaga pętli bot kontra bot (dwie instancje gry). Nie ma jej. |
| Ranking Elo | Do policzenia z wyników turnieju. |
| Statystyki zachowania i efektywność walki | Częściowo: `episodes.csv` i wyniki `evaluate` zawierają liczbę baz, SCV, koszar, Marines, wartość zniszczeń i strat. |
| Koszt uczenia (GPU-godziny, liczba gier) | Liczba gier i czas są w `episodes.csv`. Model A nie używa GPU. |
| Uzgodniony wspólny budżet obliczeniowy | Do ustalenia. Pomiary wydajności są w [wyniki.md](wyniki.md). |
| Ścieżka z klientem Windows | Opisana w [runbooku 02](../runbooks/02-klient-windows.md), nie sprawdzona. |
