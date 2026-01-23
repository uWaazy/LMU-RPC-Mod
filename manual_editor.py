import customtkinter as ctk
from pypresence import Presence
import time
import sys
import re
import threading

# --- CONFIGURAÇÕES ---
CLIENT_ID = '1463577784394973392' # Mesmo ID do LMU RPC Mod

# --- BASE DE DADOS DE ASSETS ---

CAR_ASSETS = {
    "--- Selecione um Carro ---": "lmu_logo_default",
    # Hypercars
    "Alpine A424": "car_alpine_a424",
    "Aston Martin Valkyrie": "car_aston_martin_valkyrie",
    "BMW M Hybrid V8": "car_bmw_m_hybrid_v8",
    "Cadillac V-Series.R": "car_cadillac_v_series_r",
    "Ferrari 499P": "car_ferrari_499p",
    "Glickenhaus SCG 007": "car_glickenhaus_007",
    "Isotta Fraschini Tipo 6": "car_isotta_fraschini",
    "Lamborghini SC63": "car_lamborghini_sc63",
    "Peugeot 9X8 2024": "car_peugeot_9x8_2024",
    "Peugeot 9X8": "car_peugeot_9x8",
    "Porsche 963": "car_porsche_963",
    "Toyota GR010-Hybrid": "car_toyota_gr010",
    "Vanwall Vandervell 680": "car_vanwall_680",
    # LMGT3
    "Aston Martin Vantage GT3": "car_aston_martin_vantage_gt3",
    "BMW M4 LMGT3": "car_bmw_m4_gt3",
    "Corvette Z06 GT3.R": "car_corvette_z06_gt3",
    "Ferrari 296 LMGT3": "car_ferrari_296_gt3",
    "Ford Mustang LMGT3": "car_ford_mustang_gt3",
    "Lamborghini Huracan GT3": "car_lamborghini_huracan_gt3",
    "Lexus RC F LMGT3": "car_lexus_rcf_gt3",
    "McLaren 720S Evo": "car_mclaren_720s_gt3",
    "Mercedes-AMG LMGT3": "car_mercedes_amg_gt3",
    "Porsche 911 GT3 R": "car_porsche_911_gt3",
    # LMP2
    "Oreca 07 Gibson": "car_oreca_07_2023",
    "Oreca 07 Gibson 2024": "car_oreca_07_2024",
    # LMP3
    "Ligier JS P325": "car_ligier_js_p325",
    "Ginetta G61-LT-P325": "car_ginetta_g61",
    # GTE
    "Aston Martin Vantage GTE": "car_aston_martin_vantage_gte",
    "Corvette C8.R": "car_corvette_c8r_gte",
    "Ferrari 488 GTE": "car_ferrari_488_gte",
    "Porsche 911 RSR-19": "car_porsche_911_rsr",
}

STATUS_ASSETS = {
    "--- Sem Ícone ---": None,
    "Rank Bronze": "rank_bronze",
    "Rank Silver": "rank_silver",
    "Rank Gold": "rank_gold",
    "Rank Platinum": "rank_platinum",
    "Logo LMU": "lmu_logo",
    "Bandeira Verde": "flag_green",
    "Bandeira Amarela": "flag_yellow",
    "Bandeira Vermelha": "flag_red",
    "Bandeira Azul": "flag_blue",
    "Pista: Le Mans": "track_lemans",
    "Pista: Spa": "track_spa",
    "Pista: Monza": "track_monza",
    "Pista: Interlagos": "track_interlagos",
    "Pista: COTA": "track_cota",
    "Pista: Fuji": "track_fuji",
    "Pista: Bahrain": "track_bahrain",
    "Pista: Imola": "track_imola",
    "Pista: Portimão": "track_portimao",
}

ACTIVITY_OPTIONS = [
    "Praticando",
    "Qualificação",
    "Corrida",
    "Test Day",
    "Hotlapping",
    "AFK / Ausente",
    "No Menu",
    "Replay",
    "Transmitindo",
    "Treino Livre"
]

STATE_OPTIONS = [
    "Nos Boxes",
    "Na Pista",
    "Volta Rápida",
    "Volta de Aquecimento",
    "Bandeira Vermelha",
    "Finalizado",
    "Vencendo",
    "Liderando",
    "Batido / Danificado",
    "Safety Car"
]

# --- APP ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class ManualEditorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LMU RPC - Editor Manual")
        self.geometry("400x600")
        self.resizable(False, False)
        self.configure(fg_color="#0f1012") # Fundo Dark
        
        self.rpc = None
        self.connected = False

        self.setup_ui()

    def setup_ui(self):
        # Título
        self.lbl_title = ctk.CTkLabel(self, text="EDITOR MANUAL RPC", font=("Segoe UI", 20, "bold"), text_color="white")
        self.lbl_title.pack(pady=(20, 10))

        self.lbl_subtitle = ctk.CTkLabel(self, text="Selecione as opções abaixo para atualizar", font=("Segoe UI", 12), text_color="gray")
        self.lbl_subtitle.pack(pady=(0, 20))

        # 1. Dropdown Carro (Large Image)
        self.lbl_car = ctk.CTkLabel(self, text="Veículo (Imagem Grande):", anchor="w", text_color="#b9bbbe")
        self.lbl_car.pack(padx=30, pady=(5, 0), anchor="w")
        
        self.car_names = list(CAR_ASSETS.keys())
        self.opt_car = ctk.CTkOptionMenu(self, values=self.car_names, width=340)
        self.opt_car.pack(padx=30, pady=(5, 10))

        # 2. Dropdown Status (Small Image)
        self.lbl_status = ctk.CTkLabel(self, text="Ícone de Status (Imagem Pequena):", anchor="w", text_color="#b9bbbe")
        self.lbl_status.pack(padx=30, pady=(5, 0), anchor="w")
        
        self.status_names = list(STATUS_ASSETS.keys())
        self.opt_status = ctk.CTkOptionMenu(self, values=self.status_names, width=340)
        self.opt_status.pack(padx=30, pady=(5, 10))

        # 3. Dropdown Linha 1 (Atividade)
        self.lbl_line1 = ctk.CTkLabel(self, text="Atividade (Linha Superior):", anchor="w", text_color="#b9bbbe")
        self.lbl_line1.pack(padx=30, pady=(5, 0), anchor="w")
        
        self.opt_line1 = ctk.CTkOptionMenu(self, values=ACTIVITY_OPTIONS, width=340)
        self.opt_line1.pack(padx=30, pady=(5, 10))

        # 4. Dropdown Linha 2 (Estado)
        self.lbl_line2 = ctk.CTkLabel(self, text="Estado (Linha Inferior):", anchor="w", text_color="#b9bbbe")
        self.lbl_line2.pack(padx=30, pady=(5, 0), anchor="w")
        
        self.opt_line2 = ctk.CTkOptionMenu(self, values=STATE_OPTIONS, width=340)
        self.opt_line2.pack(padx=30, pady=(5, 10))

        # 5. Controle de Tempo / Info Extra
        self.lbl_time = ctk.CTkLabel(self, text="Tempo ou Info Extra (Opcional):", anchor="w", text_color="#b9bbbe")
        self.lbl_time.pack(padx=30, pady=(5, 0), anchor="w")
        
        self.entry_time = ctk.CTkEntry(self, placeholder_text="Ex: 01:30:00 ou Volta 5/10", width=340)
        self.entry_time.pack(padx=30, pady=(5, 10))
        
        self.lbl_hint = ctk.CTkLabel(self, text="* Digite horário (00:00) para timer, ou texto para exibir.", 
                                     font=("Segoe UI", 10), text_color="gray")
        self.lbl_hint.pack(pady=(0, 10))

        # 6. Botão de Ação
        self.btn_update = ctk.CTkButton(self, text="ATUALIZAR DISCORD", command=self.update_presence,
                                        width=340, height=50, font=("Segoe UI", 14, "bold"),
                                        fg_color="#1f6aa5", hover_color="#144870")
        self.btn_update.pack(padx=30, pady=(30, 10))

        self.lbl_info = ctk.CTkLabel(self, text="Pronto para conectar.", text_color="gray")
        self.lbl_info.pack(pady=5)

    def parse_input(self, text):
        """Detecta se é Tempo (Timer) ou Texto Livre."""
        text = text.strip()
        if not text:
            return {'type': 'none', 'value': None}
        
        # Regex para HH:MM:SS ou MM:SS
        if re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', text):
            parts = list(map(int, text.split(':')))
            seconds = 0
            if len(parts) == 3: # HH:MM:SS
                seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2: # MM:SS
                seconds = parts[0] * 60 + parts[1]
            
            return {'type': 'time', 'value': seconds}
        else:
            # Texto livre (ex: "Volta 5/10")
            return {'type': 'text', 'value': text}

    def connect_rpc(self):
        if not self.rpc:
            try:
                self.rpc = Presence(CLIENT_ID)
                self.rpc.connect()
                self.connected = True
                print("Conectado ao Discord RPC.")
            except Exception as e:
                self.lbl_info.configure(text=f"Erro de Conexão: {e}", text_color="#FF5555")
                return False
        return True

    def update_presence(self):
        # 1. Conectar se necessário
        if not self.connect_rpc():
            return

        # 2. Coletar Dados
        car_name = self.opt_car.get()
        car_key = CAR_ASSETS.get(car_name, "lmu_logo_default")

        status_name = self.opt_status.get()
        status_key = STATUS_ASSETS.get(status_name, None)

        line1 = self.opt_line1.get() # Atividade
        line2 = self.opt_line2.get() # Estado

        # 3. Lógica de Tempo / Extra
        time_input = self.entry_time.get()
        parsed = self.parse_input(time_input)
        
        end_time = None

        if parsed['type'] == 'time':
            # Se for tempo, cria um timer de contagem regressiva
            now = time.time()
            end_time = now + parsed['value']
        elif parsed['type'] == 'text':
            # Se for texto, adiciona à Linha 2 (Estado)
            # Ex: "Na Pista | Volta 5/10"
            line2 = f"{line2} | {parsed['value']}"

        # 4. Enviar Update
        try:
            self.rpc.update(
                details=line1,
                state=line2,
                large_image=car_key,
                large_text=car_name, # Tooltip da imagem grande
                small_image=status_key,
                small_text=status_name if status_key else None, # Tooltip da imagem pequena
                end=end_time
            )
            
            self.lbl_info.configure(text="Status Atualizado com Sucesso!", text_color="#00FF00")
            self.btn_update.configure(fg_color="#2E7D32", text="ATUALIZADO!")
            
            # Reseta cor do botão após 2s
            self.after(2000, lambda: self.btn_update.configure(fg_color="#1f6aa5", text="ATUALIZAR DISCORD"))

        except Exception as e:
            self.lbl_info.configure(text=f"Erro ao atualizar: {e}", text_color="#FF5555")
            # Se der erro de pipe, tenta desconectar para reconectar na próxima
            self.rpc = None
            self.connected = False

if __name__ == "__main__":
    try:
        app = ManualEditorApp()
        app.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)