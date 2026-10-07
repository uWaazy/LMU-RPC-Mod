import sys
import os
import time
import threading
import tkinter as tk
import tkinter.messagebox
import locale
import logging
from logging.handlers import RotatingFileHandler
import json
import winreg
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), 'pyLMUSharedMemory'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'pyRfactor2SharedMemory'))

try:
    from pypresence import Presence
    from pystray import Icon, MenuItem, Menu
    from PIL import Image, ImageDraw, ImageTk
    import customtkinter as ctk
    import psutil
    from pyLMUSharedMemory.lmu_data import SimInfo
    try:
        from version import VERSION, BUILD_TYPE, AUTHOR
    except ImportError:
        VERSION = ".0.1"
        BUILD_TYPE = "DEV"
        AUTHOR = "uWaazy"
except ImportError as e:
    root = tk.Tk()
    root.withdraw()
    
    err_msg = str(e)
    if "pyLMUSharedMemory" in err_msg or "pyRfactor2SharedMemory" in err_msg:
        instruction = "Verifique se as pastas 'pyLMUSharedMemory' e 'pyRfactor2SharedMemory' estão presentes."
    else:
        instruction = "Execute 'pip install -r requirements.txt' para instalar as dependências."

    tkinter.messagebox.showerror("Erro Crítico - Dependência Faltando", 
        f"O aplicativo não pode iniciar porque falta um componente:\n\n{e}\n\n"
        f"Solução: {instruction}")
    sys.exit(1)

def setup_logging():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    logger = logging.getLogger("LMU_RPC")
    logger.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    
    file_handler = RotatingFileHandler("lmu_rpc.log", maxBytes=2*1024*1024, backupCount=2, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

IS_FROZEN = getattr(sys, 'frozen', False)

if IS_FROZEN:

    try:
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = sys.stdout
    except Exception:
        pass

    logger = logging.getLogger("LMU_RPC")
    logger.addHandler(logging.NullHandler())
else:
    logger = setup_logging()

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Exceção não tratada:", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

CLIENT_ID = '1463577784394973392'

LANGUAGE = 'en'

if "--lang" in sys.argv:
    try:
        index = sys.argv.index("--lang")
        arg_lang = sys.argv[index + 1].lower()
        if arg_lang.startswith("pt"):
            LANGUAGE = 'pt-br'
        elif arg_lang.startswith("es"):
            LANGUAGE = 'es'
        print(f"[DEBUG] Idioma forçado via argumento: {LANGUAGE}")
    except IndexError:
        print("[AVISO] Argumento --lang usado sem especificar idioma. Usando padrão.")

else:
    try:
        sys_lang = locale.getdefaultlocale()[0]
        if sys_lang:
            if str(sys_lang).lower().startswith('pt'):
                LANGUAGE = 'pt-br'
            elif str(sys_lang).lower().startswith('es'):
                LANGUAGE = 'es'
    except:
        pass
    print(f"[DEBUG] Idioma detectado do sistema: {LANGUAGE}")

TRANSLATIONS = {
    'pt-br': {
        'test_day': 'Dia de Teste',
        'practice': 'Treino Livre',
        'qualify': 'Qualificação',
        'warmup': 'Aquecimento',
        'race': 'Corrida',
        'menu': 'No Menu Principal',
        'lobby': 'No Lobby',
        'time_remaining': 'Faltam {}',
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
        'lmu_exclusive_data_note': 'Safety Rating: {} | Safety: {} | Badge: {} (Dados LMU simulados)',
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
        'ui_autostart': 'Iniciar com o Windows'
    },
    'en': {
        'test_day': 'Test Day',
        'practice': 'Practice',
        'qualify': 'Qualifying',
        'warmup': 'Warmup',
        'race': 'Race',
        'menu': 'In Menus',
        'lobby': 'In Lobby',
        'time_remaining': '{} remaining',
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
        'lmu_exclusive_data_note': 'Safety Rating: {} | Safety: {} | Badge: {} (Simulated LMU data)',
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
        'ui_autostart': 'Start with Windows'
    },
    'es': {
        'test_day': 'Día de Pruebas',
        'practice': 'Práctica',
        'qualify': 'Clasificación',
        'warmup': 'Calentamiento',
        'race': 'Carrera',
        'menu': 'En los Menús',
        'lobby': 'En el Lobby',
        'time_remaining': '{} restantes',
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
        'lmu_exclusive_data_note': 'Safety Rating: {} | Safety: {} | Badge: {} (Datos LMU simulados)',
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
        'ui_connection_error_msg': 'No se pudo conectar a Discord.\nVerifique si Discord está abierto.\n\nError: {}',
        'ui_autostart': 'Iniciar con Windows'
    }
}

def get_text(key, *args):
    lang = TRANSLATIONS.get(LANGUAGE, TRANSLATIONS['en'])
    text = lang.get(key, TRANSLATIONS['en'].get(key, key))
    if args:
        return text.format(*args)
    return text

class RF2Data:
    def __init__(self):
        self.lmu = SimInfo()
        self.last_et = -1.0
        self.stale_counter = 0
        self.vehicle_name_cache = {}
        logger.info("Módulo de leitura de memória (pyLMUSharedMemory) inicializado.")

    def reconnect(self):
        try:
            self.lmu = SimInfo()
        except Exception as e:
            logger.debug(f"Erro ao reconectar SimInfo: {e}")

    def get_session_name(self, session_id):
        if session_id == 0: return 'test_day'
        if 1 <= session_id <= 4: return 'practice'
        if 5 <= session_id <= 8: return 'qualify'
        if session_id == 9: return 'warmup'
        if 10 <= session_id <= 13: return 'race'
        return 'menu'

    def get_player_ranks(self, vehicle):
        dr_value = 0.0
        sr_value = 0.0
        dr_tier = "N/A"
        sr_tier = "N/A"
        
        if vehicle:
            try:
                dr_value = getattr(vehicle, 'mDriverRating', 0.0) or 0.0
                sr_value = getattr(vehicle, 'mSafetyRating', 0.0) or 0.0
            except (AttributeError, TypeError):
                pass

        # Convert numeric ratings to tier strings
        dr_tier = rating_to_string(dr_value) if dr_value > 0 else "N/A"
        sr_tier = rating_to_string(sr_value) if sr_value > 0 else "N/A"

        return {
            'dr_value': dr_value,
            'sr_value': sr_value,
            'dr_tier': dr_tier,
            'sr_tier': sr_tier,
            'sr_class': sr_tier,
            'sr_number': sr_value
        }

    def _safe_decode(self, raw_bytes):
        try:
            if raw_bytes is None:
                return ""
            return raw_bytes.decode('utf-8', errors='ignore').split('\x00')[0].strip()
        except Exception:
            return ""

    def get_player_vehicle_from_api(self, raw_vehicle_name, veh_filename):
        cache_key = (veh_filename or "").lower().strip(), (raw_vehicle_name or "").lower().strip()
        if cache_key in self.vehicle_name_cache:
            cached_name = self.vehicle_name_cache[cache_key]
            logger.debug(f"Vehicle name translation cache hit: {cache_key} -> {cached_name}")
            return cached_name

        logger.debug(f"Vehicle name translation cache miss: raw_vehicle_name={raw_vehicle_name!r}, veh_filename={veh_filename!r}")
        try:
            response = requests.get('http://localhost:6397/rest/sessions/getAllVehicles', timeout=1.0)
            if response.status_code == 200:
                vehicles = response.json()
                for v in vehicles:
                    api_id = v.get("id", "")
                    api_veh_file = v.get("vehFile", "")
                    api_veh_name = v.get("vehicle", "")
                    api_desc = v.get("desc", "")

                    # Match primário e infalível: ID único do arquivo .VEH
                    if veh_filename and (veh_filename.lower() in api_id.lower() or veh_filename.lower() in api_veh_file.lower()):
                        path = v.get("fullPathTree", "")
                        if path:
                            clean_name = path.split(",")[-1].strip()
                            self.vehicle_name_cache[cache_key] = clean_name
                            return clean_name

                    # Match secundário: Nome da string caso o veh_filename falhe
                    if raw_vehicle_name.lower() in api_veh_name.lower() or raw_vehicle_name.lower() in api_desc.lower():
                        path = v.get("fullPathTree", "")
                        if path:
                            clean_name = path.split(",")[-1].strip()
                            self.vehicle_name_cache[cache_key] = clean_name
                            return clean_name
        except Exception as e:
            logger.debug(f"API translation failed: {e}")
        return raw_vehicle_name

    def normalize_track_name(self, raw_name):
        if not raw_name:
            return raw_name

        s = raw_name.lower()
        track_display = raw_name

        track_map = {
            "carlos pace": "Interlagos",
            "interlagos": "Interlagos",
            "algarve": "Portimão",
            "portimao": "Portimão",
            "enzo e dino": "Imola",
            "imola": "Imola",
            "monza": "Monza",
            "sarthe": "Le Mans",
            "le mans": "Le Mans",
            "spa": "Spa-Francorchamps",
            "francorchamps": "Spa-Francorchamps",
            "sebring": "Sebring",
            "bahrain": "Bahrain",
            "fuji": "Fuji",
            "cota": "COTA",
            "americas": "COTA",
            "qatar": "Qatar",
            "lusail": "Qatar",
            "silverstone": "Silverstone",
            "paul ricard": "Paul Ricard",
            "ricard": "Paul Ricard",
            "barcelona": "Barcelona",
            "catalunya": "Barcelona",
            "daytona": "Daytona",
            "laguna seca": "Laguna Seca",
            "laguna": "Laguna Seca",
            "road atlanta": "Road Atlanta",
            "atlanta": "Road Atlanta",
            "long beach": "Long Beach",
        }

        for key, val in track_map.items():
            if key in s:
                track_display = val
                break

        return track_display

    def update(self):
        try:
            lmu_data = self.lmu.LMUData
            if not lmu_data:
                self.reconnect()
                lmu_data = self.lmu.LMUData
                if not lmu_data:
                    return {'status': 'game_closed'}

            scoring = lmu_data.scoring
            
            current_et = scoring.scoringInfo.mCurrentET
            
            if current_et == self.last_et:
                self.stale_counter += 1
            else:
                self.stale_counter = 0
                self.last_et = current_et
            
            if self.stale_counter > 2:
                player_vehicle = None
                try:
                    for vehicle in scoring.vehScoringInfo:
                        if vehicle.mIsPlayer:
                            player_vehicle = vehicle
                            break
                except: pass
                stale_ranks = self.get_player_ranks(player_vehicle)

                lmu_data = None
                scoring = None
                player_vehicle = None
                self.reconnect()
                lmu_data = self.lmu.LMUData
                
                is_stale = False
                if not lmu_data:
                    is_stale = True
                else:
                    try:
                        scoring = lmu_data.scoring
                        if scoring.scoringInfo.mCurrentET == self.last_et:
                            is_stale = True
                    except:
                        is_stale = True

                if is_stale:
                    return {
                        'status': 'connected_menu',
                        'session': 'menu',
                        'track_name': '',
                        'ranks': stale_ranks
                    }
            
            session_name = self.get_session_name(scoring.scoringInfo.mSession)
            track_name_raw = self._safe_decode(scoring.scoringInfo.mTrackName)
            track_name = self.normalize_track_name(track_name_raw)
            
            player_vehicle = None
            for vehicle in scoring.vehScoringInfo:
                if vehicle.mIsPlayer:
                    player_vehicle = vehicle
                    break
            
            ranks = self.get_player_ranks(player_vehicle)

            if not player_vehicle:
                return {
                    'status': 'connected_menu',
                    'session': session_name,
                    'track_name': track_name,
                    'ranks': ranks
                }

            raw_vehicle_name = self._safe_decode(player_vehicle.mVehicleName)
            if raw_vehicle_name.endswith(":LM"):
                raw_vehicle_name = raw_vehicle_name[:-3]
            elif raw_vehicle_name.endswith(":ELMS"):
                raw_vehicle_name = raw_vehicle_name[:-5]

            # Lê o nome do ficheiro (ID do carro) de forma segura:
            try:
                veh_filename = player_vehicle.mVehFilename.decode('utf-8', errors='ignore').split('\x00')[0].strip()
            except Exception:
                veh_filename = ""

            try:
                clean_vehicle_name = self.get_player_vehicle_from_api(raw_vehicle_name, veh_filename)
            except Exception:
                clean_vehicle_name = raw_vehicle_name

            vehicle_name = clean_vehicle_name or raw_vehicle_name
            logger.debug(f"Using vehicle name for RPC: {vehicle_name}")

            vehicle_class = self._safe_decode(player_vehicle.mVehicleClass)
            veh_filename = self._safe_decode(player_vehicle.mVehFilename)

            return {
                'status': 'connected_driving',
                'vehicle_name': vehicle_name,
                'vehicle_class': vehicle_class,
                'veh_filename': veh_filename,
                'track_name': track_name,
                'session': self.get_session_name(scoring.scoringInfo.mSession),
                'position': player_vehicle.mPlace,
                'lap': player_vehicle.mTotalLaps + 1,
                'total_laps': scoring.scoringInfo.mMaxLaps,
                'current_et': scoring.scoringInfo.mCurrentET,
                'end_et': scoring.scoringInfo.mEndET,
                'ranks': ranks,
                'game_phase': scoring.scoringInfo.mGamePhase
            }

        except Exception as e:
            logger.debug(f"Erro na leitura de memória (jogo fechado ou carregando): {e}")
            return {'status': 'game_closed'}

def _get_car_asset_and_name(vehicle_name, veh_filename=None, vehicle_class=""):
    
    if veh_filename:
        fname = veh_filename.lower().replace('\\', '/') 
        
        folder_map = {
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

        for folder, (asset, name) in folder_map.items():
            if folder in fname:
                return asset, name

    if not vehicle_name:
        return "lmu_logo_default", "Le Mans Ultimate"

    vehicle_name_lower = vehicle_name.lower()

    car_map = {
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

    for asset_key, data in car_map.items():
        car_real_name = data[0]
        keywords = data[1]
        
        for keyword in keywords:
            if keyword in vehicle_name_lower:
                return asset_key, car_real_name

    return "lmu_logo_default", vehicle_name 


def get_car_asset_and_name(vehicle_name, veh_filename=None, vehicle_class=""):
    asset, name = _get_car_asset_and_name(vehicle_name, veh_filename, vehicle_class)
    logger.debug(f"Car asset resolution: vehicle_name={vehicle_name!r} veh_filename={veh_filename!r} vehicle_class={vehicle_class!r} => {asset!r}, {name!r}")
    return asset, name


def get_track_asset_key(name):
    if not name: return 'lmu_logo'
    clean = name.lower().replace("'", "")
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

def get_game_pid():

    for proc in psutil.process_iter():
        try:

            if proc.name() in ['LeMansUltimate.exe', 'Le Mans Ultimate.exe']:
                return proc.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception:
            continue
    return None

def create_icon_image():
    icon_path = resource_path("icon.png")
    if os.path.exists(icon_path):
        try:
            return Image.open(icon_path)
        except:
            pass
            
    image = Image.new('RGB', (64, 64), (0, 50, 100))
    dc = ImageDraw.Draw(image)
    dc.rectangle((32, 0, 64, 32), fill=(255, 255, 255))
    dc.rectangle((0, 32, 32, 64), fill=(255, 255, 255))
    return image

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

VALID_BADGES = {
    "sr-clean", "sr-rookie", "sr-warning", "sr-probation", "sr-saint",
    "sr-danger", "sr-noob", "content-creator", "early-access",
    "irl-driver", "s397", "test-driver"
}

class ToolTip:
    def __init__(self, widget, text_func):
        self.widget = widget
        self.text_func = text_func
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text_func:
            return
        text = self.text_func() if callable(self.text_func) else str(self.text_func)
        if not text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=text, justify=tk.LEFT,
                         background="#2f3136", foreground="#ffffff",
                         relief=tk.SOLID, borderwidth=1,
                         font=("Segoe UI", 9, "normal"), padx=6, pady=4)
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            try:
                tw.destroy()
            except Exception:
                pass



def rating_to_string(rating_value):
    """Converte valor numérico de rating para formato de tier (ex: 1 -> 'Silver 1', 3 -> 'Gold 3')"""
    if isinstance(rating_value, str):
        return rating_value.strip()
    try:
        val = float(rating_value)
    except (ValueError, TypeError):
        return str(rating_value)
    
    # LMU rating tiers: Bronze < Silver < Gold < Platinum
    # Based on typical LMU rating ranges
    if val >= 1000:
        tier = "Platinum"
        rank = min(3, max(1, round(val / 333) - 2))
    elif val >= 600:
        tier = "Gold"
        rank = min(3, max(1, round(val / 200) - 1))
    elif val >= 300:
        tier = "Silver"
        rank = min(3, max(1, round(val / 100)))
    else:
        tier = "Bronze"
        rank = min(3, max(1, round(val / 100) + 1))
    
    return f"{tier} {rank}"


class RaceControlProfile:
    def __init__(self, config=None):
        self.config = config or {}
        self.dr = str(self.config.get("dr", "S1 (64%)")).strip()
        self.sr = str(self.config.get("sr", "Gold S3 (82%)")).strip()
        self.badge = str(self.config.get("badge", "sr-clean")).strip()
        self.last_fetch_time = 0
        self.lock = threading.Lock()
        self.dr_value = 0.0
        self.sr_value = 0.0

    def get_badge_asset(self):
        with self.lock:
            b = self.badge.lower().strip()
            if not b:
                return "sr-clean"
            if b.endswith(".png") or b.endswith(".jpg"):
                b = os.path.splitext(b)[0]
            clean = b.replace("badge_", "").replace("_", "-")
            if clean in VALID_BADGES:
                return clean
            if b in VALID_BADGES:
                return b
            return "sr-clean"

    def get_tooltip(self):
        with self.lock:
            dr_val = self.dr if self.dr else "N/A"
            sr_val = self.sr if self.sr else "N/A"
            return f"DR: {dr_val} | SR: {sr_val}"

    def update_from_config(self, config):
        with self.lock:
            self.config = config
            if "dr" in config and config["dr"]:
                self.dr = str(config["dr"]).strip()
            if "sr" in config and config["sr"]:
                self.sr = str(config["sr"]).strip()
            if "badge" in config and config["badge"]:
                self.badge = str(config["badge"]).strip()

    def refresh_from_api(self):
        """Consulta assíncrona da API REST interna do LMU (porta 6397) para dados de perfil/ranks se disponíveis."""
        now = time.time()
        if now - self.last_fetch_time < 2:
            return
        self.last_fetch_time = now

        endpoints = [
            "http://localhost:6397/rest/profile",
            "http://localhost:6397/rest/player",
            "http://localhost:6397/rest/racecontrol/profile",
            "http://localhost:6397/racecontrol/user"
        ]

        def _fetch():
            for url in endpoints:
                try:
                    resp = requests.get(url, timeout=1.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        logger.debug(f"API profile hit from {url}: {data}")
                        with self.lock:
                            if isinstance(data, dict):
                                if "dr" in data and data["dr"]:
                                    dr_val = data["dr"]
                                    self.dr = rating_to_string(dr_val)
                                elif "driverRating" in data and data["driverRating"]:
                                    dr_val = data["driverRating"]
                                    self.dr = rating_to_string(dr_val)
                                if "sr" in data and data["sr"]:
                                    sr_val = data["sr"]
                                    self.sr = rating_to_string(sr_val)
                                elif "safetyRating" in data and data["safetyRating"]:
                                    sr_val = data["safetyRating"]
                                    self.sr = rating_to_string(sr_val)
                                if "badge" in data and data["badge"]:
                                    self.badge = str(data["badge"]).strip()
                        break
                except Exception:
                    continue

        threading.Thread(target=_fetch, daemon=True).start()

    def refresh_from_memory(self, result):
        """Atualiza DR/SR diretamente da memória compartilhada do LMU."""
        ranks = result.get('ranks', {}) if isinstance(result, dict) else {}
        if not ranks:
            return
        try:
            dr_val = ranks.get('dr_value', 0.0)
            sr_val = ranks.get('sr_value', 0.0)
            if dr_val and dr_val > 0:
                self.dr_value = float(dr_val)
                self.dr = rating_to_string(self.dr_value)
            if sr_val and sr_val > 0:
                self.sr_value = float(sr_val)
                self.sr = rating_to_string(self.sr_value)
        except (ValueError, TypeError):
            pass


class LMU_RPC_App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("")
        self.geometry("420x420")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.configure(fg_color="#0f1012")

        try:
            icon_ico = resource_path("icon.ico")
            icon_png = resource_path("icon.png")
            
            if os.path.exists(icon_ico):
                self.iconbitmap(icon_ico)
            elif os.path.exists(icon_png):
                icon_img = ImageTk.PhotoImage(file=icon_png)
                self.wm_iconphoto(False, icon_img)
        except Exception:
            pass

        self.rf2 = RF2Data()
        self.rpc = None
        self.running = False
        self.start_time = None
        self.last_state = None
        self.tray_icon = None
        self.img_cache = {}
        
        self.config = self.load_config()
        self.rc_profile = RaceControlProfile(self.config)

        self.setup_ui()
        logger.info("App LMU RPC Mod iniciado. Versão 2.0 (Modern UI)")

    def setup_ui(self):
        # Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) 
        self.grid_rowconfigure(1, weight=0) 
        self.grid_rowconfigure(2, weight=0) 
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=1) 

        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, pady=(0, 15), sticky="ew")

        try:
            banner_path = resource_path("preview.png")
            if os.path.exists(banner_path):
                pil_banner = Image.open(banner_path)
                # Redimensiona se for muito largo para a janela (max 400px)
                if pil_banner.width > 400:
                    ratio = 400 / pil_banner.width
                    pil_banner = pil_banner.resize((400, int(pil_banner.height * ratio)), Image.Resampling.LANCZOS)
                
                banner_img = ctk.CTkImage(light_image=pil_banner, dark_image=pil_banner, size=pil_banner.size)
                self.lbl_banner = ctk.CTkLabel(self.header_frame, text="", image=banner_img)
                self.lbl_banner.pack(pady=0)
        except Exception:
            pass

        self.switch_var = ctk.BooleanVar(value=self.config.get("autostart", False))
        self.switch_autostart = ctk.CTkSwitch(
            self.header_frame, 
            text=get_text('ui_autostart'), 
            command=self.toggle_autostart,
            variable=self.switch_var,
            font=("Segoe UI", 11),
            height=20,
            width=40,
            progress_color="#1f6aa5"
        )
        self.switch_autostart.pack(pady=(5, 0), padx=20, anchor="e")

        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.grid(row=1, column=0, pady=(0, 10))
        
        self.lbl_status = ctk.CTkLabel(self.status_frame, text=get_text('ui_disconnected'), font=("Segoe UI", 22, "bold"), text_color="#FF5555")
        self.lbl_status.pack()
        
        self.lbl_substatus = ctk.CTkLabel(self.status_frame, text=get_text('ui_service_stopped'), font=("Segoe UI", 13), text_color="gray")
        self.lbl_substatus.pack()

        self.card_frame = ctk.CTkFrame(self, fg_color="#1e1f22", corner_radius=15, width=380, height=110, border_width=0)
        self.card_frame.grid(row=2, column=0, padx=20, pady=(0, 20))
        self.card_frame.grid_propagate(False) 

        self.lbl_large_img = ctk.CTkLabel(self.card_frame, text="", width=90, height=90)
        self.lbl_large_img.place(x=10, y=10)

        self.lbl_small_img = ctk.CTkLabel(self.card_frame, text="", width=28, height=28, fg_color="transparent")
        self.lbl_small_img.place(x=74, y=74)
        self.lbl_small_img.lift()
        self.badge_tooltip = ToolTip(self.lbl_small_img, self.rc_profile.get_tooltip)

        self.lbl_card_title = ctk.CTkLabel(self.card_frame, text="Le Mans Ultimate", font=("Segoe UI", 13, "bold"), text_color="white", anchor="w")
        self.lbl_card_title.place(x=110, y=12)

        self.lbl_card_details = ctk.CTkLabel(self.card_frame, text="...", font=("Segoe UI", 12), text_color="#b9bbbe", anchor="w")
        self.lbl_card_details.place(x=110, y=35)

        self.lbl_card_state = ctk.CTkLabel(self.card_frame, text="...", font=("Segoe UI", 12), text_color="#b9bbbe", anchor="w")
        self.lbl_card_state.place(x=110, y=55)

        self.lbl_card_timer = ctk.CTkLabel(self.card_frame, text="00:00 elapsed", font=("Segoe UI", 12), text_color="#b9bbbe", anchor="w")
        self.lbl_card_timer.place(x=110, y=75)

        # 3. Botões de Controle
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=3, column=0, pady=0)
        
        self.btn_start = ctk.CTkButton(self.btn_frame, text=get_text('ui_start_rpc'), command=self.start_rpc, 
                                       fg_color="#1f6aa5", hover_color="#144870", width=160, height=45, corner_radius=8, font=("Segoe UI", 13, "bold"))
        self.btn_start.grid(row=0, column=0, padx=10)
        
        self.btn_stop = ctk.CTkButton(self.btn_frame, text=get_text('ui_stop_rpc'), command=self.stop_rpc, 
                                      fg_color="#d32f2f", hover_color="#9a0007", width=160, height=45, corner_radius=8, font=("Segoe UI", 13, "bold"), state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=10)

        if BUILD_TYPE == "RELEASE":
            ver_text = f"v{VERSION} | by {AUTHOR}"
        else:
            ver_text = f"{BUILD_TYPE} {VERSION} | by {AUTHOR}"
            
        self.lbl_footer = ctk.CTkLabel(self, text=ver_text, font=("Segoe UI", 10), text_color="gray50")
        self.lbl_footer.grid(row=4, column=0, pady=(15, 10))

    def load_preview_image(self, key, size, circular=False):
        cache_key = f"{key}_{size}_{circular}"
        if cache_key in self.img_cache:
            return self.img_cache[cache_key]

        pil_img = None
        base_path = os.path.dirname(os.path.abspath(__file__))
        
        # Subpastas de assets suportadas: cars, badges, ranks, tracks e raiz de assets
        subdirs = ["cars", "badges", "ranks", "tracks", ""]
        candidates = []
        for subdir in subdirs:
            folder = os.path.join(base_path, "assets", subdir) if subdir else os.path.join(base_path, "assets")
            candidates.append(os.path.join(folder, f"{key}.png"))
            candidates.append(os.path.join(folder, f"{key}.jpg"))
            res_folder = resource_path(os.path.join("assets", subdir)) if subdir else resource_path("assets")
            candidates.append(os.path.join(res_folder, f"{key}.png"))
            candidates.append(os.path.join(res_folder, f"{key}.jpg"))

        candidates.extend([
            os.path.join(base_path, f"{key}.png"),
            os.path.join(base_path, f"{key}.jpg"),
            resource_path(f"{key}.png"),
            resource_path(f"{key}.jpg"),
            os.path.join(base_path, "assets", "cars", "lmu_logo.png"),
            os.path.join(base_path, "assets", "lmu_logo.png"),
            resource_path(os.path.join("assets", "lmu_logo.png")),
            resource_path("lmu_logo.png")
        ])

        for path in candidates:
            if os.path.exists(path):
                try:
                    pil_img = Image.open(path)
                    break
                except Exception:
                    pass

        if not pil_img:
            pil_img = Image.new('RGB', size, (47, 49, 54))

        pil_img = pil_img.resize(size, Image.Resampling.LANCZOS)

        if circular:
            mask = Image.new('L', size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0) + size, fill=255)
            
            pil_img = pil_img.convert("RGBA")
            output = Image.new('RGBA', size, (0, 0, 0, 0))
            output.paste(pil_img, (0, 0), mask)
            
            # Borda sutil de 2px estilo Discord
            border_draw = ImageDraw.Draw(output)
            border_draw.ellipse((0, 0, size[0] - 1, size[1] - 1), outline=(30, 31, 34, 255), width=2)
            pil_img = output

        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
        self.img_cache[cache_key] = ctk_img
        return ctk_img

    def start_rpc(self):
        if self.running: return
        try:
            self.rpc = Presence(CLIENT_ID)
            self.rpc.connect()
            self.running = True
            self.lbl_status.configure(text=get_text('ui_connected_discord'), text_color="#3BA55C") # Verde Discord
            self.lbl_substatus.configure(text=get_text('ui_waiting_game_sub'))
            logger.info("RPC conectado ao Discord.")
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.update_loop()
        except Exception as e:
            logger.error(f"Erro ao conectar no Discord: {e}")
            tkinter.messagebox.showerror(get_text('ui_connection_error'), get_text('ui_connection_error_msg', e))

    def stop_rpc(self):
        self.running = False
        if self.rpc:
            try:
                self.rpc.clear()
                self.rpc.close()
                logger.info("RPC desconectado.")
            except: pass
            self.rpc = None
        
        self.lbl_status.configure(text=get_text('ui_disconnected'), text_color="#FF5555")
        self.lbl_substatus.configure(text=get_text('ui_service_stopped'))
        self.lbl_card_details.configure(text="...")
        self.lbl_card_state.configure(text="...")
        self.lbl_card_timer.configure(text="00:00 elapsed")
        self.lbl_large_img.configure(image=self.load_preview_image("lmu_logo", (90, 90)))
        self.lbl_small_img.configure(image="")
        self.lbl_small_img.place_forget()
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.start_time = None

    def update_loop(self):
        if not self.running: return

        try:
            game_pid = get_game_pid()

            if game_pid is None:
                # Jogo fechado
                self.lbl_status.configure(text=get_text('ui_waiting_game'), text_color="#FFA500") 
                self.lbl_substatus.configure(text=get_text('ui_open_lmu'))
                
                if self.last_state != 'clear':
                    logger.info("Desconectado/Jogo fechado.")
                    if self.rpc:
                        try:
                            self.rpc.clear()
                        except: pass
                    self.start_time = None
                    self.last_state = 'clear'
                    self.lbl_card_details.configure(text="Waiting...")
                    self.lbl_card_state.configure(text="")
                    self.lbl_large_img.configure(image=self.load_preview_image("lmu_logo", (90, 90)))
                    self.lbl_small_img.place_forget()
                self.after(1000, self.update_loop)
                return

            result = self.rf2.update()
            status = result.get('status')

            if status == 'game_closed':
                status = 'connected_menu'
                result = {'status': 'connected_menu', 'session': 'menu', 'track_name': '', 'ranks': self.rf2.get_player_ranks(None)}
                self.rc_profile.refresh_from_memory(result)

            if status in ['connected_menu', 'connected_driving']:
                self.rc_profile.refresh_from_api()
                self.rc_profile.refresh_from_memory(result)
                self.lbl_status.configure(text=get_text('ui_connected_lmu'), text_color="#00FF00") 
                self.lbl_substatus.configure(text=get_text('ui_sending_rp'))
                
                if self.start_time is None:
                    self.start_time = time.time()

                if status == 'connected_driving':
                    session_raw = result.get('session', '').lower()
                    track_name = result.get('track_name', '')
                    vehicle_name = result.get('vehicle_name', '')
                    veh_filename = result.get('veh_filename', '')
                    
                    pos = result['position']
                    
                    session_display = get_text(session_raw)
                    
                    game_phase = result.get('game_phase', 5)
                    current_et = result.get('current_et', 0.0)
                    end_et = result.get('end_et', 0.0)
                    lap = max(1, result.get('lap', 1))
                    total_laps = result.get('total_laps', 0)

                    time_info = ""
                    if game_phase == 0:
                        time_info = get_text('waiting')
                    elif game_phase in (1, 2):
                        time_info = get_text('grid')
                    elif game_phase == 3:
                        time_info = get_text('formation_lap')
                    elif game_phase == 4:
                        time_info = get_text('countdown')
                    else:
                        has_valid_timer = 0 < end_et < 172800
                        time_left = end_et - current_et if has_valid_timer else 0

                        if has_valid_timer and time_left > 0 and (total_laps >= 1000 or total_laps <= 0):
                            hours, rem = divmod(int(time_left), 3600)
                            mins, secs = divmod(rem, 60)
                            time_str = f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins:02d}:{secs:02d}"
                            time_info = get_text('time_remaining', time_str)
                        elif 0 < total_laps < 1000:
                            laps_left = max(0, total_laps - lap + 1)
                            if laps_left <= 1:
                                time_info = get_text('last_lap')
                            else:
                                time_info = get_text('lap_progress', lap, total_laps, laps_left)
                        elif has_valid_timer and time_left <= 0 and (total_laps >= 1000 or total_laps <= 0):
                            if session_raw == 'race':
                                time_info = get_text('last_lap')
                            else:
                                time_info = get_text('lap_single', lap)
                        else:
                            time_info = get_text('lap_single', lap)

                    details = f"P{pos} | {track_name} | {session_display}"
                    state = f"{time_info} | {vehicle_name}"

                    car_asset, car_real_name = get_car_asset_and_name(vehicle_name, veh_filename, result.get('vehicle_class', ''))
                    track_asset = get_track_asset_key(track_name)
                    cycle_enabled = self.config.get("cycle_track_image", False)
                    cycle_toggle = (int(time.time()) // 5) % 2 == 1 if cycle_enabled else False

                    # Alterna a cada 5 segundos entre carro e pista (respeitando rate limit do Discord IPC)
                    if cycle_enabled and track_asset is not None and cycle_toggle:
                        large_image_key = track_asset
                        large_text_val = track_name
                    else:
                        large_image_key = car_asset
                        large_text_val = car_real_name

                    small_image_key = self.rc_profile.get_badge_asset()
                    small_text_val = self.rc_profile.get_tooltip()
                
                else:
                    details = get_text('menu_details')
                    state = get_text('menu') 
                    large_image_key = "lmu_logo"
                    large_text_val = "Le Mans Ultimate"
                    small_image_key = self.rc_profile.get_badge_asset()
                    small_text_val = self.rc_profile.get_tooltip()
                
                self.lbl_card_details.configure(text=details)
                self.lbl_card_state.configure(text=state)
                
                l_img = self.load_preview_image(large_image_key, (90, 90))
                self.lbl_large_img.configure(image=l_img)

                if small_image_key:
                    s_img = self.load_preview_image(small_image_key, (28, 28), circular=True)
                    self.lbl_small_img.configure(image=s_img)
                    self.lbl_small_img.place(x=74, y=74)
                    self.lbl_small_img.lift()
                else:
                    self.lbl_small_img.place_forget()
                
                if self.start_time:
                    elapsed = int(time.time() - self.start_time)
                    mins, secs = divmod(elapsed, 60)
                    hours, mins = divmod(mins, 60)
                    time_str = f"{hours:02d}:{mins:02d}:{secs:02d} elapsed" if hours > 0 else f"{mins:02d}:{secs:02d} elapsed"
                    self.lbl_card_timer.configure(text=time_str)

                current_update = (details, state, large_image_key, small_image_key, small_text_val)
                if current_update != self.last_state:
                    logger.debug(f"Sending RPC update: details={details!r}, state={state!r}, large_image={large_image_key!r}, small_image={small_image_key!r}, small_text={small_text_val!r}")
                    try:
                        update_payload = {
                            "details": details,
                            "state": state,
                            "large_image": large_image_key,
                            "large_text": large_text_val,
                            "start": self.start_time,
                            "pid": game_pid
                        }
                        if small_image_key and small_text_val:
                            update_payload["small_image"] = small_image_key
                            update_payload["small_text"] = small_text_val

                        self.rpc.update(**update_payload)
                        self.last_state = current_update
                    except Exception as rpc_e:
                        logger.error(f"Erro ao enviar update para Discord RPC: {rpc_e}")

        except Exception as e:
            logger.error(f"Erro no loop principal: {e}", exc_info=True)
            self.lbl_substatus.configure(text=f"Erro: {str(e)[:20]}...")

        self.after(1000, self.update_loop)

    def minimize_to_tray(self):
        self.withdraw()
        image = create_icon_image()
        menu = Menu(
            MenuItem('Abrir (Open)', self.restore_window),
            MenuItem('Sair (Quit)', self.quit_app)
        )
        self.tray_icon = Icon("LMU RPC", image, "LMU RPC Mod", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def restore_window(self, icon, item):
        self.tray_icon.stop()
        self.after(0, self.deiconify)

    def quit_app(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
        self.stop_rpc()
        self.destroy()
        sys.exit(0)

    def load_config(self):
        default_config = {
            "autostart": False,
            "steamid": "76561198989955397",
            "dr": "S1 (64%)",
            "sr": "Gold S3 (82%)",
            "badge": "sr-clean",
            "cycle_track_image": False
        }
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_config.update(data)
                    return default_config
            except Exception:
                pass
        return default_config

    def save_config(self):
        try:
            with open("config.json", "w") as f:
                json.dump(self.config, f)
        except Exception as e:
            logger.error(f"Erro ao salvar config: {e}")

    def toggle_autostart(self):
        state = self.switch_var.get()
        self.config["autostart"] = state
        self.save_config()
        
        if state:
            self.add_to_startup()
        else:
            self.remove_from_startup()

    def add_to_startup(self):
        if getattr(sys, 'frozen', False):
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "LMU_RPC_Mod", 0, winreg.REG_SZ, sys.executable)
                winreg.CloseKey(key)
                logger.info("Adicionado ao startup do Windows.")
            except Exception as e:
                logger.error(f"Erro ao adicionar ao startup: {e}")
        else:
            logger.info("Modo Dev: Autostart simulado (ON)")

    def remove_from_startup(self):
        if getattr(sys, 'frozen', False):
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, "LMU_RPC_Mod")
                winreg.CloseKey(key)
                logger.info("Removido do startup do Windows.")
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.error(f"Erro ao remover do startup: {e}")
        else:
            logger.info("Modo Dev: Autostart simulado (OFF)")

if __name__ == "__main__":
    try:
        app = LMU_RPC_App()
        app.mainloop()
    except KeyboardInterrupt:
        logger.info("Aplicação encerrada via Terminal (Ctrl+C).")
    except Exception as e:
        logger.critical("Erro fatal na aplicação", exc_info=True)
