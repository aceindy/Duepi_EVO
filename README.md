[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

## Duepi-EVO
The `Duepi EVO` climate platform is a reverse engineered implementation of the app which is controlling Pellet stove heaters using a Duepi Evo Wifi module.
This is in no way associated with the company Duepi and comes with no guarantees or warranty. Use at your own risk.

## Prerequisites
### Hardware
You must have the ESP Module installed and flash it with https://github.com/jeelabs/esp-link.
Baudrate 115200, 8N1

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
    min_temperature: 20
    max_temperature: 30
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

Huge thanks go to pascal_bornat@hotmail.com
who found the strings to control the EVO board and interfaced it to Jeedom
