# Runbooki

Instrukcje krok po kroku do powtarzalnych czynności w projekcie. Każdy runbook mówi, co
wpisać, czego się spodziewać na ekranie i jak sprawdzić, że się udało. Opis tego, *jak
projekt jest zbudowany i dlaczego*, jest osobno w [dokumentacji](../docs/README.md).

| Nr | Runbook | Kiedy sięgnąć |
|----|---------|---------------|
| 01 | [Środowisko Docker (headless)](01-srodowisko-docker.md) | Pierwsze uruchomienie na nowej maszynie, przebudowa obrazu |
| 02 | [Klient Windows](02-klient-windows.md) | Chcesz oglądać grę na żywo |
| 03 | [Pierwsza gra i diagnostyka](03-pierwsza-gra.md) | Sprawdzenie, że wszystko działa od gry po odczyty |
| 04 | [Trening Q-Learning](04-trening-q-learning.md) | Uczenie Modelu A, wznawianie, podgląd postępu |
| 05 | [Ewaluacja i powtórki](05-ewaluacja-i-powtorki.md) | Pomiar skuteczności agenta, zapis i oglądanie gier |
| 06 | [Testy, jakość kodu, zależności](06-testy-i-zaleznosci.md) | Przed commitem, przy dodawaniu biblioteki |
| 07 | [Rozwiązywanie problemów](07-rozwiazywanie-problemow.md) | Coś nie działa |

## Konwencje

- Wszystkie komendy uruchamiaj z katalogu głównego repozytorium.
- Komendy są jednolinijkowe i działają tak samo w PowerShell i w Git Bash.
- `docker compose run --rm sc2 <komenda>` uruchamia komendę w kontenerze z grą. Kod jest
  podmontowany z dysku, więc zmiany w plikach `.py` działają od razu, bez przebudowy obrazu.
- `uv run <komenda>` uruchamia komendę w lokalnym środowisku Pythona (Windows).
- Wyniki pracy (`runs/`, `replays/`) nie trafiają do Gita.

## Stan weryfikacji

Runbooki 01, 03, 04, 05 i 06 zostały przećwiczone na maszynie, na której powstał projekt
(Windows 10, Docker Desktop 28.5, RTX 3090, i7-13700F, 32 GB RAM), 13 listopada 2026.
Runbook 02 został przećwiczony dzień później na świeżej instalacji klienta Windows (gra
w wersji 5.0.17). Niesprawdzone zostało tylko oglądanie powtórek w kliencie, co jest
zaznaczone w jego treści.
