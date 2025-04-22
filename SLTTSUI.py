import os
import sys
import customtkinter as ctk
from tkinter import messagebox
from configparser import ConfigParser

class MainWindow(ctk.CTk):
    def __init__(self, global_config):
        super().__init__()
        self.global_config = global_config  # Use the global configuration object
        self.title("Second Life TTS")
        self.geometry(global_config.get('Settings', 'window_geometry', fallback="1024x768"))
        icon_path = os.path.join(getattr(sys, '_MEIPASS', os.path.abspath('.')), "SLTTS.ico")
        self.iconbitmap(icon_path)
        self.resizable(True, True)

        # Apply dark mode
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Layout
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=2)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Terminal-like display
        self.text_display = ctk.CTkTextbox(self.main_frame, wrap="word", state="disabled", font=("Consolas", 16))
        self.text_display.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        self.text_display.tag_config("R", foreground="#ff8080")
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)

        # Buttons and controls
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.grid(row=1, column=0, columnspan=2, sticky="n", pady=(2, 12))

        self.start_button = ctk.CTkButton(self.button_frame, text="Start Log Reading", text_color="#d1d1d1", font=("Consolas", 14, "bold"), command=self.toggle_log_reading, width=220)
        self.start_button.grid(row=0, column=0, padx=5)

        self.spelling_check_button = ctk.CTkButton(self.button_frame, text="Toggle Spelling Check", text_color="#d1d1d1", font=("Consolas", 14, "bold"), command=self.toggle_spelling_check, width=220)
        self.spelling_check_button.grid(row=0, column=1, padx=5)

        self.obs_filter_button = ctk.CTkButton(self.button_frame, text="Toggle OBS Chat Filter", text_color="#d1d1d1", font=("Consolas", 14, "bold"), command=self.toggle_obs_filter, width=220)
        self.obs_filter_button.grid(row=0, column=2, padx=5)

        self.test_button = ctk.CTkButton(self.button_frame, text="Test TTS", text_color="#d1d1d1", font=("Consolas", 14, "bold"), command=self.toggle_test_reading, width=220)
        self.test_button.grid(row=0, column=3, padx=5)

        # Configure column weights for the main frame
        self.main_frame.columnconfigure(0, weight=1)  # Labels take 30%
        self.main_frame.columnconfigure(1, weight=9)  # Entries take 70%

        # Volume slider
        self.volume_label = ctk.CTkLabel(self.main_frame, text="Output volume:", font=("Consolas", 12, "bold"))
        self.volume_label.grid(row=2, column=0, sticky="w")

        self.volume_slider = ctk.CTkSlider(self.main_frame, from_=0, to=100, command=self.change_volume)
        self.volume_slider.set(int(self.global_config.get('Settings', 'volume', fallback=75)))
        self.volume_slider.grid(row=2, column=1, sticky="ew", pady=(6, 6))

        # Log file path input
        self.log_file_path_label = ctk.CTkLabel(self.main_frame, text="Secondlife Chat Log File and Path:", font=("Consolas", 12, "bold"))
        self.log_file_path_label.grid(row=3, column=0, sticky="w")

        self.log_file_path_input = ctk.CTkEntry(self.main_frame)
        self.log_file_path_input.insert(0, self.global_config.get('Settings', 'log_file_path', fallback=""))
        self.log_file_path_input.grid(row=3, column=1, sticky="ew", pady=(0, 6))

        # Edge TTS Voice input
        self.edge_voice_label = ctk.CTkLabel(self.main_frame, text="Edge TTS Voice LLM:", font=("Consolas", 12, "bold"))
        self.edge_voice_label.grid(row=4, column=0, sticky="w")

        self.edge_voice_input = ctk.CTkEntry(self.main_frame)
        self.edge_voice_input.insert(0, self.global_config.get('Settings', 'edge_tts_llm', fallback=""))
        self.edge_voice_input.grid(row=4, column=1, sticky="ew", pady=(0, 6))

        # IgnoreList management
        self.ignore_list_label = ctk.CTkLabel(self.main_frame, text="Ignore Object, Avatar List (comma-separated):", font=("Consolas", 12, "bold"))
        self.ignore_list_label.grid(row=5, column=0, sticky="w")

        self.ignore_list_input = ctk.CTkEntry(self.main_frame)
        self.ignore_list_input.insert(0, self.global_config.get('Settings', 'ignore_list', fallback=""))
        self.ignore_list_input.grid(row=5, column=1, sticky="ew", pady=(0, 6))

        # Update Ignore List button
        self.update_ignore_list_button = ctk.CTkButton(self.main_frame, text="Update Ignore List", font=("Consolas", 14, "bold"), command=self.update_ignore_list, width=220)
        self.update_ignore_list_button.grid(row=6, column=0, columnspan=2, pady=(20, 10))

        # Save Config button
        self.save_config_button = ctk.CTkButton(self.main_frame, text="Save Config", font=("Consolas", 14, "bold"), command=self.save_config, width=220)
        self.save_config_button.grid(row=7, column=0, columnspan=2, pady=(5, 10))

    def toggle_log_reading(self):
        # Placeholder for log reading toggle logic
        # messagebox.showinfo("Info", "Toggled log reading.")
        print("Log reading toggled.")

    def toggle_test_reading(self):
        # Placeholder for test reading logic
        # messagebox.showinfo("Info", "Test TTS triggered.")
        print("Test TTS triggered.")

    def toggle_spelling_check(self):
        current_value = self.global_config.getboolean('Settings', 'enable_spelling_check', fallback=True)
        new_value = not current_value
        self.global_config.set('Settings', 'enable_spelling_check', str(new_value))
        message = "Grammar tool and spellchecker check enabled." if new_value else "Grammar tool and spellchecker check disabled."
        self.update_display(message)

    def toggle_obs_filter(self):
        current_value = self.global_config.getboolean('Settings', 'obs_chat_filtered', fallback=True)
        new_value = not current_value
        self.global_config.set('Settings', 'obs_chat_filtered', str(new_value))
        status = "enabled" if new_value else "disabled"
        self.update_display(f"Unfiltered or corrected chat to OBS page {status}.")

    def update_display(self, message):
        self.text_display.configure(state="normal")
        if '] IGNORED!' in message:
            message = message.replace("] IGNORED!", "]")
            self.text_display.insert("end", message + "\n", "R")
        else:
            self.text_display.insert("end", message + "\n")
        self.text_display.configure(state="disabled")
        self.text_display.see("end")

    def change_volume(self, value):
        self.global_config.set('Settings', 'volume', str(int(float(value))))
        self.update_display(f"Volume set to {int(float(value))}%")

    def update_ignore_list(self):
        input_text = self.ignore_list_input.get()
        self.global_config.set('Settings', 'ignore_list', input_text)

    def save_config(self):
        self.global_config.set('Settings', 'log_file_path', self.log_file_path_input.get())
        self.global_config.set('Settings', 'edge_tts_llm', self.edge_voice_input.get())
        self.global_config.set('Settings', 'window_geometry', self.geometry())
        with open("config.ini", 'w') as config_file:
            self.global_config.write(config_file)
        self.update_display("Configuration saved.")

    def on_close(self):
        self.save_config()
        self.destroy()

def main(global_config):
    app = MainWindow(global_config)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    # app.mainloop()

if __name__ == "__main__":
    global_config = ConfigParser()
    global_config.read("config.ini")
    main(global_config)