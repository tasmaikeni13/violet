"""Violet Studio: interactive Tkinter interface for the Violet cipher machine."""

from __future__ import annotations

import json
import queue
import random
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = ROOT_DIR / "violet_core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from violet_engine import ALPHABET, VioletMachine, generate_random_key

APP_BG = "#0D0014"
PANEL_BG = "#170021"
FIELD_BG = "#1B0328"
ACCENT = "#8B2FC9"
ACCENT_HOVER = "#A34CE3"
LAVENDER = "#B57BEE"
GOLD = "#D4AF37"
TEXT_PRIMARY = "#E8D5FF"
TEXT_MUTED = "#B893D6"
SUCCESS = "#B8FFD0"
ERROR = "#FF6D8D"
GRID = "#2C0D3D"
MONO = ("Courier New", 11)
SANS = ("Segoe UI", 10)
SANS_BOLD = ("Segoe UI Semibold", 10)
TITLE_FONT = ("Segoe UI Semibold", 22)
SUBTITLE_FONT = ("Segoe UI", 10)
DEFAULT_PLUGBOARD = "AZ BY CX DW EV FU GT HS IR JQ"


class RoundedButton(tk.Canvas):
    """Canvas-based button with a rounded rectangle and hover effect."""

    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command,
        width: int = 180,
        height: int = 40,
        bg: str = ACCENT,
        hover_bg: str = ACCENT_HOVER,
        fg: str = "white",
        font=SANS_BOLD,
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            bg=master.cget("bg"),
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.command = command
        self.base_color = bg
        self.hover_color = hover_bg
        self.text_color = fg
        self.font = font
        self.width = width
        self.height = height
        self._draw(bg, text)
        self.bind("<Enter>", lambda _: self._draw(self.hover_color, text))
        self.bind("<Leave>", lambda _: self._draw(self.base_color, text))
        self.bind("<Button-1>", lambda _: self.command())

    def _draw(self, fill: str, text: str) -> None:
        self.delete("all")
        radius = 18
        points = [
            radius,
            0,
            self.width - radius,
            0,
            self.width,
            0,
            self.width,
            radius,
            self.width,
            self.height - radius,
            self.width,
            self.height,
            self.width - radius,
            self.height,
            radius,
            self.height,
            0,
            self.height,
            0,
            self.height - radius,
            0,
            radius,
            0,
            0,
        ]
        self.create_polygon(points, smooth=True, fill=fill, outline="")
        self.create_text(
            self.width / 2,
            self.height / 2,
            text=text,
            fill=self.text_color,
            font=self.font,
        )


class VioletStudioApp(tk.Tk):
    """Single-window desktop interface for encryption, analysis, and documentation."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Violet Studio")
        self.configure(bg=APP_BG)
        self.minsize(1000, 700)
        self.geometry("1320x840")

        self.worker_queue: "queue.Queue[Tuple[str, object]]" = queue.Queue()
        self.analysis_after_id: Optional[str] = None

        self.current_key = self._build_default_key()
        self.rotor_position_vars: List[tk.IntVar] = []
        self.rotor_position_labels: List[tk.StringVar] = []
        self.switch_position_vars: List[tk.IntVar] = []
        self.plugboard_var = tk.StringVar(value=DEFAULT_PLUGBOARD)
        self.plugboard_status_var = tk.StringVar(value="10 pairs configured · valid")
        self.plugboard_status_color = SUCCESS
        self.status_var = tk.StringVar(value="Ready")
        self.plaintext_count_var = tk.StringVar(value="0 characters")
        self.live_ic_var = tk.StringVar(value="0.0000")
        self.live_fixed_var = tk.StringVar(value="0 steps · 0.0%")
        self.live_nonreciprocity_var = tk.StringVar(value="0.0%")
        self.live_state_var = tk.StringVar(value="R: A-A-A-A-A | S: 00-00-00-00-00-00")
        self.live_unique_var = tk.StringVar(value="0")

        self._configure_styles()
        self._build_shell()
        self._populate_key_widgets_from_key(self.current_key)
        self.after(100, self._poll_worker_queue)
        self.after(150, self._update_live_analysis)

    def _build_default_key(self) -> Dict[str, object]:
        key = generate_random_key(seed=42)
        key["rotor_positions"] = [0, 0, 0, 0, 0]
        key["switch_positions"] = [0, 0, 0, 0, 0, 0]
        key["plugboard_pairs"] = [list(token) for token in DEFAULT_PLUGBOARD.split()]
        return key

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=APP_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL_BG, foreground=TEXT_MUTED, padding=(16, 10))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        style.configure("Violet.TFrame", background=PANEL_BG)
        style.configure("Card.TFrame", background=FIELD_BG)
        style.configure("TLabel", background=APP_BG, foreground=TEXT_PRIMARY, font=SANS)
        style.configure("Card.TLabel", background=FIELD_BG, foreground=TEXT_PRIMARY, font=SANS)
        style.configure("Accent.TLabel", background=APP_BG, foreground=GOLD, font=SANS_BOLD)
        style.configure("Violet.Horizontal.TProgressbar", troughcolor=GRID, background=ACCENT, bordercolor=GRID)

    def _build_shell(self) -> None:
        header = tk.Frame(self, bg=APP_BG)
        header.pack(fill="x", padx=24, pady=(18, 10))
        tk.Label(
            header,
            text="🟣 VIOLET — Cascade Electromechanical Cipher",
            font=TITLE_FONT,
            fg=TEXT_PRIMARY,
            bg=APP_BG,
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Rotor × Stepping-Switch Cascade · S₂₆ · 2¹¹¹ keys",
            font=SUBTITLE_FONT,
            fg=TEXT_MUTED,
            bg=APP_BG,
        ).pack(anchor="w", pady=(4, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(0, 18))

        self.cipher_tab = tk.Frame(self.notebook, bg=APP_BG)
        self.analysis_tab = tk.Frame(self.notebook, bg=APP_BG)
        self.about_tab = tk.Frame(self.notebook, bg=APP_BG)
        self.notebook.add(self.cipher_tab, text="⚙ CIPHER STUDIO")
        self.notebook.add(self.analysis_tab, text="📊 LIVE ANALYSIS")
        self.notebook.add(self.about_tab, text="📖 ABOUT VIOLET")

        self._build_cipher_tab()
        self._build_analysis_tab()
        self._build_about_tab()

    def _section_label(self, master: tk.Misc, text: str) -> tk.Label:
        return tk.Label(master, text=text, font=("Segoe UI Semibold", 11), fg=GOLD, bg=master.cget("bg"))

    def _text_area(self, master: tk.Misc, fg: str, state: str = "normal", height: int = 8) -> tk.Text:
        widget = tk.Text(
            master,
            height=height,
            bg=FIELD_BG,
            fg=fg,
            insertbackground=LAVENDER,
            font=MONO,
            relief="flat",
            wrap="word",
            padx=12,
            pady=12,
            highlightthickness=1,
            highlightbackground=GRID,
            highlightcolor=ACCENT,
        )
        widget.configure(state=state)
        return widget

    def _build_cipher_tab(self) -> None:
        self.cipher_tab.columnconfigure(0, weight=2)
        self.cipher_tab.columnconfigure(1, weight=3)
        self.cipher_tab.rowconfigure(0, weight=1)

        left = tk.Frame(self.cipher_tab, bg=PANEL_BG, padx=18, pady=18)
        right = tk.Frame(self.cipher_tab, bg=PANEL_BG, padx=18, pady=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=6)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=6)
        left.columnconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self._section_label(left, "ROTOR STAGE").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        for index in range(5):
            label = tk.Label(left, text=f"Rotor {index + 1}", bg=PANEL_BG, fg=TEXT_PRIMARY, font=SANS)
            label.grid(row=index + 1, column=0, sticky="w", pady=4)

            value = tk.IntVar(value=0)
            self.rotor_position_vars.append(value)
            display = tk.StringVar(value="0 · A")
            self.rotor_position_labels.append(display)
            spinbox = tk.Spinbox(
                left,
                from_=0,
                to=25,
                width=6,
                textvariable=value,
                command=self._on_rotor_spin,
                bg=FIELD_BG,
                fg=TEXT_PRIMARY,
                buttonbackground=GRID,
                insertbackground=LAVENDER,
                relief="flat",
                font=MONO,
            )
            spinbox.grid(row=index + 1, column=1, sticky="w", pady=4)
            spinbox.bind("<KeyRelease>", lambda _event: self._on_rotor_spin())
            tk.Label(left, textvariable=display, bg=PANEL_BG, fg=TEXT_MUTED, font=MONO).grid(row=index + 1, column=1, sticky="e", padx=(0, 70))
            RoundedButton(left, text="🔀 Randomize", width=120, height=32, command=lambda idx=index: self._randomize_rotor(idx)).grid(
                row=index + 1, column=2, sticky="e", padx=(8, 0)
            )

        plugboard_row = 7
        self._section_label(left, "PLUGBOARD (10 pairs)").grid(row=plugboard_row, column=0, columnspan=3, sticky="w", pady=(18, 8))
        self.plugboard_entry = tk.Entry(
            left,
            textvariable=self.plugboard_var,
            bg=FIELD_BG,
            fg=TEXT_PRIMARY,
            insertbackground=LAVENDER,
            relief="flat",
            font=MONO,
        )
        self.plugboard_entry.grid(row=plugboard_row + 1, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.plugboard_entry.bind("<KeyRelease>", lambda _event: self._validate_plugboard())
        self.plugboard_status_label = tk.Label(left, textvariable=self.plugboard_status_var, bg=PANEL_BG, fg=SUCCESS, font=SANS)
        self.plugboard_status_label.grid(row=plugboard_row + 2, column=0, columnspan=3, sticky="w")

        switch_start = plugboard_row + 4
        self._section_label(left, "STEPPING-SWITCH STAGE").grid(row=switch_start, column=0, columnspan=3, sticky="w", pady=(18, 12))
        for index in range(6):
            tk.Label(left, text=f"Switch {index + 1}", bg=PANEL_BG, fg=TEXT_PRIMARY, font=SANS).grid(row=switch_start + index + 1, column=0, sticky="w", pady=4)
            value = tk.IntVar(value=0)
            self.switch_position_vars.append(value)
            spinbox = tk.Spinbox(
                left,
                from_=0,
                to=24,
                width=6,
                textvariable=value,
                bg=FIELD_BG,
                fg=TEXT_PRIMARY,
                buttonbackground=GRID,
                insertbackground=LAVENDER,
                relief="flat",
                font=MONO,
            )
            spinbox.grid(row=switch_start + index + 1, column=1, sticky="w", pady=4)
            spinbox.bind("<KeyRelease>", lambda _event: self._refresh_status_preview())
            RoundedButton(left, text="🔀", width=56, height=30, command=lambda idx=index: self._randomize_switch(idx)).grid(
                row=switch_start + index + 1, column=2, sticky="e"
            )

        RoundedButton(left, text="🔀 Randomize All Switches", width=220, height=36, command=self._randomize_all_switches).grid(
            row=switch_start + 7, column=0, columnspan=3, sticky="ew", pady=(10, 8)
        )
        RoundedButton(left, text="🔑 GENERATE RANDOM KEY", width=250, height=44, command=self._generate_random_key).grid(
            row=switch_start + 8, column=0, columnspan=3, sticky="ew", pady=(8, 10)
        )

        button_row = tk.Frame(left, bg=PANEL_BG)
        button_row.grid(row=switch_start + 9, column=0, columnspan=3, sticky="ew")
        button_row.columnconfigure((0, 1), weight=1)
        RoundedButton(button_row, text="💾 Save Key", width=150, height=34, command=self._save_key).grid(row=0, column=0, sticky="w")
        RoundedButton(button_row, text="📂 Load Key", width=150, height=34, command=self._load_key).grid(row=0, column=1, sticky="e")

        self._section_label(right, "PLAINTEXT").grid(row=0, column=0, sticky="w")
        self.plaintext_text = self._text_area(right, TEXT_PRIMARY, height=10)
        self.plaintext_text.grid(row=1, column=0, sticky="nsew", pady=(6, 4))
        self.plaintext_text.bind("<KeyRelease>", lambda _event: self._update_plaintext_count())
        tk.Label(right, textvariable=self.plaintext_count_var, bg=PANEL_BG, fg=TEXT_MUTED, font=SANS).grid(row=2, column=0, sticky="w")
        RoundedButton(right, text="🔒 ENCRYPT →", width=220, height=42, command=self._start_encrypt).grid(row=3, column=0, sticky="w", pady=(14, 12))

        separator = tk.Frame(right, height=1, bg=GRID)
        separator.grid(row=4, column=0, sticky="ew", pady=(0, 14))

        self._section_label(right, "CIPHERTEXT").grid(row=5, column=0, sticky="w")
        self.ciphertext_text = self._text_area(right, SUCCESS, height=8)
        self.ciphertext_text.grid(row=6, column=0, sticky="nsew", pady=(6, 12))
        RoundedButton(right, text="🔓 DECRYPT →", width=220, height=42, command=self._start_decrypt).grid(row=7, column=0, sticky="w", pady=(0, 12))

        self._section_label(right, "DECRYPTED TEXT").grid(row=8, column=0, sticky="w")
        self.decrypted_text = self._text_area(right, GOLD, height=8)
        self.decrypted_text.grid(row=9, column=0, sticky="nsew", pady=(6, 12))

        utility_row = tk.Frame(right, bg=PANEL_BG)
        utility_row.grid(row=10, column=0, sticky="ew")
        RoundedButton(utility_row, text="🔄 SWAP ⟺", width=150, height=34, command=self._swap_text).pack(side="left")
        RoundedButton(utility_row, text="🗑 CLEAR ALL", width=150, height=34, command=self._clear_all).pack(side="left", padx=10)

        status_bar = tk.Label(right, textvariable=self.status_var, bg=FIELD_BG, fg=TEXT_MUTED, font=MONO, anchor="w", padx=12, pady=8)
        status_bar.grid(row=11, column=0, sticky="ew", pady=(16, 0))
        right.rowconfigure(1, weight=2)
        right.rowconfigure(6, weight=1)
        right.rowconfigure(9, weight=1)

    def _build_analysis_tab(self) -> None:
        self.analysis_tab.columnconfigure(0, weight=1)
        self.analysis_tab.rowconfigure(3, weight=1)
        container = tk.Frame(self.analysis_tab, bg=PANEL_BG, padx=18, pady=18)
        container.pack(fill="both", expand=True, padx=6, pady=6)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        container.columnconfigure(2, weight=1)

        self._section_label(container, "LIVE ANALYSIS INPUT — type to see cipher properties update in real time").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        self.live_input_text = self._text_area(container, TEXT_PRIMARY, height=8)
        self.live_input_text.grid(row=1, column=0, columnspan=3, sticky="nsew")
        self.live_input_text.bind("<KeyRelease>", self._schedule_live_analysis)

        metric_card_left = tk.Frame(container, bg=FIELD_BG, padx=14, pady=14)
        metric_card_mid = tk.Frame(container, bg=FIELD_BG, padx=14, pady=14)
        metric_card_right = tk.Frame(container, bg=FIELD_BG, padx=14, pady=14)
        metric_card_left.grid(row=2, column=0, sticky="nsew", padx=(0, 8), pady=(14, 8))
        metric_card_mid.grid(row=2, column=1, sticky="nsew", padx=8, pady=(14, 8))
        metric_card_right.grid(row=2, column=2, sticky="nsew", padx=(8, 0), pady=(14, 8))

        tk.Label(metric_card_left, text="Index of Coincidence", bg=FIELD_BG, fg=GOLD, font=SANS_BOLD).pack(anchor="w")
        tk.Label(metric_card_left, textvariable=self.live_ic_var, bg=FIELD_BG, fg=TEXT_PRIMARY, font=("Segoe UI Semibold", 18)).pack(anchor="w", pady=(6, 10))
        self.ic_progress = ttk.Progressbar(metric_card_left, style="Violet.Horizontal.TProgressbar", maximum=100)
        self.ic_progress.pack(fill="x")
        tk.Label(metric_card_left, text="0% = random-like · 100% = English-like", bg=FIELD_BG, fg=TEXT_MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(6, 0))

        tk.Label(metric_card_mid, text="Fixed Point Counter", bg=FIELD_BG, fg=GOLD, font=SANS_BOLD).pack(anchor="w")
        tk.Label(metric_card_mid, textvariable=self.live_fixed_var, bg=FIELD_BG, fg=TEXT_PRIMARY, font=("Segoe UI Semibold", 18)).pack(anchor="w", pady=(6, 10))
        tk.Label(metric_card_mid, text="Unique Permutations Used", bg=FIELD_BG, fg=GOLD, font=SANS_BOLD).pack(anchor="w")
        tk.Label(metric_card_mid, textvariable=self.live_unique_var, bg=FIELD_BG, fg=LAVENDER, font=("Segoe UI Semibold", 18)).pack(anchor="w", pady=(6, 0))

        tk.Label(metric_card_right, text="Non-reciprocity Rate", bg=FIELD_BG, fg=GOLD, font=SANS_BOLD).pack(anchor="w")
        tk.Label(metric_card_right, textvariable=self.live_nonreciprocity_var, bg=FIELD_BG, fg=TEXT_PRIMARY, font=("Segoe UI Semibold", 18)).pack(anchor="w", pady=(6, 10))
        self.nonreciprocity_progress = ttk.Progressbar(metric_card_right, style="Violet.Horizontal.TProgressbar", maximum=100)
        self.nonreciprocity_progress.pack(fill="x")
        tk.Label(metric_card_right, text="Current Machine State", bg=FIELD_BG, fg=GOLD, font=SANS_BOLD).pack(anchor="w", pady=(12, 0))
        tk.Label(metric_card_right, textvariable=self.live_state_var, bg=FIELD_BG, fg=LAVENDER, font=MONO).pack(anchor="w", pady=(6, 0))

        chart_card = tk.Frame(container, bg=FIELD_BG, padx=14, pady=14)
        chart_card.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        chart_card.columnconfigure(0, weight=1)
        tk.Label(chart_card, text="Letter Frequency Chart", bg=FIELD_BG, fg=GOLD, font=SANS_BOLD).pack(anchor="w")
        self.frequency_canvas = tk.Canvas(chart_card, bg=FIELD_BG, highlightthickness=0, height=240)
        self.frequency_canvas.pack(fill="both", expand=True, pady=(10, 0))

    def _build_about_tab(self) -> None:
        container = tk.Frame(self.about_tab, bg=PANEL_BG)
        container.pack(fill="both", expand=True, padx=6, pady=6)
        text = tk.Text(
            container,
            bg=FIELD_BG,
            fg=TEXT_PRIMARY,
            insertbackground=LAVENDER,
            relief="flat",
            wrap="word",
            font=("Segoe UI", 11),
            padx=18,
            pady=18,
        )
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        text.tag_configure("heading", foreground=GOLD, font=("Segoe UI Semibold", 15), spacing1=10, spacing3=6)
        text.tag_configure("subheading", foreground=LAVENDER, font=("Segoe UI Semibold", 12), spacing1=8, spacing3=4)
        text.tag_configure("body", foreground=TEXT_PRIMARY, font=("Segoe UI", 11), spacing3=6)
        text.tag_configure("formula", foreground=SUCCESS, font=("Courier New", 14, "bold"), spacing1=10, spacing3=10)
        text.tag_configure("mono", foreground=TEXT_MUTED, font=("Courier New", 11), spacing3=6)

        sections = [
            ("heading", "What Violet Is\n"),
            (
                "body",
                "Violet is a theoretical electromechanical cipher machine that sends every letter through two independent scrambling stages. The first stage is rotor-based, like a reflectorless Enigma without the reciprocity weakness. The second stage is a bank of Strowger stepping switches, similar in spirit to telephone exchange selectors. Each stage evolves on every keystroke, but they evolve at different rhythms.\n\n",
            ),
            ("subheading", "How Violet Differs From Enigma\n"),
            (
                "body",
                "• No reflector, so encryption is not generically its own inverse.\n• Self-encryption is possible, removing Enigma's strongest crib constraint.\n• The rotor odometer is strict base-26 with no double-stepping anomaly.\n\n",
            ),
            ("subheading", "How Violet Differs From Purple\n"),
            (
                "body",
                "• Violet never partitions the alphabet into separate groups.\n• All 26 letters pass through every active component.\n• The switch stage is only one layer in a larger cascade, not the whole machine.\n\n",
            ),
            ("heading", "Cascade Formula\n"),
            ("formula", "E_t = σ_t ∘ ρ_t\n\n"),
            ("heading", "Entropy Comparison\n"),
            ("mono", "+----------------+---------------+\n| Machine        | Entropy (bits)|\n+----------------+---------------+\n| Purple         | ~60           |\n| Enigma         | ~77           |\n| Violet         | ~111          |\n+----------------+---------------+\n\n"),
            ("heading", "Machine Period\n"),
            (
                "body",
                "The canonical Violet period is N = 26^5 × 25^6 ≈ 2.94 × 10^15 states. In plain terms, at 100 characters per minute, that is roughly 55 million years of continuous typing before the machine repeats its full state cycle.\n\n",
            ),
            ("heading", "Credits\n"),
            ("body", "Theory by Tasmai Keni · Implementation by Violet Studio\n"),
        ]
        for tag, content in sections:
            text.insert("end", content, tag)
        text.configure(state="disabled")

    def _parse_plugboard(self) -> List[Tuple[str, str]]:
        tokens = [token.strip().upper() for token in self.plugboard_var.get().split() if token.strip()]
        if len(tokens) != 10:
            raise ValueError("Exactly 10 plugboard pairs are required.")
        pairs: List[Tuple[str, str]] = []
        used = set()
        for token in tokens:
            if len(token) != 2 or any(letter not in ALPHABET for letter in token):
                raise ValueError("Each plugboard pair must be two letters, for example AZ.")
            if token[0] == token[1]:
                raise ValueError("Plugboard pairs must swap distinct letters.")
            if token[0] in used or token[1] in used:
                raise ValueError("Each letter may appear in only one plugboard pair.")
            used.update(token)
            pairs.append((token[0], token[1]))
        return pairs

    def _validate_plugboard(self) -> bool:
        try:
            pairs = self._parse_plugboard()
        except ValueError as exc:
            self.plugboard_status_var.set(str(exc))
            self.plugboard_status_label.configure(fg=ERROR)
            return False

        self.current_key["plugboard_pairs"] = [list(pair) for pair in pairs]
        self.plugboard_status_var.set(f"{len(pairs)} pairs configured · valid")
        self.plugboard_status_label.configure(fg=SUCCESS)
        self._refresh_status_preview()
        return True

    def _populate_key_widgets_from_key(self, key: Dict[str, object]) -> None:
        for index, value in enumerate(key["rotor_positions"]):
            self.rotor_position_vars[index].set(int(value))
        for index, value in enumerate(key["switch_positions"]):
            self.switch_position_vars[index].set(int(value))
        tokens = ["".join(pair) for pair in key["plugboard_pairs"]]
        self.plugboard_var.set(" ".join(tokens))
        self._on_rotor_spin()
        self._validate_plugboard()
        self._refresh_status_preview()

    def _current_key_from_widgets(self) -> Dict[str, object]:
        if not self._validate_plugboard():
            raise ValueError(self.plugboard_status_var.get())
        key = {
            "rotors": self.current_key["rotors"],
            "rotor_positions": [int(var.get()) % 26 for var in self.rotor_position_vars],
            "plugboard_pairs": [list(pair) for pair in self._parse_plugboard()],
            "switch_wirings": self.current_key["switch_wirings"],
            "switch_positions": [int(var.get()) % 25 for var in self.switch_position_vars],
        }
        self.current_key = key
        return key

    def _machine_from_widgets(self) -> VioletMachine:
        return VioletMachine.from_key(self._current_key_from_widgets())

    def _on_rotor_spin(self) -> None:
        for index, variable in enumerate(self.rotor_position_vars):
            value = int(variable.get()) % 26
            variable.set(value)
            self.rotor_position_labels[index].set(f"{value} · {ALPHABET[value]}")
        self._refresh_status_preview()

    def _randomize_rotor(self, index: int) -> None:
        self.rotor_position_vars[index].set(random.randint(0, 25))
        self._on_rotor_spin()

    def _randomize_switch(self, index: int) -> None:
        self.switch_position_vars[index].set(random.randint(0, 24))
        self._refresh_status_preview()

    def _randomize_all_switches(self) -> None:
        for variable in self.switch_position_vars:
            variable.set(random.randint(0, 24))
        self._refresh_status_preview()

    def _generate_random_pairs(self) -> List[List[str]]:
        letters = list(ALPHABET)
        random.shuffle(letters)
        return [[letters[2 * index], letters[2 * index + 1]] for index in range(10)]

    def _generate_random_key(self) -> None:
        self.current_key["rotor_positions"] = [random.randint(0, 25) for _ in range(5)]
        self.current_key["switch_positions"] = [random.randint(0, 24) for _ in range(6)]
        self.current_key["plugboard_pairs"] = self._generate_random_pairs()
        self._populate_key_widgets_from_key(self.current_key)

    def _save_key(self) -> None:
        try:
            key = self._current_key_from_widgets()
        except ValueError as exc:
            messagebox.showerror("Invalid key", str(exc), parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save Violet key",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(key, handle, indent=2)
        self.status_var.set(f"Saved key to {Path(path).name}")

    def _load_key(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Load Violet key",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                key = json.load(handle)
            VioletMachine.from_key(key)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Load failed", f"Could not load the key file.\n\n{exc}", parent=self)
            return
        self.current_key = key
        self._populate_key_widgets_from_key(self.current_key)
        self.status_var.set(f"Loaded key from {Path(path).name}")

    def _update_plaintext_count(self) -> None:
        content = self.plaintext_text.get("1.0", "end-1c")
        count = sum(character.isalpha() for character in content)
        self.plaintext_count_var.set(f"{count} alphabetic characters")

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", value)

    def _refresh_status_preview(self) -> None:
        rotor_letters = "-".join(ALPHABET[int(var.get()) % 26] for var in self.rotor_position_vars)
        switch_values = "-".join(f"{int(var.get()) % 25:02d}" for var in self.switch_position_vars)
        self.status_var.set(f"State preview · R: {rotor_letters} | S: {switch_values}")

    def _swap_text(self) -> None:
        plaintext = self.plaintext_text.get("1.0", "end-1c")
        ciphertext = self.ciphertext_text.get("1.0", "end-1c")
        self._set_text(self.plaintext_text, ciphertext)
        self._set_text(self.ciphertext_text, plaintext)
        self._update_plaintext_count()

    def _clear_all(self) -> None:
        for widget in (self.plaintext_text, self.ciphertext_text, self.decrypted_text, self.live_input_text):
            self._set_text(widget, "")
        self._update_plaintext_count()
        self._update_live_analysis()
        self.status_var.set("Cleared all text areas")

    def _start_encrypt(self) -> None:
        self._start_worker("encrypt")

    def _start_decrypt(self) -> None:
        self._start_worker("decrypt")

    def _start_worker(self, mode: str) -> None:
        try:
            key = self._current_key_from_widgets()
        except ValueError as exc:
            messagebox.showerror("Invalid key", str(exc), parent=self)
            return

        if mode == "encrypt":
            payload = self.plaintext_text.get("1.0", "end-1c")
        else:
            payload = self.ciphertext_text.get("1.0", "end-1c")

        self.status_var.set(f"Running {mode}ion …")

        def worker() -> None:
            started = time.perf_counter()
            machine = VioletMachine.from_key(key)
            if mode == "encrypt":
                result = machine.encrypt(payload)
            else:
                result = machine.decrypt(payload)
            elapsed = time.perf_counter() - started
            self.worker_queue.put((mode, {"result": result, "elapsed": elapsed, "key": key}))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_worker_queue(self) -> None:
        try:
            while True:
                mode, payload = self.worker_queue.get_nowait()
                result = payload["result"]
                elapsed = payload["elapsed"]
                key = payload["key"]
                machine = VioletMachine.from_key(key)
                processed = len(result)
                state_label = self._format_state(machine.initial_rotor_positions, machine.initial_switch_positions)
                if mode == "encrypt":
                    self._set_text(self.ciphertext_text, result)
                else:
                    self._set_text(self.decrypted_text, result)
                self.status_var.set(f"{mode.title()}ed {processed} characters in {elapsed:.4f}s · {state_label}")
        except queue.Empty:
            pass
        self.after(100, self._poll_worker_queue)

    def _schedule_live_analysis(self, _event=None) -> None:
        if self.analysis_after_id is not None:
            self.after_cancel(self.analysis_after_id)
        self.analysis_after_id = self.after(120, self._update_live_analysis)

    def _update_live_analysis(self) -> None:
        self.analysis_after_id = None
        try:
            machine = self._machine_from_widgets()
        except ValueError:
            return

        plaintext = "".join(character for character in self.live_input_text.get("1.0", "end-1c").upper() if character.isalpha())
        if not plaintext:
            self.live_ic_var.set("0.0000")
            self.live_fixed_var.set("0 steps · 0.0%")
            self.live_nonreciprocity_var.set("0.0%")
            self.live_state_var.set(self._format_state(machine.initial_rotor_positions, machine.initial_switch_positions))
            self.live_unique_var.set("0")
            self.ic_progress["value"] = 0
            self.nonreciprocity_progress["value"] = 0
            self._draw_frequency_chart(Counter())
            return

        ciphertext_chars: List[str] = []
        fixed_steps = 0
        non_reciprocal = 0
        unique = set()
        identity = list(range(26))

        machine.reset()
        for char in plaintext:
            machine._step_rotors()
            machine._step_switches()
            state = machine.get_state()
            permutation = state["E_t"]
            unique.add(tuple(int(value) for value in permutation.tolist()))
            if any(int(permutation[index]) == identity[index] for index in range(26)):
                pass
            if not all(int(permutation[int(permutation[index])]) == identity[index] for index in range(26)):
                non_reciprocal += 1
            output_char = ALPHABET[int(permutation[ord(char) - ord("A")])]
            if output_char == char:
                fixed_steps += 1
            ciphertext_chars.append(output_char)

        ciphertext = "".join(ciphertext_chars)
        counts = Counter(ciphertext)
        count_values = [counts[letter] for letter in ALPHABET]
        total = len(ciphertext)
        ic = 0.0
        if total > 1:
            ic = sum(value * (value - 1) for value in count_values) / (total * (total - 1))

        fixed_pct = (fixed_steps / total) * 100 if total else 0.0
        nonreciprocity_rate = (non_reciprocal / total) * 100 if total else 0.0
        random_ic = 1 / 26
        english_ic = 0.065
        scale = max(0.0, min(1.0, (ic - random_ic) / (english_ic - random_ic))) if english_ic != random_ic else 0.0

        self.live_ic_var.set(f"{ic:.4f}")
        self.live_fixed_var.set(f"{fixed_steps} steps · {fixed_pct:.1f}%")
        self.live_nonreciprocity_var.set(f"{nonreciprocity_rate:.1f}%")
        self.live_state_var.set(self._format_state(machine.rotor_positions, machine.switch_positions))
        self.live_unique_var.set(str(len(unique)))
        self.ic_progress["value"] = scale * 100
        self.nonreciprocity_progress["value"] = nonreciprocity_rate
        self._draw_frequency_chart(counts)

    def _draw_frequency_chart(self, counts: Counter) -> None:
        self.frequency_canvas.delete("all")
        width = max(640, self.frequency_canvas.winfo_width() or 640)
        height = max(220, self.frequency_canvas.winfo_height() or 220)
        self.frequency_canvas.configure(width=width, height=height)
        padding = 20
        chart_width = width - 2 * padding
        chart_height = height - 40
        total = sum(counts.values()) or 1
        max_freq = max((counts[letter] / total for letter in ALPHABET), default=1 / 26)
        bar_width = chart_width / 26

        for index, letter in enumerate(ALPHABET):
            frequency = counts[letter] / total
            bar_height = (frequency / max_freq) * (chart_height - 20) if max_freq else 0
            x0 = padding + index * bar_width + 2
            y0 = chart_height - bar_height + 10
            x1 = padding + (index + 1) * bar_width - 2
            y1 = chart_height + 10
            self.frequency_canvas.create_rectangle(x0, y0, x1, y1, fill=ACCENT, outline="")
            self.frequency_canvas.create_text((x0 + x1) / 2, chart_height + 24, text=letter, fill=TEXT_MUTED, font=("Segoe UI", 8))

    def _format_state(self, rotor_positions: List[int], switch_positions: List[int]) -> str:
        rotor_letters = "-".join(ALPHABET[position % 26] for position in rotor_positions)
        switch_values = "-".join(f"{position % 25:02d}" for position in switch_positions)
        return f"R: {rotor_letters} | S: {switch_values}"


def main() -> None:
    app = VioletStudioApp()
    app.mainloop()


if __name__ == "__main__":
    main()
