[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/Z8Z050HKY)
## Duepi-EVO
The `Duepi EVO` climate platform is a reverse engineered implementation of the app which is controlling Pellet stove heaters using a Duepi Evo Wifi module.
With this module it is possible to control your pellet stove with [HomeAssistant](https://community.home-assistant.io/t/pellet-stove-duepi-evo/255841?u=aceindy).

This is in no way associated with the company Duepi and comes with no guarantees or warranty. Use at your own risk.

![image](https://github.com/user-attachments/assets/5f820ef9-7ab9-4dc2-88cc-a643e5076973)

## Prerequisites
### Hardware
This uses an ESP01 board with 5/3.3v adapter with ser2net software.

I recently found a config for ESPHome (which has my preference, but I switched back, as it wasn't very stable.
You will find a configureation example here https://github.com/aceindy/Duepi_EVO/blob/main/ESPHome/duepi-pelletstove.yaml

### ESPLink works for sure:
You must have the ESP01 Module installed and flash it with https://github.com/jeelabs/esp-link.
Baudrate 115200, 8N1.
Pin layout is mentioned in the pdf (pcb, J8)

Easiest way to install ESP-Link is to use this Online installer page on my GitHub site [ESP-Link](https://aceindy.github.io/esp-link/)
Note that I have re-compiled the firmware to host on ports 23 and 2000, which allows to use the newer myDPRemote app too (as it has port 2000 hardcoded).

#### As well as Espeasy (info from a Duroflame Rembrand user):
Optionally one can use the Wemos D1 flashed with [ESPeasy](https://www.letscontrolit.com/wiki/index.php/ESPEasy). This device has a 5V input and integrated CH340 for easy flashing. The only tweak needed was to add 5ms timeout delay in the serial device settings of espeasy to get robust data from the pellet stove. In Esp_easy flashed device select the Device: Communication - [Serial Server](https://www.letscontrolit.com/wiki/index.php?title=Ser2Net) and fill in the appropiate fields (harware serial GPIO-3 and -1, port 1234 (or any) baud rate 115200, serial config 8N1,RX receive 5ms, 256 buffer). 

## Functionality
- Control target temperature.
- Control system on/off.
- Control fan speed (only when actual temperature below target temperature) 1-5

## Configuration
### Recommended: UI setup (Config Flow)
1. Go to **Settings -> Devices & Services -> Add Integration**.
2. Search for **Duepi EVO**.
3. Enter:
   - `host`
   - `port`
   - `name`
   - `unique_id`
4. After creation, edit options to configure:
   - `scan_interval`
   - `min_temp`
   - `max_temp`
   - `auto_reset`
   - `temp_nofeedback`
   - `init_command`

### Legacy YAML configuration (deprecated)
YAML is still supported temporarily and will be auto-imported into Config Entries when possible.

```yaml
climate:
  - platform: duepi_evo
    name: <your heaters name here>
    host: 192.168.1.123
    port: 2000
    scan_interval: 60
    min_temp: 20
    max_temp: 30
    auto_reset: true
    unique_id: <unique_name>
    temp_nofeedback: 16
    init_command: false
```

Configuration variables:
- **name** (*optional*): Name of your climate entity. Defaults to "Duepi EVO".
- **host** (*required*): IP address used for the serial@tcp device.
- **port** (*optional*): Port in use. Defaults to 2000. When using aceindy's ESP-Link build, port 23 also works.
- **scan_interval** (*optional*): Poll interval in seconds. Defaults to 60.
- **min_temp / max_temp** (*optional*): Available setpoint range in HA. Defaults to 16-30.
- **auto_reset** (*optional*): Auto reset when "Ignition failure" or "Out of pellets". Defaults to false.
- **unique_id** (*optional*): Custom unique suffix. Defaults to "duepi_unique".
- **temp_nofeedback** (*optional*): Fallback setpoint when stove does not report setpoint. Defaults to 16.
- **init_command** (*optional*): Some stoves require an additional init command before they accept a command. Use this when you receive time-outs on new commands.

## Troubleshooting
Please set your logging for the custom_component to debug:
```yaml
logger:
  default: warn
  logs:
    custom_components.duepi_evo: debug
```
## Development (devcontainer/local helper scripts)
The helper scripts auto-detect the repository root from their own path.
For local runs, use Python 3.13.2 or newer.
If needed, you can override the workspace location explicitly:

```bash
WORKSPACE=/absolute/path/to/Duepi_EVO bash scripts/setup.sh
WORKSPACE=/absolute/path/to/Duepi_EVO bash scripts/ha.sh start
```

## Example Lovelace entities card (new dedicated sensors):
```yaml
type: entities
entities:
  - entity: climate.pellet_stove
  - entity: sensor.pellet_stove_burner_status
  - entity: sensor.pellet_stove_error_code
  - entity: sensor.pellet_stove_exh_fan_speed
  - entity: sensor.pellet_stove_flu_gas_temp
  - entity: sensor.pellet_stove_pellet_speed
  - entity: sensor.pellet_stove_power_level
  - entity: sensor.pellet_stove_pcb_temperature
  - entity: sensor.pellet_stove_total_burn_time
  - entity: sensor.pellet_stove_burn_time_since_reset
  - entity: binary_sensor.pellet_stove_pressure_switch
```

### Legacy climate attributes
Legacy `climate.*` attributes are still exposed for compatibility and are planned to be removed after two releases.

Confirmed working on:
- Amesti 8100 plus2
- AMG
- ALP srl Guisy
- Artel
- Casatelli Leonardo 8/9
- Centrometal
- Duroflame Carré
- Duroflame Pelle
- Duroflame Rembrand
- FireShop Dinamica 6
- Foco
- Interstove
- Italia mod 8 el
- Julia Next
- Kalor
- Qlima Viola 85 S-Line
- Wamsler Westminster Quatro 6

Big thanks go to Pascal Bornat (who initially started reverse engineering for Jeedom)
and Oxan van Leeuwen (for the Stream server for ESPHomeproject)

[Buy Me A Coffee](https://ko-fi.com/aceindy)! :coffee:

## Star History
[![Star History Chart](https://api.star-history.com/svg?repos=aceindy/Duepi_EVO&type=date&legend=top-left)](https://www.star-history.com/#aceindy/Duepi_EVO&type=date&legend=top-left)
