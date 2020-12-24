#constants

#Status results
str_cool1="0802002A"
str_cool2="08010029"
str_off="00000020"
str_igniting="01010022"
str_ignited="02010023"
str_ack="00000020"

#Get data
get_status = "\x1bRD90005f&"
get_temperature = "\x1bRD100057&"

#Set data
set_temperature = "\x1bRF2xx0yy&"
set_powerLevel = "\x1bRF00x0yy&"
set_powerOff = "\x1bRF000058&"
set_powerOn = "\x1bRF001059&"
