#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Needs > pip install edge-tts pygame-ce regex unidecode emoji aiohttp customtkinter
import sys
import os
import logging
logging.basicConfig(filename='sltts.log', level=logging.DEBUG, format='%(asctime)s : %(message)s', datefmt='%m-%d %H:%M', filemode='w', encoding='utf-8')
logging.error("Starting Up")

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
from datetime import datetime, timedelta
import html
import json
from SLTTSUI import MainWindow
import threading
import builtins
import shutil

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
request = 0 # speak_text is request 0, stop_monitoring is request 1
thread = 1 # speak_text is thread 0, stop_monitoring is thread 1
last_message = None
last_user = None
last_voice = None
last_chat = 0
tool = None
readloop = False
play_volume = 0.75  # Default volume
min_char = 2  # Default minimum characters
verbose = 0

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

        # as a test removing "WITH" in script_name or 
        if "SMALL CAPITAL" in script_name: # Small Capitals will convert to ASCII Latin so keep then
            # Seriously ! ŦorestŞheŨrt is Latin ... but with stroke F, cedilla S and tilde U
            script_name = script_name.split()[0] + ' Extended'
        elif "DIGIT" in script_name:
            # We want to exclude digits from being counted as different scripts since they are used in all languages
            script_name = ''
        else:
            script_name = script_name.split()[0]

        if script_name != '' and script_name not in script_names:
            script_names.add(script_name)
            if len(script_names) > 1: return False

    if len(script_names) <= 1: # and "LATIN Extended" not in script_names:
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
    elif len(message) == 1:
        return message

    # Collapse repeated grapheme clusters (including emoji) processing each cluster individually for spam
    word_parts = re.findall(r"\S+", message)
    message = ''
    for word in word_parts: # Analyse individual clusters for spam
        _word = re.sub(r'[^\d]', '', word)
        if len(_word) < 4: # Each word being checked can contain 3 numbers or less
            #word = emoji.replace_emoji(word, replace=emoji_to_word) # Replace common emojis with their names. This will introduce more spam if used and become counter-productive. 
            word = re.sub(r'(\.)\1{3,}', r' ', word) # Allow ellipsis '...' to pass since is is used in roleplay, but replace larger patterns of dots with white space
            word = re.sub(r'(\X)\1{3,}', r'\1', word) # Throttle repeated characters to 3
            temp = re.sub(r'[_]', '', word) # Remove _ since regex treats it as alphanumeric
            temp_len = len(temp) # Initial length of message without '_'
            non_alnum_len = len(re.sub(r'[\d\p{L}\p{M}]', '', temp)) # Length of string without '_', letters or numbers
            if (temp_len - non_alnum_len == 0): # Word does not contain any '_', letters or numbers so consider it spam
               if temp_len > 3:
                   word = ''
               else:
                   temp = re.sub(r'[+=*./\-?!"\':;,()$£€¥]{1,}', '', temp) # These characters can be spoken or emoted in English so should not be counted as spam
                   if temp_len == len(temp):
                        word = ''
            elif clean_name(re.sub(r'[^\d\p{L}\p{M}]', '', word)) == False: # If word contains characters in more than one language regard it as spam 
                word = ''
            word = re.sub(r'\.\*', '. *', word) # Edge tts says 'dot asterisk' instead of 'asterisk' if asterisk appears after a full-stop so spilt '.*' using a space 
        if (word != ''): message = message + " " + word # Reconstruct sentence word by word while appending spaces
    message = message.strip()

    #message = re.sub(r'(\X)\1{3,}', r'\1', message) # Replaced with above code so is no longer needed

    if len(message) == 1:
        return message

    # Remove unwanted characters while preserving letters, punctuation, spaces, digits, and math symbols
    # message = re.sub(r'[^\p{L}\d\s\p{P}+\-*/=<>^|~]', '', message, flags=re.UNICODE)  # Remove unsupported characters

    # Replace L$ with Linden Dollars
    message = re.sub(r'(\d+.+|\s\d+.+|$) (L\$)', r'\1 Linden dollars', message, flags=re.IGNORECASE) # Replace symbol at end off number+space
    message = re.sub(r"(\bL\$) (\d+.+|\s\d+.+|$)", r"\2 Linden dollars", message, flags=re.IGNORECASE) # Replace symbol at start of number+space and swap to the end
    message = re.sub(r'(\d+.+|\s\d+.+|$)(L\$)', r'\1 Linden dollars', message, flags=re.IGNORECASE) # Replace symbol at end off number
    message = re.sub(r"(\bL\$)(\d+.+|\s\d+.+|$)", r"\2 Linden dollars", message, flags=re.IGNORECASE) # Replace symbol at start of number and swap to the end
    message = re.sub(r"\bL\$", r"Linden dollars", message, flags=re.IGNORECASE) # Replace elsewhere

    # Replace hyphen with "minus" or space based on context
    #message = re.sub(r'(?<=\d)-(?=\d|\=)', ' to ', message) # Dash denotes a sequence from-to if paced directly next to numbers like 30-40 degrees. Edge tts can already do this.
    #message = re.sub(r'(?<=\w)-(?=\w)', '', message) # Hyphen is dropped in-between/inbetween words joining them together for correct grammar. 
    # Counter productive on some words and it conflicts with the replacement of abbreviations and slang in the next block of code

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
    temp = re.sub(r'(?<=\p{L}|\p{M}|\d|\s|^)\.\.\.?(?=)', '…', message) # Replace three dots '...' in a row with ellipsis symbol to count them as one character only
    temp = re.sub(r'[_\s]', '', temp) # Don't count _ and white space as part of length
    temp_len = len(temp) # Initial length of processed message without '_' and spaces
    non_alnum_len = len(re.sub(r'[\d\p{L}\p{M}]', '', temp)) # Length of temp string without '_' and spaces
    if (temp_len - non_alnum_len == 0): # Message does not contain any '_', letters or numbers so might be spam
        if temp_len == len(re.sub(r'[()"]', '', temp)): # Protect bracketed or quoted content. May or may not be desired
            print(f"IGNORED! Message '{message}' is considered gibberish/ascii art. Length: {len(message)}")
            return ""
    if total_length > 10: # Short sentances could contain emijis so let them pass and filter longer content
        if re.search(r'\d', temp): # Prevent sequences of numbers separated by commas, dots, and currency from being counted as spam
            temp = re.sub(r'([$£€¥])(\d+)', r'\2', temp) # Ignore main international currency symbols if before numbers
            temp = re.sub(r'(?<=\d|^)[,.]?(?=)', '', temp) # Stops "$1,000,000 !!!" and other numbers separated by dots or commas being regarded as spam
        non_alnum_len = len(re.sub(r'[\d\p{L}\p{M}()"]', '', temp)) # Protect bracketed or quoted content
        ratio = 1 - (non_alnum_len / total_length) # Ratio of alpha numeric characters to total length of message
        if (ratio < 0.70 - 1/total_length): # Using a dynamic threshold the lower the ratio the more potential spam
            print(f"IGNORED! Message '{message}' is considered gibberish/ascii art. Ratio: {ratio:.2f}, Length: {len(message)}")
            return ""
        elif (ratio < 0.80): # Message might still contain spam so try to clean it
            print(f"IGNORED! Message '{message}' may have been cleaned of suspected gibberish/ascii art. Ratio: {ratio:.2f}, Length: {len(message)}")
            message = re.sub(r'[^\d\p{L}\p{M}\s,.;:\'"?!/\-+*=()£$€¥%]', ' ', message).strip() # Remove all but letters, digits, and basic punctuation
            message = re.sub(r'\s+', ' ', message).strip() # Clean out excess white space the might have been added

    return message

def guess_gender_and_voice(first_name):
    global window, EdgeVoice
    # Precompiled regex patterns for efficiency
    female_endings = [re.compile(ending + r'\Z', re.IGNORECASE) for ending in ['ss', 'ia', 'et', '[aeiou]ko', 'yl', 'ah', 'iya', 'it', 'yn', 'th', 'ey', '[pbv]ril', 'gail', 'at', 'bby', 'ndy', 'py', 'any', '[^n]ny', 'ssy', 'iel', 'ell']]
    male_endings = [re.compile(ending + r'\Z', re.IGNORECASE) for ending in ['el', 'hu', 'ge', 'pe', 're', 'ce', 'de']]
    male_exceptions = [re.compile(pat, re.IGNORECASE) for pat in [r'\bGiora\b', r'\bEzra\b', r'\bElisha\b', r'\bAkiva\b', r'\bAba\b', r'\bAmit\b', r'kko\Z', r'\bSasha\b', r'\bAndy\b', r'\bPhil\b', r'\bAnthony\b']]
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
            'edge_tts_llm': 'en-US-AndrewMultilingualNeural, en-US-EmmaMultilingualNeural',
            'concurrent_edge_tts_threads': '3',
            'replay_chat': '0'
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
current_player = 0
speaker_active = []
speakers = 3
recording = ""

async def speak_text(text2say, VoiceOverride=None, local_file_counter=0, chat_delta = timedelta(seconds=0), test_msg = False):
    """Use Edge TTS to speak the given text."""
    global EdgeVoice, window, current_player, speaker_active, speakers, recording, follow_timestamps, record, replay_chat, verbose
    
    if VoiceOverride is not None:
        EdgeVoice = VoiceOverride

    if not is_valid_voice_format(EdgeVoice):
        print(f"Invalid voice format: {EdgeVoice}. Using default voice 'en-US-EmmaMultilingualNeural'.")
        logging.error(f"Invalid voice format: {EdgeVoice}. Using default voice 'en-US-EmmaMultilingualNeural'.")
        EdgeVoice = "en-US-EmmaMultilingualNeural"

    try:
        # Generate and save the audio file
        output_file = f"output{local_file_counter}.mp3"

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
            logging.error(f"Error generating audio: {e} Text to say: {text2say}")
            if not test_msg:
                # Wait for other concurrent threads to give way to play each output file in the right order
                while local_file_counter != globals()["current_player"]:
                    await asyncio.sleep(0.25)
                current_player = (current_player + 1) % speakers # Activate the next player in the seqnece
                speaker_active[local_file_counter] = 0 # Tell programme that playback has stopped in this thread
            return

        # Wait to play output file in the right order
        if not test_msg:
            while local_file_counter != globals()["current_player"]:
                await asyncio.sleep(0.25)

        # Play the audio file
        if os.path.exists(output_file):
            if not replay_chat or not record:
                pygame.mixer.music.load(output_file)
                pygame.mixer.music.play()
            if not test_msg:
                # Record audio output
                if record:
                    if follow_timestamps and os.path.exists('silence.mp3'):
                        # add silence to fill time elapsed between sgements of spoken text
                        if os.path.exists(recording):
                            size = os.path.getsize(recording)
                        else: size = 0
                        duration = round(size/144 * 0.024,3) # total duration of mp3 recording so far, rounded to correct maths errors since the result can only contain 3 decimel figures
                        if verbose: print(f"VERBOSE! Duration of recording {duration}s, File size {size} bytes, Total time elapsed {chat_delta}")
                        padding = chat_delta.total_seconds() - duration # add these seconds of silence between chats to the end of the recording
                        if verbose: print(f"VERBOSE! Seconds of padding needed {round(padding,3)}")
                        if padding >= 60:
                            minutes = int(padding / 60)
                            padding = padding%60
                            for i in range(minutes): 
                                with open('silence.mp3', 'rb') as f2, open(recording, 'ab') as f1:
                                    shutil.copyfileobj(f2, f1)
                        if padding > 0:                 
                            with open("silence.mp3", 'rb') as file1:
                                silence = file1.read()
                            frames = int(padding/0.024 + 0.5) # number of frames needed where each frame is 0.024s
                            bytes2write = int(frames * 144) # number of bytes used by these frames
                            if verbose: print(f"VERBOSE! Bytes needed {bytes2write}")
                            f2 = silence[:bytes2write]
                            fileout = open(recording, 'ab')
                            fileout.write(f2)
                            fileout.close()                  
                    # append mp3 tts file to recording
                    with open(output_file, 'rb') as f2, open(recording, 'ab') as f1:
                        shutil.copyfileobj(f2, f1)
                        f1.close()
                        f2.close()
        else:
            print(f"Output file not found: {output_file}")
            logging.error(f"Output file not found: {log_file}")
            if not test_msg:
                current_player = (current_player + 1) % speakers # Activate the next player in the seqnece
                speaker_active[local_file_counter] = 0 # Tell programme that playback has stopped in this thread
                await asyncio.sleep(0.25)
            return

        # Wait for playback to finish with timeout
        timeout = 60  # maximum wait time in seconds
        elapsed = 0
        while pygame.mixer.music.get_busy() and elapsed < timeout:
            await asyncio.sleep(0.1)
            elapsed += 0.1

    finally:
        # Clean up and reset the flag
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()

    # When output file stops playing
    if not test_msg:
        current_player = (current_player + 1) % speakers # Activate the next player in the seqnece
        speaker_active[local_file_counter] = 0 # Tell programme that playback has stopped in this thread
        await asyncio.sleep(0.25)

# List to store chat messages for the website
chat_messages = []

def format_chat_message(message):
    """Format a chat message with separate styling for username and message text."""
    # Check if message contains a colon separator (username: message format)
    if '¿ ' in message:
        parts = message.split('¿ ', 1)
        username = html.escape(parts[0])
        msg_text = html.escape(parts[1])
        return f"<div class='chat-line'><span class='chat-name'>{username}</span><span class='chat-message'> {msg_text}</span></div>"
    elif ': ' in message:
        parts = message.split(': ', 1)
        username = html.escape(parts[0])
        msg_text = html.escape(parts[1])
        return f"<div class='chat-line'><span class='chat-name'>{username}</span><span class='chat-message'>: {msg_text}</span></div>"
    else:
        # If no colon, it's just a plain message (no username)
        return f"<div class='chat-line'><span class='chat-message'>{html.escape(message)}</span></div>"

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
                    format_chat_message(msg['message'])
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
            }
            .chat-name {
                color: #bfea7c; /* Username stays mint green */
            }
            .chat-message {
                color: #e5e5e5; /* Message text is grey */
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

replay_chat = False
follow_timestamps = True
record = False
stamp_read = False

def name_recording():
    global recording
    # generate unique name for audio recording file
    dtm = datetime.now()
    if dtm.microsecond >= 500000:
        dtm = dtm + timedelta(seconds=1)
        dtm = dtm.replace(microsecond=0)
    else: dtm = dtm.replace(microsecond=0)
    dtmstr = f"{dtm}".replace(":","-")
    recording = f"Chat {dtmstr}.mp3"
    c = 1
    while os. path.exists(recording) and c<1000:
        recording = f"Chat {dtmstr} ({c}).mp3"
        c = c + 1
    if c > 1000: 
        print(f"WARNING! {recording} already exists.")
        return False
    print(f"Audio will be recorded to .\{recording} while reading chat log.")
    return True
 
async def stopped_speaking():
    global window, speakers, speaker_active, thread
    window.start_busy()
    while(True): # wait for speakers to finish speaking and close open .mp3 files
        i = 0
        for s in range(speakers):
            i = i + speaker_active[s]
        if i == 0:
            break
        await asyncio.sleep(0.25)
    thread = 1
    return thread

# Modify the monitor_log function to call update_chat
async def monitor_log(log_file):
    global last_message, last_user, IgnoreList, last_chat, OBSChatFiltered, readloop, play_volume, min_char, name2voice, last_voice, SpeakOnlyList, slang_replacements, window
    global current_player, output_file_counter, speaker_active, speakers, request, thread, recording, record, stamp_read
    # await speak_text("Starting up! Monitoring log file...", "en-US-EmmaMultilingualNeural", speakers, True)
    thread = 0
    request = 0
    last_message = None
    last_user = None
    last_voice = None
    last_chat = 0
    
    # prepare to read ascending time stamps
    epoch_time = '1970-01-01 00:00:00'
    date_format = '%Y-%m-%d %H:%M:%S'
    date_stamp = initial_stamp = datetime.strptime(epoch_time, date_format)
    start_time = datetime.now()
    stamp_read = False
    chat_delta = timedelta(seconds=0)

    # initiate playback counter and playback task lists for simultaneous tts encoders
    current_player = output_file_counter = 0
    task1 = []
    if len(speaker_active) < speakers:
        for s in range(speakers):
            task1.append(0)
            speaker_active.append(0)
    elif len(speaker_active) == speakers:
        for s in range(speakers):
            task1.append(0)
            speaker_active[s] = 0

    # Start at the end of the file
    last_position = 0
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as file:
            if not replay_chat:
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
        # start reading the chat log
        while readloop:
            if request: # request made to stop monitoring
                if await stopped_speaking(): 
                    return
            current_mod_time = os.path.getmtime(log_file)
            # Check if the file has been modified
            if current_mod_time != last_mod_time or replay_chat:
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
                        if replay_chat and len(new_lines):
                            log_read = True
                        for line in new_lines:
                            if request: # request made to stop monitoring
                                if await stopped_speaking(): 
                                    return
                            line = line.strip()
                            if line:
                                # Process the line (existing logic)
                                try:
                                    window.start_busy()
                                    if line.startswith("[") and line[11] == " " and (line[20] == "]" or line[17] == "]"):
                                        isemote = False
                                        isrepat = False
                                        # Extract timestamp and message
                                        timestamp, rest = line[1:].split(']', 1)
                                        """Begin Replay Chat Log Code"""
                                        # Read chat log file from start to end
                                        if follow_timestamps and (replay_chat or record):
                                            # convert SL timestamp to a datetime object used by Python
                                            date_time = timestamp.replace("/","-")
                                            if len(date_time) is 19:
                                                date_format = "%Y-%m-%d %H:%M:%S"
                                            elif len(date_time) is 16:
                                                date_format = "%Y-%m-%d %H:%M"
                                                
                                            try:
                                                new_stamp = datetime.strptime(date_time, date_format)
                                            except Exception as e:
                                                logging.error(f"Error reading date stamp: {e}")

                                            if not stamp_read:
                                                start_time = datetime.now()
                                                time_delta = timedelta(seconds=0)
                                                initial_stamp = new_stamp
                                                stamp_read = True
                                            else:
                                                time_delta = new_stamp - date_stamp
                                                
                                            # duration between this and the last chat
                                            date_stamp = new_stamp

                                            # duration between this and the first chat
                                            chat_delta = date_stamp - initial_stamp
                                            
                                            dtm = start_time
                                            if dtm.microsecond >= 500000:
                                                dtm = dtm + timedelta(seconds=1)
                                                dtm = dtm.replace(microsecond=0)
                                            else: dtm = dtm.replace(microsecond=0)
                                      
                                            if not record and stamp_read and replay_chat:
                                                # wait untill time difference reaches delta
                                                print(f"TIMECODE! Waiting {time_delta.total_seconds()} seconds until {dtm + chat_delta} for next line.")
                                                while (datetime.now() - start_time) < chat_delta:
                                                    if request: # request made to stop monitoring
                                                        if await stopped_speaking(): 
                                                            return
                                                    await asyncio.sleep(1.00)
                                        else: chat_delta = timedelta(seconds=0)
                                        """End Replay Chat Log Code"""
                                        # speaker can exist in the following formats:
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
                                            
                                            # Try to split camel case (e.g., MsLaiken -> Ms Laiken or MsLaniSmit > Ms Lani Smit)
                                            # speaker = " ".join(re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])', speaker))
                                            
                                            # Use unidecode to transliterate the speaker name
                                            tmp_speaker = unidecode(speaker.lower(), errors='ignore', replace_str='¿').title()

                                            if speaker == 'Second Life':
                                                first_name = None
                                            elif " " in tmp_speaker:
                                                tmp = (re.sub(r'\s+', ' ', tmp_speaker).strip()).split(' ')
                                                salutations = {"lady", "lord", "sir", "miss", "ms", "mr", "mrs", "dr", "prof", "the", "master", "mistress", "madam", "madame", "dame", "captain", "chief", "colonel", "general", "admiral", "officer", "agent", "dj", "jarl"}
                                                if all(part.isalnum() for part in tmp):
                                                    if tmp[0].lower() in salutations and len(tmp) > 1:
                                                        if clean_name(tmp[1]):
                                                            first_name = tmp[1]
                                                    elif clean_name(tmp[0]):
                                                        first_name = tmp[0]
                                            elif tmp_speaker.isalnum():
                                                if clean_name(tmp_speaker):
                                                    first_name = tmp_speaker

                                            # Remove leading numbers only if followed by a non-digit, and trailing numbers only if preceded by a non-digit
                                            if first_name is not None: first_name = re.sub(r'^\d+(?=\D)|(?<=\D)\d+$', '', first_name)

                                            # Replace known display name/gibberish name with replacement name in slang replacements
                                            if first_name in slang_replacements:
                                                first_name = slang_replacements[first_name]

                                            logging.warning(f"Avatar Name: {speaker_part}, UniDecode: {tmp_speaker} Result Speaker: {first_name}")

                                            if first_name:
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

                                            if "MultilingualNeural" not in thisvoice:
                                                message = re.sub(r'(£)(\S+|\s\S+|$)', r'\2 pounds sterling', message) # Fix currency before decoding in ASCII
                                                message = re.sub(r'£', r'pounds sterling ', message)
                                                message = re.sub(r'(¥)(\S+|\s\S+|$)', r'\2 yen', message)
                                                message = re.sub(r'¥', r'yen ', message)
                                                message = re.sub(r'\s+', ' ', message).strip()
                                                message = unidecode(message).strip()

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
                                                    to_cc = f"{first_name}¿ {message}" if OBSChatFiltered else f"{first_name}¿ {messageorg}"
                                                    print(f"{to_speak}")
                                                else:
                                                    to_speak = f"{first_name} {manner}: {message}"
                                                    to_cc = f"{first_name}: {message}" if OBSChatFiltered else f"{first_name}: {messageorg}"
                                                    print(f"{to_speak}")

                                                await update_chat(to_cc)

                                                # Break text up to allow faster encoding
                                                # Limit for SL Chat is 1023 bytes and for EdgeTTS is 4096 bytes
                                                parts = []
                                                limit = 256
                                                length = len(to_speak)
                                                if length > limit:
                                                    # split into sentances if text is too long and break
                                                    # the text up to encode and speak each part seperatly
                                                    sentances = re.finditer(r"\. .", to_speak)
                                                    indices = [m.start(0) for m in sentances]
                                                    if indices:
                                                        # length should be long enough but not too long for the second part to encode while first part is speaking
                                                        length = int(length/(1 + int(length/limit)))
                                                        #length = int(len(to_speak)/3)
                                                        i=0
                                                        for x in range(len(indices)):
                                                            pos = indices[x]
                                                            if i < pos and i <= length:
                                                                i = pos
                                                            elif i > length: break
                                                        parts = [to_speak[:1+i], to_speak[1+i:].strip()]
                                                    else: parts = [to_speak]
                                                else:
                                                    parts = [to_speak]
                                                for to_speak in parts:
                                                    # Wait until an output file is free
                                                    while speaker_active[output_file_counter]:
                                                        await asyncio.sleep(0.25)
                                                    # Speak text
                                                    if play_volume > 0:
                                                        speaker_active[output_file_counter] = 1
                                                        task1[output_file_counter] = asyncio.create_task(speak_text(to_speak, thisvoice, output_file_counter, chat_delta))
                                                        if speakers == 1: await task1[output_file_counter]
                                                        # Rotate to next output file
                                                        output_file_counter = (output_file_counter + 1) % speakers
                                                    #chat_delta = timedelta(seconds=0)
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
                                    elif last_user is not None or replay_chat == True:
                                        """ Read Text File Code """
                                        # Read any text file without SL timecodes using assigned name2voice as Narrator
                                        if replay_chat and last_user is None:
                                            speaker_part = "Narrator"
                                            thisvoice = None
                                            if name2voice:
                                                if speaker_part in name2voice:
                                                    thisvoice = name2voice[speaker_part]
                                            if speaker_part in name_cache:
                                                cached = name_cache[speaker_part]
                                                if isinstance(cached, tuple) and len(cached) == 3:
                                                    first_name, gender, thisvoice = cached
                                                else:
                                                    first_name = cached
                                            else: first_name = speaker_part
                                            if thisvoice is None:
                                                gender, thisvoice = guess_gender_and_voice(speaker_part)
                                                if gender:
                                                    logging.warning(f"Speaker {first_name} Gender set to {gender} and Assigned voice to {thisvoice}")
                                                    # Let's cashe this so we not check this ever damn time
                                                    name_cache[speaker_part] = (first_name, gender, thisvoice)
                                            last_voice = thisvoice
                                            last_user = first_name
                                        """ End Read Text File Code """
                                        message = line.strip()
                                        message = url2word(message).strip()
                                        message = spell_check_message(message)
                                        if "MultilingualNeural" not in last_voice:
                                            message = re.sub(r'(£)(\S+|\s\S+|$)', r'\2 pounds sterling', message) # Fix currency before decoding in ASCII
                                            message = re.sub(r'£', r'pounds sterling ', message)
                                            message = re.sub(r'(¥)(\S+|\s\S+|$)', r'\2 yen', message)
                                            message = re.sub(r'¥', r'yen ', message)
                                            message = re.sub(r'\s+', ' ', message).strip()
                                            message = unidecode(message).strip()
                                        if last_message != message and message:
                                            last_message = message
                                            print(f"{message}")
                                            if not replay_chat or last_user is not "Narrator":
                                                await update_chat(message) # we do not want the user's name appearing in the OBS chat multiple times, formatted wrongly, if they are quoting multiple lines
                                            else: await update_chat(f"{last_user}:" + ' ' + message)
                                            parts = []
                                            limit = 256
                                            length = len(message)
                                            if length > limit:
                                                # split into sentances if text is too long and break
                                                # the text up to encode and speak each part seperatly
                                                sentances = re.finditer(r"\. .", message)
                                                indices = [m.start(0) for m in sentances]
                                                if indices:
                                                    #length = int(len(message)/3)
                                                    length = int(length/(1 + int(length/limit)))
                                                    i=0
                                                    for x in range(len(indices)):
                                                        pos = indices[x]
                                                        if i < pos and i <= length:
                                                            i = pos
                                                        elif i > length: break
                                                    parts = [message[:1+i], message[1+i:].strip()]
                                                else: parts = [message]
                                            else:
                                                parts = [message]
                                            for message in parts:
                                                # Wait until an output file is free
                                                while speaker_active[output_file_counter]:
                                                    await asyncio.sleep(0.25)
                                                # Speak text
                                                if play_volume > 0:
                                                    speaker_active[output_file_counter] = 1
                                                    task1[output_file_counter] = asyncio.create_task(speak_text(message, last_voice, output_file_counter, chat_delta))
                                                    if speakers == 1: await [output_file_counter]
                                                    # Rotate to next output file
                                                    output_file_counter = (output_file_counter + 1) % speakers
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

                                window.stop_busy()
                            await asyncio.sleep(0.3) # Qt5 update_display might crash if we spam it too fast
                except FileNotFoundError:
                    logging.error(f"Log file not found: {log_file}")
                except IOError as e:
                    logging.error(f"Error reading log file IO Error: {e}")
                except Exception as e:
                    logging.error(f"Error reading log file Unexpected error: {e}")
            if replay_chat and log_read:
                print("There are no more lines to speak. Stop log reading or add new lines to the chat log to be spoken.")
                log_read = False
            await asyncio.sleep(1)
    except Exception as e:
        logging.error(f"Error in monitor_log: {e}")
        print(f"Error while monitoring log file: {e}")
    finally:
        print("Stopped monitoring log file.")
        shut_down_monitoring()

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
    """Request to stop the monitor_log task safely."""
    global request
    window.start_button.configure(text="Stopping Log Reading", text_color="#ffa1a1")
    request = 1

def shut_down_monitoring():
    """Stop the monitor_log task when work is done"""
    global monitor_task, monitor_loop
    if monitor_task is None:
        original_print("Log monitoring is not running.")
        return

    monitor_task.cancel()  # Cancel the task
    monitor_task = None    

    if monitor_loop is not None:
        monitor_loop.stop()  # Stop the event loop
        monitor_loop = None

    # Make sure that the playback threads will work properly after being started again
    pygame.mixer.music.stop()
    pygame.mixer.music.unload()

    # Clear website chat log
    global chat_messages
    chat_messages.clear()
    # Turn off busy signal on main window
    window.stop_busy()
    # Give threads time to stop
    time.sleep(0.25)
    # Give back control
    global request, thread, readloop
    readloop = False
    request = 0
    thread = 0
    window.start_button.configure(text="Start Log Reading", text_color="#d1d1d1")

def update_lists():
    """Update the IgnoreList and SpeakOnlyList from the UI."""
    print("Updating IgnoreList and SpeakOnlyList...")
    update_global("IgnoreList", [item.strip().lower() for item in window.ignore_list_input.get("1.0", "end").split(',')])
    update_global("SpeakOnlyList", [item.strip().lower() for item in window.onlytalk_list_input.get("1.0", "end").split(',')])

async def speak_test_message():
    """Speak a test message."""
    test_message = "This is a Test message from the Second Life Chat to Speech program."
    task0 = asyncio.create_task(speak_text(test_message, "en-US-EmmaMultilingualNeural", speakers, timedelta(seconds=0), True))
    await task0

if __name__ == "__main__":
    if create_default_config('config.ini'):
        logging.error("Default config.ini created. Please edit it with your settings.")
        sys.exit(0)

    config = ConfigParser()
    config.read('config.ini')

    # Parse configuration values
    global Enable_Spelling_Check, IgnoreList, OBSChatFiltered, EdgeVoicem, SpeakOnlyList#, speakers, replay_chat, follow_timestamps, record, verbose
    log_file_path = config.get('Settings', 'log_file_path')
    Enable_Spelling_Check = config.getboolean('Settings', 'enable_spelling_check')
    IgnoreList = [item.strip() for item in config.get('Settings', 'ignore_list', fallback='').split(',')]
    SpeakOnlyList = [item.strip() for item in config.get('Settings', 'speak_only_list', fallback='').split(',')]
    OBSChatFiltered = config.getboolean('Settings', 'obs_chat_filtered')
    EdgeVoice = config.get('Settings', 'edge_tts_llm')
    min_char = config.getint('Settings', 'min_char', fallback=2)
    speakers = config.getint('Settings', 'concurrent_edge_tts_threads', fallback=3)
    if speakers <= 0: speakers = 1
    elif speakers > 12: speakers = 12
    replay_chat = config.getint('Settings', 'replay_chat', fallback=0)
    follow_timestamps = config.getint('Settings', 'follow_timestamps', fallback=1)
    record = config.getint('Settings', 'record', fallback=0)
    verbose = config.getint('Settings', 'verbose', fallback=0)
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
        #global readloop
        #readloop = False
        stop_monitoring()

    last_toggle_time = 0
    def toggle_monitoring():
        """Toggle monitoring based on the button state."""
        global last_toggle_time
        current_time = time.time()
        if current_time - last_toggle_time < 0.2:  # Check if 0.2 seconds have passed
            return

        last_toggle_time = current_time
        if window.start_button.cget("text") == "Start Log Reading":
            start_monitoring_ui()
        else:
            stop_monitoring_ui()
    
    def toggle_recording():
        """Toggle recording based on the button state."""
        global record, stamp_read
        if window.record_button.cget("text") == "Record Audio":
            if name_recording():
                window.record_button.configure(text = "Stop Recording", text_color="#ff8080")
                stamp_read = False
                record = 1
        else:
            record = 0
            window.record_button.configure(text = "Record Audio", text_color="#d1d1d1")
            print(f"Stopped recording to file: .\{recording}")
    
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
    window.record_button.configure(command=toggle_recording)
    # audio_device_menu
    window.audio_device_menu.configure(command=lambda value: set_audio_device(value))
  
    # speak_text("Starting up! Monitoring log file...")
    window.test_button.configure(command=lambda: asyncio.run(speak_test_message()))    # Override the print function to append to window.text_display
 
    original_print = print  # Keep a reference to the original print function
    def custom_print(*args, **kwargs):
        message = " ".join(map(str, args))  # Combine all arguments into a single string
        try:
            if 'window' in globals() and hasattr(window, 'text_display') and window.winfo_exists():
                window.update_display(message)
        except Exception:
            # Window is destroyed or not available, just use original print
            pass

        original_print(*args, **kwargs)  # Optionally, call the original print function

    # Replace the built-in print function with the custom one
    builtins.print = custom_print

    print("Second Life Chat log to Speech version 2.0.0-beta2, by Jara Lowell")
    
    if record == True:
        toggle_recording()
    
    # Start the window application event loop
    try:
        window.mainloop()
    except Exception as e:
        logging.error(f"Error in main loop: {e}")
