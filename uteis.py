def directions():
    return list("wasd")

def inside_range(pos, size):
    return pos[0] in range(size[0]) and pos[1] in range(size[1])

#retorna a nova posição a partir de certa ação
def new_pos(pos, action):
    cx, cy = pos
    if   action == "w":
        return cx, cy - 1
    elif action == "a":
        return cx - 1, cy
    elif action == "s":
        return cx, cy + 1
    elif action == "d":
        return cx + 1, cy

#retorna a posição anterior a certa ação
def prior_pos(pos, action):
    cx, cy = pos
    if   action == "w":
        return cx, cy + 1
    elif action == "a":
        return cx + 1, cy
    elif action == "s":
        return cx, cy - 1
    elif action == "d":
        return cx - 1, cy

def manhattan_distance(pos1, pos2):
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])


