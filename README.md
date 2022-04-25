## How to run

Due to restrictions with GPIO pins on the raspberry pi, the script has to be run as root which
conflicts with the userspace sound manager

1. Kill the userspace sound manager (eg. pulseaudio)
2. Start the sound manager as root (eg. sudo pulseaudio)
3. Connect to the bluetooth speaker
4. Run 'sudo python3 main.py'

## Dependencies
- numpy
- pygame
- RPi.GPIO
- rpi_ws281x

## Note on music & fonts

Due to copyright reasons, we cannot upload the music and fonts
