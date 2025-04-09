#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Needs > pip install edge-tts language_tool_python asyncio regex pygame unicodedata
import asyncio
import os
import time
import pygame
import regex as re
from edge_tts import Communicate
import gc
import unicodedata

# Initialize pygame mixer globally
pygame.mixer.init()
pygame.mixer.music.set_volume(0.5)  # Set volume to 50%

# Flag to indicate whether audio is currently playing
is_playing = False
last_message = None
last_user = None
last_chat = 0
Enable_Spelling_Check = True

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

def spell_check_message(message):
    global Enable_Spelling_Check
    message = message.strip()

    if not message:
        return ""  # Return empty string if message is empty
    elif len(message) == 1:
        symbol_to_word = {
                "?": "Question mark", "!": "Exclamation mark", ".": "Dot", ",": "Comma", ":": "Colon", ";": "Semicolon",
                "-": "Dash", "+": "Plus", "=": "Equals", "*": "Asterisk", "/": "Slash", "\\": "Backslash", "@": "At symbol",
                "#": "Hash", "$": "Dollar sign", "%": "Percent", "^": "Caret", "&": "Ampersand", "(": "Left parenthesis",
                ")": "Right parenthesis", "[": "Left bracket", "]": "Right bracket", "{": "Left brace", "}": "Right brace",
                "<": "Less than", ">": "Greater than", "|": "Pipe", "~": "Tilde", "`": "Backtick",
            }
        return symbol_to_word.get(message, message) # Return the word for the symbol or the symbol itself

    # Remove unwanted characters while preserving letters, punctuation, spaces, digits, and math symbols
    message = re.sub(r'[^\p{L}\d\s\p{P}+\-*/=<>^|~]', '', message, flags=re.UNICODE).strip()

    # Simplify Second Life map URLs
    message = re.sub(r'http://maps\.secondlife\.com/secondlife/([^/]+)/\d+/\d+/\d+', lambda match: match.group(1).replace('%20', ' '), message)

    # Replace Second Life agent or group links with "Second Life Link"
    message = re.sub(r'secondlife:///app/(agent|group)/[0-9a-fA-F\-]+/about', r'\1 link', message)

    # Simplify general URLs to their domain
    message = re.sub(r'https?://(?:www\.)?([^/\s]+).*', r'\1 link', message)

    # Collapse repeated characters (3 or more)
    message = re.sub(r'(.)\1{2,}', r'\1', message)

    # Replace hyphen with "minus" or space based on context
    message = re.sub(r'(?<=\d)-(?=\d|\=)', ' minus ', message)
    message = re.sub(r'(?<=\w)-(?=\w)', ' ', message)

    # Replace common abbreviations v3.1 slang replacements
    slang_replacements = {
        "gonna": "going to", "gotta": "got to", "wanna": "want to", "kinda": "kind of",
        "sorta": "sort of", "shoulda": "should have", "coulda": "could have", "tough": "though",
        "woulda": "would have", "gotcha": "got you", "lemme": "let me", "gimme": "give me",
        "brb": "be right back", "omg": "oh my god", "lol": "laughing out loud", "sec": "second",
        "thx": "thanks", "ty": "thank you", "np": "no problem", "idk": "I don't know",
        "afk": "away from keyboard", "btw": "by the way", "hehe": "laughs", "hihi": "laughs",
        "rp": "role play", "sl": "Second Life", "ctf": "Capture the Flag", "kurrii": "Kurr-rie",
        "ooc": "Out of Character", "ic": "In Character", "tal ": "Taal", "gor": "Gor"
    }
    for slang, replacement in slang_replacements.items():
        message = re.sub(rf'\b{slang}\b', replacement, message, flags=re.IGNORECASE)

    # Perform spelling check if enabled
    if Enable_Spelling_Check:
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

    return message

async def speak_text(text2say):
    """Use Edge TTS to speak the given text."""
    global is_playing

    # Wait until the current audio finishes
    while is_playing:
        await asyncio.sleep(0.25)

    is_playing = True  # Indicate audio is playing

    try:
        # Generate and save the audio file
        output_file = "output.mp3"
        # options are: Female en-US-AvaMultilingualNeural or en-US-EmmaMultilingualNeural
        #              Male   en-US-AndrewMultilingualNeural or en-US-BrianMultilingualNeural
        try:
            await Communicate(text = text2say, voice='en-US-EmmaMultilingualNeural', rate = '+8%', pitch = '+0Hz').save(output_file)
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

def monitor_log(log_file):
    print("Monitoring log file... Press Ctrl+C to stop.")
    asyncio.run(speak_text("Starting up! Monitoring log file..."))
    global last_message, last_user, IgnoreList, last_chat

    # Start at the end of the file
    last_position = 0
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as file:
            file.seek(0, os.SEEK_END)
            last_position = file.tell()

    last_mod_time = os.path.getmtime(log_file)
    last_gc_time = time.time()
    name_cache = {}

    try:
        while True:
            current_time = time.time()
            current_mod_time = os.path.getmtime(log_file)

            # Perform garbage collection every 5 minutes
            if current_time - last_gc_time >= 300:
                gc.collect()
                last_gc_time = current_time

            if current_mod_time != last_mod_time:
                last_mod_time = current_mod_time
                with open(log_file, 'r', encoding='utf-8') as file:
                    file.seek(last_position)
                    new_lines = file.readlines()
                    last_position = file.tell()
                    for line in new_lines:
                        line = line.strip()
                        if line:
                            # Extract the speaker and message
                            # Expected line format: [timestamp] display name (legacy.name): message
                            # This works correct for FireStorm and Lindenlabs viewer. Radegast is different and for /me dues not put a : after the namme so breaks emotes
                            try:
                                if line.startswith("[20"):
                                    isemote = False
                                    isrepat = False
                                    # Get tje timestamp and the rest of the line
                                    timestamp, rest = line.split(']', 1)
                                    # Get the name
                                    speaker_part, message = rest.split(':', 1)
                                    speaker_part = speaker_part.strip()
                                    message = message.strip()
                                    first_name = None
                                    # IgnoreList
                                    if speaker_part in name_cache:
                                        first_name = name_cache[speaker_part]
                                    elif speaker_part.lower() not in IgnoreList:
                                        if '(' in speaker_part and ')' in speaker_part:
                                            # Get legacy name format
                                            speaker = speaker_part.split('(')[1].split(')')[0].strip()  # Extract the part inside parentheses
                                            first_name = speaker.split('.')[0].capitalize()  # Extract the first part before the dot
                                            # Make speaker_part withouth ( and ) and the legacy name
                                            speaker = speaker_part.split('(')[0].strip()
                                        else:
                                            speaker = speaker_part

                                        if speaker == 'Second Life':
                                            # Ignore Second Life system messages as a name
                                            first_name = None
                                        elif " " in speaker:
                                            # Check if the first two parts are alpha numeric
                                            tmp = speaker.split(' ')
                                            salutations = {"lady", "lord", "sir", "miss","ms", "mr", "mrs", "dr", "prof"}  # Add more as needed
                                            if all(part.isalnum() for part in tmp):
                                                if tmp[0].lower() in salutations and len(tmp) > 1:
                                                    if clean_name(tmp[1]):
                                                        first_name = tmp[1].capitalize()
                                                elif clean_name(tmp[0]):
                                                    first_name = tmp[0].capitalize()
                                        elif speaker.isalnum():
                                            # If the name is alpha numeric, use it as the first name
                                            if clean_name(speaker):
                                                first_name = speaker.capitalize()

                                        # Letc cache the name for later use
                                        if first_name:
                                            # Remove any trailing digits from the first name
                                            first_name = re.sub(r'(?<!\p{L})\d+$', '', first_name)
                                            name_cache[speaker_part] = first_name

                                    if first_name:
                                        if last_user != first_name:
                                            # Update the last user if it's different from the current one
                                            last_user = first_name
                                            isrepat = False
                                        elif time.time() - last_chat >= 120:
                                            # Check if more than 5 minutes have elapsed since same speaker last spoke
                                            isrepat = False
                                        else:
                                            isrepat = True
                                        # if the message starts with "/me", remove it
                                        if message.startswith("/me"):
                                            message = message[3:].strip()
                                            isemote = True
                                            isrepat = False
                                        if message.startswith("shouts: "):
                                            message = message[8:].strip()
                                        if message.startswith("whispers: "):
                                            message = message[10:].strip()
                                        # Do a spell check on the message
                                        message = spell_check_message(message)

                                        if last_message == message:
                                            message = ''  # Clear the message if it's the same as the last one

                                        # Check if the message is not empty after spell check
                                        if message:
                                            last_message = message  # Update the last message
                                            if isrepat:
                                                to_speak = f"{message}"
                                                print(f"           {message}")  # Debug print
                                            elif isemote:
                                                to_speak = f"{first_name} {message}"
                                                print(f"[{time.strftime('%H:%M:%S', time.localtime())}] {to_speak}")  # Debug print
                                            else:
                                                to_speak = f"{first_name} says: {message}"
                                                print(f"[{time.strftime('%H:%M:%S', time.localtime())}] {to_speak}")  # Debug print
                                            asyncio.run(speak_text(to_speak))
                                            last_chat = time.time()
                                    else:
                                        last_user = None  # Reset last user if no valid name found
                                        print(f"[{time.strftime('%H:%M:%S', time.localtime())}] IGNORED! {speaker_part}: {message}")  # Debug print
                                elif last_user != None:
                                    message = line.strip()
                                    # chech the string length and if it is a number or not
                                    message = spell_check_message(message)
                                    if last_message != message and message:
                                        last_message = message
                                        print(f"           {message}")  # Debug print
                                        asyncio.run(speak_text(message))
                                else:
                                    print(f"[{time.strftime('%H:%M:%S', time.localtime())}] IGNORED No TimmeTamp!: {line.strip()}")
                            except ValueError:
                                print(f"[{time.strftime('%H:%M:%S', time.localtime())}] ERROR! Could not parse line: {line.strip()}")
            time.sleep(1)  # Poll every second
    except KeyboardInterrupt:
        print("Stopped monitoring.")

if __name__ == "__main__":
    log_file_path = r"D:\SecondLife\Logs\ALAvatar.Name\chat.txt"
    Enable_Spelling_Check = False  # Set to True to enable spelling check or False to Disable it
    IgnoreList = ["zcs", "gm", "murr", "dina"] # Object names we want to ignore in lower case

    if Enable_Spelling_Check:
        import language_tool_python
        # Initialize the LanguageTool instance
        tool = language_tool_python.LanguageTool('en-US')

    monitor_log(log_file_path)
