import pygame, threading, sys, time, random

# ----------------- Classes -----------------
class TrafficSignal:
    def __init__(self, red, yellow, green, minimum, maximum):
        self.red = red
        self.yellow = yellow
        self.green = green
        self.minimum = minimum
        self.maximum = maximum
        self.signalText = "30"

class Vehicle(pygame.sprite.Sprite):
    def __init__(self, lane, vehicleClass, direction, will_turn):
        pygame.sprite.Sprite.__init__(self)
        self.vehicleClass = vehicleClass
        self.direction = direction
        self.speed = speeds[vehicleClass]
        self.x, self.y = x[direction][lane], y[direction][lane]
        self.crossed = 0
        self.willTurn = will_turn
        self.originalImage = pygame.image.load(f"images/{direction}/{vehicleClass}.png")
        self.currentImage = self.originalImage
        simulation.add(self)

    def move(self):
        # Simplified movement rules
        if self.direction == 'right':
            self.x += self.speed
        elif self.direction == 'left':
            self.x -= self.speed
        elif self.direction == 'down':
            self.y += self.speed
        elif self.direction == 'up':
            self.y -= self.speed

# ----------------- Signal Logic -----------------
def initialize():
    signals.append(TrafficSignal(0, 5, 20, 10, 60))
    signals.append(TrafficSignal(25, 5, 20, 10, 60))
    signals.append(TrafficSignal(30, 5, 20, 10, 60))
    signals.append(TrafficSignal(30, 5, 20, 10, 60))
    repeat()

def repeat():
    global currentGreen, currentYellow, nextGreen
    while(signals[currentGreen].green > 0):
        updateValues()
        time.sleep(1)
    currentYellow = 1
    while(signals[currentGreen].yellow > 0):
        updateValues()
        time.sleep(1)
    currentYellow = 0
    currentGreen = nextGreen
    nextGreen = (currentGreen+1) % noOfSignals
    repeat()

def updateValues():
    for i in range(noOfSignals):
        if i == currentGreen:
            if currentYellow == 0:
                signals[i].green -= 1
            else:
                signals[i].yellow -= 1
        else:
            signals[i].red -= 1

# ----------------- Vehicle Generation -----------------
def generateVehicles():
    while True:
        vehicle_type = random.choice(list(vehicleTypes.values()))
        lane_number = random.randint(0,1)
        direction_number = random.randint(0,3)
        Vehicle(lane_number, vehicle_type, directionNumbers[direction_number], will_turn=0)
        time.sleep(1)

# ----------------- Main Simulation -----------------
class Main:
    thread_init = threading.Thread(target=initialize)
    thread_init.daemon = True
    thread_init.start()

    thread_vehicles = threading.Thread(target=generateVehicles)
    thread_vehicles.daemon = True
    thread_vehicles.start()

    screen = pygame.display.set_mode((1400, 800))
    pygame.display.set_caption("Traffic Simulation")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()

        screen.blit(background, (0,0))
        for signal in signals:
            # Show signals and timers (simplified for case study)
            pass  

        for vehicle in simulation:
            screen.blit(vehicle.currentImage, (vehicle.x, vehicle.y))
            vehicle.move()

        pygame.display.update()
