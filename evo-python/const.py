# constants

# Status results
str_off = "00000020"       # Off
str_igniting = "01010022"  # Ignition starting
str_ignited = "02010023"   # Flame on
str_cool1 = "0802002A"     # Cooling down
str_cool2 = "08010029"     # Cooling down
str_cool3 = "10010022"     # Cooling down (eco)
str_eco_off = "10030024"   # Eco standby
str_ack = "00000020"       # both acknoledge and off

# Get data
get_status = "\x1bRD90005f&"
get_temperature = "\x1bRD100057&"

# Set data
set_temperature = "\x1bRF2xx0yy&"
set_powerLevel = "\x1bRF00x0yy&"
set_powerOff = "\x1bRF000058&"
set_powerOn = "\x1bRF001059&"
