# constants
state_ack   = 0x00000020
state_eco   = 0x10000000
state_clean = 0x04000000
state_cool  = 0x08000000
state_off   = 0x00000020
state_on    = 0x02000000
state_start = 0x01000000


remote_reset    = "\x1bRD60005C&"


# Status results
str_off =      "00000020"              # Off
str_igniting = "01010022"              # Ignition starting
str_igniting_load_wood = "01020023"    # Ignition load wood
str_igniting_fire_on = "01030024"      # Ignition fire on
str_igniting_fire_vent_on = "01040025" # Ignition fire on + vent on
str_ignited =  "02010023"              # Flame on
str_cool1 =    "0802002A"              # Cooling down
str_cool2 =    "08010029"              # Cooling down
str_cool3 =    "10010022"              # Cooling down (eco)
str_eco_off =  "10030024"              # Eco standby
str_ack =      "00000020"              # both acknoledge and off

# Get data
get_errorstate  = "\x1bRDA00067&"
get_exhfanspeed = "\x1bREF0006D&"
get_flugastemp  = "\x1bRD000056&" 
get_pelletspeed = "\x1bRD40005A&"
get_setpoint    = "\x1bRC60005B&"
get_status      = "\x1bRD90005f&"
get_temperature = "\x1bRD100057&"
get_powerLevel  = "\x1bRD300059&"

# Set data
set_augercor    = "\x1bRD50005A&"
set_extractcor  = "\x1bRD50005B&"
set_temperature = "\x1bRF2xx0yy&"
set_pelletcor   = "\x1bRD50005B&"
set_powerLevel  = "\x1bRF00xx0yy&"
set_powerOff    = "\x1bRF000058&"
set_powerOn     = "\x1bRF001059&"
