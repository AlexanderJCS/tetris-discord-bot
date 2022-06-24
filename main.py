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
]


@dataclass
class Colors:
    discord = 0x7298da
    green = 0x2ad140
    red = 0xff4400


class Statistics:
    def __init__(self):
        self.blocks = 0
        self.score = 0
        self.lines_cleared = 0

        with open("highscore.txt", "r") as f:
            self.highscore = int(f.read())


client = Bot(".")
color = Colors()


class Tetromino:
    def __init__(self):
        self.coordinates = copy.deepcopy(random.choice(TETROMINO_SHAPES))
        self.centerpoint = self.coordinates.pop()
        self.color = random.choice("🟦🟩🟪🟥")

    def move_coords(self, x, y):
        # Returns the horizontal and vertical movement of the block given

        new_coords = copy.deepcopy(self.coordinates)

        for coordinate in new_coords:
            coordinate[0] += x
            coordinate[1] += y

        return new_coords

    def rotate(self, rotation):
        # Uses geometry to rotate the block

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

        with open("highscore.txt", "r") as f:
            self.highscore = f.read()

    def block_at_coordinates(self, x, y):
        # Returns a block at the given coordinates, None if there is no block. Used for checking if a block can be moved
        for tetromino in self.tetrominoes:
            for coordinate in tetromino.coordinates:
                if coordinate[0] == x and coordinate[1] == y:
                    return tetromino

    def valid_move(self, tetromino, new_coords):
        # Checks if the tetromino can be moved to the new coordinates

        for coordinates in new_coords:
            # Check if the tetromino is outside the screen
            if coordinates[0] < 0 or coordinates[0] >= WIDTH or coordinates[1] >= HEIGHT:
                return False

            if self.block_at_coordinates(*coordinates) not in (tetromino, None):
                return False
        return True

    def fall_all_tetrominoes(self, fall_last_block):
        # Falls all the tetrominoes that can be fallen.

        if fall_last_block is True:
            self.stats.score += 10

        for i, tetromino in enumerate(self.tetrominoes):
            if i == len(self.tetrominoes) - 1 and fall_last_block is False:
                continue

            if self.valid_move(tetromino, new_coords := tetromino.move_coords(0, 1)):
                self.tetrominoes[i].coordinates = new_coords
                self.tetrominoes[i].move_center(0, 1)

    def draw(self):
        # Draws the screen in emojis to be displayed in the self.edit_message() function
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
        # Edits the message with the output of the draw function
        embed = discord.Embed(
            title="Tetris",
            description=self.draw(),
            color=color.discord
        )

        embed.set_footer(text=f"Score: {self.stats.score} | Highscore: {self.stats.highscore}")

        await self.message.edit(embed=embed)

    def get_reaction(self):
        # Gets reactions from the user and changes self vars accordingly to be used by other functions
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
        # Adds reactions at the start of the game. Required for self.get_reaction()
        emojis = ["⏪", "⬅", "🔄", "🔁", "➡", "⏩", "⬇"]

        for emoji in emojis:
            await self.message.add_reaction(emoji)

    def move_x(self):
        # Moves the last tetromino in the tetrominoes list horizontally

        self.tetrominoes[-1].move_center(self.direction, 0)

        for _ in range(abs(self.direction)):
            if self.valid_move(
                    self.tetrominoes[-1],
                    new_coords := self.tetrominoes[-1].move_coords(self.direction / abs(self.direction), 0)
            ):
                self.tetrominoes[-1].coordinates = new_coords

        self.direction = 0

    def rotate_block(self):
        # Rotates the last block in the tetrominoes list, the one being controlled by the player

        if not self.rotation:
            return

        if self.valid_move(self.tetrominoes[-1], new_coords := self.tetrominoes[-1].rotate(self.rotation)):
            self.tetrominoes[-1].coordinates = new_coords

        self.rotation = 0

    def detect_full_lines(self):
        # Returns a list of full lines that need to be removed, needed for self.clear_lines()
        full_lines = []

        for y in range(HEIGHT):
            for x in range(WIDTH):
                if self.block_at_coordinates(x, y) in (None, self.tetrominoes[-1]):
                    break

            else:
                full_lines.append(y)

        return full_lines

    def clear_lines(self, lines_to_clear):
        # Takes in the output from the detect_full_lines function and clears the lines

        for i, tetromino in enumerate(self.tetrominoes):
            for j, coordinate in reversed(list(enumerate(tetromino.coordinates))):
                if coordinate[1] in lines_to_clear:
                    self.tetrominoes[i].coordinates.pop(j)

        for _ in lines_to_clear:
            self.stats.lines_cleared += 1
            self.stats.score += 1000
            self.fall_all_tetrominoes(False)

    def teleport_down(self):
        # Teleports the tetromino to the bottom of the screen, called a hard drop in the game
        if not self.down:
            return

        while self.valid_move(
                self.tetrominoes[-1],
                new_coords := self.tetrominoes[-1].move_coords(0, 1)
        ):
            self.tetrominoes[-1].coordinates = new_coords

    def lose_check(self, tetromino):  # sourcery skip: use-any, use-next
        # Checks if the player lost
        # Ignores sourcery refactoring because of readability

        for coordinate in tetromino.coordinates:
            if self.block_at_coordinates(*coordinate) != tetromino:
                return True

        return False

    async def post_lose_message(self):
        # Edits the message announcing the loss
        embed = discord.Embed(
            title="Game Over!",
            description=f"Score: {self.stats.score}\n"
                        f"Highscore: {self.stats.highscore}\n"
                        f"Lines cleared: {self.stats.lines_cleared}\n"
                        f"Blocks spawned: {self.stats.blocks}",
            color=color.red
        )

        await self.message.edit(embed=embed)

    async def highscore_check(self):
        # Checks if the highscore is beaten and sends a message
        if self.stats.score < self.stats.highscore:
            return

        embed = discord.Embed(
            title="New Highscore!",
            description=f"Score: {self.stats.score}\n"
                        f"Previous highscore: {self.stats.highscore}\n",
            color=color.green
        )

        await self.ctx.send(embed=embed)

    async def run_game(self):
        self.message = await self.ctx.send("** **")  # Send an empty message to be edited later
        await self.add_action()  # Add the reactions to the message
        await asyncio.sleep(1)

        spawn_new_block = False  # Adds a one frame buffer to move left or right

        while True:
            # Spawn new block
            if spawn_new_block and not self.valid_move(self.tetrominoes[-1], self.tetrominoes[-1].move_coords(0, 1)):
                self.stats.blocks += 1
                self.tetrominoes.append(Tetromino())

                if self.lose_check(self.tetrominoes[-1]):
                    break

                spawn_new_block = False

            # Schedule a block to be spawned next frame if the block cannot fall
            if not self.valid_move(self.tetrominoes[-1], self.tetrominoes[-1].move_coords(0, 1)):
                spawn_new_block = True

            self.get_reaction()
            self.clear_lines(self.detect_full_lines())
            self.fall_all_tetrominoes(True)
            self.teleport_down()
            self.rotate_block()
            self.move_x()

            await self.edit_message()
            await asyncio.sleep(1)

        await self.post_lose_message()
        await self.highscore_check()


@client.command()
async def tetris(ctx):
    t = Tetris(ctx)
    await t.run_game()


@client.event
async def on_ready():
    print(f"Logged in as {client.user.name}, {client.user.id}")


with open("token.txt") as tokenfile:
    client.run(tokenfile.read())
