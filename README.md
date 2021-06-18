[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/Z8Z050HKY)
## Duepi-EVO
The `Duepi EVO` climate platform is a reverse engineered implementation of the app which is controlling Pellet stove heaters using a Duepi Evo Wifi module.
With this module it is possible to control your pellet stove with HomeAssistant.
This is in no way associated with the company Duepi and comes with no guarantees or warranty. Use at your own risk.

## Prerequisites
### Hardware
This uses an ESP01 board with 5/3.3v adapter.
You must have the ESP01 Module installed and flash it with https://github.com/jeelabs/esp-link.
Baudrate 115200, 8N1.
Pin layout is mentioned in the pdf (pcb, J8)

## Functionality
- Control target temperature.
- Control system on/off.

## Configuration
Add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
climate:
  - platform: duepi_evo
    name: <your heaters name here
    host: 192.168.1.123
    port: 23
    scan_interval: 60
    min_temp: 20
    max_temp: 30
```

Configuration variables:

- **name** (*optional*): The name of your climate entity. Default is `Duepi Evo`
- **min/max_temperature** (*optional*): The available setpoint range within HA. Default is 15-30 degs celsius.
## Troubleshooting
Please set your logging for the custom_component to debug:
```yaml
logger:
  default: warn
  logs:
    custom_components.duepi_evo: debug
```
Confirmed working on:
- Qlima Viola 85 S-Line
- Kalor
- Artel
- Foco
- Centrometal
- AMG
- Interstove
- Wamsler Westminster Quatro 6

## To do
Store setpoint and current fan-speed as HA variable, as the stove does not transmit these.

Huge thanks go to pascal_bornat@hotmail.com
who found the strings to control the EVO board and interfaced it to Jeedom

[Buy Me A Coffee](https://ko-fi.com/aceindy)! :coffee:

