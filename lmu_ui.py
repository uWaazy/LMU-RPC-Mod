"""lmu_ui.py - utilitarios de interface usados pelo preview (imagens dos assets, tooltip, caminhos)."""
import os
import sys
import tkinter as tk

from PIL import Image, ImageDraw
import customtkinter as ctk


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


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
        tk.Label(tw, text=text, justify=tk.LEFT, background="#2f3136", foreground="#ffffff",
                 relief=tk.SOLID, borderwidth=1, font=("Segoe UI", 9, "normal"), padx=6, pady=4).pack(ipadx=1)

    def hide_tip(self, event=None):
        tw, self.tip_window = self.tip_window, None
        if tw:
            try:
                tw.destroy()
            except Exception:
                pass


ASSET_SUBDIRS = ("cars", "badges", "ranks", "tracks", "")


class ImageCache:
    """Carrega imagens de assets/<cars|badges|ranks|tracks>/<chave>.png|jpg (a mesma busca do app original)."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.cache = {}

    def find(self, key):
        for root in (self.base_dir, resource_path(".")):
            for sub in ASSET_SUBDIRS:
                folder = os.path.join(root, "assets", sub) if sub else os.path.join(root, "assets")
                for ext in (".png", ".jpg", ".jpeg"):
                    path = os.path.join(folder, key + ext)
                    if os.path.exists(path):
                        return path
        return None

    def get(self, key, size, circular=False):
        cache_key = (key, size, circular)
        if cache_key in self.cache:
            return self.cache[cache_key]
        pil_img = None
        path = self.find(key) or self.find("lmu_logo")
        if path:
            try:
                pil_img = Image.open(path)
            except Exception:
                pil_img = None
        if pil_img is None:
            pil_img = Image.new("RGB", size, (47, 49, 54))
        pil_img = pil_img.resize(size, Image.Resampling.LANCZOS)
        if circular:
            mask = Image.new("L", size, 0)
            ImageDraw.Draw(mask).ellipse((0, 0) + size, fill=255)
            pil_img = pil_img.convert("RGBA")
            out = Image.new("RGBA", size, (0, 0, 0, 0))
            out.paste(pil_img, (0, 0), mask)
            ImageDraw.Draw(out).ellipse((0, 0, size[0] - 1, size[1] - 1), outline=(30, 31, 34, 255), width=2)
            pil_img = out
        img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
        self.cache[cache_key] = img
        return img

    def missing(self, key):
        """True se a chave nao tem imagem em assets/ (o Discord tambem nao teria, a menos que esteja no Developer Portal)."""
        return not self.find(key)
