#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Needs > pip install edge-tts language_tool_python asyncio regex pygame unidecode
import sys
import os
import logging
logging.basicConfig(filename='sltts.log', level=logging.DEBUG, format='%(asctime)s : %(message)s', datefmt='%m-%d %H:%M', filemode='w')
logging.error("Startin Up")

import asyncio
import time
import pygame
import regex as re
from edge_tts import Communicate
from edge_tts import list_voices
import unicodedata
from unidecode import unidecode
from configparser import ConfigParser
from aiohttp import web
from datetime import datetime
import html
import json
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
last_voice = None
last_chat = 0
tool = None
readloop = False
play_volume = 0.75  # Default volume
min_char = 2  # Default minimum characters

def ascii_name(name):
    # Remove all non-letter characters except spaces (\d\s- to allow hyphenated names and numbers)
    name = re.sub(r'[^\p{L}\s]', '', name)
    # Transliterate to ASCII
    name = unidecode(name, errors='ignore', replace_str='')
    # Remove extra spaces and capitalize each word
    name = name.strip().title()
    return name

    # ascii_name("**Андрей**")       > 'Andrei'
    # ascii_name(" * * さくら * * ")  > 'Sakura'
    # ascii_name("ms ʟᴀɪᴋᴇɴ")        > 'Ms Laiken'
    # ascii_name("Αλέξανδρος")       > 'Alexandros'

def clean_name(name):
    # Lets check if only one language is used in the name
    # This is a very simple check, but it works for most cases
    name = name.lower()

    script_names = set()
    for char in name:
        try:
            script_name = unicodedata.name(char)
        except ValueError:
            script_name = "Unknown" # Handle characters without a name
            continue

        if "WITH" in script_name or "SMALL CAPITAL" in script_name:
            # Seriously ! ŦorestŞheŨrt is Latin ... but with stroke F, cedilla S and tilde U
            script_name = script_name.split()[0] + ' Extended'
        elif "DIGIT" in script_name:
            # We do want to keep numbers as LATIN, or thay get aded as DIGIT
            script_name = 'LATIN'
        else:
            script_name = script_name.split()[0]

        if script_name not in script_names:
            script_names.add(script_name)

    if len(script_names) == 1: # and "LATIN Extended" not in script_names:
        return True

    return False

def emoji_to_word(emoji_char, _):
    """Convert an emoji to its descriptive word."""
    return emoji.demojize(emoji_char).replace(":", "").replace("_", " ")

def url2word(message):
    # Simplify Second Life map URLs
    message = re.sub(r'http://maps\.secondlife\.com/secondlife/([^/]+)/\d+/\d+/\d+', lambda match: match.group(1).replace('%20', ' '), message)

    # Replace Second Life agent or group links with "Second Life Link"
    message = re.sub(r'secondlife:///app/(agent|group)/[0-9a-fA-F\-]+/(about|displayname|inspect)', lambda m: f"[SL {m.group(1).capitalize()} URL]", message)

    # Simplify general URLs to their domain
    message = re.sub(r'(https?://(?:www\.)?([^/\s]+)[^\s]*)', r'\2 link', message)

    # Replace words longer than 64 characters with "(blank)"
    message = ' '.join(word if len(word) <= 64 else "(blank)" for word in message.split())

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
    message = re.sub(r'(?<=\d)-(?=\d|\=)', ' to ', message) # Dash denotes a sequence from-to if paced directly next to numbers like 30-40 degrees
    message = re.sub(r'(?<=\w)-(?=\w)', '', message) # Hyphen is dropped in-between/inbetween words joining them together for correct grammar.

    # Replace common abbreviations v3.2 slang replacements
    for slang, replacement in slang_replacements.items():
        message = re.sub(rf'\b{slang}\b', replacement, message, flags=re.IGNORECASE)

    # Perform spelling check if enabled
    if Enable_Spelling_Check:
        '''
        # Disabled, cant seem to get this to work with PyInstaller

        if tool is None:  # Check if 'tool' is already initialized
            try:
                import language_tool_python
                tool = language_tool_python.LanguageTool('en-US')
            except ImportError as e:
                logging.error(f"Error importing language_tool_python: {e}")

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
        '''

    # Remove unwanted characters that should be removed (non-speakable characters)
    forbidden_categories = ["So", "Mn", "Mc", "Me", "C", "Sk"]
    message = "".join(c for c in message if unicodedata.category(c) not in forbidden_categories)

    # Collapse repeated characters (3 or more)
    message = re.sub(r'([^0-9])\1{3,}', r'\1', message)

    if len(message) > 1:
        message = message[0].upper() + message[1:]

    # Replace double spaces with a single space
    message = re.sub(r'\s+', ' ', message).strip()

    # Remove gibberish
    total_length = len(message)
    temp = re.sub(r'[_]', '', message)
    temp_len = len(temp)
    non_alnum_len = len(re.sub(r'[\d\p{L}\p{M}]', '', temp))
    if (temp_len - non_alnum_len == 0):
        print(f"IGNORED! Message '{message}' is considered gibberish/ascii art. Length: {total_length}")
        return ""
    elif total_length > 10:
        cleaned = re.sub(r'(?<=[a-zA-Z]|\d|\s|^)\.\.\.?(?=)', '…', message) # Convert ... to ellipsis symbol and contract repeated dots
        cleaned = re.sub(r'[+\-*/=<>^|~,.\\#\'":;_`¦]', '', cleaned)
        cleaned_length = len(cleaned)
        ratio = cleaned_length / total_length
        if (ratio < 0.70):
            print(f"IGNORED! Message '{message}' is considered gibberish/ascii art. Ratio: {ratio:.2f}, Length: {total_length}")
            return ""

    return message

def guess_gender_and_voice(first_name):
    global window, EdgeVoice
    # Precompiled regex patterns for efficiency
    female_endings = [re.compile(ending + r'\Z', re.IGNORECASE) for ending in ['ss', 'ia', 'et', '[aeiou]ko', 'yl', 'ah', 'iya', 'it', 'li', 'yn', 'th', 'ey', '[pbv]ril', 'gail', 'at', 'bby', 'ndy', 'py', 'any', '[^n]ny', 'un', 'ssy', 'ele', 'iel', 'ell']]
    male_endings = [re.compile(ending + r'\Z', re.IGNORECASE) for ending in ['el', 'hu', 'ya', 'ge', 'pe', 're', 'ce', 'de', 'le']]
    male_exceptions = [re.compile(pat, re.IGNORECASE) for pat in [r'\bGiora\b', r'\bEzra\b', r'\bElisha\b', r'\bAkiva\b', r'\bAba\b', r'\bAmit\b', r'kko\Z', r'Sasha', r'\bAndy\b', r'\bPhil\b']]
    female_exceptions = [re.compile(pat, re.IGNORECASE) for pat in [r'Bint', r'\bRachael\b', r'\bRachel\b', r'\bLael\b', r'\bLiel\b', r'\bYael\b', r'\bGal\b', r'\bRain\b', r'\bSky\b', r'\bJill\b', r'\bAgnes\b', r'\bMary\b', r'\bKaren\b', r'\bErin\b', r'\bMerav\b', r'\bSharon\b']]

    _first_name = re.sub(r'[0-9]', '', first_name).lower()

    # Grab the config value. If input is 2; like "en-US-AndrewMultilingualNeural, en-US-EmmaMultilingualNeural"
    # use the first for male and the second for female; otherwise return always the one value given
    current_value = window.edge_voice_input.get()
    voices = [v.strip() for v in current_value.split(",")]
    if not voices:
        # Empty config ? return default
        male_voice = female_voice = EdgeVoice = "en-US-EmmaMultilingualNeural"
        return None, EdgeVoice
    elif len(voices) == 2:
        male_voice, female_voice = voices
        EdgeVoice = male_voice
    else:
        # Welp only 1 value or more then 2? exit...
        male_voice = female_voice = voices[0]
        EdgeVoice = voices[0]
        return None, EdgeVoice

    # 1. Female exceptions
    for pat in female_exceptions:
        if pat.search(_first_name):
            return 'female', female_voice

    # 2. Male exceptions
    for pat in male_exceptions:
        if pat.search(_first_name):
            return 'male', male_voice

    # 3. Female endings
    for pat in female_endings:
        if pat.search(_first_name):
            return 'female', female_voice

    # 4. Male endings
    for pat in male_endings:
        if pat.search(_first_name):
            return 'male', male_voice

    # 5. Fallback: last letter heuristic
    if re.match(r"[aei]", _first_name[-1:], re.IGNORECASE):
        return 'female', female_voice
    elif re.match(r"[ou]", _first_name[-1:], re.IGNORECASE):
        return 'male', male_voice

    # 6. Default fallback
    return None, male_voice

def is_valid_voice_format(voice_name):
    """Validate if the voice name follows the format xx-XX-NAME."""
    pattern = r"^[a-z]{2}-[A-Z]{2}-[A-Za-z]+Neural$"
    return bool(re.match(pattern, voice_name))

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

output_file_counter = 0

async def speak_text(text2say, VoiceOverride=None):
    """Use Edge TTS to speak the given text."""
    global is_playing, EdgeVoice, output_file_counter, window

    # Wait until the current audio finishes
    while is_playing:
        await asyncio.sleep(0.25)

    is_playing = True  # Indicate audio is playing
    if VoiceOverride is not None:
        EdgeVoice = VoiceOverride

    if not is_valid_voice_format(EdgeVoice):
        print(f"Invalid voice format: {EdgeVoice}. Using default voice 'en-US-EmmaMultilingualNeural'.")
        logging.error(f"Invalid voice format: {EdgeVoice}. Using default voice 'en-US-EmmaMultilingualNeural'.")
        EdgeVoice = "en-US-EmmaMultilingualNeural"

    try:
        # Generate and save the audio file
        output_file = f"output{output_file_counter}.mp3"
        output_file_counter = (output_file_counter + 1) % 3

        # Dynamically adjust the rate based on text length
        min_len, max_len = 64, 384
        min_rate, max_rate = 1, 8
        text_len = len(text2say)
        if text_len <= min_len:
            _rate = f'+{min_rate}%'
        elif text_len >= max_len:
            _rate = f'+{max_rate}%'
        else:
            # Linear interpolation between min_rate and max_rate, rounded to nearest integer
            interp = round(min_rate + (max_rate - min_rate) * (text_len - min_len) / (max_len - min_len))
            _rate = f'+{interp}%'

        try:
            await Communicate(text = text2say, voice=EdgeVoice, rate = _rate, pitch = '+0Hz').save(output_file)
        except Exception as e:
            logging.error(f"Error generating audio: {e}")
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
                    logging.error("Client disconnected while sending SSE.")
                    break  # Exit the loop if the client disconnects

            # Send a keep-alive message every 5 seconds
            try:
                await response.write(":\n\n".encode('utf-8'))
            except (ConnectionResetError, asyncio.CancelledError):
                logging.error("Client disconnected while sending keep-alive.")
                break

    except asyncio.CancelledError:
        logging.error("SSE handler task was cancelled.")
    except Exception as e:
        logging.error(f"Error in SSE handler: {e}")
    finally:
        try:
            await response.write_eof()
        except ConnectionResetError:
            logging.error("Connection reset while closing response stream.")
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
        logging.error(f"Error loading chat_template.html: {e}")
        filesend = 'internal template'
    except Exception as e:
        logging.error(f"Unexpected error loading chat_template.html: {e}")
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
                font-size: 20px;
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
                text-shadow: -1px -1px 2px #000000d1, 1px -1px 0 #000000d1, -1px 1px 0 #000000d1, 1px 1px 0 #000000d1, 1px 1px 1px #000000, 0 0 1em #000000, 0 0 0.2em #000000;
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
                        const fadeoutDuration = Math.min(60, Math.max(18, messageLength / 9));
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
            logging.warning(f"OBS Page service started on http://localhost:{port} Use this URL in OBS via a browser source.")
            break
        except OSError as e:
            if e.errno == 98 or e.errno == 10048:  # Port already in use
                logging.error(f"Port {port} is already in use. Trying port {port + 10}...")
                port += 10
            else:
                logging.error(f"Error starting server: {e}")
                raise

# Modify the monitor_log function to call update_chat
async def monitor_log(log_file):
    # await speak_text("Starting up! Monitoring log file...")
    global last_message, last_user, IgnoreList, last_chat, OBSChatFiltered, readloop, play_volume, min_char, name2voice, last_voice, SpeakOnlyList

    # Start at the end of the file
    last_position = 0
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as file:
            file.seek(0, os.SEEK_END)
            last_position = file.tell()
    else:
        print(f"Log file not found: {log_file}")
        logging.error(f"Log file not found: {log_file}")
        return

    last_mod_time = os.path.getmtime(log_file)
    name_cache = {}
    iswarned = False

    try:
        while readloop:
            current_mod_time = os.path.getmtime(log_file)
            # Check if the file has been modified
            if current_mod_time != last_mod_time:
                last_mod_time = current_mod_time

                # Reopen the file to ensure we get the latest data
                try:
                    with open(log_file, 'r', encoding='utf-8') as file:
                        file.seek(last_position)  # Seek to the last known position
                        new_lines = file.readlines()
                        if len(new_lines) > 50000 and not iswarned:
                            print("Warning: Log file is over 50,000 lines. This may cause performance issues.")
                            logging.warning("Log file is over 50,000 lines. This may cause performance issues.")
                            iswarned = True
                            await asyncio.sleep(0.3)
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
                                        # speaker can excist of the following formats:
                                        # [20:00:00] Firstname: Hello
                                        # [20:00:00] Firstname Hello
                                        # [20:00:00] Firstname Lastname: Hello
                                        # [20:00:00] Firstname Lastname Hello
                                        # [20:00:00] Display Name (Firstname.Lastname): Hello
                                        # [20:00:00] Display Name (Firstname.Lastname) Hello
                                        # [20:00:00] Display Name (Firstname): Hello
                                        # [20:00:00] Display Name (Firstname) Hello
                                        if ': ' in rest:
                                            speaker_part, message = rest.split(':', 1) # This fails for Radegast as when it is an emote it removes the :
                                        else:
                                            speaker_part = "Second Life"
                                            message = rest
                                        speaker_part = speaker_part.strip()
                                        message = url2word(message).strip()
                                        messageorg = message

                                        first_name = None
                                        ignore_match = False
                                        speak_only_match = False
                                        thisvoice = None
                                        gender = None

                                        if name2voice:
                                            if speaker_part in name2voice:
                                                thisvoice = name2voice[speaker_part]

                                        if IgnoreList and any(item.strip() for item in IgnoreList):
                                            for ignore_item in IgnoreList:
                                                if ignore_item.endswith('*'):
                                                    if speaker_part.lower().startswith(ignore_item[:-1].lower()):
                                                        ignore_match = True
                                                        break
                                                elif speaker_part.lower() == ignore_item.lower():
                                                    ignore_match = True
                                                    break

                                        if SpeakOnlyList and any(item.strip() for item in SpeakOnlyList):  # Ensure SpeakOnlyList is defined and not empty
                                            original_print(f"SpeakOnlyList: {SpeakOnlyList}")
                                            for speak_item in SpeakOnlyList:
                                                if speak_item.endswith('*'):
                                                    if speaker_part.lower().startswith(speak_item[:-1].lower()):
                                                        speak_only_match = True
                                                        break
                                                elif speaker_part.lower() == speak_item.lower():
                                                    speak_only_match = True
                                                    break
                                            if not speak_only_match:
                                                ignore_match = True

                                        # Handle IgnoreList and speaker name extraction
                                        if ignore_match and speaker_part in name_cache:
                                            del name_cache[speaker_part]
                                        elif speaker_part in name_cache:
                                            cached = name_cache[speaker_part]
                                            if isinstance(cached, tuple) and len(cached) == 3:
                                                first_name, gender, thisvoice = cached
                                            else:
                                                first_name = cached
                                            # first_name = name_cache[speaker_part]
                                        elif not ignore_match:
                                            if '(' in speaker_part and ')' in speaker_part:
                                                speaker = speaker_part.split('(')[1].split(')')[0].strip()
                                                if '.' in speaker:
                                                    first_name = speaker.split('.')[0].capitalize()
                                                else:
                                                    first_name = speaker.capitalize()
                                                speaker = speaker_part.split('(')[0].strip()
                                            else:
                                                speaker = speaker_part

                                            # Lets allow trasnlators for now that transalte spesificly to english
                                            if speaker[-3:] == ">en":
                                                speaker = speaker.rsplit(' ', 1)[0]

                                            if speaker == 'Second Life':
                                                first_name = None
                                            elif " " in speaker:
                                                tmp = (re.sub(r'\s+', ' ', speaker).strip()).split(' ')
                                                salutations = {"lady", "lord", "sir", "miss", "ms", "mr", "mrs", "dr", "prof", "the", "master", "mistress", "madam", "madame", "dame", "captain", "chief", "colonel", "general", "admiral", "officer", "agent", "dj"}
                                                if all(part.isalnum() for part in tmp):
                                                    if tmp[0].lower() in salutations and len(tmp) > 1:
                                                        if clean_name(tmp[1]):
                                                            first_name = ascii_name(tmp[1])
                                                    elif clean_name(tmp[0]):
                                                        first_name = ascii_name(tmp[0])
                                            elif speaker.isalnum():
                                                if clean_name(speaker):
                                                    first_name = ascii_name(speaker)

                                            if first_name:
                                                first_name = re.sub(r'(?<!\p{L})\d+$', '', first_name)
                                                name_cache[speaker_part] = (first_name, gender, thisvoice)
                                                if thisvoice is not None:
                                                    logging.warning(f"Speaker {first_name} Gender set to {gender} and Assigned voice to {thisvoice}")

                                        # Process the message
                                        if first_name:
                                            if thisvoice is None:
                                                gender, thisvoice = guess_gender_and_voice(first_name)
                                                if gender:
                                                    logging.warning(f"Speaker {first_name} Gender set to {gender} and Assigned voice to {thisvoice}")
                                                    # Lets cashe this so we not check this ever damn time
                                                    name_cache[speaker_part] = (first_name, gender, thisvoice)

                                            if last_user != speaker_part or last_message == None:
                                                last_user = speaker_part
                                                last_voice = thisvoice
                                                isrepat = False
                                            elif time.time() - last_chat >= 120:
                                                isrepat = False
                                            else:
                                                isrepat = True

                                            manner = 'says'
                                            if message.startswith("/me"):
                                                message = message[3:].strip()
                                                messageorg = messageorg[3:].strip()
                                                isemote = True
                                                isrepat = False
                                            elif message.startswith("shouts: "):
                                                message = message[8:].strip()
                                                messageorg = messageorg[8:].strip()
                                                manner = 'shouts'
                                            elif message.startswith("whispers: "):
                                                message = message[10:].strip()
                                                messageorg = messageorg[10:].strip()
                                                manner = 'whispers'

                                            message = spell_check_message(message)
                                            if len(message) < min_char:
                                                message = ''
                                                last_message = None

                                            if last_message == (speaker_part + ':' + message) and time.time() - last_chat < 121:
                                                message = ''

                                            if message:
                                                last_message = speaker_part + ':' + message
                                                if isrepat:
                                                    to_speak = f"{message}"
                                                    to_cc = f"{first_name}: {message}" if OBSChatFiltered else f"{first_name}: {messageorg}"
                                                    print(f"{message}")
                                                elif isemote:
                                                    to_speak = f"{first_name} {message}"
                                                    to_cc = f"{first_name} {message}" if OBSChatFiltered else f"{first_name} {messageorg}"
                                                    print(f"{to_speak}")
                                                else:
                                                    to_speak = f"{first_name} {manner}: {message}"
                                                    to_cc = f"{first_name}: {message}" if OBSChatFiltered else f"{first_name}: {messageorg}"
                                                    print(f"{to_speak}")

                                                await update_chat(to_cc)
                                                if play_volume > 0:
                                                    await speak_text(to_speak, thisvoice)
                                                last_chat = time.time()
                                            elif messageorg:
                                                print(f"IGNORED! {first_name}: {messageorg}")
                                                if not OBSChatFiltered:
                                                    await update_chat(f"{first_name}: {messageorg}")
                                                last_chat = time.time()
                                        else:
                                            last_user = None
                                            last_voice = None
                                            if speaker_part == "Second Life":
                                                speaker_part = ""
                                            else:
                                                speaker_part = speaker_part + ": "
                                            print(f"IGNORED! {speaker_part}{message}")
                                    elif last_user is not None:
                                        message = line.strip()
                                        message = url2word(message).strip()
                                        message = spell_check_message(message)
                                        if last_message != message and message:
                                            last_message = message
                                            print(f"{message}")
                                            await update_chat(last_user + ' ' + message)
                                            if play_volume > 0:
                                                await speak_text(message, last_voice)
                                    else:
                                        rest = line.strip()
                                        match = re.search(r'\d{2}\]\s*(.*)', line)
                                        if match:
                                            rest = match.group(1).strip()
                                        print(f"IGNORED! {url2word(rest).strip()}")
                                except ValueError:
                                    rest = line.strip()
                                    match = re.search(r'\d{2}\]\s*(.*)', line)
                                    if match:
                                        rest = match.group(1).strip()
                                    print(f"IGNORED! {url2word(rest).strip()}")
                            await asyncio.sleep(0.3) # Qt5 update_display might crash if we spam it too fast
                except FileNotFoundError:
                    logging.error(f"Log file not found: {log_file}")
                except IOError as e:
                    logging.error(f"Error reading log file IO Error: {e}")
                except Exception as e:
                    logging.error(f"Error reading log file Unexpected error: {e}")
            await asyncio.sleep(1)
    except Exception as e:
        logging.error(f"Error in monitor_log: {e}")
        print(f"Error while monitoring log file: {e}")
    finally:
        print("Stopped monitoring log file.")

def update_global(variable_name, value):
    """Update a global variable dynamically."""
    globals()[variable_name] = value
    original_print(f"Updated global {variable_name} to {value}")
    name_cache = {}  # Reset the name cache when updating global variables
    # Ignore List updated:
    if variable_name == "SpeakOnlyList":
        toprint = ''
        for item in value:
            toprint += item.strip() + ', '
        print(f"Updated Speak Only List: {toprint[:-2]}")
    if variable_name == "IgnoreList":
        toprint = ''
        for item in value:
            toprint += item.strip() + ', '
        print(f"Updated Ignore List: {toprint[:-2]}")
    if variable_name == "Enable_Spelling_Check":
        window.global_config.set('Settings', 'enable_spelling_check', str(value))
        message = "Grammar tool and spellchecker check enabled." if value else "Grammar tool and spellchecker check disabled."
        print(message)
        if value:
            window.spelling_check_button.configure(text="Toggle Spelling Check", text_color="#80ff80")
        else:
            window.spelling_check_button.configure(text="Toggle Spelling Check", text_color="#d1d1d1")
    if variable_name == "OBSChatFiltered":
        window.global_config.set('Settings', 'obs_chat_filtered', str(value))
        status = "enabled" if value else "disabled"
        print(f"Unfiltered or corrected chat to OBS page {status}.")
        if value:
            window.obs_filter_button.configure(text="Toggle OBS Chat Filter", text_color="#80ff80")
        else:
            window.obs_filter_button.configure(text="Toggle OBS Chat Filter", text_color="#d1d1d1")

def update_volume(value, window=None):
    """Update the volume setting."""
    global play_volume
    play_volume = value / 100  # Convert to a percentage
    pygame.mixer.music.set_volume(play_volume)
    if window:
        window.volume_label.configure(text=f"Output volume: {int(value)}")

# Add this method to the MainWindow class
def set_audio_device(selected_device):
    """Set the audio device for playback."""
    if selected_device == "Select Playback Device":
        return
    global play_volume, pygame
    pygame.mixer.quit()  # Quit the mixer to reinitialize with the new device
    pygame.mixer.init(devicename=selected_device)
    print(f"Audio device set to: {selected_device}")
    pygame.mixer.music.set_volume(play_volume)

def update_minchar(value, window=None):
    """Update the minimum character setting."""
    global min_char
    min_char = int(value)  # Convert to an integer
    if window:
        window.global_config.set('Settings', 'min_char', str(min_char))
        window.characters_label.configure(text=f"Minimum Characters: {value}")

def load_slang_replacements(file_path):
    if file_path and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError as e:
                logging.error(f"Error: loading file: {e}")
                return {}
    else:
        logging.error(f"Error: file not found: {file_path}")
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
        logging.error("Log monitoring is already running.")
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

def update_lists():
    """Update the IgnoreList and SpeakOnlyList from the UI."""
    print("Updating IgnoreList and SpeakOnlyList...")
    update_global("IgnoreList", [item.strip().lower() for item in window.ignore_list_input.get("1.0", "end").split(',')])
    update_global("SpeakOnlyList", [item.strip().lower() for item in window.onlytalk_list_input.get("1.0", "end").split(',')])

async def speak_test_message():
    """Speak a test message."""
    test_message = "This is a Test message from the Second Life Chat to Speech program."
    await speak_text(test_message)

if __name__ == "__main__":
    if create_default_config('config.ini'):
        logging.error("Default config.ini created. Please edit it with your settings.")
        sys.exit(0)

    config = ConfigParser()
    config.read('config.ini')

    # Parse configuration values
    global Enable_Spelling_Check, IgnoreList, OBSChatFiltered, EdgeVoicem, SpeakOnlyList
    log_file_path = config.get('Settings', 'log_file_path')
    Enable_Spelling_Check = config.getboolean('Settings', 'enable_spelling_check')
    IgnoreList = [item.strip() for item in config.get('Settings', 'ignore_list', fallback='').split(',')]
    SpeakOnlyList = [item.strip() for item in config.get('Settings', 'speak_only_list', fallback='').split(',')]
    OBSChatFiltered = config.getboolean('Settings', 'obs_chat_filtered')
    EdgeVoice = config.get('Settings', 'edge_tts_llm')
    min_char = config.getint('Settings', 'min_char', fallback=2)
    # all_voices = asyncio.run(get_voices()) # Fetch all voices

    update_volume(config.getint('Settings', 'volume', fallback=75))

    # app = QApplication(sys.argv)
    window = MainWindow(config)

    # Connect the UI's start button to start the log monitoring
    loop = None
    tasks = []
    monitor_task = None
    monitor_loop = None
    slang_replacements = {}
    name2voice = {}

    def start_monitoring_ui():
        """Start monitoring from the UI."""
        global chat_messages, slang_replacements, readloop, name2voice
        # log_file_path = window.log_file_path_input.text()  # Get the log file path from the input field
        log_file_path = window.log_file_path_input.get()  # Get the log file path from the input field
        if os.path.exists(log_file_path):
            readloop = True
            slang_replacements = load_slang_replacements("slangreplce.json")
            if slang_replacements:
                print(f"Abbreviation file reading done, {len(slang_replacements)} replacements found and loaded.")
            name2voice = load_slang_replacements("name2voice.json")
            if name2voice:
                print(f"Name to voice file reading done, {len(name2voice)} replacements found and loaded.")
            chat_messages.clear()
            start_monitoring(log_file_path)
            window.start_button.configure(text="Stop Log Reading", text_color="#ff8080")
        else:
            logging.error(f"Chat Log file not found: {log_file_path}")
            print(f"Chat Log file not found: {log_file_path}")

    def stop_monitoring_ui():
        """Stop monitoring from the UI."""
        global chat_messages, readloop
        readloop = False
        stop_monitoring()
        chat_messages.clear()
        window.start_button.configure(text="Start Log Reading", text_color="#d1d1d1")

    last_toggle_time = 0
    def toggle_monitoring():
        """Toggle monitoring based on the button state."""
        global last_toggle_time
        current_time = time.time()
        if current_time - last_toggle_time < 3:  # Check if 3 seconds have passed
            return

        last_toggle_time = current_time
        if window.start_button.cget("text") == "Start Log Reading":
            start_monitoring_ui()
        else:
            stop_monitoring_ui()
    
    # Start the server in the background
    run_server_in_background()

    # Connect the UI buttons to the respective functions
    window.start_button.configure(command=toggle_monitoring)
    # window.spelling_check_button.configure(command=lambda: update_global("Enable_Spelling_Check", not Enable_Spelling_Check))
    window.obs_filter_button.configure(command=lambda: update_global("OBSChatFiltered", not OBSChatFiltered))
    window.update_ignore_list_button.configure(command=lambda: update_lists())
    window.save_config_button.configure(command=window.save_config)
    window.volume_slider.configure(command=lambda value: update_volume(float(value), window))
    window.characters_slider.configure(command=lambda value: update_minchar(int(value), window))
    # audio_device_menu
    window.audio_device_menu.configure(command=lambda value: set_audio_device(value))
  
    # speak_text("Starting up! Monitoring log file...")
    window.test_button.configure(command=lambda: asyncio.run(speak_test_message()))

    # Override the print function to append to window.text_display
    original_print = print  # Keep a reference to the original print function
    def custom_print(*args, **kwargs):
        message = " ".join(map(str, args))  # Combine all arguments into a single string
        if 'window' in globals() and hasattr(window, 'text_display'):
            window.update_display(message)

        original_print(*args, **kwargs)  # Optionally, call the original print function

    # Replace the built-in print function with the custom one
    builtins.print = custom_print

    print("Second Life Chat log to Speech version 1.5.4, by Jara Lowell")

    # Start the window application event loop
    try:
        window.mainloop()
    except Exception as e:
        logging.error(f"Error in main loop: {e}")
