# Wyniki i pomiary

Stan na 14 listopada 2026. Wszystko zmierzone w kontenerze z linuksowym StarCraft II 4.10,
na mapie `Simple64`, przeciw wbudowanej SI grającej Terranami. Maszyna: i7-13700F
(24 wątki), 32 GB RAM, z czego 16 GB dla Dockera. Jedyny wyjątek to oznaczona
[kontrola na kliencie Windows](#kontrola-na-kliencie-windows).

Surowe dane leżą w `runs/` (poza Gitem). Każdą tabelę da się odtworzyć komendami
z [runbooka 04](../runbooks/04-trening-q-learning.md) i [05](../runbooks/05-ewaluacja-i-powtorki.md).

## W skrócie

Model A (tabelaryczny Q-Learning) był trenowany pięć razy, za każdym razem przeciw Easy
i planowo przez 500 gier. Każdy trening ujawnił wadę środowiska, którą potem
poprawialiśmy, więc kolejne wiersze to kolejne wersje środowiska, a nie ten sam
eksperyment powtórzony pięć razy.

| Trening | Co doszło w środowisku | Agent losowy | Końcówka treningu (ε = 0,05) | Ocena zachłanna tablicy |
|---------|------------------------|--------------|------------------------------|-------------------------|
| v1 | decyzja co 1,43 s | 27% (40/150) | 37% (51/137) | 53% (16/30) |
| v2 | agent pytany tylko, gdy ma wybór | 33% (8/24) | przerwany po 99 grach | nie oceniano |
| v3 | rezerwacja minerałów, optymistyczne wartości początkowe | 33% (16/48) | 42% (84/200) | 60% (18/30) |
| v4 | `EXPAND` tylko tam, gdzie da się budować | 40% (29/72) | 57,5% (115/200) | 23% (11/48) |
| v5 | limit zapasu populacji | 61% (44/72) | 94% (188/200) | 88% (42/48) |

Agent skryptowy wygrywał z Easy 100% gier na każdej wersji środowiska.

Trzy rzeczy, które warto wiedzieć przed czytaniem szczegółów:

- **Na obecnym środowisku Q-Learning wyraźnie się uczy.** Tablica v5 wygrywa z Easy 88%
  gier w ocenie zachłannej i 94% z eksploracją 5%, wobec 61% agenta losowego. Agent
  skryptowy wygrywa 100%.
- **To środowisko zdecydowało o wyniku, nie zmiana algorytmu.** Treningi v3, v4 i v5 mają
  te same hiperparametry. Różnią się tylko tym, jakie akcje oferuje maska.
- **Tablica uczona przeciw Easy słabo przenosi się na Medium**: 27% wygranych, wobec 4%
  agenta losowego i 71% skryptowego.

## Czego nauczyły nas te treningi

1. **Maska akcji musi być uczciwa.** Akcja oferowana, a potem odrzucana, kosztuje tylko
   chwilę czasu gry. Uczący się agent traktuje ją jak tanie „poczekaj" i sięga po nią
   coraz częściej (v3: z 25 do 89 odrzuconych akcji na grę).
2. **Akcja bez widocznego kosztu jest nadużywana.** Magazyn zawsze dało się zbudować,
   a nagroda nie mówi, że jest zbędny. Zamrożona tablica v4 budowała 38 magazynów na grę.
3. **Czekanie musi mieć cenę.** Gdy `NO_OP` trwało 1,43 s, jego wartość różniła się od
   najlepszej akcji o 1%, czyli mniej niż szum. Agent uczył się czekać zamiast produkować.
4. **Im więcej robi warstwa makro, tym silniejszy jest agent losowy.** Po kolejnych
   poprawkach losowe granie wygrywało z Easy 33%, 40% i 61% gier, więc zostaje mniej
   miejsca na pokazanie uczenia. Przeciw Medium agent losowy prawie nie wygrywa,
   a skryptowy wygrywa w 71%, więc do porównań modeli Medium nadaje się lepiej.
5. **Tablicę trzeba oceniać więcej niż jednym sposobem.** Ocena zachłanna jednej
   zapisanej tablicy dała 53% (v1), 60% (v3) i 23% (v4), choć w treningu wyniki były
   zbliżone: przy małych różnicach wartości to, którą akcję tablica wskazuje jako
   najlepszą, zależy od chwili zapisu. Opcja `--explore` w `evaluate` zostawia tablicy
   jej końcową eksplorację; warto też ocenić kilka checkpointów. W v5 wszystkie te
   oceny są zgodne (88–96%).
6. **Nie wolno edytować kodu środowiska w trakcie treningu** (patrz v1).

## Obecne środowisko

### Agenci odniesienia

Agent skryptowy to ręcznie napisana kolejność budowy, agent losowy wybiera równomiernie
spośród dostępnych akcji.

| Agent | Przeciwnik | W / P / R | Wygrane (95% CI) | Śr. czas gry | Śr. wartość zniszczeń / strat |
|-------|------------|-----------|------------------|--------------|-------------------------------|
| skryptowy | VeryEasy | 24 / 0 / 0 | 100% (86–100%) | 5,1 min | 2828 / 75 |
| skryptowy | Easy | 24 / 0 / 0 | 100% (86–100%) | 5,2 min | 3304 / 225 |
| skryptowy | Medium | 17 / 7 / 0 | 71% (51–85%) | 7,9 min | 3786 / 3452 |
| losowy | VeryEasy | 24 / 0 / 0 | 100% (86–100%) | 13,1 min | 7024 / 565 |
| losowy | Easy | 30 / 15 / 3 | 63% (48–75%) | 15,8 min | 8010 / 5643 |
| losowy | Medium | 1 / 22 / 1 | 4% (1–20%) | 12,6 min | 2570 / 9404 |

Agent losowy przeciw Easy ma duży rozrzut między seriami, więc zmierzyliśmy go dwa razy.
Druga seria 24 gier dała 14 wygranych, 5 przegranych i 5 remisów. Łącznie to 44 z 72,
czyli 61% (95% CI 50–72%), i tę wartość przyjmujemy jako odniesienie dla v5.

Co z tego wynika:

- **Zestaw akcji makro wystarcza na Easy.** Agent skryptowy wygrywa wszystkie gry w około
  5 minut. To górne odniesienie dla modeli uczących się na tych samych akcjach.
- **VeryEasy nie nadaje się do mierzenia postępu.** Wygrywa z nim nawet agent losowy.
- **Medium zostawia najwięcej miejsca na poprawę**, ale jest trudny już dla agenta
  skryptowego.

### Trening v5: limit zapasu populacji

Ustawienia jak w v4 (`--initial-q 0.5`). To pierwszy trening na środowisku, w którym
maska nie oferuje ani niewykonalnych ekspansji, ani zbędnych magazynów.

| Gry | W | P | R | Wygrane | Śr. nagroda | Śr. czas gry | Decyzji na grę | Marines na grę | Magazynów na grę | `ATTACK` na grę | Odrzuconych akcji na grę | ε na końcu bloku |
|-----|---|---|---|---------|-------------|--------------|----------------|----------------|------------------|-----------------|--------------------------|------------------|
| 1–50 | 28 | 10 | 12 | 56% | +1,343 | 16,4 min | 172 | 154 | 14,2 | 10,8 | 0,1 | 0,87 |
| 51–100 | 27 | 17 | 6 | 54% | +1,003 | 15,9 min | 169 | 147 | 12,8 | 10,8 | 0,6 | 0,73 |
| 101–150 | 35 | 9 | 6 | 70% | +1,353 | 14,5 min | 157 | 131 | 12,1 | 9,9 | 0,6 | 0,60 |
| 151–200 | 41 | 8 | 1 | 82% | +1,481 | 13,3 min | 146 | 120 | 11,3 | 8,8 | 0,6 | 0,46 |
| 201–250 | 47 | 2 | 1 | 94% | +1,827 | 12,5 min | 135 | 111 | 11,0 | 8,1 | 0,1 | 0,32 |
| 251–300 | 47 | 1 | 2 | 94% | +1,690 | 10,8 min | 123 | 94 | 8,6 | 6,8 | 0,3 | 0,19 |
| 301–350 | 47 | 3 | 0 | 94% | +1,631 | 11,0 min | 117 | 86 | 7,1 | 6,8 | 0,0 | 0,05 |
| 351–400 | 46 | 4 | 0 | 92% | +1,523 | 10,6 min | 121 | 88 | 7,0 | 6,2 | 0,8 | 0,05 |
| 401–450 | 49 | 0 | 1 | 98% | +1,670 | 9,7 min | 108 | 84 | 6,6 | 5,7 | 0,0 | 0,05 |
| 451–500 | 46 | 3 | 1 | 92% | +1,522 | 10,3 min | 118 | 90 | 6,6 | 5,9 | 0,5 | 0,05 |

Koszt: 42 minuty czasu rzeczywistego, 6257 minut czasu gry, 68 201 decyzji,
515 odwiedzonych stanów. Jedna gra (numer 97) padła przy starcie i została automatycznie
powtórzona; kod nie był w tym czasie zmieniany.

**Co widać w treningu.** Odsetek wygranych rósł razem ze spadkiem eksploracji: od 56%
w pierwszym bloku do 92–98% w ostatnich czterech. W ostatnich 200 grach przy ε = 0,05
agent wygrał 188 razy, przegrał 10 i 2 razy zremisował (94%, CI 90–97%),
wobec 61% agenta losowego (44 z 72, CI 50–72%). Gry skróciły się z 16,4 do około 10 minut,
a agent z czasem zlecał mniej magazynów i rzadziej przełączał armię między atakiem
a odwrotem.

**Oceny zapisanej tablicy** (bez uczenia, przeciw Easy, o ile nie podano inaczej):

| Co oceniano | W / P / R | Wygrane (95% CI) |
|-------------|-----------|------------------|
| Tablica końcowa, zachłannie | 42 / 6 / 0 na 48 gier | 88% (75–94%) |
| Tablica końcowa, z eksploracją 5% (`--explore`) | 45 / 3 / 0 na 48 gier | 94% (83–98%) |
| Checkpoint po 400 grach, zachłannie | 23 / 1 / 0 na 24 gry | 96% (80–99%) |
| Checkpoint po 450 grach, zachłannie | 23 / 1 / 0 na 24 gry | 96% (80–99%) |
| Tablica końcowa, zachłannie, **przeciw Medium** | 13 / 35 / 0 na 48 gier | 27% (17–41%) |

W ocenie zachłannej tablica końcowa szkoliła średnio 86 Marines na grę, zlecała
6,3 magazynu i miała 1,0 odrzuconej akcji na grę, a gra trwała średnio 9,8 minuty.
Wszystkie cztery oceny przeciw Easy są ze sobą zgodne, inaczej niż w v4. Przeciw Medium
tablica wygrywa częściej niż agent losowy (4%), ale dużo rzadziej niż skryptowy (71%):
nigdy nie grała z tym przeciwnikiem.

**Czego tablica się nauczyła.** Najczęściej odwiedzane stany mają czytelne preferencje:

| Stan | Najwyżej ceniona akcja | Najniżej ceniona akcja (z wypróbowanych co najmniej 20 razy) |
|------|------------------------|------------------------|
| 30 lub więcej Marines, armia w obronie, baza bezpieczna | `ATTACK` (0,85) | `TRAIN_SCV` (0,69) |
| 30 lub więcej Marines, armia w ataku | `TRAIN_MARINE` (0,91) | `RETREAT` (0,71) |
| 16–30 Marines, armia w ataku | `TRAIN_MARINE` (0,80) | `RETREAT` (0,65) |

Czyli: atakuj dużą armią, w trakcie ataku dalej produkuj i nie wycofuj się. Tabelę
z własnej tablicy wydrukuje kod z [model-a-q-learning.md](model-a-q-learning.md#plik-tablicy).

### Kontrola na kliencie Windows

Jedyny pomiar spoza kontenera. Tablica v5, wytrenowana w kontenerze na grze 4.10, zagrała
10 gier przeciw Easy na kliencie Windows z grą 5.0.17 (ocena zachłanna, dwie gry naraz,
[runbook 02](../runbooks/02-klient-windows.md)):

| Co oceniano | W / P / R | Wygrane (95% CI) | Śr. czas gry | Śr. wartość zniszczeń / strat |
|-------------|-----------|------------------|--------------|-------------------------------|
| Tablica końcowa v5, zachłannie, klient Windows | 8 / 2 / 0 na 10 gier | 80% (49–94%) | 10,1 min | 4610 / 4300 |

Tablica wczytuje się i gra na nowszej wersji bez zmian w kodzie, a wynik nie odbiega od
oceny z kontenera (88%, CI 75–94%). Dziesięć gier to za mało, żeby porównywać platformy:
to kontrola działania, a nie pomiar. Wszystkie wyniki do porównań modeli robimy
w kontenerze.

## Historia: jak doszliśmy do obecnego środowiska

Wspólne ustawienia wszystkich treningów: 500 gier przeciw Easy, 12 gier naraz, α = 0,1,
γ = 0,99, ε od 1,0 do 0,05 przez 350 gier.

### v1: decyzja co interwał

Pierwsza wersja środowiska pytała agenta o akcję co każdy interwał (1,43 s gry), także
wtedy, gdy jedyną opcją było `NO_OP`. Kod tej wersji to commit `8ab603f`. Wartości
początkowe tablicy 0.

| Gry | W | P | R | Wygrane | Śr. nagroda | Decyzji na grę | Udział `NO_OP` | Marines na grę | ε na końcu bloku |
|-----|---|---|---|---------|-------------|----------------|----------------|----------------|------------------|
| 1–50 | 15 | 14 | 21 | 30% | +0,886 | 744 | 74% | 132 | 0,87 |
| 51–100 | 11 | 16 | 23 | 22% | +0,712 | 761 | 74% | 133 | 0,73 |
| 101–150 | 14 | 19 | 17 | 28% | +0,638 | 746 | 74% | 132 | 0,60 |
| 151–200 | 17 | 17 | 16 | 34% | +0,759 | 744 | 74% | 136 | 0,46 |
| 201–250 | 30 | 12 | 8 | 60% | +1,234 | 691 | 73% | 131 | 0,32 |
| 251–300 | 27 | 19 | 4 | 54% | +0,798 | 675 | 70% | 123 | 0,19 |
| 301–350 | 23 | 25 | 2 | 46% | +0,270 | 641 | 68% | 97 | 0,05 |
| 351–400 | 21 | 27 | 2 | 42% | +0,027 | 534 | 68% | 71 | 0,05 |
| 401–450 | 15 | 35 | 0 | 30% | −0,326 | 612 | 68% | 79 | 0,05 |
| 451–500 | 18 | 31 | 1 | 36% | −0,118 | 572 | 70% | 73 | 0,05 |

Koszt: 48 minut czasu rzeczywistego, 8095 minut czasu gry (około 135 godzin),
336 020 decyzji, 932 odwiedzone stany z 7200.

**Zastrzeżenie do danych.** Gra numer 364 padła przy starcie (błąd połączenia z grą)
i została automatycznie powtórzona. Nowy proces gry wczytał jednak kod środowiska, który
był w tym czasie edytowany, więc 13 gier między numerami 364 a 499 rozegrało się już na
zasadach z v2. Widać je w `episodes.csv` po kilkakrotnie mniejszej liczbie decyzji na
minutę gry. Tabela obejmuje wszystkie gry. Bez tych 13 gier ostatnie 150 gier daje
51 wygranych na 137 (37%), a z nimi 54 na 150 (36%).

**Co się stało.** Agent poprawiał się, dopóki część akcji była losowa: przy ε między 0,3
a 0,45 wygrywał 60% gier. Gdy eksploracja zeszła do 5%, wynik spadł do 37%, a liczba
wyszkolonych Marines na grę ze 132 do około 75. Agent nauczył się czekać zamiast
produkować. `NO_OP` na jeden interwał prowadzi do prawie tego samego stanu, więc jego
wartość to wartość najlepszej akcji pomnożona przez γ, czyli mniejsza o 1%. Szum
estymacji przy α = 0,1 jest większy. Po około 100 grach `NO_OP` było najlepszą akcją
w 205 z 391 odwiedzonych stanów. Dodatkowo 51% decyzji miało dostępne wyłącznie `NO_OP`.

**Ocena zachłanna:** 16 wygranych, 12 przegranych, 2 remisy na 30 gier (53%, CI 36–70%).

**Wniosek:** punkty decyzyjne sterowane zdarzeniami
([srodowisko.md](srodowisko.md#punkty-decyzyjne)).

### v2: punkty decyzyjne sterowane zdarzeniami (przerwany)

Agent pytany tylko wtedy, gdy ma wybór, `NO_OP` to czekanie do 10 s, dyskonto zależne od
czasu. Trening przerwaliśmy po 99 grach (11 minut), bo wynik systematycznie spadał.

| Gry | W | P | R | Wygrane | Decyzji na grę | Marines na grę | `EXPAND` na grę | `BUILD_BARRACKS` na grę | ε na końcu bloku |
|-----|---|---|---|---------|----------------|----------------|-----------------|-------------------------|------------------|
| 1–20 | 14 | 3 | 3 | 70% | 224 | 129 | 21,5 | 10,3 | 0,95 |
| 21–40 | 10 | 7 | 3 | 50% | 255 | 116 | 30,8 | 15,9 | 0,89 |
| 41–60 | 8 | 11 | 1 | 40% | 257 | 110 | 33,7 | 17,9 | 0,84 |
| 61–80 | 5 | 14 | 1 | 25% | 261 | 103 | 34,9 | 21,1 | 0,79 |
| 81–99 | 6 | 12 | 1 | 32% | 252 | 103 | 30,7 | 19,4 | 0,73 |

**Co się stało.** Liczba decyzji na grę spadła z około 740 do 240, a udział `NO_OP` z 74%
do 37%, czyli zmiana zadziałała zgodnie z planem. Agent zaczął jednak coraz częściej
wybierać `EXPAND`, do 35 razy na grę przy limicie trzech baz.

**Pierwsza diagnoza była błędna.** Założyliśmy, że rozkazy budowy przepadają, bo agent
wydaje minerały przed dojściem SCV, i dodaliśmy rezerwację minerałów. Pomiar po tej
zmianie pokazał, że `EXPAND` nadal pada średnio 34 razy na grę agenta losowego.

**Właściwa przyczyna:** maska oferowała `EXPAND`, którego nie dało się wykonać. Na
`Simple64` trzecią „wolną" lokalizacją jest ekspansja przeciwnika i budowa jest tam
odrzucana. Odrzucona akcja kosztowała jeden interwał, podczas gdy `NO_OP` do siedmiu.

### v3: rezerwacja minerałów i optymistyczne wartości początkowe

Dodatkowo wartości początkowe tablicy 0,5 zamiast 0 (`--initial-q 0.5`). Przy wartościach
powyżej zera akcje jeszcze niewypróbowane wyglądają lepiej niż wypróbowane, a dzięki
dyskontu zależnemu od czasu czekanie wypada od początku gorzej niż działanie. Wada maski
`EXPAND` nadal działała.

| Gry | W | P | R | Wygrane | Śr. nagroda | Marines na grę | Odrzuconych akcji na grę | ε na końcu bloku |
|-----|---|---|---|---------|-------------|----------------|--------------------------|------------------|
| 1–50 | 22 | 27 | 1 | 44% | +0,315 | 118 | 25 | 0,87 |
| 51–100 | 26 | 18 | 6 | 52% | +0,703 | 122 | 29 | 0,73 |
| 101–150 | 30 | 14 | 6 | 60% | +0,882 | 113 | 32 | 0,60 |
| 151–200 | 21 | 23 | 6 | 42% | +0,287 | 113 | 39 | 0,46 |
| 201–250 | 22 | 26 | 2 | 44% | +0,258 | 113 | 46 | 0,32 |
| 251–300 | 26 | 17 | 7 | 52% | +0,513 | 99 | 51 | 0,19 |
| 301–350 | 24 | 20 | 6 | 48% | +0,365 | 98 | 62 | 0,05 |
| 351–400 | 23 | 19 | 8 | 46% | +0,361 | 101 | 86 | 0,05 |
| 401–450 | 22 | 24 | 4 | 44% | +0,231 | 101 | 81 | 0,05 |
| 451–500 | 15 | 31 | 4 | 30% | −0,256 | 97 | 89 | 0,05 |

Koszt: 63 minuty czasu rzeczywistego (równolegle działały pomiary odniesienia),
7755 minut czasu gry, 137 040 decyzji, 729 odwiedzonych stanów.

**Co widać.** Wynik nie rósł, a liczba odrzuconych akcji rosła przez cały trening,
z 25 do 89 na grę. To niemal wyłącznie niewykonalne `EXPAND`.

**Ocena zachłanna:** 18 wygranych, 10 przegranych, 2 remisy na 30 gier (60%, CI 42–75%).

**Wniosek:** maska oferuje `EXPAND` tylko wtedy, gdy po naszej stronie mapy jest miejsce,
w którym bazę da się postawić
([srodowisko.md](srodowisko.md#gdzie-wolno-się-rozbudować)). U agenta losowego `EXPAND`
spadło z 34 do 2,2 na grę, a odrzucone akcje z 32 do 1,3.

### v4: uczciwa maska `EXPAND`

Ustawienia jak w v3. Pierwszy trening bez awarii gier i bez znanej wady maski.

| Gry | W | P | R | Wygrane | Śr. nagroda | Śr. czas gry | Decyzji na grę | Marines na grę | Odrzuconych akcji na grę | ε na końcu bloku |
|-----|---|---|---|---------|-------------|--------------|----------------|----------------|--------------------------|------------------|
| 1–50 | 17 | 25 | 8 | 34% | +0,278 | 16,6 min | 216 | 125 | 1,2 | 0,87 |
| 51–100 | 26 | 19 | 5 | 52% | +0,846 | 16,9 min | 215 | 140 | 0,8 | 0,73 |
| 101–150 | 21 | 19 | 10 | 42% | +0,582 | 16,4 min | 219 | 123 | 1,7 | 0,60 |
| 151–200 | 31 | 12 | 7 | 62% | +1,106 | 15,3 min | 201 | 117 | 1,5 | 0,46 |
| 201–250 | 28 | 17 | 5 | 56% | +0,784 | 15,4 min | 206 | 114 | 2,8 | 0,32 |
| 251–300 | 25 | 19 | 6 | 50% | +0,529 | 15,2 min | 221 | 109 | 5,6 | 0,19 |
| 301–350 | 26 | 17 | 7 | 52% | +0,649 | 14,4 min | 200 | 104 | 3,9 | 0,05 |
| 351–400 | 29 | 18 | 3 | 58% | +0,687 | 14,2 min | 204 | 99 | 2,8 | 0,05 |
| 401–450 | 34 | 14 | 2 | 68% | +0,939 | 14,0 min | 199 | 97 | 3,7 | 0,05 |
| 451–500 | 26 | 20 | 4 | 52% | +0,470 | 14,4 min | 210 | 90 | 10,9 | 0,05 |

Koszt: 45,5 minuty czasu rzeczywistego, 7645 minut czasu gry, 104 638 decyzji,
727 odwiedzonych stanów.

**Co widać w treningu.** Odsetek wygranych rósł z 34% w pierwszym bloku do 52–68%
w ostatnich czterech. W ostatnich 200 grach przy ε = 0,05 agent wygrał 115 razy (57,5%,
CI 51–64%), wobec 40% agenta losowego (29 z 72, CI 30–52%). Różnica 17 punktów
procentowych jest większa, niż tłumaczyłby sam rozrzut (test dwóch proporcji daje p około
0,01), więc to pierwszy trening, w którym widać uczenie. Przedziały ufności jednak
niemal się stykają, a odniesienie losowe ma duży rozrzut między seriami.

**Ocena zachłanna:** 11 wygranych, 36 przegranych, 1 remis na 48 gier (23%, CI 13–37%).
To dużo gorzej niż w treningu. Zamrożona tablica zlecała średnio 38 magazynów i 26 budów
koszar na grę, a szkoliła 57 Marines; odrzuconych akcji było 14 na grę. Magazyn dało się
zbudować zawsze, gdy było 100 minerałów, nigdy nie był odrzucany i nie ma własnego
kosztu w nagrodzie, więc tablica nie odróżnia potrzebnego magazynu od zbędnego.
W trakcie treningu tablica zmienia się po każdym kroku, więc agent nie tkwi w takim
wyborze długo. Zamrożona tablica powtarza go do końca gry.

**Wniosek:** maska oferuje `BUILD_SUPPLY_DEPOT` tylko wtedy, gdy zapas populacji,
liczony razem z magazynami w drodze, jest mniejszy niż 16
([srodowisko.md](srodowisko.md#limit-zapasu-populacji)). U agenta losowego liczba
zlecanych magazynów spadła z 31 do 16 na grę, a liczba wyszkolonych Marines wzrosła
z około 110 do 154.

### Agenci odniesienia na wcześniejszych wersjach środowiska

Do porównań z v4 (uczciwa maska `EXPAND`, jeszcze bez limitu zapasu populacji):

| Agent | Przeciwnik | W / P / R | Wygrane (95% CI) |
|-------|------------|-----------|------------------|
| skryptowy | VeryEasy | 24 / 0 / 0 | 100% (86–100%) |
| skryptowy | Easy | 24 / 0 / 0 | 100% (86–100%) |
| skryptowy | Medium | 17 / 7 / 0 | 71% (51–85%) |
| losowy | VeryEasy | 23 / 0 / 1 | 96% (80–99%) |
| losowy | Easy | 23 / 18 / 7 | 48% (35–62%) |
| losowy | Medium | 0 / 24 / 0 | 0% (0–14%) |

Osobna seria 24 gier agenta losowego przeciw Easy na tym samym kodzie dała 6 wygranych.
Łącznie to 29 z 72, czyli 40% (95% CI 30–52%).

Do porównań z v2 (po zmianie punktów decyzyjnych, przed rezerwacją minerałów):

| Agent | Przeciwnik | W / P / R | Wygrane (95% CI) |
|-------|------------|-----------|------------------|
| skryptowy | VeryEasy | 24 / 0 / 0 | 100% (86–100%) |
| skryptowy | Easy | 24 / 0 / 0 | 100% (86–100%) |
| skryptowy | Medium | 14 / 10 / 0 | 58% (39–76%) |
| losowy | VeryEasy | 24 / 0 / 0 | 100% (86–100%) |
| losowy | Easy | 8 / 15 / 1 | 33% (18–53%) |
| losowy | Medium | 1 / 23 / 0 | 4% (1–20%) |

Do porównań z v3 (po rezerwacji minerałów, przed poprawką maski `EXPAND`):

| Agent | Przeciwnik | W / P / R | Wygrane (95% CI) |
|-------|------------|-----------|------------------|
| skryptowy | VeryEasy | 24 / 0 / 0 | 100% (86–100%) |
| skryptowy | Easy | 24 / 0 / 0 | 100% (86–100%) |
| skryptowy | Medium | 17 / 7 / 0 | 71% (51–85%) |
| losowy | VeryEasy | 24 / 0 / 0 | 100% (86–100%) |
| losowy | Easy | 16 / 30 / 2 | 33% (22–48%) |
| losowy | Medium | 0 / 24 / 0 | 0% (0–14%) |

Dla v1 odniesieniem jest początek samego treningu, gdy akcje były niemal losowe:
40 wygranych w pierwszych 150 grach (27%).

## Wydajność

| Pomiar | Wartość |
|--------|---------|
| Jedna gra agenta skryptowego, 5,5 minuty czasu gry, maszyna bez obciążenia | 12 s łącznie ze startem gry |
| Trening v4, 12 gier naraz | 500 gier w 45,5 minuty: 11 gier na minutę, około 168 minut gry na minutę czasu rzeczywistego |
| Trening v5, 12 gier naraz | 500 gier w 42 minuty: 12 gier na minutę (gry są krótsze, bo agent szybciej wygrywa) |
| Obciążenie przy 12 grach naraz | 12–18 rdzeni, 6–9,5 GB pamięci |
| Testy jednostkowe | kilka sekund |
| Testy integracyjne (7 testów z prawdziwą grą) | 40–80 s zależnie od obciążenia |
| Pierwsze budowanie obrazu | kilkanaście minut, obraz 9,7 GB |

Model A nie używa GPU. Cały koszt uczenia to symulacja gry na procesorze.
