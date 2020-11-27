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
from scores import HighScoresFetch

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

DATA_INDEX_BEST_ROUND = ["level", "timestamp", "timestamp2", "score", "total_moves", "total_pushes", "total_steps"]
DATA_INDEX_CURR_ROUND = ["Moves", "Pushes", "Steps"]

SCORE_INFO = {
    "level": "Level",
    "score": "Score",
    "timestamp": "Date",
    "timestamp2": "",
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
    "black": (0, 0, 0),
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


def draw_info(surface, text, pos, color=COLORS["black"], background=None, size=24):
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
    textsurface = pygame.font.Font(None, int(24 / SCALE)).render(text, True, COLORS["black"])
    return textsurface.get_width(), textsurface.get_height()

# draw a table providing position for top and margin for right
def draw_table_from_right_top(canvas, col_l_info, col_r_info, title_info, max_width, positions):
    col_l, col_l_color = col_l_info
    col_r, col_r_color = col_r_info
    title, title_color = title_info
    pos_top, margin_right = positions
    canvas_width = canvas.get_width()

    # find place for title
    title_width, title_height = get_draw_size(title)
    title_margin = (max_width-margin_right-title_width)/2
    title_pos = title_width+title_margin+margin_right

    # draw title of table
    draw_info(canvas, title, (canvas_width-title_pos, pos_top), title_color)

    content_initial_height = pos_top+title_height+20
    for i, col in enumerate(col_l):
        curr_height = content_initial_height+i*20
        col_r_content = col_r[i]
        
        # draw left side of column
        draw_info(canvas, col, (canvas_width-max_width, curr_height), col_l_color)

        # draw right side of colum
        draw_info(canvas, col_r_content, (canvas_width-get_draw_size(col_r_content)[0]-margin_right, curr_height), col_r_color)


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

    player = last_player = state['player']

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
                if hs.data != []:
                    best_entry = hs.get_best_entry(type="max", key="score")

                    split_timestamp = best_entry["timestamp"].split("T")
                    fixed_width = get_draw_size(split_timestamp[0])[0]+get_draw_size("Data: ")[0]+RIGHT_INFO_MARGIN_RIGHT+RIGHT_INFO_SPACE_BETWEEN_COLS
                    
                    # adjust best_entry dict
                    best_entry["timestamp"] = split_timestamp[0]
                    best_entry["timestamp2"] = split_timestamp[1]

                player = state['player']

                last_player = curr_player
            
            # draw player info
            player_h_from_top = SCREEN.get_height() - 40
            player_w, _ = get_draw_size(player)
            draw_info(SCREEN, player, (SCREEN.get_width()-player_w-RIGHT_INFO_MARGIN_RIGHT, player_h_from_top), COLORS["light_blue"])
            draw_info(SCREEN, "Player: ", (SCREEN.get_width()-player_w-get_draw_size("Player: ")[0]-RIGHT_INFO_MARGIN_RIGHT-RIGHT_INFO_SPACE_BETWEEN_COLS, player_h_from_top), COLORS["white"])

            if hs != None and hs.data != []:
                # table for best round
                draw_table_from_right_top(SCREEN, ([SCORE_INFO[d] for d in DATA_INDEX_BEST_ROUND], COLORS["black"]), ([str(best_entry[info]) for info in DATA_INDEX_BEST_ROUND], COLORS["white"]), ("Best Round", COLORS["yellow"]), fixed_width, (RIGHT_INFO_MARGIN_TOP, RIGHT_INFO_MARGIN_RIGHT))
            
            # some conditions to coop with state['score']
            if not isinstance(state['score'], int) and len(state['score']) > len(DATA_INDEX_CURR_ROUND):
                # adapt position of current round table depending if there is a table for best round
                current_round_pos_top = 230 if hs.data != [] else RIGHT_INFO_MARGIN_TOP
                curr_round_data_fetch = [str(state['score'][i+1]) for i in range(len(DATA_INDEX_CURR_ROUND))]
                
                # if there is no data from best round, adapt the fixed size to the data of current round
                if hs.data == []:
                    max_key = lambda s:len(s)
                    fixed_width = get_draw_size(max(curr_round_data_fetch, key=max_key))[0]+get_draw_size(max(DATA_INDEX_CURR_ROUND, key=max_key))[0]+RIGHT_INFO_MARGIN_RIGHT+RIGHT_INFO_SPACE_BETWEEN_COLS
   
                # table for current round
                draw_table_from_right_top(SCREEN, (DATA_INDEX_CURR_ROUND, COLORS["black"]), (curr_round_data_fetch, COLORS["white"]), ("Current Round", COLORS["red"]), fixed_width, (current_round_pos_top, RIGHT_INFO_MARGIN_RIGHT))

        if "level" in state:
            top_pos = 335 if hs.data != [] else 147
            draw_info(
                SCREEN,
                f"{state['level']}",
                (SCREEN.get_width()-162, top_pos),
                color=COLORS["white"], size=50
            )
        else:
            for i, word in enumerate(["Run a client  ", "to see scores!"]):
                word_w, word_h = get_draw_size(word)
                draw_info(SCREEN, word, (SCREEN.get_width()-word_w-40, RIGHT_INFO_MARGIN_TOP+word_h+i*20), COLORS["white"])

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
