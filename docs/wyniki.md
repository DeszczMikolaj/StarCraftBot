# Wyniki i pomiary

Stan na 13 listopada 2026. Wszystko zmierzone w kontenerze z linuksowym StarCraft II 4.10,
na mapie `Simple64`, przeciw wbudowanej SI grającej Terranami. Maszyna: i7-13700F
(24 wątki), 32 GB RAM, z czego 16 GB dla Dockera.

Surowe dane leżą w `runs/` (poza Gitem). Każdą tabelę da się odtworzyć komendami
z [runbooka 04](../runbooks/04-trening-q-learning.md) i [05](../runbooks/05-ewaluacja-i-powtorki.md).

## Agenci odniesienia (bez uczenia)

Po 24 gry, bieżące zasady środowiska. Agent skryptowy to ręcznie napisana kolejność
budowy, agent losowy wybiera równomiernie spośród dostępnych akcji.

| Agent | Przeciwnik | W / P / R | Wygrane (95% CI) | Śr. czas gry | Śr. wartość zniszczeń / strat |
|-------|------------|-----------|------------------|--------------|-------------------------------|
| skryptowy | VeryEasy | 24 / 0 / 0 | 100% (86–100%) | 5,0 min | 2734 / 58 |
| skryptowy | Easy | 24 / 0 / 0 | 100% (86–100%) | 5,3 min | 3354 / 235 |
| skryptowy | Medium | 14 / 10 / 0 | 58% (39–76%) | 9,3 min | 3970 / 4742 |
| losowy | VeryEasy | 24 / 0 / 0 | 100% (86–100%) | 10,5 min | 5846 / 533 |
| losowy | Easy | 8 / 15 / 1 | 33% (18–53%) | 16,2 min | 4904 / 10288 |
| losowy | Medium | 1 / 23 / 0 | 4% (1–20%) | 12,1 min | 1143 / 9531 |

Co z tego wynika:

- **Zestaw akcji makro wystarcza na Easy.** Agent skryptowy wygrywa wszystkie gry w około
  5 minut. Jest to górne odniesienie dla modeli uczących się na tych samych akcjach.
- **VeryEasy nie nadaje się do mierzenia postępu.** Wygrywa z nim nawet agent losowy.
- **Easy jest dobrym przeciwnikiem treningowym.** Między agentem losowym (33%)
  a skryptowym (100%) jest dużo miejsca na poprawę.
- **Medium jest trudny już dla agenta skryptowego.** Sama produkcja Marines i atak grupą
  przestają wystarczać.

Przy 24 grach przedziały ufności są szerokie. Do porównań modeli w turnieju zakładamy
50–100 gier na parę.

## Model A, trening v1: decyzja co interwał

Pierwsza wersja środowiska pytała agenta o akcję co każdy interwał (1,43 s gry), także
wtedy, gdy jedyną opcją było `NO_OP`. Kod tej wersji to commit `8ab603f`.

Ustawienia: 500 gier przeciw Easy, 12 gier naraz, α = 0,1, γ = 0,99, ε od 1,0 do 0,05
przez 350 gier, wartości początkowe 0.

| Gry | W | P | R | Wygrane | Śr. nagroda | Śr. czas gry | Decyzji na grę | Udział `NO_OP` | Marines na grę | ε na końcu bloku |
|-----|---|---|---|---------|-------------|--------------|----------------|----------------|----------------|------------------|
| 1–50 | 15 | 14 | 21 | 30% | +0,886 | 17,7 min | 744 | 74% | 132 | 0,87 |
| 51–100 | 11 | 16 | 23 | 22% | +0,712 | 18,1 min | 761 | 74% | 133 | 0,73 |
| 101–150 | 14 | 19 | 17 | 28% | +0,638 | 17,7 min | 746 | 74% | 132 | 0,60 |
| 151–200 | 17 | 17 | 16 | 34% | +0,759 | 17,7 min | 744 | 74% | 136 | 0,46 |
| 201–250 | 30 | 12 | 8 | 60% | +1,234 | 16,4 min | 691 | 73% | 131 | 0,32 |
| 251–300 | 27 | 19 | 4 | 54% | +0,798 | 16,1 min | 675 | 70% | 123 | 0,19 |
| 301–350 | 23 | 25 | 2 | 46% | +0,270 | 15,2 min | 641 | 68% | 97 | 0,05 |
| 351–400 | 21 | 27 | 2 | 42% | +0,027 | 13,4 min | 534 | 68% | 71 | 0,05 |
| 401–450 | 15 | 35 | 0 | 30% | −0,326 | 15,3 min | 612 | 68% | 79 | 0,05 |
| 451–500 | 18 | 31 | 1 | 36% | −0,118 | 14,3 min | 572 | 70% | 73 | 0,05 |

Koszt: 48 minut czasu rzeczywistego, 8095 minut czasu gry (około 135 godzin),
336 020 decyzji i tyle samo aktualizacji tablicy, 932 odwiedzone stany z 7200.

**Zastrzeżenie do danych.** Gra numer 364 padła przy starcie (błąd połączenia z grą)
i została automatycznie powtórzona. Nowy proces gry wczytał jednak kod środowiska, który
był w tym czasie edytowany, więc 13 gier między numerami 364 a 499 rozegrało się już na
nowych zasadach punktów decyzyjnych. Widać je w `episodes.csv` po kilkakrotnie mniejszej
liczbie decyzji na minutę gry. Tabela powyżej obejmuje wszystkie gry. Bez tych 13 gier
ostatnie 150 gier daje 51 wygranych, 83 przegrane i 3 remisy na 137 (37%), a z nimi
54 / 93 / 3 na 150 (36%). Wniosek jest w obu wariantach ten sam.

### Co się stało

Agent poprawiał się, dopóki część akcji była losowa: przy ε między 0,3 a 0,45 wygrywał
60% gier, dwa razy częściej niż na początku. Gdy eksploracja zeszła do 5%, wynik spadł
do 37% w ostatnich 150 grach, czyli do poziomu agenta losowego. Jednocześnie liczba
wyszkolonych Marines na grę spadła ze 132 do około 75.
Agent nie nauczył się złej strategii ataku. Nauczył się **czekać zamiast produkować**.

Przyczyna jest w konstrukcji zadania, nie w błędzie kodu. `NO_OP` na jeden interwał
prowadzi do prawie tego samego stanu, w którym można wykonać tę samą akcję chwilę
później. Jego wartość to wartość najlepszej akcji pomnożona przez γ, czyli mniejsza
o 1%. Szum estymacji przy α = 0,1 jest większy niż ta różnica. Po około 100 grach
`NO_OP` było najlepszą akcją w 205 z 391 odwiedzonych stanów, a wartości akcji w często
odwiedzanych stanach różniły się o 1–2% (np. 0,4008 dla `NO_OP` wobec 0,3922 dla
`TRAIN_MARINE`). Dopóki eksploracja jest duża, losowe akcje i tak utrzymują produkcję.
Agent zachłanny trzyma się `NO_OP` wszędzie tam, gdzie szum akurat przechylił szalę.

Dodatkowo 51% decyzji miało dostępne wyłącznie `NO_OP`, więc połowa aktualizacji tablicy
nie niosła żadnego wyboru.

### Wniosek dla środowiska

Zmieniliśmy sposób wyznaczania punktów decyzyjnych
([srodowisko.md](srodowisko.md#punkty-decyzyjne)): agent nie jest pytany, gdy nie ma
wyboru, `NO_OP` oznacza czekanie do 10 sekund, a dyskonto zależy od czasu, który
faktycznie upłynął. Czekanie przy dostępnej akcji kosztuje wtedy około 6% wartości
zamiast 1%.

### Ocena zachłanna tablicy v1

30 gier bez eksploracji i bez uczenia, przeciw Easy, na zasadach odpowiadających v1
(`--wait-intervals 1`): 16 wygranych, 12 przegranych, 2 remisy, czyli 53% (95% CI
36–70%). Średni czas gry 14,6 min, średnia wartość zniszczeń 5283 wobec strat 9028.

Punktem odniesienia dla tych zasad jest początek treningu v1, gdy akcje były niemal
losowe: 40 wygranych w pierwszych 150 grach (27%). Tablica v1 gra więc lepiej niż agent
losowy, ale przedział ufności przy 30 grach jest szeroki, a wynik w końcówce treningu
(37% przy ε = 0,05) był niższy niż w ocenie zachłannej.

## Model A, trening v2: punkty decyzyjne sterowane zdarzeniami (przerwany)

Te same ustawienia co v1, nowe zasady punktów decyzyjnych. Trening przerwaliśmy po 99
grach (11 minut), bo wynik systematycznie się pogarszał.

| Gry | W | P | R | Wygrane | Śr. nagroda | Decyzji na grę | Marines na grę | `EXPAND` na grę | `BUILD_BARRACKS` na grę | ε na końcu bloku |
|-----|---|---|---|---------|-------------|----------------|----------------|-----------------|-------------------------|------------------|
| 1–20 | 14 | 3 | 3 | 70% | +1,409 | 224 | 129 | 21,5 | 10,3 | 0,95 |
| 21–40 | 10 | 7 | 3 | 50% | +0,674 | 255 | 116 | 30,8 | 15,9 | 0,89 |
| 41–60 | 8 | 11 | 1 | 40% | +0,275 | 257 | 110 | 33,7 | 17,9 | 0,84 |
| 61–80 | 5 | 14 | 1 | 25% | −0,308 | 261 | 103 | 34,9 | 21,1 | 0,79 |
| 81–99 | 6 | 12 | 1 | 32% | −0,116 | 252 | 103 | 30,7 | 19,4 | 0,73 |

### Co się stało

Liczba decyzji na grę spadła z około 740 do 240, a udział `NO_OP` z 74% do 37%, czyli
zmiana punktów decyzyjnych zadziałała zgodnie z planem. Ujawniła jednak inną wadę
środowiska. Już przy niewielkim udziale akcji zachłannych (ε od 0,95 do 0,79) agent
coraz częściej wybierał `EXPAND` i `BUILD_BARRACKS`: odpowiednio 35 i 21 razy na grę,
przy limicie trzech baz i sześciu koszar. Liczba wyszkolonych Marines spadała, a z nią
odsetek wygranych.

**Pierwsza diagnoza była błędna.** Założyliśmy, że rozkazy przepadają, bo agent wydaje
minerały przed dojściem SCV, i dodaliśmy rezerwację minerałów. Pomiar po tej zmianie
pokazał, że `EXPAND` nadal pada średnio 34 razy na grę agenta losowego.

**Właściwa przyczyna:** maska oferuje `EXPAND`, którego nie da się wykonać. Trzecią
„wolną" lokalizacją na `Simple64` jest ekspansja przeciwnika i budowa jest tam
odrzucana. Odrzucona akcja kosztuje jeden interwał (1,43 s), podczas gdy `NO_OP` kosztuje
do siedmiu, więc w tablicy wygląda prawie tak dobrze jak najlepsza akcja. Agent zachłanny
wybiera ją coraz częściej i traci decyzje, które mogły pójść na produkcję. Wzrost liczby
`BUILD_BARRACKS` to głównie odbudowa koszar w przegrywanych grach, czyli skutek, a nie
przyczyna.

### Wniosek dla środowiska

Do naprawy pozostaje maska `EXPAND`
([srodowisko.md](srodowisko.md#znana-wada-expand-oferowane-gdy-nie-da-się-go-wykonać)).
Ta wada działała we wszystkich trzech treningach, więc żaden z nich nie pokazuje, jak
Q-Learning radzi sobie na poprawnym środowisku.

## Agenci odniesienia po dodaniu rezerwacji minerałów

| Agent | Przeciwnik | W / P / R | Wygrane (95% CI) |
|-------|------------|-----------|------------------|
| skryptowy | VeryEasy | 24 / 0 / 0 | 100% (86–100%) |
| skryptowy | Easy | 24 / 0 / 0 | 100% (86–100%) |
| skryptowy | Medium | 17 / 7 / 0 | 71% (51–85%) |
| losowy | VeryEasy | 24 / 0 / 0 | 100% (86–100%) |
| losowy | Easy | 16 / 30 / 2 | 33% (22–48%) |
| losowy | Medium | 0 / 24 / 0 | 0% (0–14%) |

## Model A, trening v3: rezerwacja minerałów i optymistyczne wartości początkowe

Trening (500 gier, `--initial-q 0.5`) był w toku w chwili zapisu tego dokumentu i nie
został jeszcze oceniony. Po 264 grach odsetek wygranych w blokach po 50 gier wynosił
44%, 52%, 60%, 42% i 44%, bez wyraźnego trendu, a liczba odrzuconych akcji rosła
z 25 do 46 na grę. Dane są w `runs/q_easy_v3/`; streszczenie pokaże
`uv run python -m scbot.report runs/q_easy_v3`.

## Wydajność

| Pomiar | Wartość |
|--------|---------|
| Jedna gra, 5 minut czasu gry, maszyna bez obciążenia | 10,8 s łącznie ze startem gry |
| Trening v1, 12 gier naraz | 10,4 ukończonej gry na minutę, czyli około 169 minut gry na minutę czasu rzeczywistego |
| Obciążenie przy 12 grach naraz | 12–18 rdzeni, 6–9,5 GB pamięci |
| Testy jednostkowe | kilka sekund |
| Testy integracyjne (7 testów z prawdziwą grą) | 40–80 s zależnie od obciążenia |
| Pierwsze budowanie obrazu | kilkanaście minut, obraz 9,7 GB |

Model A nie używa GPU. Cały koszt uczenia to symulacja gry na procesorze.
