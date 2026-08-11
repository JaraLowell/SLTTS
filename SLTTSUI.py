import os
import sys
import time
import json
import customtkinter as ctk
from tkinter import messagebox
from configparser import ConfigParser
from pygame._sdl2 import get_audio_device_names

def merge_config_settings(config, current_values, default_values=None):
    """Merge current UI values into the config while preserving existing values."""
    default_values = default_values or {}

    if not config.has_section('Settings'):
        config.add_section('Settings')

    for key, value in default_values.items():
        if not config.has_option('Settings', key):
            config.set('Settings', key, str(value))

    for key, value in current_values.items():
        if value is None:
            continue
        if value == '':
            continue
        config.set('Settings', key, str(value))

    return config

class MainWindow(ctk.CTk):
    def __init__(self, global_config):
        super().__init__()
        self.global_config = global_config  # Use the global configuration object
        self.title("Second Life TTS")
        self.geometry(global_config.get('Settings', 'window_geometry', fallback="1024x768"))
        icon_path = os.path.join(getattr(sys, '_MEIPASS', os.path.abspath('.')), "SLTTS.ico")
        self.iconbitmap(icon_path)
        self.resizable(True, True)
        self.name2voice_file = "name2voice.json"
        self.name2voice_change_callback = None
        self.name2voice_editor_window = None
        self.name2voice_rows = []
        self.slang_file = "slangreplce.json"
        self.slang_change_callback = None
        self.slang_editor_window = None
        self.slang_rows = []

        # Busy indicator variables
        self.is_busy = False
        self.busy_chars = ["🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚", "🕛"]
        self.busy_index = 0
        self.busy_animation_id = None

        # Apply dark mode
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Layout
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=2)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Terminal-like display
        self.text_display = ctk.CTkTextbox(self.main_frame, wrap="word", state="disabled", font=("Consolas", 16), border_width=1, border_color='#1d1d1d')
        self.text_display.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        self.text_display.tag_config("R", foreground="#ff8080")
        self.text_display.tag_config("T", foreground="#a1a1a1")
        self.text_display.tag_config("B", foreground="#8080ff")
        self.text_display.tag_config("G", foreground="#80ff80")
        self.text_display.tag_config("A", foreground="#f1da80")
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)

        # Buttons and controls
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.grid(row=1, column=0, columnspan=2, sticky="n", pady=(2, 12))

        # Status indicator (clock when busy, invisible when not)
        self.status_indicator = ctk.CTkLabel(self.button_frame, text=self.busy_chars[0], font=("Consolas", 20))
        self.status_indicator.grid(row=0, column=0,  padx=(5,0))

        self.start_button = ctk.CTkButton(self.button_frame, text="Start Log Reading", text_color="#d1d1d1", font=("Consolas", 14, "bold"), width=220, border_width=0, border_color="#888888")
        self.start_button.grid(row=0, column=1, padx=5)

        '''
        self.spelling_check_button = ctk.CTkButton(self.button_frame, text="Toggle Spelling Check", text_color="#d1d1d1", font=("Consolas", 14, "bold"), command=self.toggle_spelling_check, width=220, border_width=1, border_color="#888888")
        self.spelling_check_button.grid(row=0, column=1, padx=5)
        if self.global_config.getboolean('Settings', 'enable_spelling_check', fallback=True):
            self.spelling_check_button.configure(text="Toggle Spelling Check", text_color="#80ff80")
        '''

        self.obs_filter_button = ctk.CTkButton(self.button_frame, text="Toggle OBS Chat Filter", text_color="#d1d1d1", font=("Consolas", 14, "bold"), command=self.toggle_obs_filter, width=220, border_width=0, border_color="#888888")
        self.obs_filter_button.grid(row=0, column=2, padx=5)
        if self.global_config.getboolean('Settings', 'obs_chat_filtered', fallback=True):
            self.obs_filter_button.configure(text="Toggle OBS Chat Filter", text_color="#80ff80")

        self.test_button = ctk.CTkButton(self.button_frame, text="Test TTS", text_color="#d1d1d1", font=("Consolas", 14, "bold"), width=220, border_width=0, border_color="#888888")
        self.test_button.grid(row=0, column=3, padx=5)

        # pygame audio device output pulldown selection button / no label
        audio_devices = get_audio_device_names(False)
        self.audio_device_menu = ctk.CTkOptionMenu(self.button_frame, values=audio_devices, width=220, dynamic_resizing=False, font=("Consolas", 14, "bold"))
        self.audio_device_menu.set("Select Playback Device")
        self.audio_device_menu.grid(row=0, column=4, padx=5)

        # Configure column weights for the main frame
        self.main_frame.columnconfigure(0, weight=1)  # Labels take 30%
        self.main_frame.columnconfigure(1, weight=9)  # Entries take 70%

        # Volume slider
        tmpvalue = int(self.global_config.get('Settings', 'volume', fallback=75))
        self.volume_label = ctk.CTkLabel(self.main_frame, text="Output volume: " + str(tmpvalue), font=("Consolas", 12, "bold"))
        self.volume_label.grid(row=2, column=0, sticky="w")

        self.volume_slider = ctk.CTkSlider(self.main_frame, from_=0, to=100, command=self.change_volume)
        self.volume_slider.set(int(self.global_config.get('Settings', 'volume', fallback=75)))
        self.volume_slider.grid(row=2, column=1, sticky="ew", pady=(6, 6))

        # Chat position slider
        log_file = self.global_config.get('Settings', 'log_file_path', fallback="")
        if os.path.exists(log_file):
            size = os.path.getsize(log_file)
        else: size = 0

        self.chat_position_label = ctk.CTkLabel(self.main_frame, text="Position in Chat Log File: 0.0%", font=("Consolas", 12, "bold"))
        self.chat_position_label.grid(row=5, column=0, sticky="w")

        self.chat_slider = ctk.CTkSlider(self.main_frame, from_=0, to=1000)
        self.chat_slider.set(0)
        self.chat_slider.grid(row=5, column=1, sticky="ew", pady=(6, 6))

        # Minimumm Characters to send to TTS
        tmpvalue = int(self.global_config.get('Settings', 'min_char', fallback=2))
        self.characters_label = ctk.CTkLabel(self.main_frame, text="Minimum Characters To Speak: " + str(tmpvalue), font=("Consolas", 12, "bold"))
        self.characters_label.grid(row=3, column=0, sticky="w")

        self.characters_slider = ctk.CTkSlider(self.main_frame, from_=0, to=1023)
        self.characters_slider.set(tmpvalue)
        self.characters_slider.grid(row=3, column=1, sticky="ew", pady=(6, 6))

        # Log file path input
        self.log_file_path_label = ctk.CTkLabel(self.main_frame, text="Secondlife Chat Log File and Path:", font=("Consolas", 12, "bold"))
        self.log_file_path_label.grid(row=4, column=0, sticky="w")

        self.log_file_path_input = ctk.CTkEntry(self.main_frame, border_width=0)
        self.log_file_path_input.insert(0, self.global_config.get('Settings', 'log_file_path', fallback=""))
        self.log_file_path_input.grid(row=4, column=1, sticky="ew", pady=(6, 6))

        # Edge TTS Voice input
        self.edge_voice_label = ctk.CTkLabel(self.main_frame, text="Edge TTS Voice LLM (M,F):", font=("Consolas", 12, "bold"))
        self.edge_voice_label.grid(row=6, column=0, sticky="w")

        self.edge_voice_input = ctk.CTkEntry(self.main_frame, border_width=0)
        self.edge_voice_input.insert(0, self.global_config.get('Settings', 'edge_tts_llm', fallback=""))
        self.edge_voice_input.grid(row=6, column=1, sticky="ew", pady=(0, 6))

        # IgnoreList management
        self.ignore_list_label = ctk.CTkLabel(self.main_frame, text="Ignore Object, Avatar List\n(comma-separated):", font=("Consolas", 12, "bold"))
        self.ignore_list_label.grid(row=7, column=0, sticky="nw")

        self.ignore_list_input = ctk.CTkTextbox(self.main_frame, height=50, wrap="word")
        self.ignore_list_input.insert("1.0", self.global_config.get('Settings', 'ignore_list', fallback=""))
        self.ignore_list_input.grid(row=7, column=1, sticky="ew", pady=(0, 6))

        # Names allowed to speak list management
        self.onlytalk_list_label = ctk.CTkLabel(self.main_frame, text="Only allowed to talk List\n(comma-separated):", font=("Consolas", 12, "bold"))
        self.onlytalk_list_label.grid(row=8, column=0, sticky="nw")

        self.onlytalk_list_input = ctk.CTkTextbox(self.main_frame, height=50, wrap="word")
        self.onlytalk_list_input.insert("1.0", self.global_config.get('Settings', 'speak_only_list', fallback=""))
        self.onlytalk_list_input.grid(row=8, column=1, sticky="ew", pady=(0, 6))

        # Bottom action buttons on one row
        self.bottom_actions_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.bottom_actions_frame.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(2, 15), padx=(3, 3))
        self.bottom_actions_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Save Config button
        self.save_config_button = ctk.CTkButton(self.bottom_actions_frame, text="Save Config", font=("Consolas", 14, "bold"), command=self.save_config, width=220, border_width=0, border_color="#888888")
        self.save_config_button.grid(row=0, column=0, padx=(0, 4), sticky="w")

        # Name to voice editor button
        self.name_sex_button = ctk.CTkButton(self.bottom_actions_frame, text="Name Sex", font=("Consolas", 14, "bold"), width=220, border_width=0, border_color="#888888", command=self.open_name2voice_editor)
        self.name_sex_button.grid(row=0, column=1, padx=4, sticky="ew")

        # Slang replacement editor button
        self.slang_edit_button = ctk.CTkButton(self.bottom_actions_frame, text="Slang Edit", font=("Consolas", 14, "bold"), width=220, border_width=0, border_color="#888888", command=self.open_slang_editor)
        self.slang_edit_button.grid(row=0, column=2, padx=4, sticky="ew")

        # Update Ignore List button
        self.update_ignore_list_button = ctk.CTkButton(self.bottom_actions_frame, text="Update Ignore List", font=("Consolas", 14, "bold"), command=self.update_ignore_list, width=220, border_width=0, border_color="#888888")
        self.update_ignore_list_button.grid(row=0, column=3, padx=(4, 0), sticky="e")
        
        # Record button
        self.record_button = ctk.CTkButton(self.button_frame, text="Record Audio", font=("Consolas", 14, "bold"), width=220, border_width=0, border_color="#888888")
        self.record_button.grid(row=1, column=1, columnspan=1, sticky="nw", pady=(5, 0), padx=(5, 0))

        # Replay button
        self.replay_button = ctk.CTkButton(self.button_frame, text="Replay Chat", font=("Consolas", 14, "bold"), width=220, border_width=0, border_color="#888888")
        self.replay_button.grid(row=1, column=2, columnspan=1, sticky="nw", pady=(5, 0), padx=(5, 0))

        # Quick play button
        self.quick_button = ctk.CTkButton(self.button_frame, text="Set Quick Play", font=("Consolas", 14, "bold"), width=220, border_width=0, border_color="#888888", state=ctk.DISABLED)
        self.quick_button.grid(row=1, column=3, columnspan=1, sticky="nw", pady=(5, 0), padx=(5, 0))

        # Open log file button
        self.open_button = ctk.CTkButton(self.button_frame, text="Open File", font=("Consolas", 14, "bold"), width=220, border_width=0, border_color="#888888")
        self.open_button.grid(row=1, column=4, sticky="nw", pady=(5, 0), padx=(5, 0))

        # Pause button
        self.pause_button = ctk.CTkButton(self.button_frame, text="\u23f8", font=("Consolas", 14, "bold"), width=20, border_width=0, border_color="#888888")
        self.pause_button.grid(row=1, column=0, columnspan=1, sticky="nw", pady=(5, 0), padx=(5,0))

    def toggle_spelling_check(self):
        current_value = self.global_config.getboolean('Settings', 'enable_spelling_check', fallback=True)
        new_value = not current_value
        self.global_config.set('Settings', 'enable_spelling_check', str(new_value))

    def toggle_obs_filter(self):
        current_value = self.global_config.getboolean('Settings', 'obs_chat_filtered', fallback=True)
        new_value = not current_value
        self.global_config.set('Settings', 'obs_chat_filtered', str(new_value))

    def update_display(self, message):
        self.text_display.configure(state="normal")
        self.text_display.insert("end", f"[{time.strftime('%H:%M:%S', time.localtime())}] ", "T")
        if 'IGNORED! ' in message:
            message = message.replace("IGNORED! ", "")
            self.text_display.insert("end", message + "\n", "R")
        elif 'TIMECODE! ' in message:
            message = message.replace("TIMECODE! ", "")
            self.text_display.insert("end", message + "\n", "B")
        elif 'NOTICE! ' in message:
            message = message.replace("NOTICE! ", "")
            self.text_display.insert("end", message + "\n", "A")
        elif 'VERBOSE! ' in message:
            message = message.replace("VERBOSE! ", "")
            self.text_display.insert("end", message + "\n", "G")
        else:
            self.text_display.insert("end", message + "\n")
        self.text_display.configure(state="disabled")
        self.text_display.see("end")

    def change_volume(self, value):
        self.global_config.set('Settings', 'volume', str(int(float(value))))

    def update_ignore_list(self):
        input_text = self.ignore_list_input.get("1.0", "end-1c").strip().lower()
        self.global_config.set('Settings', 'ignore_list', input_text)
        input_text = self.onlytalk_list_input.get("1.0", "end-1c").strip().lower()
        self.global_config.set('Settings', 'speak_only_list', input_text)

    def set_name2voice_change_callback(self, callback):
        self.name2voice_change_callback = callback

    def set_slang_change_callback(self, callback):
        self.slang_change_callback = callback

    def open_name2voice_editor(self):
        if self.name2voice_editor_window is not None and self.name2voice_editor_window.winfo_exists():
            self.name2voice_editor_window.lift()
            self.name2voice_editor_window.focus_force()
            return

        self.name2voice_editor_window = ctk.CTkToplevel(self)
        self.name2voice_editor_window.title("Name to Voice Mapping")
        self.name2voice_editor_window.geometry("920x640")
        self.name2voice_editor_window.transient(self)
        self.name2voice_editor_window.grab_set()
        self.name2voice_editor_window.protocol("WM_DELETE_WINDOW", self._close_name2voice_editor)

        outer = ctk.CTkFrame(self.name2voice_editor_window, corner_radius=10)
        outer.pack(fill="both", expand=True, padx=10, pady=10)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(2, weight=1)

        title_label = ctk.CTkLabel(outer, text="Name / Voice Mapping", font=("Consolas", 18, "bold"))
        title_label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 6))

        header_frame = ctk.CTkFrame(outer, fg_color="transparent")
        header_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        header_frame.grid_columnconfigure(0, weight=3)
        header_frame.grid_columnconfigure(1, weight=4)
        ctk.CTkLabel(header_frame, text="Name", font=("Consolas", 13, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header_frame, text="TTS Voice", font=("Consolas", 13, "bold")).grid(row=0, column=1, sticky="w")

        self.name2voice_rows = []
        self.name2voice_rows_frame = ctk.CTkScrollableFrame(outer, corner_radius=8)
        self.name2voice_rows_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.name2voice_rows_frame.grid_columnconfigure(0, weight=1)

        controls_frame = ctk.CTkFrame(outer, fg_color="transparent")
        controls_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(4, 10))

        add_button = ctk.CTkButton(controls_frame, text="Add Row", width=160, command=lambda: self._add_name2voice_row("", ""))
        add_button.pack(side="left", padx=(0, 6))

        cancel_button = ctk.CTkButton(controls_frame, text="Cancel", width=160, fg_color="#5e5e5e", hover_color="#4e4e4e", command=self._close_name2voice_editor)
        cancel_button.pack(side="right", padx=(6, 0))

        save_button = ctk.CTkButton(controls_frame, text="Save", width=160, command=self._save_name2voice_editor)
        save_button.pack(side="right", padx=(6, 0))

        rows = self._load_name2voice_rows()
        if not rows:
            rows = [("", "")]

        for name, voice in rows:
            self._add_name2voice_row(name, voice)

    def _load_name2voice_rows(self):
        if not os.path.exists(self.name2voice_file):
            return []

        try:
            with open(self.name2voice_file, "r", encoding="utf-8-sig") as file:
                data = json.load(file)
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Cannot read {self.name2voice_file}:\n{e}")
            return []
        except OSError as e:
            messagebox.showerror("File Error", f"Cannot read {self.name2voice_file}:\n{e}")
            return []

        if isinstance(data, dict):
            return list(data.items())

        messagebox.showwarning("Unexpected Format", f"{self.name2voice_file} should contain a JSON object mapping names to voices.")
        return []

    def _add_name2voice_row(self, name="", voice=""):
        row_frame = ctk.CTkFrame(self.name2voice_rows_frame, fg_color="transparent")
        row_frame.grid_columnconfigure(0, weight=3)
        row_frame.grid_columnconfigure(1, weight=4)

        name_entry = ctk.CTkEntry(row_frame, border_width=0)
        name_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=3)
        name_entry.insert(0, str(name))

        voice_entry = ctk.CTkEntry(row_frame, border_width=0)
        voice_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=3)
        voice_entry.insert(0, str(voice))

        remove_button = ctk.CTkButton(row_frame, text="Remove", width=90, fg_color="#9c4f4f", hover_color="#874343", command=lambda f=row_frame: self._remove_name2voice_row(f))
        remove_button.grid(row=0, column=2, sticky="e", pady=3)

        self.name2voice_rows.append({
            "frame": row_frame,
            "name_entry": name_entry,
            "voice_entry": voice_entry,
        })
        self._refresh_name2voice_row_positions()

    def _remove_name2voice_row(self, row_frame):
        if len(self.name2voice_rows) == 1:
            only_row = self.name2voice_rows[0]
            only_row["name_entry"].delete(0, "end")
            only_row["voice_entry"].delete(0, "end")
            return

        self.name2voice_rows = [row for row in self.name2voice_rows if row["frame"] != row_frame]
        row_frame.destroy()
        self._refresh_name2voice_row_positions()

    def _refresh_name2voice_row_positions(self):
        for index, row in enumerate(self.name2voice_rows):
            row["frame"].grid(row=index, column=0, sticky="ew", pady=(0, 4), padx=4)

    def _save_name2voice_editor(self):
        mapping = {}
        seen_names = set()

        for row in self.name2voice_rows:
            name = row["name_entry"].get().strip()
            voice = row["voice_entry"].get().strip()

            if not name and not voice:
                continue
            if not name or not voice:
                messagebox.showwarning("Missing Value", "Each row must include both a name and a voice.")
                return

            key = name.casefold()
            if key in seen_names:
                messagebox.showwarning("Duplicate Name", f"Duplicate name found: {name}")
                return

            seen_names.add(key)
            mapping[name] = voice

        try:
            with open(self.name2voice_file, "w", encoding="utf-8") as file:
                json.dump(mapping, file, indent=2, ensure_ascii=False)
        except OSError as e:
            messagebox.showerror("Save Failed", f"Could not write {self.name2voice_file}:\n{e}")
            return

        if callable(self.name2voice_change_callback):
            try:
                self.name2voice_change_callback()
            except Exception as e:
                self.update_display(f"NOTICE! Mapping saved, but reload failed: {e}")

        self.update_display(f"NOTICE! Saved {len(mapping)} entries to {self.name2voice_file}.")
        self._close_name2voice_editor()

    def _close_name2voice_editor(self):
        if self.name2voice_editor_window is not None and self.name2voice_editor_window.winfo_exists():
            self.name2voice_editor_window.grab_release()
            self.name2voice_editor_window.destroy()
        self.name2voice_editor_window = None
        self.name2voice_rows = []

    def open_slang_editor(self):
        if self.slang_editor_window is not None and self.slang_editor_window.winfo_exists():
            self.slang_editor_window.lift()
            self.slang_editor_window.focus_force()
            return

        self.slang_editor_window = ctk.CTkToplevel(self)
        self.slang_editor_window.title("Slang Replacement Mapping")
        self.slang_editor_window.geometry("920x640")
        self.slang_editor_window.transient(self)
        self.slang_editor_window.grab_set()
        self.slang_editor_window.protocol("WM_DELETE_WINDOW", self._close_slang_editor)

        outer = ctk.CTkFrame(self.slang_editor_window, corner_radius=10)
        outer.pack(fill="both", expand=True, padx=10, pady=10)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(2, weight=1)

        title_label = ctk.CTkLabel(outer, text="Slang / Replacement Mapping", font=("Consolas", 18, "bold"))
        title_label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 6))

        header_frame = ctk.CTkFrame(outer, fg_color="transparent")
        header_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        header_frame.grid_columnconfigure(0, weight=3)
        header_frame.grid_columnconfigure(1, weight=4)
        ctk.CTkLabel(header_frame, text="Word", font=("Consolas", 13, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header_frame, text="Replacement", font=("Consolas", 13, "bold")).grid(row=0, column=1, sticky="w")

        self.slang_rows = []
        self.slang_rows_frame = ctk.CTkScrollableFrame(outer, corner_radius=8)
        self.slang_rows_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.slang_rows_frame.grid_columnconfigure(0, weight=1)

        controls_frame = ctk.CTkFrame(outer, fg_color="transparent")
        controls_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(4, 10))

        add_button = ctk.CTkButton(controls_frame, text="Add Row", width=160, command=lambda: self._add_slang_row("", ""))
        add_button.pack(side="left", padx=(0, 6))

        cancel_button = ctk.CTkButton(controls_frame, text="Cancel", width=160, fg_color="#5e5e5e", hover_color="#4e4e4e", command=self._close_slang_editor)
        cancel_button.pack(side="right", padx=(6, 0))

        save_button = ctk.CTkButton(controls_frame, text="Save", width=160, command=self._save_slang_editor)
        save_button.pack(side="right", padx=(6, 0))

        rows = self._load_slang_rows()
        if not rows:
            rows = [("", "")]

        for word, replacement in rows:
            self._add_slang_row(word, replacement)

    def _load_slang_rows(self):
        if not os.path.exists(self.slang_file):
            return []

        try:
            with open(self.slang_file, "r", encoding="utf-8-sig") as file:
                data = json.load(file)
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Cannot read {self.slang_file}:\n{e}")
            return []
        except OSError as e:
            messagebox.showerror("File Error", f"Cannot read {self.slang_file}:\n{e}")
            return []

        if isinstance(data, dict):
            return list(data.items())

        messagebox.showwarning("Unexpected Format", f"{self.slang_file} should contain a JSON object mapping words to replacements.")
        return []

    def _add_slang_row(self, word="", replacement=""):
        row_frame = ctk.CTkFrame(self.slang_rows_frame, fg_color="transparent")
        row_frame.grid_columnconfigure(0, weight=3)
        row_frame.grid_columnconfigure(1, weight=4)

        word_entry = ctk.CTkEntry(row_frame, border_width=0)
        word_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=3)
        word_entry.insert(0, str(word))

        replacement_entry = ctk.CTkEntry(row_frame, border_width=0)
        replacement_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=3)
        replacement_entry.insert(0, str(replacement))

        remove_button = ctk.CTkButton(row_frame, text="Remove", width=90, fg_color="#9c4f4f", hover_color="#874343", command=lambda f=row_frame: self._remove_slang_row(f))
        remove_button.grid(row=0, column=2, sticky="e", pady=3)

        self.slang_rows.append({
            "frame": row_frame,
            "word_entry": word_entry,
            "replacement_entry": replacement_entry,
        })
        self._refresh_slang_row_positions()

    def _remove_slang_row(self, row_frame):
        if len(self.slang_rows) == 1:
            only_row = self.slang_rows[0]
            only_row["word_entry"].delete(0, "end")
            only_row["replacement_entry"].delete(0, "end")
            return

        self.slang_rows = [row for row in self.slang_rows if row["frame"] != row_frame]
        row_frame.destroy()
        self._refresh_slang_row_positions()

    def _refresh_slang_row_positions(self):
        for index, row in enumerate(self.slang_rows):
            row["frame"].grid(row=index, column=0, sticky="ew", pady=(0, 4), padx=4)

    def _save_slang_editor(self):
        mapping = {}
        seen_words = set()

        for row in self.slang_rows:
            word = row["word_entry"].get().strip()
            replacement = row["replacement_entry"].get().strip()

            if not word and not replacement:
                continue
            if not word or not replacement:
                messagebox.showwarning("Missing Value", "Each row must include both a word and its replacement.")
                return

            key = word.casefold()
            if key in seen_words:
                messagebox.showwarning("Duplicate Word", f"Duplicate word found: {word}")
                return

            seen_words.add(key)
            mapping[word] = replacement

        try:
            with open(self.slang_file, "w", encoding="utf-8") as file:
                json.dump(mapping, file, indent=2, ensure_ascii=False)
        except OSError as e:
            messagebox.showerror("Save Failed", f"Could not write {self.slang_file}:\n{e}")
            return

        if callable(self.slang_change_callback):
            try:
                self.slang_change_callback()
            except Exception as e:
                self.update_display(f"NOTICE! Slang file saved, but reload failed: {e}")

        self.update_display(f"NOTICE! Saved {len(mapping)} entries to {self.slang_file}.")
        self._close_slang_editor()

    def _close_slang_editor(self):
        if self.slang_editor_window is not None and self.slang_editor_window.winfo_exists():
            self.slang_editor_window.grab_release()
            self.slang_editor_window.destroy()
        self.slang_editor_window = None
        self.slang_rows = []

    def save_config(self):
        defaults = {
            'log_file_path': '',
            'enable_spelling_check': 'False',
            'ignore_list': '',
            'obs_chat_filtered': 'True',
            'edge_tts_llm': 'en-US-EmmaMultilingualNeural',
            'volume': '75',
            'window_geometry': '1024x768',
            'min_char': '2',
            'speak_only_list': '',
            'concurrent_edge_tts_threads': '3',
            'replay_chat': '0',
            'follow_timestamps': '1',
            'record': '0',
            'verbose': '0',
        }
        current_values = {
            'log_file_path': self.log_file_path_input.get(),
            'edge_tts_llm': self.edge_voice_input.get(),
            'window_geometry': self.geometry(),
            'volume': str(int(self.volume_slider.get())),
            'ignore_list': self.ignore_list_input.get("1.0", "end-1c").strip().lower(),
            'speak_only_list': self.onlytalk_list_input.get("1.0", "end-1c").strip().lower(),
            'min_char': str(int(self.characters_slider.get())),
            'obs_chat_filtered': str(self.global_config.getboolean('Settings', 'obs_chat_filtered', fallback=True)),
            'enable_spelling_check': str(self.global_config.getboolean('Settings', 'enable_spelling_check', fallback=False)),
        }
        self.global_config = merge_config_settings(self.global_config, current_values, defaults)
        
        with open("config.ini", 'w') as config_file:
            self.global_config.write(config_file)
        self.update_display("Configuration saved.")

    def on_close(self):
        self.save_config()
        self.destroy()

    def start_busy(self):
        self.busy_ref_count = getattr(self, 'busy_ref_count', 0) + 1
        if self.busy_ref_count == 1:
            self.is_busy = True
            self.busy_index = 0
            self.busy_animation_id = self.after(100, self.update_busy_indicator)
            self.status_indicator.configure(text=self.busy_chars[0])

    def stop_busy(self):
        self.busy_ref_count = max(0, getattr(self, 'busy_ref_count', 1) - 1)
        if self.busy_ref_count == 0:
            self.is_busy = False
            if self.busy_animation_id is not None:
                self.after_cancel(self.busy_animation_id)
                self.busy_animation_id = None
            self.status_indicator.configure(text=self.busy_chars[0])

    def update_busy_indicator(self):
        if self.is_busy:
            self.busy_index = (self.busy_index + 1) % len(self.busy_chars)
            busy_indicator = self.busy_chars[self.busy_index]
            self.status_indicator.configure(text=busy_indicator)
            self.busy_animation_id = self.after(100, self.update_busy_indicator)

def main(global_config):
    app = MainWindow(global_config)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    # app.mainloop()

if __name__ == "__main__":
    global_config = ConfigParser()
    global_config.read("config.ini")
    main(global_config)