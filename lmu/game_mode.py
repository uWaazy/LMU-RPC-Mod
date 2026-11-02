ONLINE = "online"
WEEKEND = "weekend"
COOP = "coop"

# mGameMode (Shared Memory): 1 = servidor, 2 = cliente, 3 = servidor e cliente.
# MEDIDO no jogo: Fim de Semana = 0, Online (entrando num servidor) = 2.
# NAO MEDIDO ainda: Co-op. Palpite: quem HOSPEDA roda como servidor (1 ou 3); se o jogo reportar 0 mas
# houver pilotos remotos, tambem tratamos como co-op. Confirme com: python tools/diagnostico_modo.py --modo coop
SERVER = 1
CLIENT = 2
SERVER_AND_CLIENT = 3
REMOTE = 2     # mControl: 0 local, 1 IA, 2 remoto


def detect_game_mode(game_mode, controls):
    if game_mode in (SERVER, SERVER_AND_CLIENT):
        return COOP
    if game_mode == CLIENT:
        return ONLINE
    if controls.get(REMOTE, 0) > 0:
        return COOP
    return WEEKEND


def party_size(mode, num_cars, max_players):
    if mode not in (ONLINE, COOP) or num_cars < 1 or max_players < num_cars:
        return None
    return [num_cars, max_players]
