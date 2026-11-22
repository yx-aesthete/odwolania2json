# Instalacja na maszynie wirtualnej UZP

Maszyna: Ubuntu 24.04, 2 vCPU, 16 GB RAM, Docker + Compose v2, dostęp do internetu (wyjście do `api.scaleway.ai:443`).

1. `sudo git clone <repo> /opt/solution/app` (albo pobierz `instaluj.sh` i uruchom: robi to sam).
2. `sudo REPO=<repo> /opt/solution/app/deploy/vm/instaluj.sh` — tworzy `/opt/solution/{input,output,audit}`, buduje obraz (wszystkie zależności pobrane teraz), kopiuje `RUN.md` do `/opt/solution/RUN.md`, zakłada `/opt/solution/.env` z `.env.example` i robi przebieg testowy na przykładowej sprawie z repo.
3. Wpisz klucz: `sudo nano /opt/solution/.env` → `LLM_API_KEY=…` (Scaleway). Bez klucza działają same reguły.
4. Sprawdzenie: PDF-y do `/opt/solution/input`, `sudo rm -rf /opt/solution/output/*`, komenda z `/opt/solution/RUN.md`, wyniki w `/opt/solution/output`.
5. Po `sudo reboot` Docker startuje sam (`systemctl enable docker` w skrypcie), komenda z RUN.md działa bez dodatkowych kroków.

Dostęp zespołu kończy się 22.11 o 11:00: obraz musi być zbudowany wcześniej (krok 2).
