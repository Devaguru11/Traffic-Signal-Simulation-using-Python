# -*- coding: utf-8 -*-
"""
Adaptive Traffic Signal Simulation (Pygame)
- Picks next green by queue "pressure" (weighted by vehicle service times)
- Sets green time from pressure (clamped to min/max)
- Robust to missing images (draws fallbacks)
"""

import random
import math
import time
import threading
import pygame
import sys
import os

# -----------------------------
# Configuration / Parameters
# -----------------------------
defaultRed = 150
defaultYellow = 5
defaultGreen = 20
defaultMinimum = 10
defaultMaximum = 60

# service-time (sec/vehicle) — used as weights
carTime = 2.0
bikeTime = 1.0
rickshawTime = 2.25
busTime = 2.5
truckTime = 2.5

# simulation timing
noOfSignals = 4
simTime = 300
timeElapsed = 0

# state flags
currentGreen = 0
nextGreen = 1
currentYellow = 0

# speeds (px per tick)
speeds = {'car':4, 'bus':3, 'truck':3, 'rickshaw':4, 'bike':4.5}

# start coordinates
x = {'right':[0,0,0], 'down':[755,727,697], 'left':[1400,1400,1400], 'up':[602,627,657]}
y = {'right':[348,370,398], 'down':[0,0,0], 'left':[498,466,436], 'up':[800,800,800]}

vehicles = {
    'right': {0:[], 1:[], 2:[], 'crossed':0},
    'down':  {0:[], 1:[], 2:[], 'crossed':0},
    'left':  {0:[], 1:[], 2:[], 'crossed':0},
    'up':    {0:[], 1:[], 2:[], 'crossed':0}
}
vehicleTypes = {0:'car', 1:'bus', 2:'truck', 3:'rickshaw', 4:'bike'}
directionNumbers = {0:'right', 1:'down', 2:'left', 3:'up'}

# signal & UI coordinates
signalCoods = [(530,230),(810,230),(810,570),(530,570)]
signalTimerCoods = [(530,210),(810,210),(810,550),(530,550)]
vehicleCountCoods = [(480,210),(880,210),(880,550),(480,550)]
vehicleCountTexts = ["0","0","0","0"]

# stop lines & spacing
stopLines   = {'right': 590, 'down': 330, 'left': 800, 'up': 535}
defaultStop = {'right': 580, 'down': 320, 'left': 810, 'up': 545}
stops       = {'right': [580,580,580], 'down': [320,320,320], 'left': [810,810,810], 'up': [545,545,545]}
gap, gap2 = 15, 15

mid = {'right': {'x':705, 'y':445}, 'down': {'x':695, 'y':450}, 'left': {'x':695, 'y':425}, 'up': {'x':695, 'y':400}}
rotationAngle = 3

# pygame init
pygame.init()
simulation = pygame.sprite.Group()

# Colors
BLACK=(0,0,0); WHITE=(255,255,255); GREY=(90,90,90); ROAD=(40,40,40)
RED=(200,0,0); YELLOW=(220,220,0); GREEN=(0,180,0); BLUE=(70,130,180)

# -----------------------------
# Utilities: robust image loading
# -----------------------------
def load_image_safe(path, fallback_size=(50,25), fill=(180,180,180)):
    """Try to load an image; if missing, return a colored Surface of fallback_size"""
    try:
        img = pygame.image.load(path).convert_alpha()
        return img
    except Exception:
        surf = pygame.Surface(fallback_size, pygame.SRCALPHA)
        surf.fill(fill)
        pygame.draw.rect(surf, (0,0,0), surf.get_rect(), 2)
        return surf

def vehicle_fallback_size(vclass):
    # rough sizes (w,h)
    return {
        'bike':(35,15),
        'rickshaw':(40,22),
        'car':(50,25),
        'bus':(80,30),
        'truck':(90,35),
    }.get(vclass, (50,25))

# -----------------------------
# Data classes
# -----------------------------
class TrafficSignal:
    def __init__(self, red, yellow, green, minimum, maximum):
        self.red = red
        self.yellow = yellow
        self.green = green
        self.minimum = minimum
        self.maximum = maximum
        self.signalText = "0"
        self.totalGreenTime = 0

signals = []

class Vehicle(pygame.sprite.Sprite):
    def __init__(self, lane, vehicleClass, direction_number, direction, will_turn):
        super().__init__()
        self.lane = lane
        self.vehicleClass = vehicleClass
        self.speed = speeds[vehicleClass]
        self.direction_number = direction_number
        self.direction = direction
        self.x = x[direction][lane]
        self.y = y[direction][lane]
        self.crossed = 0
        self.willTurn = will_turn
        self.turned = 0
        self.rotateAngle = 0

        # choose vehicle image (robust)
        vpath = f"images/{direction}/{vehicleClass}.png"
        self.originalImage = load_image_safe(vpath, vehicle_fallback_size(vehicleClass))
        self.currentImage = self.originalImage.copy()

        vehicles[direction][lane].append(self)
        self.index = len(vehicles[direction][lane]) - 1

        # stop placement
        if direction=='right':
            if len(vehicles[direction][lane])>1 and vehicles[direction][lane][self.index-1].crossed==0:
                self.stop = (vehicles[direction][lane][self.index-1].stop
                             - vehicles[direction][lane][self.index-1].currentImage.get_rect().width - gap)
            else:
                self.stop = defaultStop[direction]
            temp = self.currentImage.get_rect().width + gap
            x[direction][lane] -= temp; stops[direction][lane] -= temp

        elif direction=='left':
            if len(vehicles[direction][lane])>1 and vehicles[direction][lane][self.index-1].crossed==0:
                self.stop = (vehicles[direction][lane][self.index-1].stop
                             + vehicles[direction][lane][self.index-1].currentImage.get_rect().width + gap)
            else:
                self.stop = defaultStop[direction]
            temp = self.currentImage.get_rect().width + gap
            x[direction][lane] += temp; stops[direction][lane] += temp

        elif direction=='down':
            if len(vehicles[direction][lane])>1 and vehicles[direction][lane][self.index-1].crossed==0:
                self.stop = (vehicles[direction][lane][self.index-1].stop
                             - vehicles[direction][lane][self.index-1].currentImage.get_rect().height - gap)
            else:
                self.stop = defaultStop[direction]
            temp = self.currentImage.get_rect().height + gap
            y[direction][lane] -= temp; stops[direction][lane] -= temp

        elif direction=='up':
            if len(vehicles[direction][lane])>1 and vehicles[direction][lane][self.index-1].crossed==0:
                self.stop = (vehicles[direction][lane][self.index-1].stop
                             + vehicles[direction][lane][self.index-1].currentImage.get_rect().height + gap)
            else:
                self.stop = defaultStop[direction]
            temp = self.currentImage.get_rect().height + gap
            y[direction][lane] += temp; stops[direction][lane] += temp

        simulation.add(self)

    def move(self):
        global currentGreen, currentYellow
        if self.direction=='right':
            if self.crossed==0 and self.x+self.currentImage.get_rect().width>stopLines[self.direction]:
                self.crossed=1; vehicles[self.direction]['crossed']+=1
            if self.willTurn==1:
                if self.crossed==0 or self.x+self.currentImage.get_rect().width<mid[self.direction]['x']:
                    if ((self.x+self.currentImage.get_rect().width<=self.stop or (currentGreen==0 and currentYellow==0) or self.crossed==1) and
                        (self.index==0 or self.x+self.currentImage.get_rect().width<(vehicles[self.direction][self.lane][self.index-1].x-gap2) or
                         vehicles[self.direction][self.lane][self.index-1].turned==1)):
                        self.x += self.speed
                else:
                    if self.turned==0:
                        self.rotateAngle += rotationAngle
                        self.currentImage = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                        self.x += 2; self.y += 1.8
                        if self.rotateAngle>=90:
                            self.turned=1
                    else:
                        if (self.index==0 or
                            self.y+self.currentImage.get_rect().height<(vehicles[self.direction][self.lane][self.index-1].y-gap2) or
                            self.x+self.currentImage.get_rect().width<(vehicles[self.direction][self.lane][self.index-1].x-gap2)):
                            self.y += self.speed
            else:
                if ((self.x+self.currentImage.get_rect().width<=self.stop or self.crossed==1 or (currentGreen==0 and currentYellow==0)) and
                    (self.index==0 or self.x+self.currentImage.get_rect().width<(vehicles[self.direction][self.lane][self.index-1].x-gap2) or
                     vehicles[self.direction][self.lane][self.index-1].turned==1)):
                    self.x += self.speed

        elif self.direction=='down':
            if self.crossed==0 and self.y+self.currentImage.get_rect().height>stopLines[self.direction]:
                self.crossed=1; vehicles[self.direction]['crossed']+=1
            if self.willTurn==1:
                if self.crossed==0 or self.y+self.currentImage.get_rect().height<mid[self.direction]['y']:
                    if ((self.y+self.currentImage.get_rect().height<=self.stop or (currentGreen==1 and currentYellow==0) or self.crossed==1) and
                        (self.index==0 or self.y+self.currentImage.get_rect().height<(vehicles[self.direction][self.lane][self.index-1].y-gap2) or
                         vehicles[self.direction][self.lane][self.index-1].turned==1)):
                        self.y += self.speed
                else:
                    if self.turned==0:
                        self.rotateAngle += rotationAngle
                        self.currentImage = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                        self.x -= 2.5; self.y += 2
                        if self.rotateAngle>=90:
                            self.turned=1
                    else:
                        if (self.index==0 or
                            self.x>(vehicles[self.direction][self.lane][self.index-1].x + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().width + gap2) or
                            self.y<(vehicles[self.direction][self.lane][self.index-1].y - gap2)):
                            self.x -= self.speed
            else:
                if ((self.y+self.currentImage.get_rect().height<=self.stop or self.crossed==1 or (currentGreen==1 and currentYellow==0)) and
                    (self.index==0 or self.y+self.currentImage.get_rect().height<(vehicles[self.direction][self.lane][self.index-1].y-gap2) or
                     vehicles[self.direction][self.lane][self.index-1].turned==1)):
                    self.y += self.speed

        elif self.direction=='left':
            if self.crossed==0 and self.x<stopLines[self.direction]:
                self.crossed=1; vehicles[self.direction]['crossed']+=1
            if self.willTurn==1:
                if self.crossed==0 or self.x>mid[self.direction]['x']:
                    if ((self.x>=self.stop or (currentGreen==2 and currentYellow==0) or self.crossed==1) and
                        (self.index==0 or self.x>(vehicles[self.direction][self.lane][self.index-1].x + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().width + gap2) or
                         vehicles[self.direction][self.lane][self.index-1].turned==1)):
                        self.x -= self.speed
                else:
                    if self.turned==0:
                        self.rotateAngle += rotationAngle
                        self.currentImage = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                        self.x -= 1.8; self.y -= 2.5
                        if self.rotateAngle>=90:
                            self.turned=1
                    else:
                        if (self.index==0 or
                            self.y>(vehicles[self.direction][self.lane][self.index-1].y + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().height + gap2) or
                            self.x>(vehicles[self.direction][self.lane][self.index-1].x + gap2)):
                            self.y -= self.speed
            else:
                if ((self.x>=self.stop or self.crossed==1 or (currentGreen==2 and currentYellow==0)) and
                    (self.index==0 or self.x>(vehicles[self.direction][self.lane][self.index-1].x + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().width + gap2) or
                     vehicles[self.direction][self.lane][self.index-1].turned==1)):
                    self.x -= self.speed

        elif self.direction=='up':
            if self.crossed==0 and self.y<stopLines[self.direction]:
                self.crossed=1; vehicles[self.direction]['crossed']+=1
            if self.willTurn==1:
                if self.crossed==0 or self.y>mid[self.direction]['y']:
                    if ((self.y>=self.stop or (currentGreen==3 and currentYellow==0) or self.crossed==1) and
                        (self.index==0 or self.y>(vehicles[self.direction][self.lane][self.index-1].y + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().height + gap2) or
                         vehicles[self.direction][self.lane][self.index-1].turned==1)):
                        self.y -= self.speed
                else:
                    if self.turned==0:
                        self.rotateAngle += rotationAngle
                        self.currentImage = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                        self.x += 1; self.y -= 1
                        if self.rotateAngle>=90:
                            self.turned=1
                    else:
                        if (self.index==0 or
                            self.x<(vehicles[self.direction][self.lane][self.index-1].x - vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().width - gap2) or
                            self.y>(vehicles[self.direction][self.lane][self.index-1].y + gap2)):
                            self.x += self.speed

# -----------------------------
# Adaptive control helpers
# -----------------------------
def weighted_pressure_for(direction):
    """Sum weighted counts of NOT-YET-CROSSED vehicles waiting on an approach."""
    counts = {'car':0,'bus':0,'truck':0,'rickshaw':0,'bike':0}
    # Lane 0 = bikes-only in your generator; lanes 1,2 = mixed
    for lane in (0,1,2):
        for v in vehicles[direction][lane]:
            if v.crossed==0:  # still waiting upstream of the stop line
                counts[v.vehicleClass] += 1
    # weighted by service time (approx how long each takes to serve)
    pressure = (counts['car']*carTime + counts['bus']*busTime + counts['truck']*truckTime +
                counts['rickshaw']*rickshawTime + counts['bike']*bikeTime)
    return pressure, counts

def choose_next_signal(current_idx):
    """Pick approach with highest pressure (not equal to current). Break ties by longest waiting (red)."""
    best_idx = None
    best_pressure = -1.0
    best_red = -1
    for i in range(noOfSignals):
        if i == current_idx:
            continue
        d = directionNumbers[i]
        pressure, _ = weighted_pressure_for(d)
        red_time = signals[i].red
        if (pressure > best_pressure) or (pressure == best_pressure and red_time > best_red):
            best_pressure = pressure
            best_red = red_time
            best_idx = i
    # fallback: if all zero, still pick round-robin
    if best_idx is None:
        best_idx = (current_idx + 1) % noOfSignals
    return best_idx, best_pressure

def green_time_from_pressure(pressure, lanes=2):
    """Compute green time from pressure; clamp to [defaultMinimum, defaultMaximum]."""
    if pressure <= 0:
        return defaultMinimum
    g = math.ceil(pressure / (lanes + 1))
    g = max(defaultMinimum, min(defaultMaximum, g))
    return g

# -----------------------------
# Initialization & timers
# -----------------------------
def initialize():
    # First signal starts immediately
    ts1 = TrafficSignal(0, defaultYellow, defaultGreen, defaultMinimum, defaultMaximum)
    signals.append(ts1)
    # Others start red = current green + yellow
    base_red = ts1.yellow + ts1.green
    ts2 = TrafficSignal(base_red, defaultYellow, defaultGreen, defaultMinimum, defaultMaximum)
    ts3 = TrafficSignal(base_red, defaultYellow, defaultGreen, defaultMinimum, defaultMaximum)
    ts4 = TrafficSignal(base_red, defaultYellow, defaultGreen, defaultMinimum, defaultMaximum)
    signals.extend([ts2, ts3, ts4])
    repeat()

def printStatus():
    for i in range(noOfSignals):
        label = "GREEN" if (i==currentGreen and currentYellow==0) else ("YELLOW" if (i==currentGreen and currentYellow==1) else "RED  ")
        s = signals[i]
        print(f"{label} TS {i+1} -> r: {s.red:>3}  y: {s.yellow:>3}  g: {s.green:>3}")
    print()

def updateValues():
    # Called roughly once per simulated second by repeat()
    for i in range(noOfSignals):
        if i == currentGreen:
            if currentYellow == 0:
                signals[i].green -= 1
                signals[i].totalGreenTime += 1
            else:
                signals[i].yellow -= 1
        else:
            signals[i].red -= 1
            if signals[i].red < 0:
                signals[i].red = 0

def generateVehicles():
    while True:
        vehicle_type = random.randint(0,4)
        if vehicle_type == 4:
            lane_number = 0
        else:
            lane_number = random.randint(0,1) + 1
        will_turn = 0
        if lane_number == 2:
            will_turn = 1 if random.randint(0,4) <= 2 else 0
        temp = random.randint(0,999)
        a = [400,800,900,1000]
        if temp < a[0]:
            direction_number = 0
        elif temp < a[1]:
            direction_number = 1
        elif temp < a[2]:
            direction_number = 2
        else:
            direction_number = 3
        Vehicle(lane_number, vehicleTypes[vehicle_type], direction_number, directionNumbers[direction_number], will_turn)
        time.sleep(0.65)

def simulationTime():
    global timeElapsed, simTime
    while True:
        timeElapsed += 1
        time.sleep(0.66)
        if timeElapsed == simTime:
            totalVehicles = 0
            print('Lane-wise Vehicle Counts')
            for i in range(noOfSignals):
                print('Lane',i+1,':',vehicles[directionNumbers[i]]['crossed'])
                totalVehicles += vehicles[directionNumbers[i]]['crossed']
            print('Total vehicles passed: ',totalVehicles)
            print('Total time passed: ',timeElapsed)
            print('No. of vehicles passed per unit time: ',(float(totalVehicles)/float(timeElapsed)))
            os._exit(0)

def repeat():
    """Main phase controller: green -> yellow -> pick next by pressure -> set times -> recurse."""
    global currentGreen, currentYellow, nextGreen
    while signals[currentGreen].green > 0:
        printStatus()
        updateValues()
        time.sleep(0.84)

    # start yellow
    currentYellow = 1
    vehicleCountTexts[currentGreen] = "0"
    # reset lane stops for current approach
    for i in range(0,3):
        stops[directionNumbers[currentGreen]][i] = defaultStop[directionNumbers[currentGreen]]
        for vehicle in vehicles[directionNumbers[currentGreen]][i]:
            vehicle.stop = defaultStop[directionNumbers[currentGreen]]

    while signals[currentGreen].yellow > 0:
        printStatus()
        updateValues()
        time.sleep(0.66)
    currentYellow = 0

    # reset the just-finished approach to defaults
    signals[currentGreen].green  = defaultGreen
    signals[currentGreen].yellow = defaultYellow
    signals[currentGreen].red    = defaultRed

    # ---- Adaptive choice here ----
    chosen_idx, pressure = choose_next_signal(currentGreen)
    nextGreen = chosen_idx
    # compute green time for the chosen approach
    gtime = green_time_from_pressure(pressure, lanes=2)
    signals[nextGreen].green = gtime

    # set its red to the upcoming (current's) yellow+green; other reds just continue counting down
    signals[nextGreen].red = signals[currentGreen].yellow + signals[currentGreen].green

    # switch to next
    currentGreen = nextGreen
    # ensure some red value for the new "next of next" if you want, but not necessary for logic

    # loop again
    repeat()

# -----------------------------
# Minimal UI (no external assets required)
# -----------------------------
class Main:
    # background load (safe)
    try:
        background = pygame.image.load('images/mod_int.png').convert()
    except Exception:
        background = None

    # start threads
    thread_time = threading.Thread(target=simulationTime, daemon=True)
    thread_time.start()
    thread_init = threading.Thread(target=initialize, daemon=True)
    thread_init.start()
    thread_gen = threading.Thread(target=generateVehicles, daemon=True)
    thread_gen.start()

    # display
    screenWidth, screenHeight = 1400, 800
    screen = pygame.display.set_mode((screenWidth, screenHeight))
    pygame.display.set_caption("SIMULATION (Adaptive)")

    # fonts
    font = pygame.font.Font(None, 30)
    big  = pygame.font.Font(None, 42)

    clock = pygame.time.Clock()

    def draw_intersection(self):
        if self.background:
            self.screen.blit(self.background,(0,0))
            return
        # simple drawn intersection if no bg image
        self.screen.fill((34, 139, 34))  # grass
        # roads
        pygame.draw.rect(self.screen, ROAD, (0,330,1400,140))     # horizontal
        pygame.draw.rect(self.screen, ROAD, (630,0,140,800))      # vertical
        # center box
        pygame.draw.rect(self.screen, GREY, (610,310,180,180), 3)

    def draw_signal_icon(self, idx):
        # Draw a simple 3-light box at signalCoods[idx] with current state
        x,y = signalCoods[idx]
        box = pygame.Rect(x, y, 60, 160)
        pygame.draw.rect(self.screen, GREY, box, border_radius=10)
        # determine color on/off
        isCurrent = (idx == currentGreen)
        if isCurrent and currentYellow==0:
            state = 'G'
        elif isCurrent and currentYellow==1:
            state = 'Y'
        else:
            state = 'R'
        # lights
        pygame.draw.circle(self.screen, RED if state=='R' else (100,0,0), (x+30,y+30), 20)
        pygame.draw.circle(self.screen, YELLOW if state=='Y' else (90,90,0), (x+30,y+80), 20)
        pygame.draw.circle(self.screen, GREEN if state=='G' else (0,80,0), (x+30,y+130), 20)

    def run(self):
        global currentGreen
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()

            self.draw_intersection()

            # signal boxes and timers
            for i in range(noOfSignals):
                self.draw_signal_icon(i)
                # timer text
                s = signals[i]
                if i==currentGreen:
                    txt = s.yellow if currentYellow else s.green
                else:
                    # show small number when close to change, else ---
                    txt = s.red if s.red<=10 else "---"
                t_surface = self.font.render(str(txt), True, WHITE, BLACK)
                self.screen.blit(t_surface, signalTimerCoods[i])

                # crossed counts
                displayText = vehicles[directionNumbers[i]]['crossed']
                vehicleCountTexts[i] = self.font.render(str(displayText), True, BLACK, WHITE)
                self.screen.blit(vehicleCountTexts[i], vehicleCountCoods[i])

            timeElapsedText = self.font.render(("Time Elapsed: "+str(timeElapsed)), True, BLACK, WHITE)
            self.screen.blit(timeElapsedText,(1100,50))

            # draw vehicles
            for v in simulation:
                self.screen.blit(v.currentImage, (v.x, v.y))
                v.move()

            # HUD: which direction is green & its computed green time
            dname = directionNumbers[currentGreen].upper()
            hud = self.big.render(f"GREEN: {dname}", True, BLUE)
            self.screen.blit(hud, (50, 40))

            pygame.display.update()
            self.clock.tick(120)

Main().run()
