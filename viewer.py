"""Viewer application."""
import argparse
import asyncio
import json
import logging
import os
import random

import websockets

import pygame
from consts import RANKS, Tiles
from mapa import Map
from game import reduce_score
from fetch import HighScoresFetch

logging.basicConfig(level=logging.DEBUG)
logger_websockets = logging.getLogger("websockets")
logger_websockets.setLevel(logging.WARN)

logger = logging.getLogger("Map")
logger.setLevel(logging.DEBUG)

MAP_X_INCREASE = 4
MAP_Y_INCREASE = 2

RIGHT_INFO_MARGIN_TOP = 30
RIGHT_INFO_MARGIN_RIGHT = 30
RIGHT_INFO_SPACE_BETWEEN_COLS = 5

SCORE_INFO = {
    "level": "Level",
    "score": "Score",
    "total_moves": "Moves",
    "total_pushes": "Pushes",
    "total_steps": "Steps"
}

KEEPER = {
    "up": (3 * 64, 4 * 64),
    "left": (3 * 64, 6 * 64),
    "down": (0, 4 * 64),
    "right": (0, 6 * 64),
}
BOX = (7 * 64, 0)
BOX_ON_GOAL = (9 * 64, 0)
GOAL = (12 * 64, 5 * 64)
WALL = (8 * 64, 6 * 64)
PASSAGE = (12 * 64, 6 * 64)
GREEN_PASSAGE = (10 * 64, 6 * 64)
GRAY_PASSAGE = (11 * 64, 6 * 64)
BLACK_SURFACE = (11 * 64, 0)

CHAR_LENGTH = 64
CHAR_SIZE = CHAR_LENGTH, CHAR_LENGTH
SCALE = 1

COLORS = {
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "pink": (255, 105, 180),
    "blue": (135, 206, 235),
    "orange": (255, 165, 0),
    "yellow": (255, 255, 0),
    "grey": (120, 120, 120),
    "light_blue": (58, 240, 240),
}
SPRITES = None
SCREEN = None


async def messages_handler(websocket_path, queue):
    """Handles server side messages, putting them into a queue."""
    async with websockets.connect(websocket_path) as websocket:
        await websocket.send(json.dumps({"cmd": "join"}))

        while True:
            update = await websocket.recv()
            queue.put_nowait(update)


class Artifact(pygame.sprite.Sprite):
    """Representation of moving pieces."""

    def __init__(self, *args, **kw):
        x, y = kw.pop("pos", ((kw.pop("x", 0), kw.pop("y", 0))))
        new_pos = scale((x, y))
        self.x, self.y = new_pos[0], new_pos[1]

        self.image = pygame.Surface(CHAR_SIZE)
        self.rect = pygame.Rect(new_pos + CHAR_SIZE)
        self.update((x, y))
        super().__init__(*args, **kw)

    def update(self, pos=None):
        """Updates the sprite with a new position."""
        if not pos:
            pos = self.x, self.y
        else:
            pos = scale(pos)
        self.rect = pygame.Rect(pos + CHAR_SIZE)
        self.image.fill((0, 0, 230))
        self.image.blit(SPRITES, (0, 0), (*PASSAGE, *scale((1, 1))))
        self.image.blit(*self.sprite)
        # self.image = pygame.transform.scale(self.image, scale((1, 1)))
        self.x, self.y = pos


class Keeper(Artifact):
    """Handles Keeper Sprites."""

    def __init__(self, *args, **kw):
        self.direction = "left"
        self.sprite = (SPRITES, (0, 0), (*KEEPER[self.direction], *scale((1, 1))))
        super().__init__(*args, **kw)

    def update(self, pos=None):
        x, y = scale(pos)

        if x > self.x:
            self.direction = "right"
        if x < self.x:
            self.direction = "left"
        if y > self.y:
            self.direction = "down"
        if y < self.y:
            self.direction = "up"

        self.sprite = (SPRITES, (0, 0), (*KEEPER[self.direction], *scale((1, 1))))
        super().update(tuple(pos))


class Box(Artifact):
    """Handles Box Sprites."""

    def __init__(self, *args, **kw):
        self.sprite = (SPRITES, (0, 0), (*BOX, *scale((1, 1))))
        if kw.pop("stored"):
            self.sprite = (SPRITES, (0, 0), (*BOX_ON_GOAL, *scale((1, 1))))
        super().__init__(*args, **kw)


def clear_callback(surf, rect):
    """Beneath everything there is a passage."""
    surf.blit(SPRITES, (rect.x, rect.y), (*PASSAGE, rect.width, rect.height))


def scale(pos):
    """Scale positions according to gfx."""
    x, y = pos
    return int(x * CHAR_LENGTH / SCALE), int(y * CHAR_LENGTH / SCALE)


def draw_background(mapa):
    """Create background surface."""
    map_x, map_y = mapa.size
    background = pygame.Surface(scale((map_x+MAP_X_INCREASE, map_y+MAP_Y_INCREASE)))
    separator = True
    for x in range(map_x+MAP_X_INCREASE):
        if x == map_x+1:
            separator = False
        for y in range(map_y+MAP_Y_INCREASE):
            wx, wy = scale((x, y))
            if x < map_x and y < map_y:
                background_sprite = sprite = PASSAGE
                if mapa.get_tile((x, y)) == Tiles.WALL:
                    sprite = WALL
                if mapa.get_tile((x, y)) in [Tiles.GOAL, Tiles.BOX_ON_GOAL, Tiles.MAN_ON_GOAL]:
                    sprite = GOAL
            else:
                background_sprite = GRAY_PASSAGE
                if y > map_y:
                    sprite = GRAY_PASSAGE
                else:
                    if separator or y == map_y:
                        sprite = BLACK_SURFACE
                    else:
                        sprite = GREEN_PASSAGE
            
            # needed to fill the background of sprites with transparency
            background.blit(SPRITES, (wx, wy), (*background_sprite, *scale((1, 1))))

            background.blit(SPRITES, (wx, wy), (*sprite, *scale((1, 1))))
    return background


def draw_info(surface, text, pos, color=(0, 0, 0), background=None, size=24):
    """Creates text based surfaces for information display."""
    myfont = pygame.font.Font(None, int(size / SCALE))
    textsurface = myfont.render(text, True, color, background)

    x, y = pos
    if x > surface.get_width():
        pos = surface.get_width() - (textsurface.get_width() + 10), y
    if y > surface.get_height():
        pos = x, surface.get_height() - textsurface.get_height()

    if background:
        surface.blit(background, pos)
    else:
        erase = pygame.Surface(textsurface.get_size())
        erase.fill(COLORS["grey"])

    surface.blit(textsurface, pos)
    return textsurface.get_width(), textsurface.get_height()

# get size of draw without drawing it
def get_draw_size(text):
    textsurface = pygame.font.Font(None, int(24 / SCALE)).render(text, True, (0,0,0))
    return textsurface.get_width(), textsurface.get_height()

async def main_loop(queue):
    """Processes events from server and display's."""
    global SPRITES, SCREEN

    main_group = pygame.sprite.LayeredUpdates()
    boxes_group = pygame.sprite.OrderedUpdates()

    logging.info("Waiting for map information from server")
    state = await queue.get()  # first state message includes map information
    logging.debug("Initial game status: %s", state)
    newgame_json = json.loads(state)

    GAME_SPEED = newgame_json["fps"]
    try:
        mapa = Map(newgame_json["map"])
    except (KeyError, FileNotFoundError):
        mapa = Map("levels/1.xsb")  # Fallback to initial map
    map_x, map_y = mapa.size
    SCREEN = pygame.display.set_mode(scale((map_x+MAP_X_INCREASE, map_y+MAP_Y_INCREASE)))
    SPRITES = pygame.image.load("data/sokoban.png").convert_alpha()

    BACKGROUND = draw_background(mapa)
    SCREEN.blit(BACKGROUND, (0, 0))
    main_group.add(Keeper(pos=mapa.keeper))

    state = {
        "score": 0,
        "player": "player1",
        "keeper": mapa.keeper,
        "boxes": mapa.boxes,
    }

    new_event = True

    last_player = state['player']

    data_index = ["level", "timestamp", "", "score", "total_moves", "total_pushes", "total_steps"]
    hs = HighScoresFetch(name=state['player'])
    best_entry = None

    while True:
        if "player" in state:
            curr_player = state['player']

        SCREEN.blit(BACKGROUND, (0, 0))
        pygame.event.pump()
        if pygame.key.get_pressed()[pygame.K_ESCAPE]:
            asyncio.get_event_loop().stop()

        main_group.clear(SCREEN, clear_callback)
        boxes_group.clear(SCREEN, clear_callback)
        
        if "score" in state and "player" in state:
            if last_player != curr_player:
                hs = HighScoresFetch(name=state['player'])
                last_player = curr_player
                best_entry = hs.get_best_entry(type="max", key="score")

            player = state['player']
            
            player_h_from_top = SCREEN.get_height() - 40
            player_w, _ = get_draw_size(player)
            draw_info(SCREEN, player, (SCREEN.get_width()-player_w-RIGHT_INFO_MARGIN_RIGHT, player_h_from_top), COLORS["light_blue"])
            draw_info(SCREEN, "Player: ", (SCREEN.get_width()-player_w-get_draw_size("Player: ")[0]-RIGHT_INFO_MARGIN_RIGHT-RIGHT_INFO_SPACE_BETWEEN_COLS, player_h_from_top), COLORS["white"])

            if hs != None and hs.data != []:
                draw_info(SCREEN, "Best Round", (SCREEN.get_width()-get_draw_size("Best Round")[0]-RIGHT_INFO_MARGIN_RIGHT-22, RIGHT_INFO_MARGIN_TOP), COLORS["yellow"])

                info_pos = RIGHT_INFO_MARGIN_TOP + 35
                title_fixed_size = get_draw_size(best_entry['timestamp'].split("T")[0])[0]+get_draw_size("Data: ")[0]+RIGHT_INFO_MARGIN_RIGHT+RIGHT_INFO_SPACE_BETWEEN_COLS
                
                for i, info in enumerate(data_index):
                    if info == "":
                        continue
                    else:
                        content = best_entry[info]

                    if info == "timestamp":
                        splitted = content.split("T")
                        draw_info(SCREEN, splitted[0], (SCREEN.get_width()-get_draw_size(splitted[0])[0]-RIGHT_INFO_MARGIN_RIGHT, info_pos+i*20), COLORS["white"])
                        draw_info(SCREEN, "Data: ", (SCREEN.get_width()-title_fixed_size, info_pos+i*20))
                        draw_info(SCREEN, splitted[1], (SCREEN.get_width()-get_draw_size(splitted[1])[0]-RIGHT_INFO_MARGIN_RIGHT, info_pos+(i+1)*20), COLORS["white"])
                        continue              

                    draw_info(SCREEN, str(content), (SCREEN.get_width()-get_draw_size(str(content))[0]-RIGHT_INFO_MARGIN_RIGHT, info_pos+i*20), COLORS["white"])
                    draw_info(SCREEN, SCORE_INFO[info]+": ", (SCREEN.get_width()-title_fixed_size, info_pos+i*20))

                curr_round_pos = 230
                draw_info(SCREEN, "Current Round", (SCREEN.get_width()-get_draw_size("Current Round")[0]-RIGHT_INFO_MARGIN_RIGHT-10, curr_round_pos), COLORS["red"])

                info_pos = curr_round_pos + 35
                for i, curr_info in enumerate(["Moves", "Pushes", "Steps"]):
                    content = state['score'][i+1]
                    draw_info(SCREEN, str(content), (SCREEN.get_width()-get_draw_size(str(content))[0]-RIGHT_INFO_MARGIN_RIGHT, info_pos+i*20), COLORS["white"])
                    draw_info(SCREEN, curr_info+": ", (SCREEN.get_width()-title_fixed_size, info_pos+i*20))

        if "level" in state:
            draw_info(
                SCREEN,
                f"{state['level']}",
                (SCREEN.get_width()-162, 335),
                color=COLORS["white"], size=50
            )

        if "boxes" in state:
            boxes_group.empty()
            for box in state["boxes"]:
                boxes_group.add(
                    Box(
                        pos=box,
                        stored=mapa.get_tile(box) in [Tiles.GOAL, Tiles.BOX_ON_GOAL],
                    )
                )

        boxes_group.draw(SCREEN)
        main_group.draw(SCREEN)

        # Highscores Board
        if "highscores" in state and "player" in state:
            if new_event:
                highscores = state["highscores"]
                highscores.append(
                    (f"<{state['player']}>", reduce_score(*state["score"]))
                )

                highscores = sorted(highscores, key=lambda s: s[1])
                highscores = highscores[: len(RANKS)]

                HIGHSCORES = pygame.Surface((256, 280))
                HIGHSCORES.fill((30, 30, 30))

                COLS = [20, 80, 150]

                draw_info(HIGHSCORES, "THE 10 BEST PLAYERS", (20, 10), COLORS["white"])
                for value, column in zip(["RANK", "SCORE", "NAME"], COLS):
                    draw_info(HIGHSCORES, value, (column, 30), COLORS["orange"])

                for i, highscore in enumerate(highscores):
                    color = (
                        random.randrange(66, 222),
                        random.randrange(66, 222),
                        random.randrange(66, 222),
                    )
                    for value, column in zip(
                        [RANKS[i + 1], str(highscore[1]), highscore[0]], COLS
                    ):
                        draw_info(HIGHSCORES, value, (column, 60 + i * 20), color)

            SCREEN.blit(
                HIGHSCORES,
                (
                    (SCREEN.get_width() - HIGHSCORES.get_width()) / 2,
                    (SCREEN.get_height() - HIGHSCORES.get_height()) / 2,
                ),
            )

        if "keeper" in state:
            main_group.update(state["keeper"])

        pygame.display.flip()

        try:
            state = json.loads(queue.get_nowait())
            new_event = True
            if "map" in state:
                logger.debug("New Level!")
                # New level! lets clean everything up!
                try:
                    mapa = Map(state["map"])
                except FileNotFoundError:
                    logger.error(
                        "Can't find levels/%s.xsb, means we have a WINNER!",
                        state["level"],
                    )
                    continue
                map_x, map_y = mapa.size
                SCREEN = pygame.display.set_mode(scale((map_x+MAP_X_INCREASE, map_y+MAP_Y_INCREASE)))
                BACKGROUND = draw_background(mapa)
                SCREEN.blit(BACKGROUND, (0, 0))

                boxes_group.empty()
                main_group.empty()
                main_group.add(Keeper(pos=mapa.keeper))
                pygame.display.flip()

        except asyncio.queues.QueueEmpty:
            await asyncio.sleep(1.0 / GAME_SPEED)
            new_event = False
            continue

if __name__ == "__main__":
    SERVER = os.environ.get("SERVER", "localhost")
    PORT = os.environ.get("PORT", "8000")

    parser = argparse.ArgumentParser()
    parser.add_argument("--server", help="IP address of the server", default=SERVER)
    parser.add_argument(
        "--scale", help="reduce size of window by x times", type=int, default=1
    )
    parser.add_argument("--port", help="TCP port", type=int, default=PORT)
    arguments = parser.parse_args()
    SCALE = arguments.scale

    LOOP = asyncio.get_event_loop()
    pygame.font.init()
    q = asyncio.Queue()
    PROGRAM_ICON = pygame.image.load("data/icon.png")
    pygame.display.set_icon(PROGRAM_ICON)

    ws_path = f"ws://{arguments.server}:{arguments.port}/viewer"

    try:
        LOOP.run_until_complete(
            asyncio.gather(messages_handler(ws_path, q), main_loop(q))
        )
    except RuntimeError as err:
        logger.error(err)
    finally:
        LOOP.stop()
