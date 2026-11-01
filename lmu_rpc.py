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
import gc
import uuid
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
    from car_resolver import resolve_car, clean_entry_name, entry_year
    from game_mode import detect_game_mode, party_size
    from lmu_core import (CLIENT_ID, LANGUAGE, TRANSLATIONS, get_text, get_car_asset_and_name, get_track_asset_key,
                          build_presence, build_menu_presence)
    from lmu_racecontrol import RaceControlProfile, extract_session_players
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


# LANGUAGE / TRANSLATIONS / get_text, carros, pistas e montagem do status moram em lmu_core.py

class RF2Data:
    def __init__(self):
        self.lmu = SimInfo()
        self.last_et = -1.0
        self.stale_counter = 0
        self.vehicle_name_cache = {}
        logger.info("Módulo de leitura de memória (pyLMUSharedMemory) inicializado.")

    def reconnect(self):
        try:
            new_lmu = SimInfo()
        except Exception as e:
            logger.debug(f"Erro ao reconectar SimInfo: {e}")
            return
        old_lmu, self.lmu = self.lmu, new_lmu
        gc.collect()
        del old_lmu

    def get_session_name(self, session_id):
        if session_id == 0: return 'test_day'
        if 1 <= session_id <= 4: return 'practice'
        if 5 <= session_id <= 8: return 'qualify'
        if session_id == 9: return 'warmup'
        if 10 <= session_id <= 13: return 'race'
        return 'menu'

    def get_player_ranks(self, vehicle, scoring=None):
        """Identificação dos pilotos para o RaceControl.

        A Shared Memory do LMU NÃO contém DR/SR/badge (só `mSteamID` por carro), então aqui
        só coletamos SteamIDs. Os ratings reais vêm de lmu_racecontrol.py. O nome do método
        e a chave 'ranks' foram mantidos para não quebrar o resto do fluxo.
        """
        players = extract_session_players(scoring) if scoring is not None else []
        local = next((p for p in players if p.get('is_player')), None)
        return {
            'steam_id': local['steam_id'] if local else '',
            'players': players,
        }

    def _safe_decode(self, raw_bytes):
        try:
            if raw_bytes is None:
                return ""
            return raw_bytes.decode('utf-8', errors='ignore').split('\x00')[0].strip()
        except Exception:
            return ""

    def get_session_info(self, scoring):
        try:
            info = scoring.scoringInfo
            controls = {}
            vehicles = []
            for i in range(info.mNumVehicles):
                veh = scoring.vehScoringInfo[i]
                control = int(veh.mControl)
                controls[control] = controls.get(control, 0) + 1
                vehicles.append((self._safe_decode(veh.mVehicleClass), int(veh.mPlace), bool(veh.mIsPlayer)))
            result = {
                'mode': detect_game_mode(int(info.mGameMode), controls),
                'num_cars': int(info.mNumVehicles),
                'max_players': int(info.mMaxPlayers),
            }
            # Posicao dentro da propria classe (mPlace e a posicao geral)
            me = next((v for v in vehicles if v[2]), None)
            if me and me[1] > 0:
                same = [v for v in vehicles if v[0] == me[0]]
                result['class_cars'] = len(same)
                result['class_position'] = 1 + sum(1 for v in same if 0 < v[1] < me[1])
            return result
        except Exception as e:
            logger.debug(f"Falha ao ler modo de jogo: {e}")
            return {}

    def get_player_model(self, lmu_data, player_vehicle):
        try:
            telemetry = lmu_data.telemetry
            entry = player_vehicle.mVehicleName
            for i in range(telemetry.activeVehicles):
                info = telemetry.telemInfo[i]
                if info.mID == player_vehicle.mID and info.mVehicleName == entry:
                    return self._safe_decode(info.mVehicleModel)
        except Exception as e:
            logger.debug(f"Falha ao ler mVehicleModel: {e}")
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
                stale_ranks = self.get_player_ranks(player_vehicle, scoring)

                lmu_data = None
                scoring = None
                player_vehicle = None
                vehicle = None
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
            
            ranks = self.get_player_ranks(player_vehicle, scoring)

            if not player_vehicle:
                return {
                    'status': 'connected_menu',
                    'session': session_name,
                    'track_name': track_name,
                    'ranks': ranks
                }

            raw_vehicle_name = clean_entry_name(self._safe_decode(player_vehicle.mVehicleName))

            # Lê o nome do ficheiro (ID do carro) de forma segura:
            try:
                veh_filename = player_vehicle.mVehFilename.decode('utf-8', errors='ignore').split('\x00')[0].strip()
            except Exception:
                veh_filename = ""

            vehicle_model = self.get_player_model(lmu_data, player_vehicle)
            vehicle_year = entry_year(raw_vehicle_name)
            if vehicle_model:
                clean_vehicle_name = resolve_car(vehicle_model, vehicle_year)[1]
            else:
                try:
                    clean_vehicle_name = self.get_player_vehicle_from_api(raw_vehicle_name, veh_filename)
                except Exception:
                    clean_vehicle_name = raw_vehicle_name

            vehicle_name = clean_vehicle_name or raw_vehicle_name
            logger.debug(f"Using vehicle name for RPC: {vehicle_name}")

            vehicle_class = self._safe_decode(player_vehicle.mVehicleClass)
            veh_filename = self._safe_decode(player_vehicle.mVehFilename)
            session_info = self.get_session_info(scoring)

            return {
                'status': 'connected_driving',
                'vehicle_name': vehicle_name,
                'vehicle_class': vehicle_class,
                'vehicle_model': vehicle_model,
                'vehicle_year': vehicle_year,
                'game_mode': session_info.get('mode', ''),
                'num_cars': session_info.get('num_cars', 0),
                'max_players': session_info.get('max_players', 0),
                'class_position': session_info.get('class_position', 0),
                'class_cars': session_info.get('class_cars', 0),
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



class LMU_RPC_App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("")
        self.geometry("420x420")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.after(300, self.hide_window_buttons)   # depois que o customtkinter termina de montar a janela
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
        self.party_id = f"lmu-rpc-{uuid.uuid4().hex[:12]}"
        self.tray_icon = None
        self.img_cache = {}
        
        self.config = self.load_config()
        self.rc_profile = RaceControlProfile(self.config)

        self.setup_ui()
        logger.info("App LMU RPC Mod iniciado. Versão 2.0 (Modern UI)")

    # O Windows nao permite esconder SO o botao maximizar: ou ele aparece (desativado) ou somem minimizar e maximizar.
    # Aqui somem os dois; o X continua mandando o app para a bandeja e a barra de tarefas minimiza normalmente.
    HIDE_MINIMIZE_TOO = True

    def hide_window_buttons(self):
        try:
            import ctypes
            GWL_STYLE, WS_MAXIMIZEBOX, WS_MINIMIZEBOX = -16, 0x00010000, 0x00020000
            SWP_FLAGS = 0x0002 | 0x0001 | 0x0004 | 0x0020      # NOMOVE | NOSIZE | NOZORDER | FRAMECHANGED
            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(self.winfo_id()) or self.winfo_id()
            style = user32.GetWindowLongW(hwnd, GWL_STYLE) & ~WS_MAXIMIZEBOX
            if self.HIDE_MINIMIZE_TOO:
                style &= ~WS_MINIMIZEBOX
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
        except Exception as e:
            logger.debug(f"Nao foi possivel esconder o botao maximizar: {e}")

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
                # Jogo sem dados de scoring: não há jogadores novos; o RaceControl mantém o último valor válido.
                result = {'status': 'connected_menu', 'session': 'menu', 'track_name': '', 'ranks': self.rf2.get_player_ranks(None)}

            if status in ['connected_menu', 'connected_driving']:
                self.rc_profile.refresh_from_api()
                self.rc_profile.refresh_from_memory(result)
                self.lbl_status.configure(text=get_text('ui_connected_lmu'), text_color="#00FF00") 
                self.lbl_substatus.configure(text=get_text('ui_sending_rp'))
                
                if self.start_time is None:
                    self.start_time = time.time()

                small_image_key = self.rc_profile.get_badge_asset()
                small_text_val = self.rc_profile.get_tooltip()
                if status == 'connected_driving':
                    presence = build_presence(result, self.config, time.time(), small_image_key, small_text_val)
                else:
                    presence = build_menu_presence(small_image_key, small_text_val)
                details, state = presence['details'], presence['state']
                large_image_key, large_text_val = presence['large_image'], presence['large_text']

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
        self.after(0, self._shutdown)

    def _shutdown(self):
        self.running = False
        if self.tray_icon:
            self.tray_icon.stop()
        self.stop_rpc()
        self.destroy()

    def load_config(self):
        default_config = {
            "autostart": False,
            "steamid": "",
            "dr": "",
            "sr": "",
            "badge": "",
            "show_party_size": True,
            "cycle_track_image": True,
            "cycle_car_seconds": 10,
            "cycle_track_seconds": 5,
            "racecontrol": {
                "enabled": True,
                "cache_ttl_seconds": 900,
                "negative_ttl_seconds": 120,
                "session_lookup": False,
                "raceos": {"enabled": False, "host": "raceos.gg", "chunk_size": 20},
                "remote_base_url": "",
                "remote_token_env": "LMU_RC_TOKEN",
                "local_endpoints": [],
                "badge_assets": {}
            }
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
