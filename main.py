"IMPORTS FOR LIGHTS"
from signal import set_wakeup_fd
import RPi.GPIO as GPIO
import time
from rpi_ws281x import PixelStrip, Color
import argparse

"IMPORTS FOR GAME"
import pygame, sys
import random

import numpy as np

GPIO.setmode(GPIO.BCM)

"SET UP AND DEFINITIONS"
WINDOWWIDTH = 1024
WINDOWHEIGHT = 768
BLACK = (0,0,0)

debug = False

class Game_Manager:
    def __init__(self, questions, light_manager, sound_manager, seat_manager, players_needed):
        self.questions = questions
        self.light_manager = light_manager
        self.sound_manager = sound_manager
        self.seat_manager = seat_manager
        self.index = None
        self.current_questions = None
        self.seated = 0
        self.players_needed = players_needed
        self.text = None
    
    def start(self, no_questions):
        self.current_questions = random.sample(self.questions, no_questions)
        self.index = 0
    
    def next(self):
        if not self.in_game():
            if self.seated < self.players_needed:
                return
            else:
                self.start(4)
        if self.index >= len(self.current_questions):
            self.index += 1
            return
        current_question = self.current_questions[self.index]
        self.light_manager.transition_to(current_question[1])
        self.sound_manager.transition_to(current_question[2])
        question = current_question[0]    
        self.display(question)
        self.index += 1
    
    def display(self, text, textsize=None):
        if textsize == None:
            f = font
        else:
            f = pygame.font.Font('fonts/space_invaders.ttf',textsize)
        if self.text == text:
            return
        self.text = text
        screen.fill((255,255,255))
        text = f.render(text, True, (0,0,0))
        textRect = text.get_rect()
        textRect.center = (WINDOWWIDTH //2, WINDOWHEIGHT //2)
        screen.blit(text,textRect)
        screen.blit(pygame.transform.rotate(screen, 180), (0, 0))
        pygame.display.update()

    def in_game(self):
        return self.index is not None and self.index <= len(self.current_questions)

    def update(self, dt):
        seated, light_active_states, pin_state = self.seat_manager.check_seats()
        self.seated = seated
        if not self.in_game():
            if seated < 1:
                self.sound_manager.transition_to(1)
                self.light_manager.transition_to((6, 1))
            elif seated < 3:
                self.sound_manager.transition_to(6)
                self.light_manager.transition_to((7, 1))
            elif seated < 6:
                self.sound_manager.transition_to(7)
                self.light_manager.transition_to((8, 1))
            else:
                self.sound_manager.transition_to(8)
                self.light_manager.transition_to((0, 0))
            if debug:
                self.display(f"{pin_state}")
            else:
                if seated >= self.players_needed:
                    self.display("Press to start new game!", 52)
                else:
                    self.display(f"Waiting for {self.players_needed - seated} more players to join...")
        self.light_manager.update(dt, light_active_states)
        self.sound_manager.update(dt)

class Light_Manager:
    def __init__(self, strip, lights, light_length):
        self.strip = strip
        self.lights = lights ## [colors, cycle_ms, offset_ms]
        self.light_length = light_length
        self.light_modes = None
        self.new_light_modes = [None, None]
        self.transition_ms = [0, 0]
        self.brightness = [1.0, 1.0]
        self.light_color_states = np.zeros([2, self.light_length], dtype=int)
        self.light_active_states = np.zeros([self.light_length])

    def transition_to(self, lights):
        if self.light_modes == None:
            self.light_modes = [None, None]
            self.light_modes[:] = lights
        if lights == self.light_modes:
            return
        for i in range(2):
            if self.light_modes[i] == lights[i]:
                continue
            self.new_light_modes[i] = lights[i]
            if self.transition_ms[i] <= 0:
                self.transition_ms[i] = max(1, 500 + self.transition_ms[i])
            
            
    def update(self, dt, light_desired_state):
        self.light_color_states += dt
        for i in range(2):
            if self.transition_ms[i] > 0:
                self.transition_ms[i] = max(0, self.transition_ms[i] - dt)
                self.brightness[i] = (self.transition_ms[i] / 500.0)
                if self.transition_ms[i] == 0:
                    self.transition_ms[i] = -500
                    self.light_modes[i] = self.new_light_modes[i]
                    _, cycle_ms, offset_ms = self.lights[self.light_modes[i]]
                    self.light_color_states[i] = [(k * offset_ms) % cycle_ms for k in range(self.light_length)]
            elif self.transition_ms[i] < 0:
                self.transition_ms[i] = min(0, self.transition_ms[i] + dt)
                self.brightness[i] = 1.0 + (self.transition_ms[i] / 500.0)
        self.light_active_states = np.clip(self.light_active_states + dt * (light_desired_state * 2 - 1) /500.0, 0, 1)
        light_colors = np.zeros([2, self.light_length, 3])
        for i in range(2):
            colors, cycle_ms, _ = self.lights[self.light_modes[i]]
            self.light_color_states[i] = self.light_color_states[i] % cycle_ms
            color_idx = (self.light_color_states[i] * len(colors)) // cycle_ms
            transition = ((self.light_color_states[i] * len(colors)) % cycle_ms) / cycle_ms
            transition = np.expand_dims(transition, 1)
            light_colors[i] = colors[color_idx] * (1.0 - transition) + colors[(color_idx + 1) % len(colors)] * transition
            light_colors[i] = light_colors[i] * self.brightness[i] + np.array([255.0, 255.0, 255.0]) * (1.0 - self.brightness[i])
        light_active_state = np.expand_dims(self.light_active_states, 1)
        light_colors = (light_colors[0] * light_active_state + light_colors[1] * (1.0 - light_active_state)).astype(int).tolist()
        for i in range(self.light_length):
            self.strip.setPixelColor(i, Color(*light_colors[i]))
        self.strip.show()

class Seat_Manager:
    def __init__(self, sensor_pins, seat_lights, bg_lights, light_length):
        self.sensor_pins = sensor_pins
        list(map(lambda x: GPIO.setup(x, GPIO.IN), sensor_pins))
        self.seat_lights = seat_lights
        self.bg_lights = bg_lights
        self.light_length = light_length

    def check_seats(self):
        seated = 0
        light_states = np.ones([self.light_length])
        pin_state = []
        for i, pin in enumerate(self.sensor_pins):
            state = GPIO.input(pin)
            seated += 1 - state
            pin_state.append(1 - state)
            light_states[self.seat_lights[i]] = state
        return seated, light_states, pin_state

class Sound_Manager:
    def __init__(self, filenames):
        self.filenames = filenames
        self.current = None
        self.transition_ms = 0

    def transition_to(self, mode):
        if self.current == self.filenames[mode]:
            return
        if self.current is not None:
            if self.transition_ms <= 0:
                self.transition_ms = max(1, 500 + self.transition_ms)
        else:
            pygame.mixer.music.load(self.filenames[mode])
            pygame.mixer.music.set_volume(0)
            self.transition_ms = -500
            pygame.mixer.music.play(-1, 0)
        self.current = self.filenames[mode]

    def update(self, dt):
        if self.transition_ms > 0:
            self.transition_ms = max(0, self.transition_ms - dt)
            pygame.mixer.music.set_volume(self.transition_ms / 500)
            if self.transition_ms == 0:
                self.transition_ms = -500
                pygame.mixer.music.load(self.current)
                pygame.mixer.music.play(-1, 0)
        elif self.transition_ms < 0:
            self.transition_ms = min(0, self.transition_ms + dt)
            pygame.mixer.music.set_volume(1 + self.transition_ms / 500)


"set up the window"
pygame.init()

#screen = pygame.display.set_mode((WINDOWWIDTH, WINDOWHEIGHT),0,32)
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.display.set_caption('Question of the DAY')
screen.fill((0,0,0))
font = pygame.font.Font('fonts/space_invaders.ttf',42)

"LED SET UPS"
# LED strip configuration:
LED_COUNT = 200        # Number of LED pixels.
#LED_PIN = 18          # GPIO pin connected to the pixels (18 uses PWM!).
LED_PIN = 12        # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10          # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False    # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

"SENSORS SET UP"
sensor_pins = [5, 26, 13, 6, 22, 19]

#Seats and lights assignment and grouping
lights = [[6 - i] + list(range(i*14 + 7, i*14+14+7)) for i in range(7)]
seat_lights = lights[:3] + lights[4:]
bg_lights = lights[3] + [range(15 * 7, 15 * 7 + 88)]

# Main program logic follows:
if __name__ == '__main__':
    # Process arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
    args = parser.parse_args()

    # Create NeoPixel object with appropriate configuration.
    strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
    # Intialize the library (must be called once before other functions).
    strip.begin()

    light_length = 193
    seat_manager = Seat_Manager(sensor_pins, seat_lights, bg_lights, light_length)
    lm = Light_Manager(strip, [
        [np.array([[0, 0, 255], [255, 0, 0], [0, 255, 0]]), 250, 10],
        [np.array([[0, 255, 0], [0, 0, 0]]), 2800, 200],
        [np.array([[0, 0, 255], [0, 128, 255], [0, 255, 0]]), 2800, 200],
        [np.array([[255, 60, 255], [128, 0, 128], [255, 0, 0]]), 2800, 200],
        [np.array([[255, 255, 0], [100, 100, 0], [255, 0, 0]]), 2800, 400],
        [np.array([[0, 0, 128], [128, 0, 128]]), 2800, 400],
        [np.array([[152, 50, 117], [129, 29, 94], [253, 47, 36], [255, 111, 1], [254, 216, 0]]), 5000, 0],
        [np.array([[0, 0, 255], [0, 255, 0]]), 2500, 100],
        [np.array([[245, 200, 0], [240, 50, 240], [230, 130, 0], [0, 240, 0]]), 500, 0],
        ], light_length)
    sm = Sound_Manager(["bg1.ogg", "cv1.ogg", "cv2.ogg", "epl2.ogg", "epl1.ogg", "cfl1.ogg", "blues.ogg", "uptown.ogg", "take.ogg"])
    gm = Game_Manager([
        ["Who do you love?", (3, 3), 2],
        ["What is your dream?", (2, 2), 5],
        ["What are you looking forward to?", (4, 4), 4],
        ["When is the last time you cried?", (5, 5), 0]
        ], lm, sm, seat_manager, 2)
    
    print('Press Ctrl-C to quit.')
    if not args.clear:
        print('Use "-c" argument to clear LEDs on exit')

    try:
        prev_time = time.time_ns()
        while True:
            current_time = time.time_ns()
            dt = (current_time - prev_time) // 1000000
            prev_time += dt * 1000000
            gm.update(dt)

            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    gm.next()
                elif event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                                    
    except KeyboardInterrupt:
        if args.clear:
            for i in range(light_length):
                strip.setPixelColor(i, Color(0, 0, 0))
            strip.show()
            
