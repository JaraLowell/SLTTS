#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Needs > pip install edge-tts language_tool_python asyncio regex pygame
import sys
import os
# Set QT_PLUGIN_PATH if running as a PyInstaller executable
if getattr(sys, 'frozen', False):  # Check if running as a PyInstaller executable
    qt_plugin_path = os.path.join(sys._MEIPASS, 'PyQt5', 'Qt', 'plugins')
    os.environ['QT_PLUGIN_PATH'] = qt_plugin_path

import asyncio
import time
import pygame
import regex as re
from edge_tts import Communicate
from edge_tts import list_voices
import gc
import unicodedata
from configparser import ConfigParser
from aiohttp import web
from datetime import datetime
import html
import json
from PyQt5.QtWidgets import QApplication
from PyQt5 import QtCore
from SLTTSUI import MainWindow
import threading
import builtins

import emoji
"""
PyInstaller Packaging Issue:
If the script is packaged into an executable using a tool like PyInstaller, the emoji.json file might not be included in the bundled application. PyInstaller does not automatically include all data files from third-party libraries unless explicitly specified in the .spec file or via configuration.
To ensure that the emoji.json file is included, you can modify the PyInstaller .spec file to include the emoji.json file as a data file. Here's an example of how to do this:

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files('emoji')  # Collect all data files from the emoji library

a = Analysis(
    ...
    datas=datas,  # Add the collected data files
    ...
)
"""

# Initialize pygame mixer globally
pygame.mixer.init()
pygame.mixer.music.set_volume(0.75)  # Set volume to 50%

# Flag to indicate whether audio is currently playing
is_playing = False
last_message = None
last_user = None
last_chat = 0
tool = None
readloop = False

def clean_name(name):
    # Lets check if only one language is used in the name
    # This is a very simple check, but it works for most cases
    script_names = set()
    for char in name:
        try:
            script_name = unicodedata.name(char)
        except ValueError:
            script_name = "Unknown" # Handle characters without a name
            continue

        if "WITH" in script_name:
            # Seriously ! ŦorestŞheŨrt is Latin ... but with stroke F, cedilla S and tilde U
            script_name = script_name.split()[0] + 'Extended'
        elif "DIGIT" in script_name:
            # We do want to keep numbers as LATIN, or thay get aded as DIGIT
            script_name = 'LATIN'
        else:
            script_name = script_name.split()[0]

        if script_name not in script_names:
            script_names.add(script_name)

    if len(script_names) == 1:
        return True

    return False

def emoji_to_word(emoji_char, _):
    """Convert an emoji to its descriptive word."""
    return emoji.demojize(emoji_char).replace(":", "").replace("_", " ")

def url2word(message):
    # Simplify Second Life map URLs
    message = re.sub(r'http://maps\.secondlife\.com/secondlife/([^/]+)/\d+/\d+/\d+', lambda match: match.group(1).replace('%20', ' '), message)

    # Replace Second Life agent or group links with "Second Life Link"
    message = re.sub(r'secondlife:///app/(agent|group)/[0-9a-fA-F\-]+/(about|displayname)', lambda m: f"[SL {m.group(1).capitalize()} URL]", message)

    # Simplify general URLs to their domain
    message = re.sub(r'(https?://(?:www\.)?([^/\s]+)[^\s]*)', r'\2 link', message)

    return message

def spell_check_message(message):
    global Enable_Spelling_Check, tool, slang_replacements
    if not message:
        return ""  # Return empty string if message is empty

    # Replace emojis with their descriptive words
    message = emoji.replace_emoji(message, replace=emoji_to_word)

    if len(message) == 1:
        return message

    # Remove unwanted characters while preserving letters, punctuation, spaces, digits, and math symbols
    # message = re.sub(r'[^\p{L}\d\s\p{P}+\-*/=<>^|~]', '', message, flags=re.UNICODE)  # Remove unsupported characters

    # Replace L$ with Linden Dollars
    message = re.sub(r"\bL\$", "Linden dollars", message, flags=re.IGNORECASE)

    # Replace hyphen with "minus" or space based on context
    message = re.sub(r'(?<=\d)-(?=\d|\=)', ' minus ', message)
    message = re.sub(r'(?<=\w)-(?=\w)', ' ', message)

    # Replace common abbreviations v3.2 slang replacements
    for slang, replacement in slang_replacements.items():
        message = re.sub(rf'\b{slang}\b', replacement, message, flags=re.IGNORECASE)

    # Perform spelling check if enabled
    if Enable_Spelling_Check:
        if tool is None:  # Check if 'tool' is already initialized
            try:
                import language_tool_python
                tool = language_tool_python.LanguageTool('en-US')
            except ImportError as e:
                print(f"Error importing language_tool_python: {e}")

        exceptions = {"Gor", "Kurrii", "Tal", "Gorean"}
        matches = tool.check(message)
        filtered_matches = [
            match for match in matches
            if not any(exception.lower() in match.context.lower() for exception in exceptions)
        ]
        message = language_tool_python.utils.correct(message, filtered_matches)

        # Ensure exception words are capitalized
        for exception in exceptions:
            message = re.sub(rf'\b{exception.lower()}\b', exception, message, flags=re.IGNORECASE)

    # Remove unwanted characters that should be removed (non-speakable characters)
    forbidden_categories = ["So", "Mn", "Mc", "Me", "C", "Sk"]
    message = "".join(c for c in message if unicodedata.category(c) not in forbidden_categories)

    # Collapse repeated characters (3 or more)
    message = re.sub(r'([^0-9])\1{2,}', r'\1', message)

    if len(message) > 1:
        message = message[0].upper() + message[1:]

    # Replace double spaces with a single space
    message = re.sub(r'\s+', ' ', message).strip()

    return message

def create_default_config(file_path):
    """Create a default config.ini file if it doesn't exist."""
    if not os.path.exists(file_path):
        print(f"Config file not found. Creating default config at {file_path}...")
        config = ConfigParser()
        config['Settings'] = {
            'log_file_path': 'D:\\SecondLife\\Logs\\SLAvatar_Name\\chat.txt',
            'enable_spelling_check': 'False',
            'ignore_list': 'zcs, gm',
            'obs_chat_filtered': 'True',
            'edge_tts_llm': 'en-US-EmmaMultilingualNeural'
        }
        with open(file_path, 'w') as config_file:
            config.write(config_file)
        return True
    return False

async def get_voices(language=None):
    all_voices = await list_voices()
    filtered_voices = [
        {"name": v['ShortName'], "gender": v['Gender'], "language": v['Locale']}
        for v in all_voices if language == 'all' or language is None or v['Locale'] == language
    ]
    return filtered_voices

async def speak_text(text2say):
    """Use Edge TTS to speak the given text."""
    global is_playing, EdgeVoice

    # Wait until the current audio finishes
    while is_playing:
        await asyncio.sleep(0.25)

    is_playing = True  # Indicate audio is playing

    try:
        # Generate and save the audio file
        output_file = "output.mp3"
        try:
            await Communicate(text = text2say, voice=EdgeVoice, rate = '+8%', pitch = '+0Hz').save(output_file)
        except Exception as e:
            print(f"Error generating audio: {e}")
            return

        # Play the audio file
        pygame.mixer.music.load(output_file)
        pygame.mixer.music.play()

        # Wait for playback to finish
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    finally:
        # Clean up and reset the flag
        pygame.mixer.music.unload()
        is_playing = False

# List to store chat messages for the website
chat_messages = []

async def update_chat(message):
    """Update the chat messages for the internal server."""
    global chat_messages

    # Add the new message with a timestamp
    timestamp = datetime.now().strftime('%H:%M:%S')
    chat_messages.append({
        "timestamp": timestamp,
        "message": message,
        "added_time": time.time()  # Track when the message was added
    })


async def sse_handler(request):
    """Handle Server-Sent Events for real-time chat updates."""
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        },
    )
    await response.prepare(request)

    try:
        while True:
            await asyncio.sleep(0.5)  # Check for updates every 0.5 seconds
            # Send only new messages to the client
            if chat_messages:
                new_messages = chat_messages[:]
                messages_html = "".join(
                    f"<div class='chat-line'>{html.escape(msg['message'])}</div>"
                    for msg in new_messages
                )
                try:
                    await response.write(f"data: {messages_html}\n\n".encode('utf-8'))
                    chat_messages.clear()  # Clear the sent messages
                except (ConnectionResetError, asyncio.CancelledError):
                    print("Client disconnected.")
                    break  # Exit the loop if the client disconnects

            # Send a keep-alive message every 5 seconds
            try:
                await response.write(":\n\n".encode('utf-8'))
            except (ConnectionResetError, asyncio.CancelledError):
                print("Client disconnected.")
                break

    except asyncio.CancelledError:
        print("SSE handler task was cancelled.")
    except Exception as e:
        print(f"Error in SSE handler: {e}")
    finally:
        try:
            await response.write_eof()
        except ConnectionResetError:
            pass

    # Close the response stream
    return response

async def chat_page_handler(request):
    """Serve the chat page with SSE integration."""
    filesend = 'chat_template.html'
    try:
        with open("chat_template.html", "r", encoding="utf-8") as file:
            html_content = file.read()
    except (UnicodeDecodeError, FileNotFoundError, PermissionError) as e:
        print(f"Error loading chat_template.html: {e}")
        filesend = 'internal template'
    except Exception as e:
        print(f"Unexpected error loading chat_template.html: {e}")
        filesend = 'internal template'

    if filesend == 'internal template':
        # Fallback to a default template
        html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Live Chat</title>
        <style>
            body {
                font-family: Ubuntu, sans-serif;
                font-size: 19px;
                background-color: rgba(0, 0, 0, 0);
                color: white;
                margin: 0;
                padding: 0;
                overflow: hidden;
                height: 100vh; /* Full viewport height */
                width: 100vw; /* Full viewport width */
            }
            #chat-container {
                display: flex;
                flex-direction: column;
                justify-content: flex-end; /* Align messages at the bottom */
                height: 100%; /* Full height of the body */
                width: 100%; /* Full width of the body */
                padding: 10px;
                box-sizing: border-box;
                overflow: hidden;
            }
            .chat-line {
                animation: fadeout 20s forwards;
                padding-left: 8px; /* Padding inside the box */
                margin-bottom: 2px; /* Space between chat lines */
                color: white; /* Text color */
                display: inline-block; /* Make the box wrap around the text */
                max-width: 100%; /* Optional: Limit the width of the box to 80% of the container */
                word-wrap: break-word; /* Ensure long words or URLs wrap to the next line */
                text-shadow: -1px -1px 0 #00000080, 1px -1px 0 #00000080, -1px 1px 0 #00000080, 1px 1px 0 #00000080, 1px 1px 1px #000000, 0 0 1em #000000, 0 0 0.2em #000000;
                transition: transform 0.5s ease, opacity 0.5s ease;
                -webkit-filter: grayscale(100%);
                filter: grayscale(100%);
            }
            @keyframes fadeout {
                0% { opacity: 1; } /* Fully visible */
                66.67% { opacity: 1; } /* Remain fully visible for 10 seconds (2/3 of 15 seconds) */
                100% { opacity: 0; } /* Fade out over the last 5 seconds */
            }
        </style>
    </head>
    <body>
        <div id="chat-container"></div>
            <script>
                const chatContainer = document.getElementById('chat-container');
                const eventSource = new EventSource('/sse');
                eventSource.onmessage = function(event) {
                    const newMessages = document.createElement('div');
                    newMessages.innerHTML = event.data;
                    Array.from(newMessages.children).forEach(child => {
                        const messageLength = child.textContent.length;
                        const fadeoutDuration = Math.min(60, Math.max(15, messageLength / 9));
                        child.style.animation = `fadeout ${fadeoutDuration}s forwards`;
                        child.addEventListener('animationend', () => {
                            chatContainer.removeChild(child);
                        });
                        chatContainer.appendChild(child);
                        if (chatContainer.children.length > 20) {
                            chatContainer.removeChild(chatContainer.firstChild);
                        }
                    });
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                };
                eventSource.onerror = function() {
                    console.error("SSE connection lost. Attempting to reconnect...");
                };
            </script>
    </body>
    </html>
    """
    print(f"Serving {filesend} to {request.remote}")
    return web.Response(text=html_content, content_type='text/html')

async def start_server():
    """Start the internal web server."""
    app = web.Application()
    app.router.add_get('/', chat_page_handler)  # Serve the chat page
    app.router.add_get('/sse', sse_handler)  # Serve the SSE endpoint
    runner = web.AppRunner(app)
    await runner.setup()
    port = 8080
    while True:
        try:
            site = web.TCPSite(runner, 'localhost', port)
            await site.start()
            print(f"OBS Page service started on http://localhost:{port} Use this URL in OBS via a browser source.")
            break
        except OSError as e:
            if e.errno == 98 or e.errno == 10048:  # Port already in use
                print(f"Port {port} is already in use. Trying port {port + 10}...")
                port += 10
            else:
                print(f"Error starting server: {e}")
                raise

# Modify the monitor_log function to call update_chat
async def monitor_log(log_file):
    await speak_text("Starting up! Monitoring log file...")
    global last_message, last_user, IgnoreList, last_chat, OBSChatFiltered, readloop

    # Start at the end of the file
    last_position = 0
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as file:
            file.seek(0, os.SEEK_END)
            last_position = file.tell()
    else:
        print(f"Log file not found: {log_file}")
        return

    last_mod_time = os.path.getmtime(log_file)
    last_gc_time = time.time()
    name_cache = {}

    try:
        while readloop:
            current_time = time.time()
            current_mod_time = os.path.getmtime(log_file)

            # Perform garbage collection every 5 minutes
            if current_time - last_gc_time >= 300:
                gc.collect()
                last_gc_time = current_time

            # Check if the file has been modified
            if current_mod_time != last_mod_time:
                last_mod_time = current_mod_time

                # Reopen the file to ensure we get the latest data
                try:
                    with open(log_file, 'r', encoding='utf-8') as file:
                        file.seek(last_position)  # Seek to the last known position
                        new_lines = file.readlines()
                        last_position = file.tell()  # Update the last position after reading

                        for line in new_lines:
                            line = line.strip()
                            if line:
                                # Process the line (existing logic)
                                try:
                                    if line.startswith("[20"):
                                        isemote = False
                                        isrepat = False
                                        # Extract timestamp and message
                                        timestamp, rest = line.split(']', 1)
                                        speaker_part, message = rest.split(':', 1)
                                        speaker_part = speaker_part.strip()
                                        message = url2word(message).strip()
                                        messageorg = message

                                        first_name = None
                                        ignore_match = False
                                        if speaker_part not in name_cache:
                                            for ignore_item in IgnoreList:
                                                if ignore_item.endswith('*'):
                                                    if speaker_part.lower().startswith(ignore_item[:-1].lower()):
                                                        ignore_match = True
                                                        break
                                                elif speaker_part.lower() == ignore_item.lower():
                                                    ignore_match = True
                                                    break

                                        # Handle IgnoreList and speaker name extraction
                                        if speaker_part in name_cache:
                                            first_name = name_cache[speaker_part]
                                        elif not ignore_match:
                                            if '(' in speaker_part and ')' in speaker_part:
                                                speaker = speaker_part.split('(')[1].split(')')[0].strip()
                                                first_name = speaker.split('.')[0].capitalize()
                                                speaker = speaker_part.split('(')[0].strip()
                                            else:
                                                speaker = speaker_part

                                            if speaker == 'Second Life':
                                                first_name = None
                                            elif " " in speaker:
                                                tmp = speaker.split(' ')
                                                salutations = {"lady", "lord", "sir", "miss", "ms", "mr", "mrs", "dr", "prof"}
                                                if all(part.isalnum() for part in tmp):
                                                    if tmp[0].lower() in salutations and len(tmp) > 1:
                                                        if clean_name(tmp[1]):
                                                            first_name = tmp[1].capitalize()
                                                    elif clean_name(tmp[0]):
                                                        first_name = tmp[0].capitalize()
                                            elif speaker.isalnum():
                                                if clean_name(speaker):
                                                    first_name = speaker.capitalize()

                                            if first_name:
                                                first_name = re.sub(r'(?<!\p{L})\d+$', '', first_name)
                                                name_cache[speaker_part] = first_name

                                        # Process the message
                                        if first_name:
                                            if last_user != first_name:
                                                last_user = first_name
                                                isrepat = False
                                            elif time.time() - last_chat >= 120:
                                                isrepat = False
                                            else:
                                                isrepat = True
                                            if message.startswith("/me"):
                                                message = message[3:].strip()
                                                messageorg = messageorg[3:].strip()
                                                isemote = True
                                                isrepat = False
                                            if message.startswith("shouts: "):
                                                message = message[8:].strip()
                                                messageorg = messageorg[8:].strip()
                                            if message.startswith("whispers: "):
                                                message = message[10:].strip()
                                                messageorg = messageorg[10:].strip()

                                            message = spell_check_message(message)

                                            if last_message == message:
                                                message = ''

                                            if message:
                                                last_message = message
                                                if isrepat:
                                                    to_speak = f"{message}"
                                                    to_cc = f"{first_name}: {message}" if OBSChatFiltered else f"{first_name}: {messageorg}"
                                                    print(f"           {message}")
                                                elif isemote:
                                                    to_speak = f"{first_name} {message}"
                                                    to_cc = f"{first_name} {message}" if OBSChatFiltered else f"{first_name} {messageorg}"
                                                    print(f"[{time.strftime('%H:%M:%S', time.localtime())}] {to_speak}")
                                                else:
                                                    to_speak = f"{first_name} says: {message}"
                                                    to_cc = f"{first_name}: {message}" if OBSChatFiltered else f"{first_name}: {messageorg}"
                                                    print(f"[{time.strftime('%H:%M:%S', time.localtime())}] {to_speak}")

                                                await update_chat(to_cc)
                                                await speak_text(to_speak)
                                                last_chat = time.time()
                                            elif messageorg:
                                                print(f"[{time.strftime('%H:%M:%S', time.localtime())}] IGNORED! {first_name}: {messageorg}")
                                                if not OBSChatFiltered:
                                                    await update_chat(f"{first_name}: {messageorg}")
                                                last_chat = time.time()
                                        else:
                                            last_user = None
                                            print(f"[{time.strftime('%H:%M:%S', time.localtime())}] IGNORED! {speaker_part}: {message}")
                                    elif last_user is not None:
                                        message = line.strip()
                                        message = spell_check_message(message)
                                        if last_message != message and message:
                                            last_message = message
                                            print(f"           {message}")
                                            await update_chat(last_user + ' ' + message)
                                            await speak_text(message)
                                    else:
                                        print(f"[{time.strftime('%H:%M:%S', time.localtime())}] IGNORED! {url2word(line).strip()}")
                                except ValueError:
                                    print(f"[{time.strftime('%H:%M:%S', time.localtime())}] IGNORED! {url2word(line).strip()}")
                            await asyncio.sleep(0.2) # Qt5 update_display might crash if we spam it too fast
                except FileNotFoundError:
                    print(f"Log file not found: {log_file}")
                except IOError as e:
                    print(f"Error reading log file: {e}")

            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error while monitoring log file: {e}")
    finally:
        print("Stopped monitoring log file.")

def update_global(variable_name, value):
    """Update a global variable dynamically."""
    globals()[variable_name] = value
    original_print(f"Updated global {variable_name} to {value}")

def update_volume(value):
    """Update the volume setting."""
    pygame.mixer.music.set_volume(value / 100)

def load_slang_replacements(file_path="slangreplce.json"):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError as e:
                print(f"Error loading slang replacements: {e}")
                return {}
    else:
        print(f"Slang replacements file not found: {file_path}")
        return {}

def run_server_in_background():
    """Run the server as a background daemon."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(start_server())
    threading.Thread(target=loop.run_forever, daemon=True).start()

def start_monitoring(log_file_path):
    """Start the monitor_log task."""
    global monitor_task, monitor_loop

    if monitor_task is not None:
        original_print("Log monitoring is already running.")
        return

    monitor_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(monitor_loop)

    monitor_task = monitor_loop.create_task(monitor_log(log_file_path))
    threading.Thread(target=monitor_loop.run_forever, daemon=True).start()
    print(f"Started monitoring log file: {log_file_path}")

def stop_monitoring():
    """Stop the monitor_log task."""
    global monitor_task, monitor_loop

    if monitor_task is None:
        original_print("Log monitoring is not running.")
        return

    monitor_task.cancel()  # Cancel the task
    monitor_task = None

    if monitor_loop is not None:
        monitor_loop.stop()  # Stop the event loop
        monitor_loop = None

if __name__ == "__main__":
    if create_default_config('config.ini'):
        print("Default config.ini created. Please edit it with your settings.")
        sys.exit(0)

    config = ConfigParser()
    config.read('config.ini')

    # Parse configuration values
    global Enable_Spelling_Check, IgnoreList, OBSChatFiltered, EdgeVoice
    log_file_path = config.get('Settings', 'log_file_path')
    Enable_Spelling_Check = config.getboolean('Settings', 'enable_spelling_check')
    IgnoreList = [item.strip() for item in config.get('Settings', 'ignore_list').split(',')]
    OBSChatFiltered = config.getboolean('Settings', 'obs_chat_filtered')
    EdgeVoice = config.get('Settings', 'edge_tts_llm')
    # all_voices = asyncio.run(get_voices()) # Fetch all voices

    pygame.mixer.music.set_volume(config.getint('Settings', 'volume', fallback=75) / 100) # Set default volume to 75%

    app = QApplication(sys.argv)
    window = MainWindow(config)

    # Connect the UI's start button to start the log monitoring
    loop = None
    tasks = []
    monitor_task = None
    monitor_loop = None

    def start_monitoring_ui():
        """Start monitoring from the UI."""
        global chat_messages, slang_replacements, readloop
        log_file_path = window.log_file_path_input.text()  # Get the log file path from the input field
        if os.path.exists(log_file_path):
            readloop = True
            slang_replacements = load_slang_replacements()
            print(f"Abbreviation file reading done, {len(slang_replacements)} replacements found and loaded.")
            # chat_messages.clear()
            start_monitoring(log_file_path)
            window.start_button.setText("Stop Log Reading")
            window.start_button.setStyleSheet("color: #e67a7f;")
        else:
            print(f"Log file not found: {log_file_path}")

    def stop_monitoring_ui():
        """Stop monitoring from the UI."""
        global chat_messages, readloop
        readloop = False
        stop_monitoring()
        chat_messages.clear()
        window.start_button.setText("Start Log Reading")
        window.start_button.setStyleSheet("color: #9d9d9d;")

    def toggle_monitoring():
        """Toggle monitoring based on the button state."""
        if window.start_button.text() == "Start Log Reading":
            start_monitoring_ui()
        else:
            stop_monitoring_ui()

    # Start the server in the background
    run_server_in_background()

    # Show the UI window
    window.show()

    # Connect the UI buttons to the respective functions
    window.start_button.clicked.connect(toggle_monitoring)
    window.spelling_check_toggled.connect(lambda value: update_global("Enable_Spelling_Check", value))
    window.obs_filter_toggled.connect(lambda value: update_global("OBSChatFiltered", value))
    window.ignore_list_updated.connect(lambda value: update_global("IgnoreList", value))
    window.log_file_path_input.textChanged.connect(lambda value: update_global("log_file_path", value))
    window.EdgeVoice_input.textChanged.connect(lambda value: update_global("EdgeVoice", value))
    window.volume_changed.connect(lambda value: update_volume(value))

    # Override the print function to append to window.text_display
    original_print = print  # Keep a reference to the original print function
    def custom_print(*args, **kwargs):
        message = " ".join(map(str, args))  # Combine all arguments into a single string
        if 'window' in globals() and hasattr(window, 'text_display'):
            window.update_display(html.escape(message))  # Append the message to the text_display widget

        original_print(*args, **kwargs)  # Optionally, call the original print function

    # Replace the built-in print function with the custom one
    builtins.print = custom_print

    print("Second Life Chat log to Speech version 1.46 Beta by Jara Lowell")

    # Start the PyQt5 application event loop
    sys.exit(app.exec_())
