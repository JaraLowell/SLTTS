#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Needs > pip install edge-tts language_tool_python asyncio regex pygame
import asyncio
import os
import time
import pygame
import regex as re
from edge_tts import Communicate
import gc

# Initialize pygame mixer globally
pygame.mixer.init()
pygame.mixer.music.set_volume(0.5)  # Set volume to 50%

# Flag to indicate whether audio is currently playing
is_playing = False
last_message = None
last_user = None
Enable_Spelling_Check = True

def spell_check_message(message):
    global Enable_Spelling_Check

    # Remove unwanted characters while preserving letters, punctuation, spaces, digits, and math symbols
    message = re.sub(r'[^\p{L}\d\s\p{P}+\-*/=<>^|~]', '', message, flags=re.UNICODE).strip()

    # Collapse repeated characters (3 or more)
    message = re.sub(r'(.)\1{2,}', r'\1', message)

    # Simplify Second Life map URLs
    message = re.sub(
        r'http://maps\.secondlife\.com/secondlife/([^/]+)/\d+/\d+/\d+',
        lambda match: match.group(1).replace('%20', ' '),
        message
    )

    # Simplify general URLs to their domain
    message = re.sub(r'https?://(?:www\.)?([^/\s]+).*', r'\1', message)

    # Replace hyphen with "minus" or space based on context
    message = re.sub(r'(?<=\d)-(?=\d|\=)', ' minus ', message)
    message = re.sub(r'(?<=\w)-(?=\w)', ' ', message)

    # Replace common abbreviations
    slang_replacements = {
        "gonna": "going to", "gotta": "got to", "wanna": "want to", "kinda": "kind of",
        "sorta": "sort of", "shoulda": "should have", "coulda": "could have",
        "woulda": "would have", "gotcha": "got you", "lemme": "let me", "gimme": "give me",
        "brb:": "be right back", "omg": "oh my god", "lol": "laughing out loud",
        "afk": "away from keyboard", "btw": "by the way", "hehe": "laughs", "hihi": "laughs",
        " rp": " role play", " sl": " Second Life", "ctf": "Capture the Flag",
        "ooc": "Out of Character", " ic": "In Character"
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
        await Communicate(text = text2say, voice='en-US-EmmaMultilingualNeural', rate = '+8%', pitch = '+0Hz').save(output_file)

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
    global last_message, last_user, IgnoreList

    # Start at the end of the file
    last_position = 0
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as file:
            file.seek(0, os.SEEK_END)
            last_position = file.tell()

    last_mod_time = os.path.getmtime(log_file)
    last_gc_time = time.time()

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
                            # Example line format: [timestamp] display name (legacy.name): message
                            try:
                                if '[' in line and ']' in line:
                                    isemote = False
                                    isrepat = False
                                    # Get tje timestamp and the rest of the line
                                    timestamp, rest = line.split(']', 1)
                                    # Get the name
                                    speaker_part, message = rest.split(':', 1)
                                    first_name = None
                                    # IgnoreList
                                    if (speaker_part.strip()).lower() not in IgnoreList:
                                        if '(' in speaker_part and ')' in speaker_part:
                                            # Using legacy name format
                                            speaker = speaker_part.split('(')[1].split(')')[0].strip()  # Extract the part inside parentheses
                                            first_name = speaker.split('.')[0].capitalize()  # Extract the first part before the dot
                                        else:
                                            # Using display name format but only if it has 2 words tha are alphabetical
                                            speaker = speaker_part.strip()
                                            tmp = speaker.split(' ')
                                            if tmp[0] == 'Second' and tmp[1] == 'Life':
                                                first_name = None  # Ignore Second Life system messages as a name
                                            elif len(tmp) == 2:
                                                if tmp[0].isalpha() and tmp[1].isalpha():
                                                    first_name = tmp[0].capitalize()
                                            elif len(tmp) == 1:
                                                if tmp[0].isalpha():
                                                    first_name = tmp[0].capitalize()
                                    else:
                                        print(f"!Ignored: {speaker_part.strip()}")  # Debug print

                                    if first_name:
                                        if last_user != first_name:
                                            last_user = first_name  # Update the last user
                                            isrepat = False
                                        else:
                                            isrepat = True
                                        # Get the message part and remove leading/trailing spaces
                                        message = message.strip()
                                        # if the message starts with "/me", remove it
                                        if message.startswith("/me"):
                                            message = message[3:].strip()
                                            isemote = True
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
                                    else:
                                        last_user = None  # Reset last user if no valid name found
                                else:
                                    message = line.strip()
                                    message = spell_check_message(message)
                                    if last_message != message and message:
                                        last_message = message
                                        if last_user != None:
                                            print(f"           {message}")  # Debug print
                                            asyncio.run(speak_text(message))
                            except ValueError:
                                print(f"Could not parse line: {line}")  # Debug print
            time.sleep(1)  # Poll every second
    except KeyboardInterrupt:
        print("Stopped monitoring.")

if __name__ == "__main__":
    log_file_path = r"D:\SecondLife\Logs\sl_resident\chat.txt"
    Enable_Spelling_Check = False  # Set to True to enable spelling check or False to Disable it
    IgnoreList = ["zcs", "gm", "murr"] # Object names we want to ignore in lower case

    if Enable_Spelling_Check:
        import language_tool_python
        # Initialize the LanguageTool instance
        tool = language_tool_python.LanguageTool('en-US')

    monitor_log(log_file_path)
