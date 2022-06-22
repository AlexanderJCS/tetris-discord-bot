import discord
from discord.ext.commands import Bot

from dataclasses import dataclass
import asyncio
import random
import copy

HEIGHT = 15
WIDTH = 8
CENTER = WIDTH // 2

TETROMINO_SHAPES = [
    [[CENTER - 1, 0], [CENTER, 0], [CENTER + 1, 0], [CENTER, 1], [CENTER, 0]],  # T-shape
    [[CENTER - 2, 0], [CENTER - 1, 0], [CENTER, 0], [CENTER + 1, 0], [CENTER, 0]],  # I-shape
    [[CENTER - 1, 0], [CENTER, 0], [CENTER + 1, 0], [CENTER + 1, 1], [CENTER, 0]],  # J-Shape
    [[CENTER - 1, 0], [CENTER, 0], [CENTER + 1, 0], [CENTER - 1, 1], [CENTER, 0]],  # L-Shape
    [[CENTER - 1, 0], [CENTER, 0], [CENTER - 1, 1], [CENTER, 1], [CENTER - 0.5, 0.5]],  # O-Shape
]


@dataclass
class Colors:
    discord = 0x7298da
    green = 0x2ad140
    red = 0xff4400


@dataclass
class Statistics:
    blocks = 0
    score = 0
    lines_cleared = 0


client = Bot(".")
color = Colors()


class Tetromino:
    def __init__(self):
        self.coordinates = copy.deepcopy(random.choice(TETROMINO_SHAPES))
        self.centerpoint = self.coordinates.pop()
        self.color = random.choice("🟦🟩🟪🟥")

    def fall(self):
        fallen_coords = copy.deepcopy(self.coordinates)

        for fallen_coord in fallen_coords:
            fallen_coord[1] += 1

        return fallen_coords

    def move_horizontal(self, direction):
        new_coords = copy.deepcopy(self.coordinates)

        for coordinate in new_coords:
            coordinate[0] += direction

        return new_coords

    def rotate(self, rotation):
        # Rotation is either -1 or 1 for counterclockwise and clockwise rotation
        rotated_coords = []

        # Subtract the origin point from the coordinates
        for coordinate in self.coordinates:
            coordinate_x = coordinate[0] - self.centerpoint[0]
            coordinate_y = coordinate[1] - self.centerpoint[1]

            new_coordinate = [coordinate_y * -1 * rotation, coordinate_x * rotation]

            new_coordinate[0] += self.centerpoint[0]
            new_coordinate[1] += self.centerpoint[1]

            rotated_coords.append(new_coordinate)

        return rotated_coords

    def move_center(self, x, y):
        self.centerpoint = (self.centerpoint[0] + x, self.centerpoint[1] + y)


class Tetris:
    def __init__(self, ctx):
        self.tetrominoes = [Tetromino()]
        self.ctx = ctx
        self.message = None
        self.direction = 0
        self.rotation = 0
        self.down = False  # whether the block is going to teleport to the bottom
        self.stats = Statistics()

    def block_at_coordinates(self, x, y):
        for tetromino in self.tetrominoes:
            for coordinate in tetromino.coordinates:
                if coordinate[0] == x and coordinate[1] == y:
                    return tetromino

    def valid_move(self, tetromino, new_coords):
        for coordinates in new_coords:
            # Check if the tetromino is outside the screen
            if coordinates[0] < 0 or coordinates[0] >= WIDTH or coordinates[1] >= HEIGHT:
                return False

            if self.block_at_coordinates(*coordinates) not in (tetromino, None):
                return False
        return True

    def fall_all_tetrominoes(self, fall_last_block):
        if fall_last_block is True:
            self.stats.score += 10

        for i, tetromino in enumerate(self.tetrominoes):
            if i == len(self.tetrominoes) - 1 and fall_last_block is False:
                continue

            if self.valid_move(tetromino, new_coords := tetromino.fall()):
                self.tetrominoes[i].coordinates = new_coords
                self.tetrominoes[i].move_center(0, 1)

    def draw(self):
        screen = ""

        for y in range(HEIGHT):
            for x in range(WIDTH):
                if tetromino := self.block_at_coordinates(x, y):
                    screen += tetromino.color
                    continue

                screen += "⬛"
            screen += "\n"

        return screen

    async def edit_message(self):
        embed = discord.Embed(
            title="Tetris",
            description=self.draw(),
            color=color.discord
        )

        embed.set_footer(text=f"Score: {self.stats.score}")

        await self.message.edit(embed=embed)

    def get_reaction(self):
        # Cache the message to get the reactions
        cache_msg = discord.utils.get(client.cached_messages, id=self.message.id)

        # Get x direction movement
        if cache_msg.reactions[0].count > 1:
            self.direction = -2

        elif cache_msg.reactions[1].count > 1:
            self.direction = -1

        elif cache_msg.reactions[4].count > 1:
            self.direction = 1

        elif cache_msg.reactions[5].count > 1:
            self.direction = 2

        # Get rotation
        if cache_msg.reactions[2].count > 1:
            self.rotation = -1

        elif cache_msg.reactions[3].count > 1:
            self.rotation = 1

        # Check if teleporting down is activated
        self.down = cache_msg.reactions[6].count > 1

    async def add_action(self):
        emojis = ["⏪", "⬅", "🔄", "🔁", "➡", "⏩", "⬇"]

        for emoji in emojis:
            await self.message.add_reaction(emoji)

    def move_x(self):
        self.tetrominoes[-1].move_center(self.direction, 0)

        for _ in range(abs(self.direction)):
            if self.valid_move(
                    self.tetrominoes[-1],
                    new_coords := self.tetrominoes[-1].move_horizontal(self.direction / abs(self.direction))
            ):
                self.tetrominoes[-1].coordinates = new_coords

        self.direction = 0

    def rotate_block(self):
        if not self.rotation:
            return

        if self.valid_move(self.tetrominoes[-1], new_coords := self.tetrominoes[-1].rotate(self.rotation)):
            self.tetrominoes[-1].coordinates = new_coords

        self.rotation = 0

    def detect_full_lines(self):
        full_lines = []

        for y in range(HEIGHT):
            for x in range(WIDTH):
                if self.block_at_coordinates(x, y) in (None, self.tetrominoes[-1]):
                    break

            else:
                full_lines.append(y)

        return full_lines

    def clear_lines(self, lines_to_clear):
        for i, tetromino in enumerate(self.tetrominoes):
            for j, coordinate in reversed(list(enumerate(tetromino.coordinates))):
                if coordinate[1] in lines_to_clear:
                    self.tetrominoes[i].coordinates.pop(j)

        for _ in lines_to_clear:
            self.stats.lines_cleared += 1
            self.stats.score += 1000
            self.fall_all_tetrominoes(False)

    def teleport_down(self):
        if not self.down:
            return

        while self.valid_move(self.tetrominoes[-1], new_coords := self.tetrominoes[-1].fall()):
            self.tetrominoes[-1].coordinates = new_coords

    def lose_check(self, tetromino):  # sourcery skip: use-any, use-next
        for coordinate in tetromino.coordinates:
            if self.block_at_coordinates(*coordinate) != tetromino:
                return True

        return False

    async def run_game(self):
        self.message = await self.ctx.send("** **")
        await self.add_action()
        await asyncio.sleep(1)

        spawn_new_block = False  # Adds a one frame buffer to move left or right

        while True:
            self.get_reaction()

            if spawn_new_block and not self.valid_move(self.tetrominoes[-1], self.tetrominoes[-1].fall()):
                self.stats.blocks += 1
                self.tetrominoes.append(Tetromino())

                if self.lose_check(self.tetrominoes[-1]):
                    break

                spawn_new_block = False
                self.direction = 0
                self.rotation = 0

            if not self.valid_move(self.tetrominoes[-1], self.tetrominoes[-1].fall()):
                spawn_new_block = True

            self.clear_lines(self.detect_full_lines())
            self.fall_all_tetrominoes(True)
            self.teleport_down()
            self.rotate_block()
            self.move_x()
            await self.edit_message()

            await asyncio.sleep(1)

        embed = discord.Embed(
            title="You Lose!",
            description=f"Score: {self.stats.score}\n"
                        f"Lines cleared: {self.stats.lines_cleared}\n"
                        f"Blocks spawned: {self.stats.blocks}",
            color=color.red
        )

        await self.message.edit(embed=embed)


@client.command()
async def start(ctx):
    t = Tetris(ctx)
    await t.run_game()


@client.event
async def on_ready():
    print(f"Logged in as {client.user.name}, {client.user.id}")


with open("token.txt") as tokenfile:
    client.run(tokenfile.read())
