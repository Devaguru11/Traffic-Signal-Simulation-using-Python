# 4-WAY JUNCTION TRAFFIC SIMULATION WITH DYNAMIC NEXT-GREEN SELECTION
# Uses the approach with the most waiting vehicles to pick the next green.

import random
import math
import time
import threading
import pygame
import sys
import os

# ----------------------------
# Default signal timing bounds
# ----------------------------
defaultRed = 150
defaultYellow = 5
defaultGreen = 20
defaultMinimum = 10
defaultMaximum = 60

signals = []
noOfSignals = 4
simTime = 300
timeElapsed = 0

currentGreen = 0        # which signal is currently green (0: right, 1: down, 2: left, 3: up)
nextGreen = None        # will be chosen dynamically
currentYellow = 0

# ----------------------------
# Average discharge times (s)
# ----------------------------
carTime = 2
bikeTime = 1
rickshawTime = 2.25
busTime = 2.5
truckTime = 2.5

# Lane config
noOfCars = 0
noOfBikes = 0
noOfBuses = 0
noOfTrucks = 0
noOfRickshaws = 0
noOfLanes = 2          # 2 main lanes + 1 bike lane (0)

# When to prepare next signal during current green
detectionTime = 5

# ----------------------------
# Speeds and coordinates
# ----------------------------
speeds = {'car':2.25, 'bus':1.8, 'truck':1.8, 'rickshaw':2, 'bike':2.5}

# Start coordinates (top-left image origin)
x = {'right':[0,0,0], 'down':[271,254,240], 'left':[1400,1400,1400], 'up':[200,210,225]}
y = {'right':[223,232,250], 'down':[0,0,0], 'left':[300,285,268], 'up':[800,800,800]}

vehicles = {
    'right': {0:[], 1:[], 2:[], 'crossed':0},
    'down' : {0:[], 1:[], 2:[], 'crossed':0},
    'left' : {0:[], 1:[], 2:[], 'crossed':0},
    'up'   : {0:[], 1:[], 2:[], 'crossed':0}
}
vehicleTypes = {0:'car', 1:'bus', 2:'truck', 3:'rickshaw', 4:'bike'}
directionNumbers = {0:'right', 1:'down', 2:'left', 3:'up'}

# Signal, timer, and count UI coordinates
signalCoods = [(590,340),(675,260),(770,430),(675,510)]
signalTimerCoods = [(530,210),(810,210),(810,550),(530,550)]
vehicleCountCoods = [(480,210),(880,210),(880,550),(480,550)]
vehicleCountTexts = ["0", "0", "0", "0"]

# Stop lines and stops (match defaults per direction)
stopLines   = {'right': 210, 'down': 220, 'left': 270, 'up': 307}
defaultStop = {'right': 200, 'down': 210, 'left': 280, 'up': 317}
stops = {
    'right': [defaultStop['right']]*3,
    'down' : [defaultStop['down']]*3,
    'left' : [defaultStop['left']]*3,
    'up'   : [defaultStop['up']]*3
}

rotationAngle = 3   # (kept for compatibility; turning disabled)
gap  = 7
gap2 = 7

pygame.init()
simulation = pygame.sprite.Group()

# ----------------------------
# Traffic signal / vehicle
# ----------------------------
class TrafficSignal:
    def __init__(self, red, yellow, green, minimum, maximum):
        self.red = red
        self.yellow = yellow
        self.green = green
        self.minimum = minimum
        self.maximum = maximum
        self.signalText = "30"
        self.totalGreenTime = 0

class Vehicle(pygame.sprite.Sprite):
    def __init__(self, lane, vehicleClass, direction_number, direction, will_turn):
        pygame.sprite.Sprite.__init__(self)
        self.lane = lane
        self.vehicleClass = vehicleClass
        self.speed = speeds[vehicleClass]
        self.direction_number = direction_number
        self.direction = direction
        self.x = x[direction][lane]
        self.y = y[direction][lane]
        self.crossed = 0
        self.willTurn = 0         # turning disabled for 4-way straight layout
        self.turned = 0
        self.rotateAngle = 0

        vehicles[direction][lane].append(self)
        self.index = len(vehicles[direction][lane]) - 1

        path = f"images/{direction}/{vehicleClass}.png"
        self.originalImage = pygame.image.load(path)
        self.currentImage = pygame.image.load(path)

        # Place and set individual stop position based on the car in front
        if direction == 'right':
            if len(vehicles[direction][lane]) > 1 and vehicles[direction][lane][self.index-1].crossed == 0:
                self.stop = vehicles[direction][lane][self.index-1].stop - vehicles[direction][lane][self.index-1].currentImage.get_rect().width - gap
            else:
                self.stop = defaultStop[direction]
            temp = self.currentImage.get_rect().width + gap
            x[direction][lane] -= temp
            stops[direction][lane] -= temp

        elif direction == 'left':
            if len(vehicles[direction][lane]) > 1 and vehicles[direction][lane][self.index-1].crossed == 0:
                self.stop = vehicles[direction][lane][self.index-1].stop + vehicles[direction][lane][self.index-1].currentImage.get_rect().width + gap
            else:
                self.stop = defaultStop[direction]
            temp = self.currentImage.get_rect().width + gap
            x[direction][lane] += temp
            stops[direction][lane] += temp

        elif direction == 'down':
            if len(vehicles[direction][lane]) > 1 and vehicles[direction][lane][self.index-1].crossed == 0:
                self.stop = vehicles[direction][lane][self.index-1].stop - vehicles[direction][lane][self.index-1].currentImage.get_rect().height - gap
            else:
                self.stop = defaultStop[direction]
            temp = self.currentImage.get_rect().height + gap
            y[direction][lane] -= temp
            stops[direction][lane] -= temp

        elif direction == 'up':
            if len(vehicles[direction][lane]) > 1 and vehicles[direction][lane][self.index-1].crossed == 0:
                self.stop = vehicles[direction][lane][self.index-1].stop + vehicles[direction][lane][self.index-1].currentImage.get_rect().height + gap
            else:
                self.stop = defaultStop[direction]
            temp = self.currentImage.get_rect().height + gap
            y[direction][lane] += temp
            stops[direction][lane] += temp

        simulation.add(self)

    def render(self, screen):
        screen.blit(self.currentImage, (self.x, self.y))

    def move(self):
        # STRAIGHT-THROUGH ONLY (no turns)
        if self.direction == 'right':
            if self.crossed == 0 and self.x + self.currentImage.get_rect().width > stopLines[self.direction]:
                self.crossed = 1
                vehicles[self.direction]['crossed'] += 1

            if ((self.x + self.currentImage.get_rect().width <= self.stop or self.crossed == 1 or (currentGreen == 0 and currentYellow == 0)) and
                (self.index == 0 or self.x + self.currentImage.get_rect().width < (vehicles[self.direction][self.lane][self.index-1].x - gap2))):
                self.x += self.speed

        elif self.direction == 'down':
            if self.crossed == 0 and self.y + self.currentImage.get_rect().height > stopLines[self.direction]:
                self.crossed = 1
                vehicles[self.direction]['crossed'] += 1

            if ((self.y + self.currentImage.get_rect().height <= self.stop or self.crossed == 1 or (currentGreen == 1 and currentYellow == 0)) and
                (self.index == 0 or self.y + self.currentImage.get_rect().height < (vehicles[self.direction][self.lane][self.index-1].y - gap2))):
                self.y += self.speed

        elif self.direction == 'left':
            if self.crossed == 0 and self.x < stopLines[self.direction]:
                self.crossed = 1
                vehicles[self.direction]['crossed'] += 1

            if ((self.x >= self.stop or self.crossed == 1 or (currentGreen == 2 and currentYellow == 0)) and
                (self.index == 0 or self.x > (vehicles[self.direction][self.lane][self.index-1].x + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().width + gap2))):
                self.x -= self.speed

        elif self.direction == 'up':
            if self.crossed == 0 and self.y < stopLines[self.direction]:
                self.crossed = 1
                vehicles[self.direction]['crossed'] += 1

            if ((self.y >= self.stop or self.crossed == 1 or (currentGreen == 3 and currentYellow == 0)) and
                (self.index == 0 or self.y > (vehicles[self.direction][self.lane][self.index-1].y + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().height + gap2))):
                self.y -= self.speed

# ----------------------------
# Helpers: queue counting & next-green selection
# ----------------------------
def count_waiting(direction_key):
    """Count vehicles that haven't crossed the stop line yet for a direction."""
    count = 0
    for lane_id in (0, 1, 2):
        for v in vehicles[direction_key][lane_id]:
            if v.crossed == 0:
                count += 1
    return count

def estimate_green_time(direction_key):
    """Estimate green time from weighted vehicle classes waiting at the stop."""
    nCars = nBuses = nTrucks = nRick = nBikes = 0
    for lane_id in (0, 1, 2):
        for v in vehicles[direction_key][lane_id]:
            if v.crossed == 0:
                if v.vehicleClass == 'car':
                    nCars += 1
                elif v.vehicleClass == 'bus':
                    nBuses += 1
                elif v.vehicleClass == 'truck':
                    nTrucks += 1
                elif v.vehicleClass == 'rickshaw':
                    nRick += 1
                elif v.vehicleClass == 'bike':
                    nBikes += 1

    g = math.ceil(((nCars*carTime) + (nRick*rickshawTime) + (nBuses*busTime) + (nTrucks*truckTime) + (nBikes*bikeTime)) / (noOfLanes + 1))
    if g < defaultMinimum: g = defaultMinimum
    if g > defaultMaximum: g = defaultMaximum
    return g

def choose_next_green_index(curr_idx):
    """Pick the next approach with the most waiting vehicles (tie-break clockwise)."""
    counts = []
    for i in range(noOfSignals):
        dir_key = directionNumbers[i]
        counts.append(count_waiting(dir_key) if i != curr_idx else -1)  # exclude current

    max_wait = max(counts)
    if max_wait <= 0:
        # If nobody is waiting, go round-robin to keep things moving
        return (curr_idx + 1) % noOfSignals

    # Tie-break clockwise from current
    for step in range(1, noOfSignals):
        idx = (curr_idx + step) % noOfSignals
        if counts[idx] == max_wait:
            return idx
    return (curr_idx + 1) % noOfSignals  # fallback

# ----------------------------
# Init & timing logic
# ----------------------------
def initialize():
    ts1 = TrafficSignal(0, defaultYellow, defaultGreen, defaultMinimum, defaultMaximum)
    signals.append(ts1)
    ts2 = TrafficSignal(ts1.red + ts1.yellow + ts1.green, defaultYellow, defaultGreen, defaultMinimum, defaultMaximum)
    signals.append(ts2)
    ts3 = TrafficSignal(defaultRed, defaultYellow, defaultGreen, defaultMinimum, defaultMaximum)
    signals.append(ts3)
    ts4 = TrafficSignal(defaultRed, defaultYellow, defaultGreen, defaultMinimum, defaultMaximum)
    signals.append(ts4)
    repeat()

def setTime():
    """Prepare nextGreen and assign its green based on current queues."""
    global nextGreen
    # decide which direction should be next
    chosen = choose_next_green_index(currentGreen)
    nextGreen = chosen
    # compute its green time
    dir_key = directionNumbers[chosen]
    greenTime = estimate_green_time(dir_key)
    signals[chosen].green = greenTime
    print(f'[Prepare] Next green -> TS {chosen+1} ({dir_key}), green={greenTime}s')

def repeat():
    global currentGreen, currentYellow, nextGreen
    prepared = False

    while signals[currentGreen].green > 0:
        printStatus()
        updateValues()

        # Prepare next choice when current green reaches detectionTime (once)
        if signals[currentGreen].green == detectionTime and not prepared:
            setTime()
            prepared = True

        time.sleep(1)

    currentYellow = 1
    vehicleCountTexts[currentGreen] = "0"

    # reset per-lane stops for current direction
    for i in range(0, 3):
        stops[directionNumbers[currentGreen]][i] = defaultStop[directionNumbers[currentGreen]]
        for vehicle in vehicles[directionNumbers[currentGreen]][i]:
            vehicle.stop = defaultStop[directionNumbers[currentGreen]]

    while signals[currentGreen].yellow > 0:
        printStatus()
        updateValues()
        time.sleep(1)

    currentYellow = 0

    # Reset old current to defaults for next cycles
    signals[currentGreen].green = defaultGreen
    signals[currentGreen].yellow = defaultYellow
    signals[currentGreen].red = defaultRed

    # If we didn't prepare (short green), choose now
    if nextGreen is None:
        setTime()

    # Switch to prepared choice
    currentGreen = nextGreen
    nextGreen = None

    # (Optional) set a hint red for fairness display; otherwise leave defaults
    # Here we set the "future next" red to current's cycle length for visual cue
    future_next = (currentGreen + 1) % noOfSignals
    signals[future_next].red = signals[currentGreen].yellow + signals[currentGreen].green

    repeat()

def printStatus():
    for i in range(0, noOfSignals):
        if i == currentGreen:
            if currentYellow == 0:
                print(" GREEN TS", i+1, "-> r:", signals[i].red, " y:", signals[i].yellow, " g:", signals[i].green)
            else:
                print("YELLOW TS", i+1, "-> r:", signals[i].red, " y:", signals[i].yellow, " g:", signals[i].green)
        else:
            print("   RED TS", i+1, "-> r:", signals[i].red, " y:", signals[i].yellow, " g:", signals[i].green)
    print()

def updateValues():
    for i in range(0, noOfSignals):
        if i == currentGreen:
            if currentYellow == 0:
                signals[i].green -= 1
                signals[i].totalGreenTime += 1
            else:
                signals[i].yellow -= 1
        else:
            signals[i].red -= 1

# ----------------------------
# Vehicle generation & sim time
# ----------------------------
def generateVehicles():
    while True:
        vehicle_type = random.randint(0,4)
        if vehicle_type == 4:
            lane_number = 0
        else:
            lane_number = random.randint(0,1) + 1

        temp = random.randint(0,999)
        direction_number = 0
        a = [400,800,900,1000]
        if temp < a[0]:
            direction_number = 0
        elif temp < a[1]:
            direction_number = 1
        elif temp < a[2]:
            direction_number = 2
        elif temp < a[3]:
            direction_number = 3

        Vehicle(lane_number, vehicleTypes[vehicle_type], direction_number, directionNumbers[direction_number], 0)
        time.sleep(0.25)

def simulationTime():
    global timeElapsed, simTime
    while True:
        timeElapsed += 1
        time.sleep(1)
        if timeElapsed == simTime:
            totalVehicles = 0
            print('Lane-wise Vehicle Counts')
            for i in range(noOfSignals):
                print('Lane', i+1, ':', vehicles[directionNumbers[i]]['crossed'])
                totalVehicles += vehicles[directionNumbers[i]]['crossed']
            print('Total vehicles passed: ', totalVehicles)
            print('Total time passed: ', timeElapsed)
            print('No. of vehicles passed per unit time: ', (float(totalVehicles)/float(timeElapsed)))
            os._exit(1)

# ----------------------------
# Main loop / Pygame
# ----------------------------
class Main:
    thread4 = threading.Thread(name="simulationTime", target=simulationTime, args=())
    thread4.daemon = True
    thread4.start()

    thread2 = threading.Thread(name="initialization", target=initialize, args=())    # initialization
    thread2.daemon = True
    thread2.start()

    black = (0, 0, 0)
    white = (255, 255, 255)

    screenWidth = 1400
    screenHeight = 800
    screenSize = (screenWidth, screenHeight)

    background = pygame.image.load('first.png')

    screen = pygame.display.set_mode(screenSize)
    pygame.display.set_caption("SIMULATION")

    redSignal = pygame.image.load('images/signals/red.png')
    yellowSignal = pygame.image.load('images/signals/yellow.png')
    greenSignal = pygame.image.load('images/signals/green.png')
    font = pygame.font.Font(None, 30)

    thread3 = threading.Thread(name="generateVehicles", target=generateVehicles, args=())
    thread3.daemon = True
    thread3.start()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()

        screen.blit(background, (0, 0))

        # Draw signals and texts
        for i in range(0, noOfSignals):
            if i == currentGreen:
                if currentYellow == 1:
                    signals[i].signalText = "STOP" if signals[i].yellow == 0 else signals[i].yellow
                    screen.blit(yellowSignal, signalCoods[i])
                else:
                    signals[i].signalText = "SLOW" if signals[i].green == 0 else signals[i].green
                    screen.blit(greenSignal, signalCoods[i])
            else:
                if signals[i].red <= 10:
                    signals[i].signalText = "GO" if signals[i].red == 0 else signals[i].red
                else:
                    signals[i].signalText = "---"
                screen.blit(redSignal, signalCoods[i])

        signalTexts = ["","","",""]
        for i in range(0, noOfSignals):
            signalTexts[i] = font.render(str(signals[i].signalText), True, white, black)
            screen.blit(signalTexts[i], signalTimerCoods[i])
            displayText = vehicles[directionNumbers[i]]['crossed']
            vehicleCountTexts[i] = font.render(str(displayText), True, black, white)
            screen.blit(vehicleCountTexts[i], vehicleCountCoods[i])

        timeElapsedText = font.render(("Time Elapsed: " + str(timeElapsed)), True, black, white)
        screen.blit(timeElapsedText, (1100, 50))

        # Vehicles
        for vehicle in simulation:
            screen.blit(vehicle.currentImage, [vehicle.x, vehicle.y])
            vehicle.move()

        pygame.display.update()

Main()
