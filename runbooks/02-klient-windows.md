# 02. Klient Windows

**Cel:** uruchamiać te same skrypty na zwykłym kliencie gry w Windows, żeby oglądać bota
na żywo.

> **Stan weryfikacji:** kroki 1–6 zostały przećwiczone 14 listopada 2026 na świeżej
> instalacji gry (wersja 5.0.17, katalog `C:\StarCraft II`, Windows 10). Nie sprawdziliśmy
> tylko oglądania powtórek w kliencie; jest to zaznaczone w sekcji
> [Powtórki](#powtórki).

Klient Windows zawsze otwiera okno gry, więc nie zastępuje środowiska headless z
[runbooka 01](01-srodowisko-docker.md). Służy do podglądu.

## Wymagania

- Konto Battle.net i około 26 GB miejsca na grę.
- [uv](https://docs.astral.sh/uv/) do zarządzania Pythonem.
- Zbudowany obraz Dockera, bo z niego kopiujemy mapy (krok 3).

## Kroki

### 1. Zainstaluj grę

Zainstaluj StarCraft II przez aplikację Battle.net (wersja darmowa wystarcza) i zapamiętaj
katalog instalacji. Gry nie trzeba uruchamiać ręcznie: pierwszy start wykona krok 5.

### 2. Przygotuj środowisko Pythona

```bash
uv sync
```

Tworzy `.venv` z Pythonem 3.12 i zależnościami z `uv.lock`, w tym PyTorch z obsługą CUDA
(kilka GB przy pierwszym pobraniu).

### 3. Dodaj mapy

Projekt gra na mapie `Simple64` z paczki `Melee`, której nie ma w standardowej instalacji.
Skopiuj ją z obrazu Dockera:

```bash
docker create --name scbot-maps starcraftbot/sc2:4.10
```

```bash
docker cp scbot-maps:/root/StarCraftII/Maps/Melee ./Melee
```

```bash
docker rm scbot-maps
```

Przenieś powstały katalog `Melee` do `<katalog gry>\Maps\` (świeża instalacja nie ma
katalogu `Maps`, więc go utwórz). Docelowo plik ma leżeć pod
`<katalog gry>\Maps\Melee\Simple64.SC2Map`. Dla gry w `C:\StarCraft II` nie były do tego
potrzebne uprawnienia administratora; dla instalacji w `Program Files` Windows o nie
poprosi.

### 4. Sprawdź środowisko

```bash
uv run python -m scbot.doctor
```

python-sc2 szuka gry w `C:\Program Files (x86)\StarCraft II`. Jeśli zainstalowałeś ją
gdzie indziej i jeszcze ani razu nie była uruchomiona, diagnostyka zgłosi:

```text
[FAIL] StarCraft II       not found at C:\Program Files (x86)\StarCraft II (default location). Install the game or set SC2PATH.
```

Wskaż wtedy katalog zmienną środowiskową na czas tej sesji terminala i powtórz komendę.
W PowerShell:

```powershell
$env:SC2PATH = "C:\StarCraft II"
```

W Git Bash:

```bash
export SC2PATH='C:\StarCraft II'
```

Oczekiwany wynik:

```text
[  ok] python             3.12.13 on Windows
[  ok] burnysc2           7.3.0
[  ok] gymnasium          1.4.0
[  ok] numpy              2.5.4
[  ok] tensorboard        2.21.0
[  ok] torch              2.14.1+cu126, CUDA available (NVIDIA GeForce RTX 3090)
[  ok] StarCraft II       C:\StarCraft II (SC2PATH), builds: Base98310
[  ok] map                C:\StarCraft II\maps\Melee\Simple64.SC2Map

Environment is ready.
```

Nawias w wierszu `StarCraft II` mówi, skąd wzięła się ścieżka: `default location`,
`SC2PATH` albo `ExecuteInfo.txt`. Zmienna `SC2PATH` jest potrzebna tylko do pierwszego
startu. Uruchomiona gra zapisuje swoje położenie w `Dokumenty\StarCraft II\ExecuteInfo.txt`,
python-sc2 odczytuje je stamtąd, a w nawiasie pojawia się `ExecuteInfo.txt`.

### 5. Pierwszy start gry

```bash
uv run python -m scbot.doctor --launch
```

Na świeżej instalacji gra pokazuje najpierw małe okno „Preparing game data" z paskiem
postępu („Downloading … / 3,578 MB"). Dopóki przygotowuje dane, nie przyjmuje połączeń,
więc komenda po 4 minutach kończy się wierszem:

```text
[FAIL] game launch        the game did not answer within 240 s. If the game shows a 'Preparing game data' window, it is still downloading data: run this command again (the download resumes) until the game starts.
```

To nie jest błąd konfiguracji. Uruchom komendę ponownie: gra wznawia pobieranie od
miejsca, w którym została przerwana. U nas trwało to łącznie około 10 minut, a katalog gry
urósł z 25,0 do 25,8 GB. Zamiast powtarzać komendę można zapewne raz uruchomić grę
z aplikacji Battle.net i poczekać na menu główne; tej drogi nie sprawdzaliśmy.

Gdy dane są gotowe, komenda trwa około pół minuty i kończy się tak:

```text
[  ok] game launch        observation of length 24, game loop 3168, minerals=125, workers=18

Environment is ready.
```

### 6. Zagraj z podglądem

```bash
uv run python -m scbot.play --agent scripted --difficulty VeryEasy --realtime
```

Otwiera się okno gry (1024×768), a bot gra w tempie człowieka: gra trwająca 5,3 minuty
zajęła u nas 336 s. Odczyty w terminalu wyglądają tak samo jak w
[runbooku 03](03-pierwsza-gra.md). Bez `--realtime` gra biegnie tak szybko, jak pozwala
komputer (u nas 17,8 s na grę trwającą 4,9 minuty), a okno też się otwiera.

Tak samo obejrzysz tablicę Q wytrenowaną w Dockerze ([runbook 04](04-trening-q-learning.md)):

```bash
uv run python -m scbot.play --agent q --model runs/q_baseline/qtable.npz --difficulty Easy --realtime
```

Tablica z treningu v5 wygrała u nas taką grę w 6,3 minuty (398 s zegarowych).

## Weryfikacja

- `doctor --launch` kończy się wierszem `Environment is ready.`
- `play` kończy się wierszem `result:` z wartością `Victory`, `Defeat` albo `Tie`.
- Testy integracyjne przechodzą także na kliencie Windows (u nas 7 testów w 78 s; w ich
  trakcie otwierają się okna gry):

```bash
uv run pytest -m sc2
```

## Powtórki

- Opcja `--replay` działa na Windows tak samo jak w kontenerze. Plik powstaje w wersji
  klienta Windows.
- **Nie sprawdziliśmy oglądania powtórek w kliencie.** Pliki `.SC2Replay` powinny otwierać
  się dwuklikiem. Powtórki zapisane przez kontener (np. `runs/<nazwa>/replays/`) pochodzą
  z wersji 4.10, więc klient może najpierw pobrać dane tej wersji.
- Sprawdzonym sposobem obejrzenia wytrenowanego agenta jest gra na żywo z krokiem 6.

## Uwagi

- Klient Windows to gra w wersji 5.0.17, a kontener w wersji 4.10. Tablica Q wytrenowana
  w Dockerze działa na kliencie Windows bez zmian ([wyniki](../docs/wyniki.md#kontrola-na-kliencie-windows)),
  ale nie mieszaj platform w obrębie jednego eksperymentu: trenuj i oceniaj w Dockerze.
- Równoległe gry (`--num-envs`) działają także na Windows; każda gra to osobny proces
  klienta z własnym oknem. Sprawdzone dla dwóch gier naraz.
