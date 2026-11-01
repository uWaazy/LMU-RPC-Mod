#!/usr/bin/env python3
"""LMU RPC Preview - o mesmo visual do LMU RPC Mod, mas TUDO editavel a mao.

Escolha carro, pista, sessao, modo, tempo, posicoes, DR/SR/badge e veja na hora no Discord.
Usa o MESMO nucleo do app original (lmu_core.py): carro/pista/texto novos aparecem nos dois.
Nao le o jogo e nao precisa do Le Mans Ultimate aberto.
"""
import os
import sys
import json
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ----------------------------------------------------------------------------------------------
# Modelo (sem GUI): guarda os valores digitados e produz o "result" que o lmu_core entende
# ----------------------------------------------------------------------------------------------
from lmu_core import (CLIENT_ID, LANGUAGES, SESSIONS, GAME_MODES, build_presence, build_menu_presence,
                      get_text, set_language, list_cars, list_tracks, scan_asset_keys, get_track_asset_key,
                      get_car_asset_and_name, format_clock, parse_clock)
from lmu_racecontrol import (OFFICIAL_BADGES, EXTRA_BADGE_SLUGS, DEFAULT_BADGE_ASSETS, badge_label,
                             parse_rating_string)

logger = logging.getLogger("LMU_RPC")

STATE_FILE = "preview_state.json"

DEFAULTS = {
    "screen": "driving",              # driving | menu
    "mode": "online",
    "session": "practice",
    "track_name": "Barcelona",
    "track_asset": "barcelona-catalunya",
    "car_name": "Mercedes-AMG LMGT3",
    "car_asset": "car_mercedes_amg_gt3",
    "time_left": "43:20",
    "phase": "5",
    "total_laps": "0",
    "lap": "1",
    "class_pos": "5",
    "class_cars": "12",
    "pos": "18",
    "cars": "20",
    "slots": "34",
    "show_grid": True,
    "image_mode": "auto",             # auto | car | track
    "cycle_car": "10",
    "cycle_track": "5",
    "dr": "S1 (30%)",
    "sr": "G1 (10%)",
    "badge": "good_driver",
    "elapsed": "00:00",
    "live_clock": False,
    "language": "",
}


def _int(value, default=0, lo=0, hi=999999):
    try:
        return max(lo, min(hi, int(str(value).strip())))
    except (TypeError, ValueError):
        return default


class PreviewModel:
    """Valores (strings/bools) -> result do lmu_core. Entrada invalida nunca vira dado inventado: avisa em `warnings`."""

    def __init__(self, values=None):
        self.values = dict(DEFAULTS)
        if values:
            self.values.update({k: v for k, v in values.items() if k in DEFAULTS})
        self.warnings = []

    def get(self, key):
        return self.values.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        if key in DEFAULTS:
            self.values[key] = value

    # ---- carro / pista -------------------------------------------------------------------
    def pick_car(self, name, asset):
        self.values["car_name"], self.values["car_asset"] = name, asset

    def pick_track(self, name, asset):
        self.values["track_name"], self.values["track_asset"] = name, asset

    # ---- saida ---------------------------------------------------------------------------
    def to_result(self):
        v = self.values
        self.warnings = [w for w in self.warnings if w != "time_left"]
        remaining = parse_clock(v["time_left"])
        total_laps = _int(v["total_laps"])
        if v["time_left"].strip() and remaining is None:
            self.warnings.append("time_left")
        num_cars = _int(v["cars"])
        pos = _int(v["pos"], 1, 1)
        result = {
            "status": "connected_driving",
            "session": v["session"],
            "track_name": v["track_name"].strip(),
            "vehicle_name": v["car_name"].strip(),
            "position": pos,
            "class_position": _int(v["class_pos"]),
            "class_cars": _int(v["class_cars"]),
            "num_cars": num_cars,
            "max_players": _int(v["slots"]),
            "game_mode": v["mode"],
            "lap": _int(v["lap"], 1, 1),
            "total_laps": total_laps,
            "current_et": 0.0,
            "end_et": float(remaining or 0),
            "game_phase": _int(v["phase"], 5, 0, 9),
            "image_mode": v["image_mode"],
        }
        if v["car_asset"].strip():
            result["car_asset"] = v["car_asset"].strip()
        track_asset = v["track_asset"].strip() or get_track_asset_key(v["track_name"])
        if track_asset and track_asset != "lmu_logo":
            result["track_asset"] = track_asset
        return result

    def config(self):
        v = self.values
        return {
            "show_party_size": bool(v["show_grid"]),
            "cycle_track_image": v["image_mode"] == "auto",
            "cycle_car_seconds": _int(v["cycle_car"], 10, 3, 3600),
            "cycle_track_seconds": _int(v["cycle_track"], 5, 3, 3600),
        }

    def badge(self):
        """(small_image, small_text) a partir de DR/SR/badge digitados. Campos vazios ou invalidos ficam de fora."""
        v = self.values
        self.warnings = [w for w in self.warnings if w not in ("dr", "sr")]
        parts = []
        for label, key in (("DR", "dr"), ("SR", "sr")):
            text = (v[key] or "").strip()
            if not text:
                continue
            rating = parse_rating_string(text)
            if rating is None:
                self.warnings.append(key)
            else:
                parts.append(f"{label} {rating.short()}")
        badge = (v["badge"] or "").strip()
        image = ""
        if badge:
            parts.append(badge_label(badge))
            image = DEFAULT_BADGE_ASSETS.get(badge) or (badge if badge in EXTRA_BADGE_SLUGS else "")
        return image, " | ".join(parts)[:128]

    def presence(self, now):
        image, text = self.badge()
        if self.values["screen"] == "menu":
            p = build_menu_presence(image, text)
        else:
            p = build_presence(self.to_result(), self.config(), now, image, text)
        return p

    # ---- salvar / carregar ---------------------------------------------------------------
    def save(self, path=STATE_FILE):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.values, f, ensure_ascii=False, indent=1)
        except OSError as e:
            logger.debug(f"preview: nao salvou estado: {e}")

    @classmethod
    def load(cls, path=STATE_FILE):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(data if isinstance(data, dict) else None)
        except (OSError, ValueError):
            return cls()


def discord_payload(presence, start_time):
    """Mesmo formato que o app original manda ao Discord (campos vazios/curtos demais sao omitidos)."""
    def ok(text):
        return isinstance(text, str) and len(text.strip()) >= 2

    payload = {"large_image": presence["large_image"]}
    for key in ("details", "state"):
        if ok(presence[key]):
            payload[key] = presence[key][:128]
    if ok(presence["large_text"]):
        payload["large_text"] = presence["large_text"][:128]
    payload["start"] = start_time
    if presence["small_image"] and ok(presence["small_text"]):
        payload["small_image"] = presence["small_image"]
        payload["small_text"] = presence["small_text"]
    return payload


def car_choices(base_dir):
    """[(rotulo, nome, asset)] = carros conhecidos + imagens de assets/cars ainda sem mapeamento."""
    out = [(name, name, asset) for asset, name in list_cars()]
    known = {a for _l, _n, a in out}
    for key in scan_asset_keys(base_dir, "cars"):
        if key not in known and key not in ("lmu_logo", "lmu_logo_default"):
            out.append((f"[assets] {key}", key, key))
    return out


def track_choices(base_dir):
    out = [(name, name, asset) for name, asset in list_tracks()]
    known = {a for _l, _n, a in out}
    for key in scan_asset_keys(base_dir, "tracks"):
        if key not in known and key != "lmu_logo":
            out.append((f"[assets] {key}", key, key))
    return out


def badge_choices():
    keys = list(OFFICIAL_BADGES) + sorted(EXTRA_BADGE_SLUGS)
    return [("", "-")] + [(k, badge_label(k)) for k in keys]


# ----------------------------------------------------------------------------------------------
# Interface
# ----------------------------------------------------------------------------------------------
LABELS = {
    "en": {
        "editor": "EDITOR", "screen": "Screen", "driving": "On track", "menu": "Main menu", "mode": "Mode",
        "session": "Session", "track": "Track", "track_name": "Track name (shown)", "track_asset": "Track image (asset)",
        "car": "Car", "car_name": "Car name (shown)", "car_asset": "Car image (asset)", "time": "Time remaining",
        "phase": "Game phase", "total_laps": "Total laps (0 = timed)", "lap": "Current lap",
        "class_pos": "Position in class", "class_cars": "Cars in class", "pos": "Overall position",
        "cars": "Cars in session", "slots": "Max slots", "show_grid": "Show (cars of slots)",
        "image": "Large image", "img_auto": "Auto (car / track)", "img_car": "Car only", "img_track": "Track only",
        "cycle_car": "Seconds on car", "cycle_track": "Seconds on track", "rating": "Rating (real values only)",
        "dr": "DR  e.g. S1 (30%)", "sr": "SR  e.g. G1 (10%)", "badge": "Badge", "elapsed": "Elapsed time",
        "live": "Live countdown", "lang": "Language", "reset": "Reset", "auto": "Auto",
        "missing": "No image for '{}' in assets/ (Discord needs it in the Developer Portal)",
        "bad": "Invalid: {}", "state_ok": "Sending preview to Discord", "preview_mode": "PREVIEW",
        "editor_hint": "Pick a preset or type your own. Changes go to Discord instantly.",
        "phase_5": "Green / on track", "phase_0": "Waiting", "phase_1": "Grid", "phase_3": "Formation lap", "phase_4": "Countdown",
    },
    "pt-br": {
        "editor": "EDITOR", "screen": "Tela", "driving": "Na pista", "menu": "Menu principal", "mode": "Modo",
        "session": "Sessão", "track": "Pista", "track_name": "Nome da pista (exibido)", "track_asset": "Imagem da pista (asset)",
        "car": "Carro", "car_name": "Nome do carro (exibido)", "car_asset": "Imagem do carro (asset)", "time": "Tempo restante",
        "phase": "Fase do jogo", "total_laps": "Voltas totais (0 = por tempo)", "lap": "Volta atual",
        "class_pos": "Posição na classe", "class_cars": "Carros na classe", "pos": "Posição geral",
        "cars": "Carros na sessão", "slots": "Vagas máximas", "show_grid": "Mostrar (carros de vagas)",
        "image": "Imagem grande", "img_auto": "Automático (carro / pista)", "img_car": "Só carro", "img_track": "Só pista",
        "cycle_car": "Segundos no carro", "cycle_track": "Segundos na pista", "rating": "Rating (só valores reais)",
        "dr": "DR  ex.: S1 (30%)", "sr": "SR  ex.: G1 (10%)", "badge": "Badge", "elapsed": "Tempo decorrido",
        "live": "Contagem regressiva ao vivo", "lang": "Idioma", "reset": "Restaurar", "auto": "Auto",
        "missing": "Sem imagem de '{}' em assets/ (o Discord precisa dela no Developer Portal)",
        "bad": "Inválido: {}", "state_ok": "Enviando preview ao Discord", "preview_mode": "PREVIEW",
        "editor_hint": "Escolha um preset ou digite o seu. As mudanças vão ao Discord na hora.",
        "phase_5": "Verde / na pista", "phase_0": "Aguardando", "phase_1": "Grid", "phase_3": "Volta de apresentação", "phase_4": "Contagem",
    },
    "es": {
        "editor": "EDITOR", "screen": "Pantalla", "driving": "En pista", "menu": "Menú principal", "mode": "Modo",
        "session": "Sesión", "track": "Pista", "track_name": "Nombre de pista (mostrado)", "track_asset": "Imagen de pista (asset)",
        "car": "Coche", "car_name": "Nombre del coche (mostrado)", "car_asset": "Imagen del coche (asset)", "time": "Tiempo restante",
        "phase": "Fase del juego", "total_laps": "Vueltas totales (0 = por tiempo)", "lap": "Vuelta actual",
        "class_pos": "Posición en la clase", "class_cars": "Coches en la clase", "pos": "Posición general",
        "cars": "Coches en la sesión", "slots": "Plazas máximas", "show_grid": "Mostrar (coches de plazas)",
        "image": "Imagen grande", "img_auto": "Automático (coche / pista)", "img_car": "Solo coche", "img_track": "Solo pista",
        "cycle_car": "Segundos en coche", "cycle_track": "Segundos en pista", "rating": "Rating (solo valores reales)",
        "dr": "DR  p. ej.: S1 (30%)", "sr": "SR  p. ej.: G1 (10%)", "badge": "Badge", "elapsed": "Tiempo transcurrido",
        "live": "Cuenta atrás en vivo", "lang": "Idioma", "reset": "Restablecer", "auto": "Auto",
        "missing": "Sin imagen de '{}' en assets/ (Discord la necesita en el Developer Portal)",
        "bad": "Inválido: {}", "state_ok": "Enviando preview a Discord", "preview_mode": "PREVIEW",
        "editor_hint": "Elige un preset o escribe el tuyo. Los cambios van a Discord al instante.",
        "phase_5": "Verde / en pista", "phase_0": "Esperando", "phase_1": "Parrilla", "phase_3": "Vuelta de formación", "phase_4": "Cuenta atrás",
    },
}
PHASES = (5, 0, 1, 3, 4)


def launch():
    import tkinter.messagebox
    try:
        import tkinter as tk
        from pypresence import Presence
        from PIL import Image, ImageTk
        import customtkinter as ctk
        from lmu_ui import ImageCache, ToolTip, resource_path
        try:
            from version import VERSION, AUTHOR
        except ImportError:
            VERSION, AUTHOR = "dev", "uWaazy"
    except ImportError as e:
        root = tk.Tk()
        root.withdraw()
        tkinter.messagebox.showerror("LMU RPC Preview", f"Falta um componente:\n\n{e}\n\nRode: pip install -r requirements-preview.txt")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("dark-blue")
    base_dir = os.path.dirname(os.path.abspath(__file__))

    class PreviewApp(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("")
            self.geometry("880x640")
            self.minsize(880, 560)
            self.configure(fg_color="#0f1012")
            self.protocol("WM_DELETE_WINDOW", self.on_close)
            try:
                ico = resource_path("icon.ico")
                if os.path.exists(ico):
                    self.iconbitmap(ico)
            except Exception:
                pass

            self.model = PreviewModel.load(os.path.join(base_dir, STATE_FILE))
            lang = self.model.get("language")
            if lang in LANGUAGES:
                set_language(lang)
            self.images = ImageCache(base_dir)
            self.rpc = None
            self.running = False
            self.start_time = None
            self.last_sent = None
            self.last_send_ts = 0.0
            self.current = None
            self.vars = {}
            self._debounce = None
            self._loading = False
            self.cars = car_choices(base_dir)
            self.tracks = track_choices(base_dir)

            self.grid_columnconfigure(0, weight=0)
            self.grid_columnconfigure(1, weight=1)
            self.grid_rowconfigure(0, weight=1)
            self.build_left()
            self.build_editor()
            self.refresh()
            self.after(1000, self.tick)

        # ------------------------------------------------------------------ idioma
        @property
        def L(self):
            from lmu_core import LANGUAGE
            return LABELS.get(LANGUAGE, LABELS["en"])

        # ------------------------------------------------------------------ painel esquerdo (igual ao app original)
        def build_left(self):
            left = ctk.CTkFrame(self, fg_color="transparent", width=420)
            left.grid(row=0, column=0, sticky="ns")
            left.grid_columnconfigure(0, weight=1)
            try:
                banner_path = resource_path("preview.png")
                if os.path.exists(banner_path):
                    pil = Image.open(banner_path)
                    if pil.width > 400:
                        ratio = 400 / pil.width
                        pil = pil.resize((400, int(pil.height * ratio)), Image.Resampling.LANCZOS)
                    img = ctk.CTkImage(light_image=pil, dark_image=pil, size=pil.size)
                    ctk.CTkLabel(left, text="", image=img).grid(row=0, column=0, pady=(0, 15))
            except Exception:
                pass

            self.lbl_status = ctk.CTkLabel(left, text=get_text('ui_disconnected'), font=("Segoe UI", 22, "bold"), text_color="#FF5555")
            self.lbl_status.grid(row=1, column=0)
            self.lbl_substatus = ctk.CTkLabel(left, text=get_text('ui_service_stopped'), font=("Segoe UI", 13), text_color="gray")
            self.lbl_substatus.grid(row=2, column=0, pady=(0, 10))

            card = ctk.CTkFrame(left, fg_color="#1e1f22", corner_radius=15, width=380, height=110, border_width=0)
            card.grid(row=3, column=0, padx=20, pady=(0, 20))
            card.grid_propagate(False)
            self.lbl_large = ctk.CTkLabel(card, text="", width=90, height=90)
            self.lbl_large.place(x=10, y=10)
            self.lbl_small = ctk.CTkLabel(card, text="", width=28, height=28, fg_color="transparent")
            self.lbl_small.place(x=74, y=74)
            self.lbl_small.lift()
            ToolTip(self.lbl_small, lambda: (self.current or {}).get("small_text", ""))
            ctk.CTkLabel(card, text="Le Mans Ultimate", font=("Segoe UI", 13, "bold"), text_color="white", anchor="w").place(x=110, y=12)
            self.lbl_details = ctk.CTkLabel(card, text="...", font=("Segoe UI", 12), text_color="#b9bbbe", anchor="w")
            self.lbl_details.place(x=110, y=35)
            self.lbl_state = ctk.CTkLabel(card, text="...", font=("Segoe UI", 12), text_color="#b9bbbe", anchor="w")
            self.lbl_state.place(x=110, y=55)
            self.lbl_timer = ctk.CTkLabel(card, text="00:00 elapsed", font=("Segoe UI", 12), text_color="#b9bbbe", anchor="w")
            self.lbl_timer.place(x=110, y=75)

            btns = ctk.CTkFrame(left, fg_color="transparent")
            btns.grid(row=4, column=0)
            self.btn_start = ctk.CTkButton(btns, text=get_text('ui_start_rpc'), command=self.start_rpc, fg_color="#1f6aa5",
                                           hover_color="#144870", width=160, height=45, corner_radius=8, font=("Segoe UI", 13, "bold"))
            self.btn_start.grid(row=0, column=0, padx=10)
            self.btn_stop = ctk.CTkButton(btns, text=get_text('ui_stop_rpc'), command=self.stop_rpc, fg_color="#d32f2f",
                                          hover_color="#9a0007", width=160, height=45, corner_radius=8,
                                          font=("Segoe UI", 13, "bold"), state="disabled")
            self.btn_stop.grid(row=0, column=1, padx=10)
            self.lbl_warn = ctk.CTkLabel(left, text="", font=("Segoe UI", 11), text_color="#FFA500", wraplength=380, justify="left")
            self.lbl_warn.grid(row=5, column=0, pady=(12, 0), padx=20)
            ctk.CTkLabel(left, text=f"PREVIEW {VERSION} | by {AUTHOR}", font=("Segoe UI", 10), text_color="gray50").grid(row=6, column=0, pady=(10, 10))

        # ------------------------------------------------------------------ painel direito (editor)
        def build_editor(self):
            if getattr(self, "editor", None):
                self.editor.destroy()
            L = self.L
            self._loading = True
            self.vars = {}
            self.editor = ctk.CTkScrollableFrame(self, fg_color="#17181b", corner_radius=12, label_text=L["editor"],
                                                 label_font=("Segoe UI", 12, "bold"))
            self.editor.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=16)
            self.editor.grid_columnconfigure(1, weight=1)
            self.row = 0
            ctk.CTkLabel(self.editor, text=L["editor_hint"], font=("Segoe UI", 11), text_color="gray60", wraplength=380,
                         justify="left").grid(row=self.row, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))
            self.row += 1

            def var(key, boolean=False):
                v = ctk.BooleanVar(value=bool(self.model.get(key))) if boolean else ctk.StringVar(value=str(self.model.get(key)))
                v.trace_add("write", lambda *_a, k=key, vv=v: self.on_var(k, vv))
                self.vars[key] = v
                return v

            def label(text):
                ctk.CTkLabel(self.editor, text=text, font=("Segoe UI", 12), anchor="w").grid(row=self.row, column=0, sticky="w", padx=(8, 6), pady=4)

            def entry(key, text, width=150):
                label(text)
                ctk.CTkEntry(self.editor, textvariable=var(key), width=width).grid(row=self.row, column=1, sticky="e", padx=8, pady=4)
                self.row += 1

            def option(key, text, pairs):
                """pairs: [(valor_interno, rotulo)]"""
                label(text)
                to_label = {k: l for k, l in pairs}
                to_key = {l: k for k, l in pairs}
                v = ctk.StringVar(value=to_label.get(str(self.model.get(key)), pairs[0][1]))

                def changed(*_a):
                    if not self._loading:
                        self.model.set(key, to_key.get(v.get(), pairs[0][0]))
                        self.on_change()
                v.trace_add("write", changed)
                ctk.CTkOptionMenu(self.editor, variable=v, values=[l for _k, l in pairs], width=190).grid(row=self.row, column=1, sticky="e", padx=8, pady=4)
                self.row += 1

            def section(text):
                ctk.CTkLabel(self.editor, text=text.upper(), font=("Segoe UI", 11, "bold"), text_color="#1f6aa5").grid(
                    row=self.row, column=0, columnspan=2, sticky="w", padx=8, pady=(14, 2))
                self.row += 1

            def combo(text, choices, on_pick):
                label(text)
                labels = [c[0] for c in choices]
                box = ctk.CTkComboBox(self.editor, values=labels, width=190, command=lambda lab: on_pick(lab))
                box.set("")
                box.grid(row=self.row, column=1, sticky="e", padx=8, pady=4)
                self.row += 1

            section(L["screen"])
            option("screen", L["screen"], [("driving", L["driving"]), ("menu", L["menu"])])
            option("mode", L["mode"], [(m, get_text(f"mode_{m}")) for m in GAME_MODES])
            option("session", L["session"], [(s, get_text(s)) for s in SESSIONS])

            section(L["track"])
            combo(L["track"], self.tracks, self.pick_track)
            entry("track_name", L["track_name"])
            entry("track_asset", L["track_asset"])

            section(L["car"])
            combo(L["car"], self.cars, self.pick_car)
            entry("car_name", L["car_name"])
            entry("car_asset", L["car_asset"])

            section(L["time"])
            entry("time_left", L["time"], 90)
            option("phase", L["phase"], [(str(p), f"{p} - {L['phase_' + str(p)]}") for p in PHASES])
            entry("total_laps", L["total_laps"], 90)
            entry("lap", L["lap"], 90)
            entry("elapsed", L["elapsed"], 90)
            label(L["live"])
            ctk.CTkSwitch(self.editor, text="", variable=var("live_clock", True), width=40).grid(row=self.row, column=1, sticky="e", padx=8)
            self.row += 1

            section(L["pos"])
            entry("class_pos", L["class_pos"], 90)
            entry("class_cars", L["class_cars"], 90)
            entry("pos", L["pos"], 90)
            entry("cars", L["cars"], 90)
            entry("slots", L["slots"], 90)
            label(L["show_grid"])
            ctk.CTkSwitch(self.editor, text="", variable=var("show_grid", True), width=40).grid(row=self.row, column=1, sticky="e", padx=8)
            self.row += 1

            section(L["image"])
            option("image_mode", L["image"], [("auto", L["img_auto"]), ("car", L["img_car"]), ("track", L["img_track"])])
            entry("cycle_car", L["cycle_car"], 90)
            entry("cycle_track", L["cycle_track"], 90)

            section(L["rating"])
            entry("dr", L["dr"], 130)
            entry("sr", L["sr"], 130)
            option("badge", L["badge"], badge_choices())

            section(L["lang"])
            langs = [("", L["auto"]), ("en", "English"), ("pt-br", "Português"), ("es", "Español")]
            label(L["lang"])
            to_label = {k: l for k, l in langs}
            to_key = {l: k for k, l in langs}
            lv = ctk.StringVar(value=to_label.get(self.model.get("language"), L["auto"]))
            lv.trace_add("write", lambda *_a: self.on_language(to_key.get(lv.get(), "")))
            ctk.CTkOptionMenu(self.editor, variable=lv, values=[l for _k, l in langs], width=190).grid(row=self.row, column=1, sticky="e", padx=8, pady=4)
            self.row += 1
            ctk.CTkButton(self.editor, text=L["reset"], command=self.reset, fg_color="#3a3b3f", hover_color="#4a4b50", width=120).grid(
                row=self.row, column=0, columnspan=2, pady=14)
            self._loading = False

        # ------------------------------------------------------------------ eventos
        def on_var(self, key, var):
            if self._loading:
                return
            self.model.set(key, var.get())
            self.on_change()

        def on_change(self):
            if self._debounce:
                self.after_cancel(self._debounce)
            self._debounce = self.after(200, self.refresh)

        def pick_car(self, label):
            for lab, name, asset in self.cars:
                if lab == label:
                    self.model.pick_car(name, asset)
                    self.set_vars(car_name=name, car_asset=asset)
                    return

        def pick_track(self, label):
            for lab, name, asset in self.tracks:
                if lab == label:
                    self.model.pick_track(name, asset)
                    self.set_vars(track_name=name, track_asset=asset)
                    return

        def set_vars(self, **kw):
            self._loading = True
            for k, val in kw.items():
                if k in self.vars:
                    self.vars[k].set(val)
            self._loading = False
            self.refresh()

        def on_language(self, lang):
            self.model.set("language", lang)
            if lang:
                set_language(lang)
            else:
                from lmu_core import detect_language
                set_language(detect_language([]))
            self.build_editor()
            self.refresh()

        def reset(self):
            lang = self.model.get("language")
            self.model = PreviewModel({"language": lang})
            self.build_editor()
            self.refresh()

        # ------------------------------------------------------------------ atualizacao
        def refresh(self, save=True):
            self._debounce = None
            if save:
                self.model.save(os.path.join(base_dir, STATE_FILE))
            now = time.time()
            p = self.model.presence(now)
            self.current = p
            self.lbl_details.configure(text=p["details"])
            self.lbl_state.configure(text=p["state"])
            self.lbl_large.configure(image=self.images.get(p["large_image"], (90, 90)))
            if p["small_image"]:
                self.lbl_small.configure(image=self.images.get(p["small_image"], (28, 28), circular=True))
                self.lbl_small.place(x=74, y=74)
                self.lbl_small.lift()
            else:
                self.lbl_small.place_forget()
            self.update_timer(now)

            notes = []
            if self.model.warnings:
                notes.append(self.L["bad"].format(", ".join(sorted(set(self.model.warnings)))))
            for key in {p["large_image"], p["small_image"]} - {""}:
                if self.images.missing(key):
                    notes.append(self.L["missing"].format(key))
            self.lbl_warn.configure(text="\n".join(notes))
            self.send(p)

        def update_timer(self, now):
            if self.start_time:
                elapsed = int(now - self.start_time)
                mins, secs = divmod(elapsed, 60)
                hours, mins = divmod(mins, 60)
                self.lbl_timer.configure(text=(f"{hours:02d}:{mins:02d}:{secs:02d}" if hours else f"{mins:02d}:{secs:02d}") + " elapsed")
            else:
                self.lbl_timer.configure(text="00:00 elapsed")

        def tick(self):
            try:
                if self.model.get("live_clock") and self.model.get("screen") == "driving":
                    left = parse_clock(self.model.get("time_left"))
                    if left:
                        self.model.set("time_left", format_clock(left - 1))
                        self.set_vars(time_left=format_clock(left - 1))
                    else:
                        self.refresh(save=False)
                else:
                    self.refresh(save=False)
            except Exception as e:
                logger.error(f"preview tick: {e}", exc_info=True)
            self.after(1000, self.tick)

        # ------------------------------------------------------------------ Discord
        def start_rpc(self):
            if self.running:
                return
            try:
                self.rpc = Presence(CLIENT_ID)
                self.rpc.connect()
            except Exception as e:
                logger.error(f"Erro ao conectar no Discord: {e}")
                tkinter.messagebox.showerror(get_text('ui_connection_error'), get_text('ui_connection_error_msg', e))
                self.rpc = None
                return
            self.running = True
            offset = parse_clock(self.model.get("elapsed")) or 0
            self.start_time = time.time() - offset
            self.last_sent = None
            self.lbl_status.configure(text=get_text('ui_connected_discord'), text_color="#3BA55C")
            self.lbl_substatus.configure(text=self.L["state_ok"])
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.refresh()

        def stop_rpc(self):
            self.running = False
            if self.rpc:
                try:
                    self.rpc.clear()
                    self.rpc.close()
                except Exception:
                    pass
                self.rpc = None
            self.start_time = None
            self.lbl_status.configure(text=get_text('ui_disconnected'), text_color="#FF5555")
            self.lbl_substatus.configure(text=get_text('ui_service_stopped'))
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.update_timer(time.time())

        def send(self, presence):
            if not (self.running and self.rpc):
                return
            payload = discord_payload(presence, self.start_time)
            key = {k: v for k, v in payload.items() if k != "start"}
            if key == self.last_sent or time.time() - self.last_send_ts < 0.9:
                return
            try:
                self.rpc.update(**payload)
                self.last_sent, self.last_send_ts = key, time.time()
                logger.info(f"preview -> Discord: {payload.get('details')!r} | {payload.get('state')!r} | {payload.get('large_image')!r}")
            except Exception as e:
                logger.error(f"Erro ao enviar update para Discord RPC: {e}")

        def on_close(self):
            self.stop_rpc()
            self.destroy()

    PreviewApp().mainloop()


if __name__ == "__main__":
    launch()
