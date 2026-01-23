import sys
import os
# Adiciona os submódulos ao Path do Python para importação
sys.path.append(os.path.join(os.path.dirname(__file__), 'pyLMUSharedMemory'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'pyRfactor2SharedMemory'))

import time
import sys
import os
import threading
import tkinter as tk
import tkinter.messagebox
import locale
import logging
from logging.handlers import RotatingFileHandler
import json
import winreg

# Adiciona os submódulos ao Path do Python para importação
sys.path.append(os.path.join(os.path.dirname(__file__), 'pyLMUSharedMemory'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'pyRfactor2SharedMemory'))

# Importação Segura das Dependências Externas
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
        VERSION = "2.0"
        BUILD_TYPE = "DEV"
        AUTHOR = "uWaazy"
except ImportError as e:
    # Se falhar, cria uma mini janela invisível apenas para mostrar o erro
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

# --- LOGGING SETUP ---
def setup_logging():
    """Configura o sistema de logs com rotação de arquivo e saída no console."""
    logger = logging.getLogger("LMU_RPC")
    logger.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    
    # File Handler (Rotativo: 2MB, mantém 2 backups)
    file_handler = RotatingFileHandler("lmu_rpc.log", maxBytes=2*1024*1024, backupCount=2, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# --- RELEASE CONFIG: LOGGING & CONSOLE ---
IS_FROZEN = getattr(sys, 'frozen', False)

if IS_FROZEN:
    # Em modo release (.exe), desabilita logs em arquivo e a janela de console
    
    # 1. Redireciona stdout/stderr para um "buraco negro" para fechar o console
    try:
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = sys.stdout
    except Exception:
        pass # Falha silenciosa se não for possível redirecionar

    # 2. Configura o logger para não fazer nada
    logger = logging.getLogger("LMU_RPC")
    logger.addHandler(logging.NullHandler())
else:
    # Em modo de desenvolvimento (rodando o .py), ativa os logs
    logger = setup_logging()

def handle_exception(exc_type, exc_value, exc_traceback):
    """Captura exceções não tratadas e as envia para o log."""
    # Ignora KeyboardInterrupt para permitir fechar com Ctrl+C no terminal
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    # Loga a exceção crítica (só terá efeito se não estiver no modo frozen)
    logger.critical("Exceção não tratada:", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

# --- SETTINGS ---
CLIENT_ID = '1463577784394973392'

# --- SYSTEM LANGUAGE DETECTION ---
LANGUAGE = 'en'

# 1. Tenta pegar via argumento (Prioridade)
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

# 2. Se não foi forçado, detecta do sistema
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

# --- TRANSLATIONS ---
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
    # Fallback to English if the language or key is not found
    lang = TRANSLATIONS.get(LANGUAGE, TRANSLATIONS['en'])
    text = lang.get(key, TRANSLATIONS['en'].get(key, key))
    if args:
        return text.format(*args)
    return text

# --- rFactor 2 / LMU Shared Memory Reader ---
class RF2Data:
    def __init__(self):
        self.lmu = SimInfo()
        self.last_et = -1.0
        self.stale_counter = 0
        logger.info("Módulo de leitura de memória (pyLMUSharedMemory) inicializado.")

    def reconnect(self):
        """Força a reinicialização da conexão com a memória compartilhada."""
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
        """Tenta ler o SR da memória do veículo."""
        sr_class = "Bronze"
        sr_number = 0
        
        if vehicle:
            try:
                # Tenta ler o valor cru da memória (mDriverRating)
                raw_sr = vehicle.mDriverRating
                if raw_sr > 0:
                    sr_number = raw_sr
                    # Lógica de detecção básica (Se > 0, assume que é válido)
                    # O mapeamento exato de classes pode ser ajustado futuramente
                    sr_class = "Silver" if raw_sr >= 1000 else "Bronze"
            except:
                pass

        return {
            'sr_class': sr_class,
            'sr_number': sr_number
        }

    def normalize_track_name(self, raw_name):
        """Normaliza o nome da pista para apelidos comuns e formata layouts."""
        if not raw_name: return ""
        s = raw_name.lower()
        
        # 1. Mapeamento de Pistas (Apelidos)
        track_display = raw_name # Fallback
        
        # Ordem importa: termos mais específicos primeiro se houver sobreposição
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
        }
        
        for key, val in track_map.items():
            if key in s:
                track_display = val
                break
                
        # 2. Detecção de Layouts (Abreviações)
        # Ignora layouts padrão como "GP", "Grand Prix" para limpar a string
        layout_map = {
            "endurance circuit": "Endurance C.",
            "outer circuit": "Outer C.",
            "paddock circuit": "Paddock C.",
            "mulsanne circuit": "Mulsanne C.",
            "national circuit": "National C.",
            "classic circuit": "Classic C.",
            "short circuit": "Short C.",
            "curva grande circuit": "Curva Grande C.",
            "school circuit": "School C.",
        }
        
        detected_layouts = []
        for l_key, l_abbr in layout_map.items():
            if l_key in s:
                # Evita falsos positivos onde "International Circuit" contém "National Circuit"
                # Ex: Algarve International Circuit -> Portimão (não deve mostrar National C.)
                if l_key == "national circuit" and ("international" in s or "internacional" in s): continue
                
                detected_layouts.append(l_abbr)
                
        if detected_layouts:
            return f"{track_display} ({', '.join(detected_layouts)})"
        
        return track_display

    def update(self):
        try:
            # Acessa a estrutura de pontuação via biblioteca
            lmu_data = self.lmu.LMUData
            if not lmu_data:
                # Tenta reconectar (pode ter sido recriado pelo jogo)
                self.reconnect()
                lmu_data = self.lmu.LMUData
                if not lmu_data:
                    return {'status': 'game_closed'}

            scoring = lmu_data.scoring
            
            # --- STALE DATA CHECK (Menu Detection) ---
            # Verifica se o tempo da sessão está congelado (Menu ou Pause)
            current_et = scoring.scoringInfo.mCurrentET
            
            if current_et == self.last_et:
                self.stale_counter += 1
            else:
                self.stale_counter = 0
                self.last_et = current_et
            
            # Se dados congelados por > 2 segundos (Menu ou Pause)
            if self.stale_counter > 2:
                # Salva ranks dos dados antigos antes de limpar referências
                # Isso evita BufferError: cannot close exported pointers exist
                player_vehicle = None
                try:
                    for vehicle in scoring.vehScoringInfo:
                        if vehicle.mIsPlayer:
                            player_vehicle = vehicle
                            break
                except: pass
                stale_ranks = self.get_player_ranks(player_vehicle)

                # Limpa referências à memória antiga para permitir o fechamento limpo do mmap
                lmu_data = None
                scoring = None
                player_vehicle = None

                # Tenta reconectar para ver se o jogo fechou o mapa (Menu)
                self.reconnect()
                lmu_data = self.lmu.LMUData
                
                # Se após reconectar, não tem dados ou continua congelado
                is_stale = False
                if not lmu_data:
                    is_stale = True
                else:
                    # Atualiza scoring com novos dados para verificação
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
            # -----------------------------------------
            
            # Dados básicos (disponíveis mesmo no menu)
            session_name = self.get_session_name(scoring.scoringInfo.mSession)
            track_name_raw = scoring.scoringInfo.mTrackName.decode('utf-8', errors='ignore').strip('\x00')
            track_name = self.normalize_track_name(track_name_raw)
            
            player_vehicle = None
            # Itera sobre os veículos para encontrar o jogador
            for vehicle in scoring.vehScoringInfo:
                if vehicle.mIsPlayer:
                    player_vehicle = vehicle
                    break
            
            ranks = self.get_player_ranks(player_vehicle)

            # Se não achou player, assume que está no Menu/Lobby (mas conectado)
            if not player_vehicle:
                return {
                    'status': 'connected_menu',
                    'session': session_name,
                    'track_name': track_name,
                    'ranks': ranks
                }

            vehicle_name = player_vehicle.mVehicleName.decode('utf-8', errors='ignore').strip('\x00')
            
            # Remove sufixos de série para limpar o visual (:LM, :ELMS)
            if vehicle_name.endswith(":LM"):
                vehicle_name = vehicle_name[:-3]
            elif vehicle_name.endswith(":ELMS"):
                vehicle_name = vehicle_name[:-5]

            vehicle_class = player_vehicle.mVehicleClass.decode('utf-8', errors='ignore').strip('\x00')
            veh_filename = player_vehicle.mVehFilename.decode('utf-8', errors='ignore').strip('\x00')

            return {
                'status': 'connected_driving',
                'vehicle_name': vehicle_name, # Usado para detecção e exibição
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

# --- UTILITIES ---
# --- CAR & TRACK ASSETS ---
def get_car_asset_and_name(vehicle_name, veh_filename=None):
    """
    Identifica o Asset Key e o Nome Real do carro baseado na string do jogo.
    PRIORIDADE: Verifica o nome da pasta de instalação (veh_filename).
    FALLBACK: Verifica o nome do veículo/equipe (vehicle_name).
    """
    
    # --- 1. DETECÇÃO POR PASTA (Infalível) ---
    if veh_filename:
        fname = veh_filename.lower().replace('\\', '/') # Normaliza barras
        
        # Mapeamento exato das pastas de instalação do LMU
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
            "vantage_amr_gt3evo_2024": ("car_aston_martin_vantage_gt3", "Aston Martin Vantage GT3"),
        }

        for folder, (asset, name) in folder_map.items():
            if folder in fname:
                return asset, name

    if not vehicle_name:
        return "lmu_logo_default", "Le Mans Ultimate"

    vehicle_name_lower = vehicle_name.lower()

    # --- 2. LÓGICA DE DESEMPATE (Equipes Multi-Classe - Fallback) ---
    # Resolve conflitos onde o nome da equipe é igual para carros diferentes
    
    if "proton" in vehicle_name_lower:
        if "mustang" in vehicle_name_lower or "gt3" in vehicle_name_lower: return 'car_ford_mustang_gt3', 'Ford Mustang LMGT3'
        if "963" in vehicle_name_lower or "hypercar" in vehicle_name_lower: return 'car_porsche_963', 'Porsche 963'
        if "rsr" in vehicle_name_lower or "gte" in vehicle_name_lower: return 'car_porsche_911_rsr', 'Porsche 911 RSR-19'
        if "oreca" in vehicle_name_lower or "lmp2" in vehicle_name_lower: return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'
        # Tentativa por número
        if "99" in vehicle_name_lower: return 'car_porsche_963', 'Porsche 963'
        if "77" in vehicle_name_lower or "88" in vehicle_name_lower or "44" in vehicle_name_lower: return 'car_ford_mustang_gt3', 'Ford Mustang LMGT3'
        if "9" in vehicle_name_lower: return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'
    
    if "iron lynx" in vehicle_name_lower:
        if "sc63" in vehicle_name_lower or "hypercar" in vehicle_name_lower: return 'car_lamborghini_sc63', 'Lamborghini SC63'
        if "huracan" in vehicle_name_lower or "gt3" in vehicle_name_lower: return 'car_lamborghini_huracan_gt3', 'Lamborghini Huracan GT3'
        if "mercedes" in vehicle_name_lower: return 'car_mercedes_amg_gt3', 'Mercedes-AMG LMGT3'
        if "rsr" in vehicle_name_lower or "gte" in vehicle_name_lower: return 'car_porsche_911_rsr', 'Porsche 911 RSR-19'
        # Tentativa por número
        if "63" in vehicle_name_lower or "19" in vehicle_name_lower: return 'car_lamborghini_sc63', 'Lamborghini SC63'
        if "60" in vehicle_name_lower: return 'car_lamborghini_huracan_gt3', 'Lamborghini Huracan GT3'
        if "61" in vehicle_name_lower: return 'car_mercedes_amg_gt3', 'Mercedes-AMG LMGT3'

    if "iron dames" in vehicle_name_lower:
        if "huracan" in vehicle_name_lower or "gt3" in vehicle_name_lower: return 'car_lambo_huracan_gt3', 'Lamborghini Huracan GT3'
        if "rsr" in vehicle_name_lower or "gte" in vehicle_name_lower: return 'car_porsche_911_rsr', 'Porsche 911 RSR-19'
        return 'car_lambo_huracan_gt3', 'Lamborghini Huracan GT3' # Default 2024

    if "team wrt" in vehicle_name_lower:
        if "bmw" in vehicle_name_lower and "hybrid" in vehicle_name_lower: return 'car_bmw_m_hybrid_v8', 'BMW M Hybrid V8'
        if "bmw" in vehicle_name_lower or "m4" in vehicle_name_lower or "gt3" in vehicle_name_lower: return 'car_bmw_m4_gt3', 'BMW M4 LMGT3'
        if "oreca" in vehicle_name_lower or "lmp2" in vehicle_name_lower: return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'
        # Tentativa por número
        if "46" in vehicle_name_lower or "31" in vehicle_name_lower: return 'car_bmw_m4_gt3', 'BMW M4 LMGT3'
        if "41" in vehicle_name_lower: return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'
        if "15" in vehicle_name_lower or "20" in vehicle_name_lower: return 'car_bmw_m_hybrid_v8', 'BMW M Hybrid V8'

    if "united autosport" in vehicle_name_lower:
        if "mclaren" in vehicle_name_lower or "gt3" in vehicle_name_lower: return 'car_mclaren_720s_gt3', 'McLaren 720S Evo'
        if "oreca" in vehicle_name_lower or "lmp2" in vehicle_name_lower: return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'
        if "ligier" in vehicle_name_lower or "lmp3" in vehicle_name_lower: return 'car_ligier_js_p325', 'Ligier JS P325'
        if "59" in vehicle_name_lower or "95" in vehicle_name_lower: return 'car_mclaren_720s_gt3', 'McLaren 720S Evo'
        return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'

    if "af corse" in vehicle_name_lower:
        if "499p" in vehicle_name_lower or "hypercar" in vehicle_name_lower: return 'car_ferrari_499p', 'Ferrari 499P'
        if "296" in vehicle_name_lower or "gt3" in vehicle_name_lower or "vista" in vehicle_name_lower: return 'car_ferrari_296_gt3', 'Ferrari 296 LMGT3'
        if "oreca" in vehicle_name_lower or "lmp2" in vehicle_name_lower: return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'
        if "488" in vehicle_name_lower or "gte" in vehicle_name_lower: return 'car_ferrari_488_gte', 'Ferrari 488 GTE'
        # Tentativa por número
        if "83" in vehicle_name_lower and "183" not in vehicle_name_lower: return 'car_ferrari_499p', 'Ferrari 499P'
        if "50" in vehicle_name_lower or "51" in vehicle_name_lower: return 'car_ferrari_499p', 'Ferrari 499P'
        if "54" in vehicle_name_lower or "55" in vehicle_name_lower: return 'car_ferrari_296_gt3', 'Ferrari 296 LMGT3'
        if "183" in vehicle_name_lower: return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'

    if "heart of racing" in vehicle_name_lower:
        if "valkyrie" in vehicle_name_lower or "hypercar" in vehicle_name_lower: return 'car_aston_martin_valkyrie', 'Aston Martin Valkyrie'
        return 'car_aston_martin_vantage_gt3', 'Aston Martin Vantage GT3'

    # --- NOVAS EQUIPES MULTI-CLASSE (LMP2 vs LMP3) ---
    if "inter europol" in vehicle_name_lower:
        if "lmp3" in vehicle_name_lower or "ligier" in vehicle_name_lower: return 'car_ligier_js_p325', 'Ligier JS P325'
        if "88" in vehicle_name_lower: return 'car_ligier_js_p325', 'Ligier JS P325'
        return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'

    if "cool racing" in vehicle_name_lower:
        if "lmp3" in vehicle_name_lower or "ligier" in vehicle_name_lower: return 'car_ligier_js_p325', 'Ligier JS P325'
        if "17" in vehicle_name_lower: return 'car_ligier_js_p325', 'Ligier JS P325'
        return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'

    if "dkr engineering" in vehicle_name_lower:
        if "lmp3" in vehicle_name_lower or "ligier" in vehicle_name_lower or "duqueine" in vehicle_name_lower: return 'car_ligier_js_p325', 'Ligier JS P325'
        if "4" in vehicle_name_lower: return 'car_ligier_js_p325', 'Ligier JS P325'
        return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'

    if "rlr msport" in vehicle_name_lower:
        if "lmp3" in vehicle_name_lower or "ligier" in vehicle_name_lower: return 'car_ligier_js_p325', 'Ligier JS P325'
        if "5" in vehicle_name_lower or "15" in vehicle_name_lower: return 'car_ligier_js_p325', 'Ligier JS P325'
        return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'

    if "team virage" in vehicle_name_lower:
        if "lmp3" in vehicle_name_lower or "ligier" in vehicle_name_lower: return 'car_ligier_js_p325', 'Ligier JS P325'
        return 'car_oreca_07_2024', 'Oreca 07 Gibson 2024'

    # --- 3. MAPEAMENTO GERAL (Fallback) ---
    # Dicionário de Mapeamento: 'Asset_Key': ['Nome Bonito', ['palavras', 'chave', 'equipes']]
    car_map = {
        # --- HYPERCARS ---
        'car_alpine_a424': ['Alpine A424', ['alpine a', 'alpine endurance team', 'a424']],
        'car_aston_martin_valkyrie': ['Aston Martin Valkyrie', ['aston martin thor team']],
        'car_bmw_m_hybrid_v8': ['BMW M Hybrid V8', [ 'bmw m team wrt', 'bmw m hybrid']],
        'car_cadillac_v_series_r': ['Cadillac V-Series.R', ['cadillac v-series', 'cadillac racing', 'team jota', 'cadillac wtr', 'whelen cadillac racing', 'action express racing', 'cadillac whelen']],
        'car_ferrari_499p': ['Ferrari 499P', ['ferrari 499p', 'ferrari af corse', 'ferrari af corse', 'af corse', 'af corse', 'af corse']],
        'car_glickenhaus_007': ['Glickenhaus SCG 007', ['glickenhaus scg', 'glickenhaus racing']],
        'car_isotta_fraschini': ['Isotta Fraschini', ['isotta fraschini tip6', 'isotta tip']],
        'car_lamborghini_sc63': ['Lamborghini SC63', ['lamborghini sc', 'lamborghini iron lynx']],
        'car_peugeot_9x8_2024': ['Peugeot 9X8 2024', ['peugeot 9x8 2024', 'peugeot totalenergies']],
        'car_peugeot_9x8': ['Peugeot 9X8', ['peugeot 9x8','peugeot totalenergies']],
        'car_porsche_963': ['Porsche 963', ['porsche 963', 'porsche penske', 'hertz team jota', 'proton competition']],
        'car_toyota_gr010': ['Toyota GR010', ['toyota gr010', 'toyota gazoo racing', 'toyota gazoo racing', 'toyota gazoo racing']],
        'car_vanwall_680': ['Vanwall Vandervell', ['vanwall 680', 'floyd vanwall racing team']],

        # --- LMGT3 ---
        'car_ford_mustang_gt3': ['Ford Mustang LMGT3', ['mustang', 'proton competition',]],
        'car_mclaren_720s_gt3': ['McLaren 720S LMGT3 Evo', ['mclaren 720s', 'united autosport',]],
        'car_mercedes_amg_gt3': ['Mercedes-AMG LMGT3', ['mercedes-amg', 'mercedes amg']],
        'car_bmw_m4_gt3': ['BMW M4 LMGT3', ['bmw m4', 'team wrt',]],
        'car_aston_martin_vantage_gt3': ['Aston Martin Vantage GT3', ['vantage gt3', 'heart of racing', 'station',]],
        'car_corvette_z06_gt3': ['Corvette Z06 LMGT3.R', ['corvette z06', 'tf sport',]],
        'car_ferrari_296_gt3': ['Ferrari 296 LMGT3', ['ferrari 296', 'vista af corse', 'spirit of race', 'gr racing', 'kessel', 'jmw motorsport']],
        'car_lamborghini_huracan_gt3': ['Lamborghini Huracan GT3', ['huracan', 'iron dames', 'iron lynx']],
        'car_lexus_rcf_gt3': ['Lexus RC F LMGT3', ['lexus rc f', 'akkodis asp',]],
        'car_porsche_911_gt3': ['Porsche 911 GT3 R', ['porsche 911 gt3', 'manthey ema', 'manthey purerxcing']],

        # --- LMP2 ---
        'car_oreca_07_2023': ['Oreca 07 Gibson', [ 'oreca 07', 'prema racing', 'vector sport', 'tower motorsports', 'nielsen racing', 'duqueine team', 'inter europol competition', 'cool racing', 'graff racing', 'dkr engineering', 'algarve pro racing', 'idec sport', 'panis racing', 'racing team turkey', 'crowdstrike', 'ao by tf', 'united autosports', 'alpine elf team', 'team wrt', 'af corse', 'jota', 'proton', 'rlr msport', 'team virage']],
        'car_oreca_07_2024': ['Oreca 07 Gibson 2024', [ 'prema', 'vector sport 2024', 'tower', 'nielsen racing 2024', 'duqueine team 2024', 'inter europol', 'cool racing 2024', 'graff', 'dkr engineering 2024', 'algarve pro racing 2024', 'crowdstrike racing by apr 2024','panis racing 2024', 'racing team turkey', 'crowdstrike', 'ao by tf 2024', 'united autosports 2024', 'united autosports usa 2024', 'inter europol competition 2024', 'alpine elf team', 'team wrt', 'af corse 2024', 'jota', 'proton competition 2024', 'rlr msport', 'team virage', 'idec sport 2024',  'iron lynx - proton 2025', 'proton competition 2025', 'rlr msport 2025', 'idec sport 2025',  'united autosports 2025',  'nielsen racing', 'algarve pro racing 2025', 'tds tacing 2025', 'nielsen racing 2025', 'inter europol competition 2025',  'clx - pure rxcing 2025', 'vds panis racing 2025', 'af corse 2025',  'ao by tf 2025']],

        # --- LMP3 ---
        'car_ginetta_g61': ['Ginetta G61-LT-P325-Evo', ['ginetta g61', 'dkr engineering',]],
        'car_ligier_js_p325': ['Ligier JS P325', ['ligier js p325', 'cool racing', 'clx motorsport', 'racing spirit of leman', 'wtm by rinaldi', 'eurointernational', 'rlr msport', 'dkr engineering', 'team virage', 'inter europol', 'ultimate', 'nielsen', 'm racing', 'inter europol competition']],

        # --- GTE ---
        'car_corvette_c8r_gte': ['Chevrolet Corvette C8.R', ['corvette c8.r', 'corvette racing']],
        'car_ferrari_488_gte': ['Ferrari 488 GTE', ['ferrari 488 gte', 'kessell racing', 'jmw motorsport', 'richard mille', 'walkenhorst motorsport', 'af corse']],
        'car_porsche_911_rsr': ['Porsche 911 RSR-19', ['porsche 911 rsr-19', 'project 1 - ao', 'dempsey-proton racing', 'gr racing', 'proton competition', 'iron lynx', 'iron dames']],
        'car_aston_martin_vantage_gte': ['Aston Martin Vantage GTE', ['vantage gte', 'vantage amr gte', 'ort by tf', 'gmb motorsport', 'dstation racing', 'tf sport', 'the feart of racing',]],
    }

    for asset_key, data in car_map.items():
        car_real_name = data[0]
        keywords = data[1]
        
        for keyword in keywords:
            if keyword in vehicle_name_lower:
                return asset_key, car_real_name

    return "lmu_logo_default", vehicle_name # Fallback, usa o nome cru no tooltip

def get_track_asset_key(name):
    if not name: return 'lmu_logo'
    clean = name.lower().replace("'", "")
    # Mappings for known tracks
    if 'le mans' in clean or 'sarthe' in clean: return 'track_lemans'
    if 'spa' in clean or 'francorchamps' in clean: return 'track_spa'
    if 'monza' in clean: return 'track_monza'
    if 'sebring' in clean: return 'track_sebring'
    if 'bahrain' in clean: return 'track_bahrain'
    if 'portimao' in clean or 'algarve' in clean: return 'track_portimao'
    if 'fuji' in clean: return 'track_fuji'
    if 'imola' in clean: return 'track_imola'
    if 'cota' in clean or 'americas' in clean: return 'track_cota'
    if 'interlagos' in clean or 'carlos pace' in clean: return 'track_interlagos'
    if 'qatar' in clean or 'lusail' in clean: return 'track_qatar' # DLC 2024
    if 'silverstone' in clean: return 'track_silverstone' # ELMS Pack
    if 'paul_ricard' in clean or 'ricard' in clean: return 'track_paul_ricard' # ELMS Pack
    # Fallback to the LMU logo
    return 'lmu_logo'

RANK_ASSETS = {
    "Bronze": "rank_bronze",
    "Silver": "rank_silver",
    "Gold":   "rank_gold",
    "Platinum": "rank_platinum"
}

def get_rank_asset(rank_name):
    if not rank_name: return RANK_ASSETS["Bronze"]
    for rank, asset in RANK_ASSETS.items():
        if rank.lower() in rank_name.lower():
            return asset
    return RANK_ASSETS["Bronze"]

def get_game_pid():
    """Busca o PID do processo do jogo para realizar o PID Binding no Discord."""
    # Itera sobre processos sem pré-carregar atributos para evitar travamentos em processos de sistema
    for proc in psutil.process_iter():
        try:
            # Tenta ler o nome. Se for processo de sistema/antivírus, pode dar AccessDenied, que ignoramos.
            if proc.name() in ['LeMansUltimate.exe', 'Le Mans Ultimate.exe']:
                return proc.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception:
            continue
    return None

def create_icon_image():
    """Carrega o ícone do app (icon.png) ou gera um fallback."""
    icon_path = resource_path("icon.png")
    if os.path.exists(icon_path):
        try:
            return Image.open(icon_path)
        except:
            pass
            
    # Fallback: Ícone gerado programaticamente
    image = Image.new('RGB', (64, 64), (0, 50, 100))
    dc = ImageDraw.Draw(image)
    dc.rectangle((32, 0, 64, 32), fill=(255, 255, 255))
    dc.rectangle((0, 32, 32, 64), fill=(255, 255, 255))
    return image

def resource_path(relative_path):
    """ Obtém o caminho absoluto para recursos, funciona em dev e no PyInstaller """
    try:
        # PyInstaller cria uma pasta temporária e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- CONFIGURAÇÃO DO TEMA ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# --- GUI APPLICATION ---
class LMU_RPC_App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configuração da Janela
        self.title("")
        self.geometry("420x420")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.configure(fg_color="#0f1012")

        # --- Configuração do Ícone da Janela ---
        try:
            # Define o ícone da janela (icon.ico ou icon.png)
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
        
        # Carrega configurações (Tarefa 1)
        self.config = self.load_config()

        self.setup_ui()
        logger.info("App LMU RPC Mod iniciado. Versão 2.0 (Modern UI)")

    def setup_ui(self):
        # Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Header
        self.grid_rowconfigure(1, weight=0) # Status
        self.grid_rowconfigure(2, weight=0) # Discord Card
        self.grid_rowconfigure(3, weight=0) # Buttons
        self.grid_rowconfigure(4, weight=1) # Footer

        # 1. Cabeçalho (Logo)
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, pady=(0, 15), sticky="ew")

        # Banner Principal (Substitui o Título de Texto)
        try:
            banner_path = resource_path("pequenobanner.png")
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

        # Switch de Autostart (Tarefa 3)
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

        # 2. Indicador de Status
        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.grid(row=1, column=0, pady=(0, 10))
        
        self.lbl_status = ctk.CTkLabel(self.status_frame, text=get_text('ui_disconnected'), font=("Segoe UI", 22, "bold"), text_color="#FF5555")
        self.lbl_status.pack()
        
        self.lbl_substatus = ctk.CTkLabel(self.status_frame, text=get_text('ui_service_stopped'), font=("Segoe UI", 13), text_color="gray")
        self.lbl_substatus.pack()

        # 3. Discord Card (Rich Presence Preview)
        self.card_frame = ctk.CTkFrame(self, fg_color="#1e1f22", corner_radius=15, width=380, height=110, border_width=0)
        self.card_frame.grid(row=2, column=0, padx=20, pady=(0, 20))
        self.card_frame.grid_propagate(False) # Tamanho fixo

        # Large Image (90x90)
        self.lbl_large_img = ctk.CTkLabel(self.card_frame, text="", width=90, height=90)
        self.lbl_large_img.place(x=10, y=10)

        # Small Image (30x30) - Canto inferior direito da imagem grande
        self.lbl_small_img = ctk.CTkLabel(self.card_frame, text="", width=30, height=30, bg_color="transparent")
        self.lbl_small_img.place(x=70, y=70)

        # Text Info
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

        # 4. Rodapé
        # Lógica de exibição da versão (Tarefa 1)
        if BUILD_TYPE == "RELEASE":
            ver_text = f"v{VERSION} | by {AUTHOR}"
        else:
            ver_text = f"{BUILD_TYPE} {VERSION} | by {AUTHOR}"
            
        self.lbl_footer = ctk.CTkLabel(self, text=ver_text, font=("Segoe UI", 10), text_color="gray50")
        self.lbl_footer.grid(row=4, column=0, pady=(15, 10))

    def load_preview_image(self, key, size, circular=False):
        """Carrega imagem local para o preview ou gera placeholder."""
        cache_key = f"{key}_{size}_{circular}"
        if cache_key in self.img_cache:
            return self.img_cache[cache_key]

        pil_img = None
        # Garante que o caminho seja relativo ao script, não ao terminal
        base_path = os.path.dirname(os.path.abspath(__file__))
        
        # Tenta encontrar o arquivo em locais comuns
        candidates = [
            os.path.join(base_path, "assets", f"{key}.png"),
            os.path.join(base_path, "assets", f"{key}.jpg"),
            os.path.join(base_path, f"{key}.png"),
            os.path.join(base_path, f"{key}.jpg"),
            os.path.join(base_path, "lmu_logo.png")
        ]
        
        for path in candidates:
            if os.path.exists(path):
                try:
                    pil_img = Image.open(path)
                    break
                except: pass
        
        if not pil_img:
            # Placeholder cinza escuro (Discord)
            pil_img = Image.new('RGB', size, (47, 49, 54))
        
        pil_img = pil_img.resize(size, Image.Resampling.LANCZOS)

        if circular:
            mask = Image.new('L', size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0) + size, fill=255)
            
            pil_img = pil_img.convert("RGBA")
            output = Image.new('RGBA', size, (0,0,0,0))
            output.paste(pil_img, (0,0), mask)
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
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.start_time = None

    def update_loop(self):
        if not self.running: return

        try:
            # Detectar PID primeiro (Conexão Imediata)
            game_pid = get_game_pid()

            if game_pid is None:
                # Jogo fechado
                self.lbl_status.configure(text=get_text('ui_waiting_game'), text_color="#FFA500") # Laranja
                self.lbl_substatus.configure(text=get_text('ui_open_lmu'))
                
                if self.last_state != 'clear':
                    logger.info("Desconectado/Jogo fechado.")
                    if self.rpc: self.rpc.clear()
                    self.start_time = None
                    self.last_state = 'clear'
                    self.lbl_card_details.configure(text="Waiting...")
                    self.lbl_card_state.configure(text="")
                self.after(1000, self.update_loop)
                return
            
            # Jogo aberto (PID encontrado) -> Tenta ler memória
            result = self.rf2.update()
            status = result.get('status')

            # Se memória falhar (Menu/Loading) mas PID existe -> Força status de Menu
            if status == 'game_closed':
                status = 'connected_menu'
                # Cria dados fictícios para o menu usando o mock de ranks existente
                result = {'status': 'connected_menu', 'session': 'menu', 'track_name': '', 'ranks': self.rf2.get_player_ranks(None)}

            if status in ['connected_menu', 'connected_driving']:
                self.lbl_status.configure(text=get_text('ui_connected_lmu'), text_color="#00FF00") # Verde Neon
                self.lbl_substatus.configure(text=get_text('ui_sending_rp'))
                
                if self.start_time is None:
                    self.start_time = time.time()
            
                # Dados Comuns (Ranks)
                ranks = result.get('ranks', {})
                sr_class = ranks.get('sr_class', 'Bronze')
                sr_number = ranks.get('sr_number', 0)
                
                # Visualização de Ranks (Apenas SR)
                small_image_key = get_rank_asset(sr_class)
                small_text_val = f"SR: {sr_class} {sr_number}"

                if status == 'connected_driving':
                    session_raw = result.get('session', '').lower()
                    track_name = result.get('track_name', '')
                    vehicle_name = result.get('vehicle_name', '')
                    veh_filename = result.get('veh_filename', '')
                    
                    pos = result['position']
                    
                    session_display = get_text(session_raw)
                    
                    # Lógica de Tempo / Voltas
                    lap = result['lap']
                    total_laps = result['total_laps']
                    is_time_based = result['end_et'] > 0 and total_laps > 1000

                    time_info = ""
                    if is_time_based:
                        time_left = result['end_et'] - result['current_et']
                        if time_left > 0:
                            hours, rem = divmod(time_left, 3600)
                            mins, secs = divmod(rem, 60)
                            time_str = f"{int(hours)}:{int(mins):02d}" if hours > 0 else f"{int(mins):02d}:{int(secs):02d}"
                            time_info = get_text('time_remaining', time_str)
                        else:
                            time_info = f"Lap {lap}/{total_laps}"
                    else:
                        time_info = f"Lap {lap}/{total_laps}"

                    # --- NOVO LAYOUT RPC ---
                    # Linha 1 (Detalhes): Posição | Pista | Sessão
                    details = f"P{pos} | {track_name} | {session_display}"
                    
                    # Linha 2 (Estado): Tempo Restante | Carro
                    state = f"{time_info} | {vehicle_name}"

                    # Passa também o nome do arquivo para a nova detecção por pasta
                    large_image_key, large_text_val = get_car_asset_and_name(vehicle_name, veh_filename)
                
                else: # 'connected_menu'
                    details = get_text('menu_details')
                    state = get_text('menu') # "Nos Menus"
                    large_image_key = "lmu_logo"
                    large_text_val = "Le Mans Ultimate"
                
                # Atualiza Card do Discord
                self.lbl_card_details.configure(text=details)
                self.lbl_card_state.configure(text=state)
                
                # Imagens
                l_img = self.load_preview_image(large_image_key, (90, 90))
                self.lbl_large_img.configure(image=l_img)
                
                s_img = self.load_preview_image(small_image_key, (30, 30), circular=True)
                self.lbl_small_img.configure(image=s_img)
                
                # Timer
                if self.start_time:
                    elapsed = int(time.time() - self.start_time)
                    mins, secs = divmod(elapsed, 60)
                    hours, mins = divmod(mins, 60)
                    time_str = f"{hours:02d}:{mins:02d}:{secs:02d} elapsed" if hours > 0 else f"{mins:02d}:{secs:02d} elapsed"
                    self.lbl_card_timer.configure(text=time_str)

                current_update = (details, state)
                if current_update != self.last_state:
                    self.rpc.update(
                        details=details,
                        state=state,
                        large_image=large_image_key,
                        large_text=large_text_val,
                        small_image=small_image_key,
                        small_text=small_text_val,
                        start=self.start_time,
                        pid=game_pid # PID Binding (Prioridade Visual)
                    )
                    self.last_state = current_update

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

    # --- CONFIG & REGISTRY METHODS ---
    def load_config(self):
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    return json.load(f)
            except: pass
        return {"autostart": False}

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
