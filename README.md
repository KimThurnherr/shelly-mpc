# Shelly MCP Server

MCP-Server für Claude zur Licht- und Temperatursteuerung mit Shelly-Geräten.

- **Licht und Relais** über die Shelly Cloud Control API v2 (schalten, dimmen, Farbtemperatur, Farbe, mehrere Geräte auf einmal). Die Geräteliste kommt vom Legacy-Endpunkt `/device/all_status`, weil die v2-API keine Liste kennt.
- **Heizkörperventile (Shelly BLU TRV)** lokal über ein oder mehrere BLU Gateway Gen3 per RPC (`BluTrv.*`). Die Cloud-API kennt keinen Befehl, um die Solltemperatur zu setzen, darum muss der MCP die Gateways im Netz direkt erreichen.

Läuft ausschliesslich als Docker-Container (Streamable HTTP) hinter einem Reverse-Proxy, geschützt mit einem statischen Bearer-Token. Alle Zugangsdaten und Adressen kommen aus Umgebungsvariablen.

## Tools

| Tool | Zweck |
|---|---|
| `get_version` | Version und Commit des laufenden Servers |
| `list_devices` | Alle Geräte des Cloud-Kontos mit Name und Raum aus der Shelly-App, online, Licht/Relais-Zustand pro Kanal, Temperaturen, TRVs |
| `get_device_status` | Status von 1-10 Geräten |
| `set_light` | Licht ein/aus, `brightness` 0-100, `temperature` 2700-7000 K, Farbe (`red`/`green`/`blue`/`white`, `gain`), `toggle_after` |
| `set_switch` | Relais/Steckdose schalten |
| `set_group` | Mehrere Lichter/Relais gleichzeitig (`id` oder `id_kanal`) |
| `list_trvs` | Alle BLU TRVs mit Name und Raum: Ist-/Solltemperatur, Ventilstellung, Batterie, Fehler (gelesen über die Cloud) |
| `get_trv` | Detailstatus eines TRV inkl. Boost/Override |
| `set_trv_target` | Solltemperatur dauerhaft setzen (4-30 °C) |
| `set_trv_override` / `clear_trv_override` | Temporäre Solltemperatur für eine Dauer |
| `set_trv_boost` / `clear_trv_boost` | Ventil für eine Dauer voll öffnen |
| `list_scenes` / `get_scene` | Szenen der Shelly-App mit Aktionen und Bedingungen bzw. vollständigem Skript |
| `run_scene` | Szene sofort einmal ausführen (nur mit `confirm=true`) |
| `set_scene_enabled` | Szene aktivieren/deaktivieren |
| `edit_scene` | Szenen-Skript ändern, ohne `confirm=true` nur Vorschau, altes Skript in der Antwort |
| `create_scene` | Neue Szene anlegen, mit eigenem Skript oder einer bestehenden Szene als Vorlage (`copy_from`), ohne `confirm=true` nur Vorschau |
| `gateway_status` | Diagnose: lokale Erreichbarkeit der Gateways (Geräte-ID, Modell, Firmware) |

Namen und Räume kommen aus der Shelly-App (`/interface/device/get_all_lists`, 5 Minuten gecacht). TRVs werden über ihren Namen aus der App, die Komponenten-ID (z.B. `200`) oder `gateway_id:200` angesprochen. Gelesen wird über die Cloud, Befehle gehen lokal an das Gateway, das per IP aus der App einem Eintrag in `SHELLY_GATEWAYS` zugeordnet wird.

## Umgebungsvariablen

| Variable | Pflicht | Beschreibung |
|---|---|---|
| `MCP_AUTH_TOKEN` | ja | Bearer-Token, mind. 32 Zeichen (`openssl rand -base64 48`). Ohne Token startet der Server nicht |
| `SHELLY_CLOUD_SERVER` | für Licht | Server-URI des Kontos, z.B. `shelly-00-eu.shelly.cloud` (nur Hosts unter `shelly.cloud` werden akzeptiert) |
| `SHELLY_CLOUD_AUTH_KEY` | für Licht | Shelly-App > Benutzereinstellungen > Authorization cloud key. Ändert sich bei einem Passwortwechsel |
| `SHELLY_GATEWAYS` | für TRV | Kommagetrennt, je `Name=http://IP` oder nur `http://IP` |
| `SHELLY_GATEWAY_PASSWORD` | nein | Passwort der Gateways (Digest-Auth, Benutzer `admin`), falls gesetzt |
| `SHELLY_HTTP_TIMEOUT` | nein | Timeout in Sekunden (Standard 15) |
| `SHELLY_TRV_CALL_TIMEOUT` | nein | Timeout für Befehle an ein TRV (Standard 65, Shelly nennt bis zu einer Minute) |
| `MCP_PATH_PREFIX` | nein | Pfad-Präfix, wenn der Reverse-Proxy unter einem Unterpfad ohne Umschreiben weiterleitet (z.B. `/shelly` → Endpoint `/shelly/mcp`) |
| `MCP_BIND_ADDR` / `MCP_HOST_PORT` | nein | Port-Mapping auf dem Docker-Host (Standard `127.0.0.1:8439`) |

## Hinweise

- Szenen sind nicht Teil der offiziellen Cloud API. Genutzt werden die Endpunkte der Shelly-App (`/scene/list`, `/scene/get`, `/scene/manual_run`, `/scene/enable`, `/scene/edit`, `/scene/add`), die Shelly jederzeit ändern kann.

- Die Cloud erlaubt 1 Request pro Sekunde und Konto. Der Server drosselt selbst und wiederholt einmal bei HTTP 429.
- Der auth_key erscheint nie in Antworten oder Logs.
- Die Gateways brauchen eine feste IP (DHCP-Reservierung oder statisch), sonst findet der MCP sie nach einem Neustart nicht mehr.
- Das Repo ist privat, das Image auf ghcr.io damit auch. Portainer braucht für `ghcr.io` eine Registry mit Zugangsdaten (Token mit `read:packages`).

## Deployment

Image wird bei jedem Push auf `main` per GitHub Actions gebaut (`.github/workflows/docker-publish.yml`). Portainer-Stack als Git-Stack auf dieses Repo, Werte als Stack-Variablen, ohne GitOps-Autoupdate.
