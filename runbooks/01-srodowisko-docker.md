# 01. Środowisko Docker (headless)

**Cel:** uruchomić StarCraft II bez interfejsu graficznego w kontenerze i potwierdzić, że
Python potrafi rozegrać w nim grę.

**Wynik:** obraz `starcraftbot/sc2:4.10` i zielona diagnostyka `scbot.doctor --launch`.

## Wymagania

- Docker Desktop z backendem WSL 2 (Windows) albo Docker Engine z wtyczką Compose (Linux).
- Około 25 GB wolnego miejsca na dysku Dockera: obraz zajmuje 9,7 GB, a pamięć podręczna
  budowania trzyma dodatkowo pobrane archiwum gry (4 GB).
- Internet przy pierwszym budowaniu.

Budowanie obrazu pobiera grę z serwerów Blizzarda i rozpakowuje ją hasłem
`iagreetotheeula`. Oznacza to akceptację licencji
[Blizzard AI and Machine Learning License](https://blzdistsc2-a.akamaihd.net/AI_AND_MACHINE_LEARNING_LICENSE.html).
Każda osoba budująca obraz powinna ją przeczytać.

## Kroki

### 1. Uruchom Dockera i sprawdź, że odpowiada

Włącz Docker Desktop, poczekaj aż ikona przestanie się animować, potem:

```bash
docker info --format "{{.ServerVersion}} CPU={{.NCPU}} RAM={{.MemTotal}}"
```

Oczekiwany wynik to jedna linia z wersją, liczbą rdzeni i pamięcią, np.
`28.5.2 CPU=24 RAM=16643997696`. Błąd o `dockerDesktopLinuxEngine` oznacza, że Docker
Desktop nie jest uruchomiony.

### 2. Zbuduj obraz

```bash
docker compose build sc2
```

Pierwsze budowanie trwało u nas kilkanaście minut, z czego około 9 to pobieranie gry.
Kolejne są szybkie, bo archiwum zostaje w pamięci podręcznej. Budowanie:

1. pobiera `SC2.4.10.zip` i sprawdza jego sumę SHA-256 zapisaną w `docker/Dockerfile`;
2. rozpakowuje grę do `/root/StarCraftII` i dokłada paczki map `Melee` i `Ladder2019Season3`;
3. instaluje zależności Pythona z `uv.lock` do `/opt/venv` (PyTorch w wersji CPU).

Na końcu powinno pojawić się `starcraftbot/sc2:4.10  Built`.

### 3. Uruchom diagnostykę z prawdziwą grą

```bash
docker compose run --rm sc2 python -m scbot.doctor --launch
```

Oczekiwany wynik:

```text
[  ok] python             3.12.12 on Linux
[  ok] burnysc2           7.3.0
[  ok] gymnasium          1.4.0
[  ok] numpy              2.5.4
[  ok] tensorboard        2.21.0
[  ok] torch              2.14.1+cpu, CPU only
[  ok] StarCraft II       /root/StarCraftII (SC2PATH), builds: Base75689
[  ok] map                /root/StarCraftII/maps/Melee/Simple64.SC2Map
[  ok] game launch        observation of length 24, game loop 2848, minerals=50, workers=17

Environment is ready.
```

Ostatni wiersz `game launch` oznacza, że gra wystartowała, bot wykonał 20 decyzji
i odczytał stan gry. Liczby w tym wierszu będą się nieco różnić między uruchomieniami.
Całość trwa kilkanaście sekund.

## Kiedy przebudować obraz

| Zmiana | Przebudowa |
|--------|------------|
| Pliki `.py`, testy, dokumentacja | Nie. Kod jest podmontowany z dysku. |
| `pyproject.toml` lub `uv.lock` | Tak: `docker compose build sc2` (kilkadziesiąt sekund). |
| `docker/Dockerfile`, `docker/install_sc2.sh` | Tak. Gra rozpakuje się ponownie z pamięci podręcznej. |

## Zasoby

Zmierzone przy 12 grach jednocześnie: około 18 rdzeni procesora i 6,2 GB pamięci, czyli
mniej więcej 1,5 rdzenia i 0,5 GB na jedną grę. Docker Desktop domyślnie dostaje połowę
pamięci komputera. Limit zmienisz w pliku `%UserProfile%\.wslconfig`.

## Sprzątanie

```bash
docker compose down
```

Usuwa kontenery i sieć projektu (np. działający TensorBoard). Obraz zostaje.

```bash
docker image rm starcraftbot/sc2:4.10
```

Usuwa obraz (9,7 GB).

```bash
docker builder prune
```

Usuwa pamięć podręczną budowania, w tym pobrane archiwum gry. Następne budowanie pobierze
je ponownie.

## Uwagi

- Kontener działa jako `root`. Na Windows nie ma to znaczenia. Na Linuksie pliki zapisane
  do `runs/` i `replays/` będą należały do roota.
- Wersja linuksowa gry to 4.10 (ostatnia wydana przez Blizzarda). Klient Windows jest
  nowszy, więc balans jednostek może się różnić. Trenuj i oceniaj modele na jednej
  platformie.
