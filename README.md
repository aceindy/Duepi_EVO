[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
#Duepi-EVO
The `Duepi EVO` climate platform is a reverse engineered implementation of the app which is controlling Pellet stove heaters using a Duepi Evo Wifi module.
This is in no way associated with the company Duepi and comes with no guarantees or warranty. Use at your own risk.

## Prerequisites
### Hardware
You must have the ESP Module installed and and flashed it with https://github.com/jeelabs/esp-link.

## Functionality as of v0.3
- Control target temperature.
- Control system on/off.

## Coming soon...
- Control power stages

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
```

Configuration variables:

- **name** (*Optional*): The name of your climate entity. Default is `Duepi Evo`

## Troubleshooting
Please set your logging for the custom_component to debug:
```yaml
logger:
  default: warn
  logs:
    custom_components.duepi_evo: debug
```

Huge thanks go to pascal_bornat@hotmail.com
who found the strings to control the EVO board and interfaced it to Jeedom