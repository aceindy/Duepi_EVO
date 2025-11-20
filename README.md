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
Add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
climate:
  - platform: duepi_evo
    name: <your heaters name here>
    host: 192.168.1.123
    port: 2000
    scan_interval: 60
    min_temp: 20
    max_temp: 30
    auto_reset: True
    unique_id: <unique_name>
    temp_nofeedback: 16
```
Configuration variables:

- **name** (*optional*): The name of your climate entity. Defaults to "Duepi Evo".
- **host** (*required*): The IP address used for the serial@tcp device.
- **port** (*optional*): The port being used. Defaults to 2000. (when using my ESPLink version, you can also use the default telnet port 23)
- **scan_interval** (*required*): The scan interval being used in seconds.
- **min/max_temperature** (*optional*): The available setpoint range within HA. Default is 16-30 degs celsius.
- **auto_reset** (*optional*): Auto reset the stove when "Ignition failed" or "Out of pellets" defaults to False.
- **unique_id** (*optional*): A unique name for the device. Defaults to "duepi_unique". Change when using multiple stoves
- **temp_nofeedback** (*optional*): The default setpoint temperature for stoves that do not store the current setpoint. Defauls to 16.

## Troubleshooting
Please set your logging for the custom_component to debug:
```yaml
logger:
  default: warn
  logs:
    custom_components.duepi_evo: debug
```
## Example lovelace entities card:
```yaml
type: entities
entities:
  - entity: climate.pellet_stove
    type: attribute
    name: Burner Status
    attribute: burner_status
    icon: mdi:fire-circle
  - entity: climate.pellet_stove
    type: attribute
    name: Error code
    attribute: error_code
    icon: mdi:code-array
  - entity: climate.pellet_stove
    type: attribute
    name: Exhaust fan speed
    attribute: exh_fan_speed
    icon: mdi:fan
  - entity: climate.pellet_stove
    type: attribute
    name: Flu gas temperature
    attribute: flu_gas_temp
    icon: mdi:temperature-celsius
  - entity: climate.pellet_stove
    type: attribute
    name: Pellet speed
    attribute: pellet_speed
    icon: mdi:speedometer
  - entity: climate.pellet_stove
    type: attribute
    name: Power level
    attribute: power_level
    icon: mdi:power-cycle
```

Confirmed working on:
- Amesti 8100 plus2
- AMG
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
