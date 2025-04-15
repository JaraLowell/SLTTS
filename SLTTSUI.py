from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal
import sys
from configparser import ConfigParser

class MainWindow(QtWidgets.QWidget):
    spelling_check_toggled = pyqtSignal(bool)
    obs_filter_toggled = pyqtSignal(bool)
    ignore_list_updated = pyqtSignal(list)
    volume_changed = pyqtSignal(int)

    def __init__(self, global_config):
        super().__init__()
        self.global_config = global_config  # Use the global configuration object
        self.setWindowTitle("Second Life TTS")
        self.setWindowIcon(QtGui.QIcon("icon.png"))
        geometry = self.global_config.get('Settings', 'window_geometry', fallback=None)
        if geometry:
            self.restoreGeometry(QtCore.QByteArray.fromHex(geometry.encode('utf-8')))
        else:
            self.setGeometry(100, 100, 900, 600)

        # Apply dark mode
        self.setStyleSheet("""
            QMainWindow {
                    background-color: #121212;
                    color: #9d9d9d;
                    font-family: Consolas, Courier New, monospace;
            }
            QWidget {
                background-color: #2b2b2b;
                color: #9d9d9d;
                font-family: Fixedsys;
                font-size: 14px;
            }
            QTextEdit, QLineEdit {
                background-color: #1e1e1e;
                color: #dddddd;
                border: 1px solid #3c3c3c;
                font-family: Consolas, Courier New, monospace;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #9d9d9d;
                border: 1px solid #5c5c5c;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QSlider::groove:horizontal {
                background: #3c3c3c;
                height: 4px;
            }
            QSlider::handle:horizontal {
                background: #9d9d9d;
                border: 1px solid #5c5c5c;
                width: 12px;
                margin: -5px 0;
            }
            QTextEdit, QPlainTextEdit {
                background-color: #1e1e1e;
                color: #dddddd;
                border: 1px solid #444444;
                font-family: Consolas, Courier New, monospace;
                line-height: 20px;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background-color: #1e1e1e;
                border: none;
            }
        """)

        # Layout
        self.layout = QtWidgets.QVBoxLayout()
        # Terminal-like display
        self.text_display = QtWidgets.QTextEdit(self)
        self.text_display.setReadOnly(True)
        self.layout.addWidget(self.text_display)

        # Buttons and controls
        self.button_layout = QtWidgets.QHBoxLayout()

        self.start_button = QtWidgets.QPushButton("Start Log Reading", self)
        self.start_button.clicked.connect(self.toggle_log_reading)
        self.button_layout.addWidget(self.start_button)

        self.spelling_check_button = QtWidgets.QPushButton("Toggle Spelling Check", self)
        self.spelling_check_button.clicked.connect(self.toggle_spelling_check)
        self.button_layout.addWidget(self.spelling_check_button)
        if self.global_config.getboolean('Settings', 'enable_spelling_check'):
            self.spelling_check_button.setStyleSheet("color: #00c983;")

        self.obs_filter_button = QtWidgets.QPushButton("Toggle OBS Chat Filter", self)
        self.obs_filter_button.clicked.connect(self.toggle_obs_filter)
        self.button_layout.addWidget(self.obs_filter_button)
        if self.global_config.getboolean('Settings', 'obs_chat_filtered'):
            self.obs_filter_button.setStyleSheet("color: #00c983;")

        self.layout.addLayout(self.button_layout)

        # Volume slider
        self.volume_label = QtWidgets.QLabel("Output volume:", self)
        self.layout.addWidget(self.volume_label)

        self.volume_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.global_config.get('Settings', 'volume', fallback=75)))
        self.volume_slider.valueChanged.connect(self.change_volume)
        self.layout.addWidget(self.volume_slider)

        # Log file path input
        self.log_file_path_label = QtWidgets.QLabel("Secondlife Chat Log File and Path:", self)
        self.layout.addWidget(self.log_file_path_label)

        self.log_file_path_input = QtWidgets.QLineEdit(self)
        self.log_file_path_input.setText(self.global_config.get('Settings', 'log_file_path', fallback=""))
        self.layout.addWidget(self.log_file_path_input)

        # Log file path input
        self.EdgeVoice_label = QtWidgets.QLabel("Edge TTS Voice LLM:", self)
        self.layout.addWidget(self.EdgeVoice_label)

        self.EdgeVoice_input = QtWidgets.QLineEdit(self)
        self.EdgeVoice_input.setText(self.global_config.get('Settings', 'edge_tts_llm', fallback=""))
        self.layout.addWidget(self.EdgeVoice_input)

        # IgnoreList management
        self.ignore_list_label = QtWidgets.QLabel("Ignore Object, Avatar List (comma-separated):", self)
        self.layout.addWidget(self.ignore_list_label)

        self.ignore_list_input = QtWidgets.QLineEdit(self)
        self.ignore_list_input.setText(self.global_config.get('Settings', 'ignore_list', fallback=""))
        self.layout.addWidget(self.ignore_list_input)

        self.update_ignore_list_button = QtWidgets.QPushButton("Update Ignore List", self)
        self.update_ignore_list_button.clicked.connect(self.update_ignore_list)
        self.layout.addWidget(self.update_ignore_list_button)

        # Save Config button
        self.save_config_button = QtWidgets.QPushButton("Save Config", self)
        self.save_config_button.clicked.connect(self.save_config)
        self.layout.addWidget(self.save_config_button)

        self.setLayout(self.layout)

    def toggle_log_reading(self):
        tmp = True
        # self.update_display("Toggled log reading.")

    def toggle_spelling_check(self):
        current_value = self.global_config.getboolean('Settings', 'enable_spelling_check', fallback=True)
        new_value = not current_value
        self.global_config.set('Settings', 'enable_spelling_check', str(new_value))
        if new_value:
            self.spelling_check_button.setStyleSheet("color: #00c983;")
            self.update_display(f"Grammar tool and spellchecker check enabled.")
        else:
            self.spelling_check_button.setStyleSheet("color: #9d9d9d;")
            self.update_display(f"Grammar tool and spellchecker check disabled.")
        self.spelling_check_toggled.emit(new_value)  # Emit signal

    def toggle_obs_filter(self):
        current_value = self.global_config.getboolean('Settings', 'obs_chat_filtered', fallback=True)
        new_value = not current_value
        self.global_config.set('Settings', 'obs_chat_filtered', str(new_value))
        if new_value:
            self.obs_filter_button.setStyleSheet("color: #00c983;")
        else:
            self.obs_filter_button.setStyleSheet("color: #9d9d9d;")
        self.obs_filter_toggled.emit(new_value)  # Emit signal
        status = "enabled" if new_value else "disabled"
        self.update_display(f"Unfiltered or corrected chat to OBS page {status}.")

    def update_display(self, message):
        self.text_display.append(message)
        self.text_display.moveCursor(QtGui.QTextCursor.End)
        self.text_display.ensureCursorVisible()

    def change_volume(self, value):
        self.global_config.set('Settings', 'volume', str(value))
        # pygame.mixer.music.set_volume(value / 100)
        self.volume_changed.emit(value)  # Emit signal

    def update_ignore_list(self):
        input_text = self.ignore_list_input.text()
        ignore_list = [item.strip() for item in input_text.split(',')]
        self.global_config.set('Settings', 'ignore_list', input_text)
        self.ignore_list_updated.emit(ignore_list)  # Emit signal
        self.update_display(f"Ignore List updated: {input_text}")

    def save_config(self):
        # Update the configuration with the current values from the UI
        self.global_config.set('Settings', 'log_file_path', self.log_file_path_input.text())
        self.global_config.set('Settings', 'edge_tts_llm', self.EdgeVoice_input.text())
        self.global_config.set('Settings', 'window_geometry', self.saveGeometry().toHex().data().decode('utf-8'))
        with open("config.ini", 'w') as config_file:
            self.global_config.write(config_file)
        self.update_display("Configuration saved.")
    
    def closeEvent(self, event):
        self.save_config()
        super().closeEvent(event)

def main(global_config):
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(global_config)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    global_config = ConfigParser()
    global_config.read("config.ini")
    main(global_config)