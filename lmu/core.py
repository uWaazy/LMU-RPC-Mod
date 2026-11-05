"""lmu/core.py - nucleo COMPARTILHADO entre o app original (lmu/app.py) e o preview (lmu/preview.py).

Tudo que define COMO o status aparece no Discord fica aqui, sem dependencia de GUI nem de Shared Memory:
  * idioma e textos (TRANSLATIONS / get_text)
  * resolucao de carros e pistas (CAR_*, TRACKS, get_car_asset_and_name, get_track_asset_key)
  * montagem das linhas e da imagem (build_presence / build_menu_presence)

Se voce adicionar um carro, pista ou texto AQUI, o app original e o preview passam a usar automaticamente.
"""
import os
import sys
import time
import locale
import logging
import unicodedata

from lmu.cars import resolve_car, MODEL_TABLE, KEYWORD_FALLBACK
from lmu.game_mode import party_size

logger = logging.getLogger("LMU_RPC")

CLIENT_ID = '1463577784394973392'   # aplicativo do Discord (os assets de imagem vivem nele)

LANGUAGES = ('en', 'pt-br', 'es')
LANGUAGE = 'en'


def detect_language(argv=None):
    """--lang pt|es|en na linha de comando; senao o idioma do sistema."""
    argv = sys.argv if argv is None else argv
    lang = 'en'
    if "--lang" in argv:
        try:
            arg_lang = argv[argv.index("--lang") + 1].lower()
            if arg_lang.startswith("pt"):
                lang = 'pt-br'
            elif arg_lang.startswith("es"):
                lang = 'es'
            print(f"[DEBUG] Idioma forcado via argumento: {lang}")
        except IndexError:
            print("[AVISO] Argumento --lang usado sem especificar idioma. Usando padrao.")
    else:
        try:
            sys_lang = locale.getdefaultlocale()[0]
            if sys_lang:
                if str(sys_lang).lower().startswith('pt'):
                    lang = 'pt-br'
                elif str(sys_lang).lower().startswith('es'):
                    lang = 'es'
        except Exception:
            pass
        print(f"[DEBUG] Idioma detectado do sistema: {lang}")
    return lang


def set_language(lang):
    global LANGUAGE
    LANGUAGE = lang if lang in LANGUAGES else 'en'
    return LANGUAGE


set_language(detect_language())

TRANSLATIONS = {
    'pt-br': {
        'test_day': 'Dia de Teste',
        'practice': 'Treino Livre',
        'qualify': 'Classificação',
        'warmup': 'Aquecimento',
        'race': 'Corrida',
        'menu': 'No Menu Principal',
        'lobby': 'No Lobby',
        'time_remaining': '⏱ {}',
        'grid_of': '{} de {}',
        'driving': 'Pilotando {} em {}',
        'details': 'P{} • Volta {}/{}',
        'details_time': 'P{} • Restam {}',
        'waiting': 'Aguardando o início da sessão...', 
        'grid': 'No Grid de Largada',
        'formation_lap': 'Volta de Apresentação',
        'countdown': 'Contagem Regressiva',
        'lap_progress': 'Volta {}/{} (Faltam {})',
        'lap_single': 'Volta {}',
        'last_lap': 'Última Volta',
        'menu_details': 'Preparando motores...',
        'mode_online': 'Online',
        'mode_coop': 'Co-op',
        'mode_weekend': 'Fim de Semana',
        'tray_open': 'Abrir',
        'tray_quit': 'Fechar',
        'ui_disconnected': 'DESCONECTADO',
        'ui_service_stopped': 'Serviço Parado',
        'ui_start_rpc': 'INICIAR RPC',
        'ui_stop_rpc': 'DESCONECTAR',
        'ui_connected_lmu': 'CONECTADO AO LMU',
        'ui_sending_rp': 'Enviando Rich Presence',
        'ui_waiting_game': 'AGUARDANDO JOGO',
        'ui_open_lmu': 'Abra o Le Mans Ultimate',
        'ui_connected_discord': 'CONECTADO AO DISCORD',
        'ui_waiting_game_sub': 'Aguardando Jogo...',
        'ui_connection_error': 'Erro de Conexão',
        'ui_connection_error_msg': 'Não foi possível conectar ao Discord.\nVerifique se o Discord está aberto.\n\nErro: {}',
        'ui_autostart': 'Iniciar com o Windows',
        'ui_options': 'Opções',
        'ui_close': 'Fechar',
        'ui_update_title': 'Atualização disponível',
        'ui_update_text': 'O LMU RPC Mod {version} já está disponível.',
        'ui_update_footer': '⬇ {version} disponível · clique para atualizar',
        'ui_update_now': 'Atualizar agora',
        'ui_update_later': 'Depois',
        'ui_update_downloading': 'Baixando atualização… {pct}%',
        'ui_update_installing': 'Instalando e reiniciando…',
        'ui_update_failed': 'Falha na atualização. Abrindo a página da versão…',
        'ui_check_updates': 'Verificar atualizações',
        'ui_minimize_to_tray': 'Minimizar para a bandeja ao fechar',
        'ui_large_image': 'Imagem grande',
        'ui_small_icon': 'Ícone pequeno',
        'ui_opt_alternate': 'Alternar',
        'ui_opt_car': 'Carro',
        'ui_opt_track': 'Pista',
        'ui_opt_badge': 'Badge',
        'ui_opt_rank': 'Patente'
    },
    'en': {
        'test_day': 'Test Day',
        'practice': 'Practice',
        'qualify': 'Qualifying',
        'warmup': 'Warmup',
        'race': 'Race',
        'menu': 'In Menus',
        'lobby': 'In Lobby',
        'time_remaining': '⏱ {}',
        'grid_of': '{} of {}',
        'driving': 'Driving {} at {}',
        'details': 'P{} • Lap {}/{}',
        'details_time': 'P{} • {} left',
        'waiting': 'Waiting for session to start...', 
        'grid': 'On the Grid',
        'formation_lap': 'Formation Lap',
        'countdown': 'Countdown',
        'lap_progress': 'Lap {}/{} ({} left)',
        'lap_single': 'Lap {}',
        'last_lap': 'Final Lap',
        'menu_details': 'Preparing to race...',
        'mode_online': 'Online',
        'mode_coop': 'Co-op',
        'mode_weekend': 'Race Weekend',
        'tray_open': 'Open',
        'tray_quit': 'Exit',
        'ui_disconnected': 'DISCONNECTED',
        'ui_service_stopped': 'Service Stopped',
        'ui_start_rpc': 'START RPC',
        'ui_stop_rpc': 'DISCONNECT',
        'ui_connected_lmu': 'CONNECTED TO LMU',
        'ui_sending_rp': 'Sending Rich Presence',
        'ui_waiting_game': 'WAITING FOR GAME',
        'ui_open_lmu': 'Open Le Mans Ultimate',
        'ui_connected_discord': 'CONNECTED TO DISCORD',
        'ui_waiting_game_sub': 'Waiting for Game...',
        'ui_connection_error': 'Connection Error',
        'ui_connection_error_msg': 'Could not connect to Discord.\nCheck if Discord is open.\n\nError: {}',
        'ui_autostart': 'Start with Windows',
        'ui_options': 'Options',
        'ui_close': 'Close',
        'ui_update_title': 'Update available',
        'ui_update_text': 'LMU RPC Mod {version} is now available.',
        'ui_update_footer': '⬇ {version} available · click to update',
        'ui_update_now': 'Update now',
        'ui_update_later': 'Later',
        'ui_update_downloading': 'Downloading update… {pct}%',
        'ui_update_installing': 'Installing and restarting…',
        'ui_update_failed': 'Update failed. Opening the release page…',
        'ui_check_updates': 'Check for updates',
        'ui_minimize_to_tray': 'Minimize to tray on close',
        'ui_large_image': 'Large image',
        'ui_small_icon': 'Small icon',
        'ui_opt_alternate': 'Alternate',
        'ui_opt_car': 'Car',
        'ui_opt_track': 'Track',
        'ui_opt_badge': 'Badge',
        'ui_opt_rank': 'Rank'
    },
    'es': {
        'test_day': 'Día de Pruebas',
        'practice': 'Práctica',
        'qualify': 'Clasificación',
        'warmup': 'Calentamiento',
        'race': 'Carrera',
        'menu': 'En los Menús',
        'lobby': 'En el Lobby',
        'time_remaining': '⏱ {}',
        'grid_of': '{} de {}',
        'driving': 'Conduciendo {} en {}',
        'details': 'P{} • Vuelta {}/{}',
        'details_time': 'P{} • {} restantes',
        'waiting': 'Esperando que comience la sesión...', 
        'grid': 'En la Parrilla',
        'formation_lap': 'Vuelta de Formación',
        'countdown': 'Cuenta Regresiva',
        'lap_progress': 'Vuelta {}/{} (Faltan {})',
        'lap_single': 'Vuelta {}',
        'last_lap': 'Última Vuelta',
        'menu_details': 'Preparándose para correr...',
        'mode_online': 'Online',
        'mode_coop': 'Cooperativo',
        'mode_weekend': 'Fin de Semana',
        'tray_open': 'Abrir',
        'tray_quit': 'Salir',
        'ui_disconnected': 'DESCONECTADO',
        'ui_service_stopped': 'Servicio Detenido',
        'ui_start_rpc': 'INICIAR RPC',
        'ui_stop_rpc': 'DESCONECTAR',
        'ui_connected_lmu': 'CONECTADO A LMU',
        'ui_sending_rp': 'Enviando Rich Presence',
        'ui_waiting_game': 'ESPERANDO JUEGO',
        'ui_open_lmu': 'Abre Le Mans Ultimate',
        'ui_connected_discord': 'CONECTADO A DISCORD',
        'ui_waiting_game_sub': 'Esperando Juego...',
        'ui_connection_error': 'Error de Conexión',
        'ui_connection_error_msg': 'No se pudo conectar a Discord.\nComprueba si Discord está abierto.\n\nError: {}',
        'ui_autostart': 'Iniciar con Windows',
        'ui_options': 'Opciones',
        'ui_close': 'Cerrar',
        'ui_update_title': 'Actualización disponible',
        'ui_update_text': 'LMU RPC Mod {version} ya está disponible.',
        'ui_update_footer': '⬇ {version} disponible · haz clic para actualizar',
        'ui_update_now': 'Actualizar ahora',
        'ui_update_later': 'Más tarde',
        'ui_update_downloading': 'Descargando actualización… {pct}%',
        'ui_update_installing': 'Instalando y reiniciando…',
        'ui_update_failed': 'Error al actualizar. Abriendo la página de la versión…',
        'ui_check_updates': 'Buscar actualizaciones',
        'ui_minimize_to_tray': 'Minimizar a la bandeja al cerrar',
        'ui_large_image': 'Imagen grande',
        'ui_small_icon': 'Icono pequeño',
        'ui_opt_alternate': 'Alternar',
        'ui_opt_car': 'Coche',
        'ui_opt_track': 'Pista',
        'ui_opt_badge': 'Badge',
        'ui_opt_rank': 'Rango'
    }
}


def get_text(key: str, *args) -> str:
    lang = TRANSLATIONS.get(LANGUAGE, TRANSLATIONS['en'])
    text = lang.get(key, TRANSLATIONS['en'].get(key, key))
    if text is None:
        text = str(key)
    if args:
        return text.format(*args)
    return text


CAR_FOLDER_MAP = {
            "911gt3r_2024": ("car_porsche_911_gt3", "Porsche 911 GT3 R"),
            "alpine_a424_2024": ("car_alpine_a424", "Alpine A424"),
            "aston_martin_valkyrie_2025": ("car_aston_martin_valkyrie", "Aston Martin Valkyrie"),
            "aston_martin_vantage_amr_2023": ("car_aston_martin_vantage_gte", "Aston Martin Vantage GTE"),
            "bmw_m_hybrid_v8_2023": ("car_bmw_m_hybrid_v8", "BMW M Hybrid V8"),
            "bmw_m4_lmgt3_2023": ("car_bmw_m4_gt3", "BMW M4 LMGT3"),
            "cadillac_v-lmdh_2023": ("car_cadillac_v_series_r", "Cadillac V-Series.R"),
            "chevrolet_c8r_lm_2023": ("car_corvette_c8r_gte", "Corvette C8.R"),
            "corvette_z06gt3r_2023": ("car_corvette_z06_gt3", "Corvette Z06 GT3.R"),
            "ferrari_296gt3_2023": ("car_ferrari_296_gt3", "Ferrari 296 LMGT3"),
            "ferrari_488gte_lm_2023": ("car_ferrari_488_gte", "Ferrari 488 GTE"),
            "ferrari_499p_2023": ("car_ferrari_499p", "Ferrari 499P"),
            "ford_mustang_gt3_2024": ("car_ford_mustang_gt3", "Ford Mustang LMGT3"),
            "ginetta_g61evo_2025": ("car_ginetta_g61", "Ginetta G61-LT-P325-Evo"),
            "isotta_tipo6_2024": ("car_isotta_fraschini", "Isotta Fraschini Tipo 6"),
            "lamborghini_huracan_gt3_2024": ("car_lamborghini_huracan_gt3", "Lamborghini Huracan GT3"),
            "lamborghini_sc63_2024": ("car_lamborghini_sc63", "Lamborghini SC63"),
            "lexusrcf_gt3_2024": ("car_lexus_rcf_gt3", "Lexus RC F LMGT3"),
            "ligier_jsp325_2025": ("car_ligier_js_p325", "Ligier JS P325"),
            "mclaren_720sgt3evo_2023": ("car_mclaren_720s_gt3", "McLaren 720S Evo"),
            "mercedes_amggt3evo_2025": ("car_mercedes_amg_gt3", "Mercedes-AMG LMGT3"),
            "oreca_07_elms_2023": ("car_oreca_07_2023", "Oreca 07 Gibson"),
            "oreca_07_lm_2023": ("car_oreca_07_2023", "Oreca 07 Gibson"),
            "peugeot_9x8_2023": ("car_peugeot_9x8", "Peugeot 9X8"),
            "peugeot_9x8_2024": ("car_peugeot_9x8_2024", "Peugeot 9X8 2024"),
            "porsche_911rsr-19_2023": ("car_porsche_911_rsr", "Porsche 911 RSR-19"),
            "porsche_963_2023": ("car_porsche_963", "Porsche 963"),
            "sgc_007_2023": ("car_glickenhaus_007", "Glickenhaus SCG 007"),
            "toyota_gr10_2023": ("car_toyota_gr010", "Toyota GR010-Hybrid"),
            "vandervell_680_2023": ("car_vanwall_680", "Vanwall Vandervell 680"),
            "oreca_07_2026": ("car_oreca_07_2026", "Oreca 07 Gibson 2025/2026"),
            "vantage_amr_gt3evo_2024": ("car_aston_martin_vantage_gt3", "Aston Martin Vantage GT3"),
            "duqueine_d09_lmp3": ("car_duqueine_d09", "Duqueine D09 LMP3"),
            "duqueine_d09_p3": ("car_duqueine_d09", "Duqueine D09 LMP3"),
            "duqueine_d09": ("car_duqueine_d09", "Duqueine D09 LMP3"),
            "genesis_gmr_001": ("car_genesis_gmr001", "Genesis GMR-001 Hypercar"),
            "genesis_gmr-001": ("car_genesis_gmr001", "Genesis GMR-001 Hypercar"),
            "genesis_gmr001": ("car_genesis_gmr001", "Genesis GMR-001 Hypercar"),
            "genesis_hypercar": ("car_genesis_gmr001", "Genesis GMR-001 Hypercar"),
            "gmr_001_hypercar": ("car_genesis_gmr001", "Genesis GMR-001 Hypercar"),
            "gmr-001_hypercar": ("car_genesis_gmr001", "Genesis GMR-001 Hypercar"),
            "gmr001_hypercar": ("car_genesis_gmr001", "Genesis GMR-001 Hypercar"),
            "gmr_001": ("car_genesis_gmr001", "Genesis GMR-001 Hypercar"),
            "gmr-001": ("car_genesis_gmr001", "Genesis GMR-001 Hypercar"),

        }

CAR_NAME_MAP = {
        'car_alpine_a424': ['Alpine A424', ['alpine a', 'alpine endurance team', 'a424']],
        'car_aston_martin_valkyrie': ['Aston Martin Valkyrie', ['aston martin thor team']],
        'car_bmw_m_hybrid_v8': ['BMW M Hybrid V8', [ 'bmw m team wrt', 'bmw m hybrid']],
        'car_cadillac_v_series_r': ['Cadillac V-Series.R', ['cadillac v-series', 'cadillac racing', 'team jota', 'cadillac wtr', 'whelen cadillac racing', 'action express racing', 'cadillac whelen']],
        'car_ferrari_499p': ['Ferrari 499P', ['ferrari 499p', 'ferrari af corse', 'ferrari af corse', 'af corse', 'af corse', 'af corse']],
        'car_glickenhaus_007': ['Glickenhaus SCG 007', ['glickenhaus scg', 'glickenhaus racing']],
        'car_isotta_fraschini': ['Isotta Fraschini', ['isotta fraschini tip6', 'isotta tip']],
        'car_lamborghini_sc63': ['Lamborghini SC63', ['lamborghini sc', 'sc63']],
        'car_peugeot_9x8_2024': ['Peugeot 9X8 2024', ['peugeot 9x8 2024', 'peugeot totalenergies']],
        'car_peugeot_9x8': ['Peugeot 9X8', ['peugeot 9x8','peugeot totalenergies']],
        'car_porsche_963': ['Porsche 963', ['porsche 963', 'porsche penske', 'hertz team jota']],
        'car_toyota_gr010': ['Toyota GR010', ['toyota gr010', 'toyota gazoo racing', 'toyota gazoo racing', 'toyota gazoo racing']],
        'car_vanwall_680': ['Vanwall Vandervell', ['vanwall 680', 'floyd vanwall racing team']],

        # --- LMGT3 ---
        'car_ford_mustang_gt3': ['Ford Mustang LMGT3', ['mustang']],
        'car_mclaren_720s_gt3': ['McLaren 720S LMGT3 Evo', ['mclaren 720s', 'united autosport',]],
        'car_mercedes_amg_gt3': ['Mercedes-AMG LMGT3', ['mercedes-amg', 'mercedes amg']],
        'car_bmw_m4_gt3': ['BMW M4 LMGT3', ['bmw m4', 'team wrt',]],
        'car_aston_martin_vantage_gt3': ['Aston Martin Vantage GT3', ['vantage gt3', 'heart of racing', 'station',]],
        'car_corvette_z06_gt3': ['Corvette Z06 LMGT3.R', ['corvette z06', 'tf sport',]],
        'car_ferrari_296_gt3': ['Ferrari 296 LMGT3', ['ferrari 296', 'vista af corse', 'spirit of race', 'gr racing', 'kessel', 'jmw motorsport']],
        'car_lamborghini_huracan_gt3': ['Lamborghini Huracan GT3', ['huracan']],
        'car_lexus_rcf_gt3': ['Lexus RC F LMGT3', ['lexus rc f', 'akkodis asp',]],
        'car_porsche_911_gt3': ['Porsche 911 GT3 R', ['porsche 911 gt3']],

        # --- LMP2 ---
        'car_oreca_07_2023': ['Oreca 07 Gibson', [ 'oreca 07', 'prema racing', 'vector sport', 'tower motorsports', 'nielsen racing', 'duqueine team', 'inter europol competition', 'cool racing', 'graff racing', 'algarve pro racing', 'idec sport', 'panis racing', 'racing team turkey', 'crowdstrike', 'ao by tf', 'united autosports', 'alpine elf team', 'team wrt', 'af corse', 'jota', 'proton', 'rlr msport', 'team virage']],
        'car_oreca_07_2024': ['Oreca 07 Gibson 2024', [ 'prema', 'vector sport 2024', 'tower', 'nielsen racing 2024', 'duqueine team 2024', 'inter europol', 'cool racing 2024', 'graff', 'algarve pro racing 2024', 'crowdstrike racing by apr 2024','panis racing 2024', 'racing team turkey', 'crowdstrike', 'ao by tf 2024', 'united autosports 2024', 'united autosports usa 2024', 'inter europol competition 2024', 'alpine elf team', 'team wrt', 'af corse 2024', 'jota', 'proton competition 2024', 'rlr msport', 'team virage', 'idec sport 2024',  'iron lynx - proton 2025', 'proton competition 2025', 'rlr msport 2025', 'idec sport 2025',  'united autosports 2025',  'nielsen racing', 'algarve pro racing 2025', 'tds tacing 2025', 'nielsen racing 2025', 'inter europol competition 2025',  'clx - pure rxcing 2025', 'vds panis racing 2025', 'af corse 2025',  'ao by tf 2025']],

        # --- LMP3 ---
        'car_ginetta_g61': ['Ginetta G61-LT-P325-Evo', ['ginetta g61']],
        'car_ligier_js_p325': ['Ligier JS P325', ['ligier js p325', 'cool racing', 'clx motorsport', 'racing spirit of leman', 'wtm by rinaldi', 'eurointernational', 'rlr msport', 'team virage', 'inter europol', 'ultimate', 'nielsen', 'm racing', 'inter europol competition']],
        'car_duqueine_d09': ['Duqueine D09 LMP3', ['duqueine d09', 'duqueine', 'lmp3']],
        'car_oreca_07_2026': ['Oreca 07 Gibson 2025/2026', ['oreca 07', 'prema', 'vector sport', 'tower', 'nielsen racing', 'duqueine team', 'inter europol competition', 'cool racing', 'graff racing', 'algarve pro racing', 'idec sport', 'panis racing', 'racing team turkey', 'crowdstrike', 'ao by tf', 'united autosports', 'alpine elf team', 'team wrt', 'af corse', 'jota', 'proton', 'rlr msport', 'team virage']],
        'car_adess_03': ['ADESS-03 LMP3', ['adess 03', 'adess', 'adess-03']],

        # --- HYPERCAR ---
        'car_genesis_gmr001': ['Genesis GMR-001 Hypercar', ['genesis', 'gmr-001', 'gmr001', 'gmr 001']],

        # --- GTE ---
        'car_corvette_c8r_gte': ['Chevrolet Corvette C8.R', ['corvette c8.r', 'corvette racing']],
        'car_ferrari_488_gte': ['Ferrari 488 GTE', ['ferrari 488 gte', 'kessell racing', 'jmw motorsport', 'richard mille', 'walkenhorst motorsport', 'af corse']],
        'car_porsche_911_rsr': ['Porsche 911 RSR-19', ['porsche 911 rsr-19', 'rsr-19']],
        'car_aston_martin_vantage_gte': ['Aston Martin Vantage GTE', ['vantage gte', 'vantage amr gte', 'ort by tf', 'gmb motorsport', 'dstation racing', 'tf sport', 'the feart of racing',]],
    }

def _get_car_asset_and_name(vehicle_name, veh_filename=None, vehicle_class=""):
    
    if veh_filename:
        fname = veh_filename.lower().replace('\\', '/') 
        
        folder_map = CAR_FOLDER_MAP

        for folder, (asset, name) in folder_map.items():
            if folder in fname:
                return asset, name

    if not vehicle_name:
        return "lmu_logo_default", "Le Mans Ultimate"

    vehicle_name_lower = vehicle_name.lower()

    car_map = CAR_NAME_MAP

    for asset_key, data in car_map.items():
        car_real_name = data[0]
        keywords = data[1]
        
        for keyword in keywords:
            if keyword in vehicle_name_lower:
                return asset_key, car_real_name

    return "lmu_logo_default", vehicle_name


_warned_models = set()


def get_car_asset_and_name(vehicle_name, veh_filename=None, vehicle_class="", vehicle_model="", vehicle_year=""):
    if vehicle_model:
        asset, name, source = resolve_car(vehicle_model, vehicle_year)
        if source != "table" and vehicle_model not in _warned_models:
            _warned_models.add(vehicle_model)
            logger.warning(f"Modelo de carro fora da tabela ({source}): {vehicle_model!r} classe={vehicle_class!r} => {asset!r}")
    else:
        asset, name = _get_car_asset_and_name(vehicle_name, veh_filename, vehicle_class)
    logger.debug(f"Car asset resolution: vehicle_name={vehicle_name!r} vehicle_model={vehicle_model!r} vehicle_class={vehicle_class!r} => {asset!r}, {name!r}")
    return asset, name


def _strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c))


def get_track_asset_key(name):
    if not name: return 'lmu_logo'
    clean = _strip_accents(name).lower().replace("'", "")
    if 'le mans' in clean or 'sarthe' in clean: return 'lemans-sarthe'
    if 'spa' in clean or 'francorchamps' in clean: return 'spa'
    if 'monza' in clean: return 'monza'
    if 'sebring' in clean: return 'sebring'
    if 'bahrain' in clean: return 'bahrain'
    if 'portimao' in clean or 'algarve' in clean: return 'portimao'
    if 'fuji' in clean: return 'fuji'
    if 'imola' in clean: return 'imola'
    if 'cota' in clean or 'americas' in clean: return 'cota'
    if 'interlagos' in clean or 'carlos pace' in clean: return 'interlagos'
    if 'qatar' in clean or 'lusail' in clean: return 'lusail'
    if 'silverstone' in clean: return 'silverstone'
    if 'ricard' in clean: return 'paulricard'
    if 'barcelona' in clean or 'catalunya' in clean: return 'barcelona-catalunya'
    if 'daytona' in clean: return 'daytona'
    if 'laguna' in clean: return 'laguna_seca'
    if 'atlanta' in clean: return 'roadatlanta'
    if 'long beach' in clean: return 'longbeach'
    return None

# (nome exibido, chave do asset no Discord). get_track_asset_key() resolve o NOME DO JOGO para estas chaves;
# o preview usa esta lista para montar o seletor de pistas. Teste garante que as duas ficam coerentes.
TRACKS = [
    ("Le Mans", "lemans-sarthe"),
    ("Spa-Francorchamps", "spa"),
    ("Monza", "monza"),
    ("Sebring", "sebring"),
    ("Bahrain", "bahrain"),
    ("Portim\u00e3o", "portimao"),
    ("Fuji", "fuji"),
    ("Imola", "imola"),
    ("COTA", "cota"),
    ("Interlagos", "interlagos"),
    ("Qatar", "lusail"),
    ("Silverstone", "silverstone"),
    ("Paul Ricard", "paulricard"),
    ("Barcelona", "barcelona-catalunya"),
    ("Daytona", "daytona"),
    ("Laguna Seca", "laguna_seca"),
    ("Road Atlanta", "roadatlanta"),
    ("Long Beach", "longbeach"),
]

SESSIONS = ('test_day', 'practice', 'qualify', 'warmup', 'race')
GAME_MODES = ('online', 'coop', 'weekend')


# ----------------------------------------------------------------------------------------------
# Catalogo (usado pelo preview): tudo que o app sabe nomear, sem duplicar listas
# ----------------------------------------------------------------------------------------------
def list_cars():
    """[(asset, nome)] sem repeticao, na ordem: tabela de lmu/cars.py, pastas .veh, nomes de equipe, palavras-chave."""
    seen, out = set(), []

    def add(asset, name):
        if asset and asset not in seen and asset != "lmu_logo_default":
            seen.add(asset)
            out.append((asset, name))

    for asset, name, variants in MODEL_TABLE.values():
        add(asset, name)
        for _year, vasset in variants.items():
            add(vasset, f"{name} ({_year})")
    for asset, name in CAR_FOLDER_MAP.values():
        add(asset, name)
    for asset, data in CAR_NAME_MAP.items():
        add(asset, data[0])
    for _words, asset, name in KEYWORD_FALLBACK:
        add(asset, name)
    return out


# ----------------------------------------------------------------------------------------------
# Icones de patente (DR) em assets/ranks: bronze / prata / ouro / platina
# ----------------------------------------------------------------------------------------------
RANK_KEYWORDS = {'B': ('bronze', 'bronz'), 'S': ('silver', 'prata'), 'G': ('gold', 'ouro'), 'P': ('platinum', 'platina')}
DEFAULT_RANK_ASSETS = {'B': 'rank_bronze', 'S': 'rank_silver', 'G': 'rank_gold', 'P': 'rank_platinum'}


def rank_asset_keys(base_dir, overrides=None):
    """letra do rank (B/S/G/P) -> chave do asset. Procura em assets/ranks (ou assets/ranked) arquivos com
    bronze/silver/gold/platinum (ou prata/ouro/platina) no nome; o que nao achar usa DEFAULT_RANK_ASSETS.
    `overrides` (config racecontrol.rank_assets) manda em tudo. Chaves em minusculas (o Discord ignora maiusculas)."""
    found = {}
    for sub in ('ranks', 'ranked'):
        for key in scan_asset_keys(base_dir, sub):
            low = key.lower()
            for letter, words in RANK_KEYWORDS.items():
                if letter not in found and any(w in low for w in words):
                    found[letter] = low
    merged = {**DEFAULT_RANK_ASSETS, **found}
    for letter, key in (overrides or {}).items():
        if letter in merged and isinstance(key, str) and key.strip():
            merged[letter] = key.strip()
    return merged


LARGE_MODES = ('auto', 'car', 'track')
SMALL_MODES = ('auto', 'badge', 'rank')


def large_image_mode(config):
    """Imagem grande: 'auto' (alterna carro/pista), 'car' ou 'track'. Configs antigas so tinham cycle_track_image."""
    mode = (config or {}).get('large_image_mode')
    if mode in LARGE_MODES:
        return mode
    return 'auto' if (config or {}).get('cycle_track_image', True) else 'car'


def mode_labels(kind):
    """{valor: texto no idioma atual} para as opcoes da janela. kind: 'large' ou 'small'."""
    if kind == 'large':
        return {'auto': get_text('ui_opt_alternate'), 'car': get_text('ui_opt_car'), 'track': get_text('ui_opt_track')}
    return {'auto': get_text('ui_opt_alternate'), 'badge': get_text('ui_opt_badge'), 'rank': get_text('ui_opt_rank')}


def mode_from_label(kind, label, default='auto'):
    for value, text in mode_labels(kind).items():
        if text == label:
            return value
    return default


def pick_small_image(badge_asset, rank_asset, config, now):
    """Icone pequeno: alterna badge <-> rank a cada `cycle_badge_seconds` (15 s). So alterna se existirem os dois."""
    mode = config.get('small_image_mode', 'auto')
    if mode == 'badge':
        return badge_asset or ''
    if mode == 'rank':
        return rank_asset or ''
    if not (badge_asset and rank_asset):
        return badge_asset or rank_asset or ''
    if not config.get('cycle_rank_image', True):
        return badge_asset
    try:
        secs = max(3, int(config.get('cycle_badge_seconds', 15)))
    except (TypeError, ValueError):
        secs = 15
    return rank_asset if (int(now) // secs) % 2 == 1 else badge_asset


def list_tracks():
    return list(TRACKS)


def scan_asset_keys(base_dir, subdir):
    """Chaves (nome do arquivo sem extensao) em assets/<subdir>. Serve para testar imagem nova antes de mapear."""
    assets = os.path.join(base_dir, "assets")
    folder = os.path.join(assets, subdir)
    try:
        if subdir and not os.path.isdir(folder):          # pasta com outra caixa: 'Ranked' x 'ranked'
            match = next((d for d in os.listdir(assets) if d.lower() == subdir.lower()), None)
            folder = os.path.join(assets, match) if match else folder
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    return [os.path.splitext(n)[0] for n in names if n.lower().endswith((".png", ".jpg", ".jpeg"))]


def format_clock(seconds):
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins:02d}:{secs:02d}"


def parse_clock(text):
    """'43:20' -> 2600, '1:05:00' -> 3900, '90' -> 90. None se invalido."""
    parts = str(text or "").strip().split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if not nums or len(nums) > 3 or any(n < 0 for n in nums):
        return None
    total = 0
    for n in nums:
        total = total * 60 + n
    return total


# ----------------------------------------------------------------------------------------------
# Montagem do status (identica para o app e para o preview)
# ----------------------------------------------------------------------------------------------
def build_time_info(result, session_raw):
    game_phase = result.get('game_phase', 5)
    current_et = result.get('current_et', 0.0)
    end_et = result.get('end_et', 0.0)
    lap = max(1, result.get('lap', 1))
    total_laps = result.get('total_laps', 0)

    if game_phase == 0:
        return get_text('waiting')
    if game_phase in (1, 2):
        return get_text('grid')
    if game_phase == 3:
        return get_text('formation_lap')
    if game_phase == 4:
        return get_text('countdown')

    has_valid_timer = 0 < end_et < 172800
    time_left = end_et - current_et if has_valid_timer else 0
    if has_valid_timer and time_left > 0 and (total_laps >= 1000 or total_laps <= 0):
        return get_text('time_remaining', format_clock(time_left))
    if 0 < total_laps < 1000:
        laps_left = max(0, total_laps - lap + 1)
        if laps_left <= 1:
            return get_text('last_lap')
        return get_text('lap_progress', lap, total_laps, laps_left)
    if has_valid_timer and time_left <= 0 and (total_laps >= 1000 or total_laps <= 0):
        return get_text('last_lap') if session_raw == 'race' else get_text('lap_single', lap)
    return get_text('lap_single', lap)


def build_presence(result, config, now, badge_asset="", badge_text="", rank_asset=""):
    """Status de quem esta NA PISTA. `result` tem o formato de RF2Data.update() (status connected_driving).

    Chaves opcionais so do preview: car_asset / car_name / track_asset (pulam a resolucao) e
    image_mode ('auto' alterna, 'car' ou 'track' fixa).
    """
    session_raw = (result.get('session', '') or '').lower()
    track_name = result.get('track_name', '')
    vehicle_name = result.get('vehicle_name', '')
    pos = result.get('position', 0)

    session_display = get_text(session_raw)
    time_info = build_time_info(result, session_raw)

    num_cars = result.get('num_cars', 0)
    mode_key = result.get('game_mode', '')
    # Posicao/total na CLASSE do jogador; entre parenteses, carros na sessao / vagas (so online)
    class_pos = result.get('class_position') or pos
    class_cars = result.get('class_cars') or num_cars
    pos_text = f"P{class_pos}/{class_cars}" if class_cars >= class_pos > 0 else f"P{class_pos}"
    if config.get("show_party_size", True):
        grid = party_size(mode_key, num_cars, result.get('max_players', 0))
        if grid:
            pos_text = f"{pos_text} ({get_text('grid_of', *grid)})"
    mode_text = get_text(f"mode_{mode_key}") if mode_key else ""
    details = " | ".join(p for p in (time_info, pos_text, mode_text) if p)
    state = " | ".join(p for p in (track_name, vehicle_name, session_display) if p)

    if result.get('car_asset'):
        car_asset, car_real_name = result['car_asset'], result.get('car_name') or vehicle_name
    else:
        car_asset, car_real_name = get_car_asset_and_name(
            vehicle_name, result.get('veh_filename', ''), result.get('vehicle_class', ''),
            result.get('vehicle_model', ''), result.get('vehicle_year', ''))
    track_asset = result.get('track_asset') or get_track_asset_key(track_name)

    image_mode = result.get('image_mode') or large_image_mode(config)
    if image_mode == 'auto':
        cycle_enabled = True
        try:
            car_secs = max(3, int(config.get("cycle_car_seconds", 10)))
            track_secs = max(3, int(config.get("cycle_track_seconds", 5)))
        except (TypeError, ValueError):
            car_secs, track_secs = 10, 5
        # Carro por car_secs, depois pista por track_secs (so quando a pista tem imagem)
        show_track = bool(cycle_enabled) and int(now) % (car_secs + track_secs) >= car_secs
    else:
        show_track = image_mode == 'track'

    if show_track and track_asset not in (None, 'lmu_logo'):
        large_image, large_text = track_asset, track_name
    else:
        large_image, large_text = car_asset, car_real_name

    return {
        "details": details, "state": state,
        "large_image": large_image, "large_text": large_text,
        "small_image": pick_small_image(badge_asset, rank_asset, config, now), "small_text": badge_text,
    }


def build_menu_presence(badge_asset="", badge_text="", rank_asset="", config=None, now: float = 0.0):
    return {
        "details": get_text('menu_details'), "state": get_text('menu'),
        "large_image": "lmu_logo", "large_text": "Le Mans Ultimate",
        "small_image": pick_small_image(badge_asset, rank_asset, config or {}, now), "small_text": badge_text,
    }
