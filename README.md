# Shelly MCP Server

MCP-Server für Claude zur Licht- und Temperatursteuerung mit Shelly-Geräten.

- **Licht und Relais** über die Shelly Cloud Control API v2 (schalten, dimmen, Farbtemperatur, Farbe, mehrere Geräte auf einmal). Die Geräteliste kommt vom Legacy-Endpunkt `/device/all_status`, weil die v2-API keine Liste kennt.
- **Heizkörperventile (Shelly BLU TRV)** lokal über ein oder mehrere BLU Gateway Gen3 per RPC (`BluTrv.*`). Die Cloud-API kennt keinen Befehl, um die Solltemperatur zu setzen, darum muss der MCP die Gateways im Netz direkt erreichen.

Läuft ausschliesslich als Docker-Container (Streamable HTTP) hinter einem Reverse-Proxy, geschützt mit einem statischen Bearer-Token. Alle Zugangsdaten und Adressen kommen aus Umgebungsvariablen.

## Tools

| Tool | Zweck |
|---|---|
| `get_version` | Version und Commit des laufenden Servers |
| `list_devices` | Alle Geräte des Cloud-Kontos mit Name, online, Licht/Relais-Zustand, Temperaturen |
| `get_device_status` | Status von 1-10 Geräten |
| `set_light` | Licht ein/aus, `brightness` 0-100, `temperature` 2700-7000 K, Farbe (`red`/`green`/`blue`/`white`, `gain`), `toggle_after` |
| `set_switch` | Relais/Steckdose schalten |
| `set_group` | Mehrere Lichter/Relais gleichzeitig (`id` oder `id_kanal`) |
| `list_trvs` | Alle BLU TRVs: Ist-/Solltemperatur, Ventilstellung, Batterie, Fehler |
| `get_trv` | Detailstatus eines TRV inkl. Boost/Override |
| `set_trv_target` | Solltemperatur dauerhaft setzen (4-30 °C) |
| `set_trv_override` / `clear_trv_override` | Temporäre Solltemperatur für eine Dauer |
| `set_trv_boost` / `clear_trv_boost` | Ventil für eine Dauer voll öffnen |

TRVs werden über ihren Namen aus der Shelly-App, die Komponenten-ID (z.B. `200`) oder `gateway:id` angesprochen.

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
| `MCP_BIND_ADDR` / `MCP_HOST_PORT` | nein | Port-Mapping auf dem Docker-Host (Standard `127.0.0.1:8439`) |

## Hinweise

- Die Cloud erlaubt 1 Request pro Sekunde und Konto. Der Server drosselt selbst und wiederholt einmal bei HTTP 429.
- Der auth_key erscheint nie in Antworten oder Logs.
- Die Gateways brauchen eine feste IP (DHCP-Reservierung oder statisch), sonst findet der MCP sie nach einem Neustart nicht mehr.
- Das Repo ist privat, das Image auf ghcr.io damit auch. Portainer braucht für `ghcr.io` eine Registry mit Zugangsdaten (Token mit `read:packages`).

## Deployment

Image wird bei jedem Push auf `main` per GitHub Actions gebaut (`.github/workflows/docker-publish.yml`). Portainer-Stack als Git-Stack auf dieses Repo, Werte als Stack-Variablen, ohne GitOps-Autoupdate.
