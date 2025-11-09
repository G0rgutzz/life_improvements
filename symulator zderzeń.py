import pygame
import random
import math
import sys

# Stałe
WIDTH, HEIGHT = 800, 600  # size of the window
PARTICLE_RADIUS = 5  # Particle radius [px]
DT = 1.0  # time delta [s]
CELL_SIZE = 4 * PARTICLE_RADIUS  # cell size = 2* particle diameter for optimal results
GRID_W = (WIDTH  + CELL_SIZE - 1) // CELL_SIZE
GRID_H = (HEIGHT + CELL_SIZE - 1) // CELL_SIZE

class Particle:
    def __init__(self, x, y, vx, vy):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy

    def update_position(self): # changing position s=vt
        self.x += self.vx * DT
        self.y += self.vy * DT

    def check_walls(self): # bouncing off the walls
        if self.x - PARTICLE_RADIUS < 0 or self.x + PARTICLE_RADIUS > WIDTH:
            self.vx = -self.vx
            self.x = max(PARTICLE_RADIUS, min(self.x, WIDTH - PARTICLE_RADIUS))
        if self.y - PARTICLE_RADIUS < 0 or self.y + PARTICLE_RADIUS > HEIGHT:
            self.vy = -self.vy
            self.y = max(PARTICLE_RADIUS, min(self.y, HEIGHT - PARTICLE_RADIUS))

    def collide_with(self, other): # collisions between particles
        dx = other.x - self.x
        dy = other.y - self.y
        dist2 = dx * dx + dy * dy # optimisation, sqrt is demanding
        if dist2 >= 4 * PARTICLE_RADIUS * PARTICLE_RADIUS:
            return  # lack of collision

        dist = math.sqrt(dist2)

        # unit vector along collision line
        nx = dx / dist
        ny = dy / dist

        # relative speed
        dvx = self.vx - other.vx
        dvy = self.vy - other.vy

        # component of relative speed along collision line
        dvn = dvx * nx + dvy * ny
        if dvn > 0:  # particles are getting further from each other
            return

        # for equal masses: changing component along nx, ny
        # (it can be written as v1' = v1 - dvn*n, v2' = v2 + dvn*n)
        impulse = dvn  # 2 * dvn / (m1+m2)  → when m1=m2 = 1
        self.vx -= impulse * nx
        self.vy -= impulse * ny
        other.vx += impulse * nx
        other.vy += impulse * ny

        # ----- separating particles, so they wouldn't glue together -----
        overlap = 2 * PARTICLE_RADIUS - dist
        if overlap > 0:
            sep = overlap / 2.0
            self.x -= sep * nx
            self.y -= sep * ny
            other.x += sep * nx
            other.y += sep * ny

def simulate(num_particles, max_speed):
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Symulacja zderzeń cząstek gazu 2D - Siatka + licznik energii")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 18)

    particles = []
    for _ in range(num_particles):
        x = random.uniform(PARTICLE_RADIUS, WIDTH - PARTICLE_RADIUS)
        y = random.uniform(PARTICLE_RADIUS, HEIGHT - PARTICLE_RADIUS)
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1, max_speed)  # Velocity from 1 to max_speed
        vx = speed * math.cos(angle)
        vy = speed * math.sin(angle)
        particles.append(Particle(x, y, vx, vy))

    # Spatial grid: list of lists (every cell is list of particles indexes)
    grid = [[[] for _ in range(GRID_H)] for _ in range(GRID_W)]

    # Initial energy - should stay the same in isolated system
    total_energy = sum(0.5 * (p.vx ** 2 + p.vy ** 2) for p in particles)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((255, 255, 255))  # Białe tło

        # Upadting position and checking collisions
        for p in particles:
            p.update_position()
            p.check_walls()

        # === 2. Clear the grid ===
        for col in grid:
            for cell in col:
                cell.clear()

        # === 3. Fill the grid with indexes ===
        for i, p in enumerate(particles):
            gx = int(p.x // CELL_SIZE)
            gy = int(p.y // CELL_SIZE)
            # Optional: check the borders of the grid (just in case)
            gx = max(0, min(gx, GRID_W - 1))
            gy = max(0, min(gy, GRID_H - 1))
            grid[gx][gy].append(i)

        # === 4. Checking collisions only inside neighbouring cells ===
        for gx in range(GRID_W):
            for gy in range(GRID_H):
                cell = grid[gx][gy]
                # collisions inside the cell
                for i in range(len(cell)):
                    for j in range(i + 1, len(cell)):
                        p1 = particles[cell[i]]
                        p2 = particles[cell[j]]
                        p1.collide_with(p2)

                # Collisions with neighbouring cells (left, right, diagonal)
                for dx, dy in [(1, 0), (1, -1), (0, -1), (-1, -1)]:
                    nx, ny = gx + dx, gy + dy
                    if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                        neighbor = grid[nx][ny]
                        for i in cell:
                            for j in neighbor:
                                if i < j:  # avoiding double-checking
                                    p1 = particles[i]
                                    p2 = particles[j]
                                    p1.collide_with(p2)

        # Getting particles
        for p in particles:
            speed = math.hypot(p.vx, p.vy)
            # Color dependent on the speed (blue -> red)
            color_val = min(255, int(40 * speed))
            color = (color_val, 0, 255 - color_val)
            pygame.draw.circle(screen, color, (int(p.x), int(p.y)), PARTICLE_RADIUS)

        # === 6. Kinetic energy ===
        current_energy = sum(0.5 * (p.vx ** 2 + p.vy ** 2) for p in particles)
        energy_text = font.render(f"Energia: {current_energy:.1f} (stała: {total_energy:.1f})", True, (0, 0, 0))
        screen.blit(energy_text, (10, 10))

        # Energy difference (should be ~0)
        diff = abs(current_energy - total_energy)
        if diff > 1e-3:
            print(f"[UWAGA] Energia się zmienia! ΔE = {diff:.6f}")

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    num_particles = 3000
    max_speed = 10
    simulate(num_particles, max_speed)