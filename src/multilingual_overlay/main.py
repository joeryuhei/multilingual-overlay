"""Tkinter UI and worker orchestration."""

import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import pytesseract

from multilingual_overlay.deepl import ApiPlan, TranslationError, translate_lines
from multilingual_overlay.ocr import recognize_lines
from multilingual_overlay.overlay import TranslationOverlay
from multilingual_overlay.pipeline import StableText, TranslationMemory
from multilingual_overlay.windows import TargetWindow, capture_window, list_windows

OCR_INTERVAL_SECONDS = 1.5
MIN_TRANSLATION_INTERVAL_SECONDS = 2.0


class OverlayApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("多言語オーバーレイ")
        root.geometry("480x440")
        root.minsize(440, 400)

        self.overlay = TranslationOverlay(root)
        self.events: queue.Queue[tuple[str, str, int, int]] = queue.Queue()
        self.stop_event: threading.Event | None = None
        self.windows: list[TargetWindow] = []

        ttk.Label(root, text="対象ウィンドウ").pack(anchor="w", padx=16, pady=(14, 4))
        row = ttk.Frame(root)
        row.pack(fill="x", padx=16)
        self.window_choice = tk.StringVar()
        self.window_combo = ttk.Combobox(row, textvariable=self.window_choice, state="readonly")
        self.window_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="更新", command=self.refresh_windows).pack(side="left", padx=(8, 0))

        ttk.Label(root, text="DeepL APIキー（メモリ内のみで使用）").pack(
            anchor="w", padx=16, pady=(14, 4)
        )
        self.api_key = tk.StringVar(value=os.environ.get("DEEPL_AUTH_KEY", ""))
        ttk.Entry(root, textvariable=self.api_key, show="*").pack(fill="x", padx=16)

        ttk.Label(root, text="DeepLプラン").pack(anchor="w", padx=16, pady=(12, 4))
        self.plan = tk.StringVar(value="free")
        ttk.Combobox(
            root, textvariable=self.plan, values=("free", "pro"), state="readonly"
        ).pack(fill="x", padx=16)

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", padx=16, pady=14)
        self.start_button = ttk.Button(buttons, text="開始", command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(buttons, text="停止", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        ttk.Button(buttons, text="オーバーレイを隠す", command=self.overlay.hide).pack(side="right")

        self.status = tk.StringVar(value="対象ウィンドウを選択してください。")
        ttk.Label(root, textvariable=self.status, wraplength=440).pack(
            anchor="w", padx=16, pady=(0, 8)
        )
        ttk.Label(
            root,
            text=(
                "プライバシー: 選択したウィンドウだけを端末内でキャプチャします。画像はDeepLへ送信せず、"
                "OCRで認識した文字列だけを翻訳のために送信します。APIキーは保存されません。"
            ),
            wraplength=440,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(4, 12))

        self.refresh_windows()
        self.root.after(150, self.process_events)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def refresh_windows(self) -> None:
        selected_title = self.window_combo.get()
        try:
            self.windows = list_windows()
        except RuntimeError as error:
            self.status.set(str(error))
            self.windows = []
        self.window_combo["values"] = [window.title for window in self.windows]
        matching_index = next(
            (index for index, window in enumerate(self.windows) if window.title == selected_title),
            None,
        )
        if matching_index is not None:
            self.window_combo.current(matching_index)
        else:
            self.window_choice.set("")
            if os.name == "nt":
                if not self.windows:
                    self.status.set(
                        "ウィンドウが見つかりません。対象アプリを開いて「更新」してください。"
                    )

    def start(self) -> None:
        selection = self.window_combo.current()
        if selection < 0 or selection >= len(self.windows):
            messagebox.showerror("ウィンドウを選択", "対象ウィンドウを選択してください。")
            return
        key = self.api_key.get().strip()
        if not key:
            messagebox.showerror("DeepL APIキーが必要です", "DeepL APIキーを入力してください。")
            return
        if self.stop_event is not None:
            return

        target = self.windows[selection]
        api_key = key
        plan: ApiPlan = "pro" if self.plan.get() == "pro" else "free"
        stop_event = threading.Event()
        self.stop_event = stop_event
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set(f"「{target.title}」を翻訳しています。")
        threading.Thread(
            target=self.translation_loop,
            args=(target, api_key, plan, stop_event),
            daemon=True,
        ).start()

    def translation_loop(
        self, target: TargetWindow, api_key: str, plan: ApiPlan, stop_event: threading.Event
    ) -> None:
        stability = StableText()
        memory = TranslationMemory()
        last_translated: tuple[str, ...] | None = None
        last_translation_at = 0.0
        try:
            while not stop_event.is_set():
                image = capture_window(target.handle)
                lines = recognize_lines(image)
                x, y = self.window_position(target.handle)
                self.events.put(("position", "", x, y))

                if stability.observe(lines, time.monotonic()):
                    current = stability.candidate
                    now = time.monotonic()
                    if current != last_translated and (
                        now - last_translation_at >= MIN_TRANSLATION_INTERVAL_SECONDS
                    ):
                        last_translation_at = now
                        try:
                            translated = memory.translate(
                                current, lambda missing: translate_lines(missing, api_key, plan)
                            )
                            last_translated = current
                            self.events.put(("translation", "\n".join(translated), x, y))
                        except TranslationError as error:
                            self.events.put(
                                ("fallback", f"{error}\n\nOCR原文:\n" + "\n".join(current), x, y)
                            )
                stop_event.wait(OCR_INTERVAL_SECONDS)
        except (RuntimeError, pytesseract.TesseractNotFoundError, pytesseract.TesseractError):
            self.events.put(
                (
                    "error",
                    "キャプチャまたはOCRに失敗しました。対象ウィンドウが開いていること、"
                    "英語・日本語データ付きTesseractがインストール済みであることを確認してください。",
                    0,
                    0,
                )
            )
        except Exception:
            self.events.put(("error", "対象ウィンドウをキャプチャできませんでした。", 0, 0))
        finally:
            self.events.put(("stopped", "", 0, 0))

    @staticmethod
    def window_position(handle: int) -> tuple[int, int]:
        import win32gui

        left, top, _, _ = win32gui.GetWindowRect(handle)
        return left, top

    def process_events(self) -> None:
        try:
            while True:
                kind, value, x, y = self.events.get_nowait()
                if kind == "translation":
                    self.overlay.show(value, x, y)
                    self.status.set("翻訳中です。")
                elif kind == "fallback":
                    self.overlay.show(value, x, y)
                    self.status.set("DeepL翻訳に失敗したため、OCR原文を表示しています。")
                elif kind == "position":
                    if self.overlay.window.state() != "withdrawn":
                        text = self.overlay.label.cget("text")
                        self.overlay.show(text, x, y)
                elif kind == "error":
                    self.status.set(value)
                    self.overlay.hide()
                elif kind == "stopped":
                    self.stop_event = None
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(150, self.process_events)

    def stop(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()
            self.status.set("翻訳を停止しています…")

    def close(self) -> None:
        self.stop()
        self.root.destroy()


def main() -> None:
    if os.name != "nt":
        raise SystemExit("このアプリは現在Windowsのみ対応しています。")
    root = tk.Tk()
    OverlayApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
