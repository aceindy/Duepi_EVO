[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
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

Optionally one can use the Wemos D1 flashed with espeasy (https://www.letscontrolit.com/wiki/index.php/ESPEasy). This device has a 5V input and integrated CH340 for easy flashing. The only tweak I needed was to add 5ms timeout delay in the serial device settings of espeasy to get robust data from my pellet stove ( Duroflame Rembrand). In Esp_easy flashed device select the Device: Communication - Serial Server (https://www.letscontrolit.com/wiki/index.php?title=Ser2Net) and fill in the appropiate fields (harware serial GPIO-3 and -1, port 1234 (or any) baud rate 115200, serial config 8N1,RX receive 5ms, 256 buffer). 

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
    name: <your heaters name here
    host: 192.168.1.123
    port: 23
    scan_interval: 60
    min_temp: 20
    max_temp: 30
    auto_reset: True
```

Configuration variables:

- **name** (*optional*): The name of your climate entity. Default is `Duepi Evo`
- **scan_interval** (*required*): The scan interval being used in seconds.
- **host** (*required*): The IP address used for the serial@tcp devic.
- **port** (*optional*): The scan interval being used. Default is 23
- **min/max_temperature** (*optional*): The available setpoint range within HA. Default is 15-30 degs celsius.
- **auto_reset** (*optional*): Auto reset the stove when "Ignition failed" or "Out of pellets" defaults to False

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
- Duroflame Rembrand

## To do
Add reset option

Huge thanks go to pascal_bornat@hotmail.com
who found the strings to control the EVO board and interfaced it to Jeedom

[Buy Me A Coffee](https://ko-fi.com/aceindy)! :coffee:

