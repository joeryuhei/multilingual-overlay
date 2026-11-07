"""Small always-on-top window for displaying translated text."""

import tkinter as tk


class TranslationOverlay:
    def __init__(self, root: tk.Tk) -> None:
        self.window = tk.Toplevel(root)
        self.window.title("日本語訳")
        self.window.attributes("-topmost", True)
        self.window.configure(bg="#171717")
        self.window.geometry("520x150+80+80")
        self.label = tk.Label(
            self.window,
            text="「開始」を押すと日本語訳がここに表示されます。",
            anchor="nw",
            justify="left",
            wraplength=480,
            padx=14,
            pady=12,
            bg="#171717",
            fg="#ffffff",
            font=("Segoe UI", 13),
        )
        self.label.pack(fill="both", expand=True)
        self.window.withdraw()

    def show(self, text: str, x: int, y: int) -> None:
        self.label.configure(text=text or "テキストを認識できませんでした。")
        self.window.geometry(f"520x150+{max(0, x + 24)}+{max(0, y + 48)}")
        self.window.deiconify()
        self.window.lift()

    def hide(self) -> None:
        self.window.withdraw()
