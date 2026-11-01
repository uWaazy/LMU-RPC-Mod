ONLINE = "online"
WEEKEND = "weekend"
CLIENT = 2
REMOTE = 2


def detect_game_mode(game_mode, controls):
    if game_mode == CLIENT or controls.get(REMOTE, 0) > 0:
        return ONLINE
    return WEEKEND


def party_size(mode, num_cars, max_players):
    if mode != ONLINE or num_cars < 1 or max_players < num_cars:
        return None
    return [num_cars, max_players]
