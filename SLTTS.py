#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Needs > pip install edge-tts language_tool_python asyncio regex pygame
import asyncio
import os
import time
import pygame
import regex as re
from edge_tts import Communicate
import language_tool_python
audio_device = None

'''
import pygame._sdl2 as sdl2
# List available audio devices
pygame.mixer.pre_init()
pygame.init()
print("Available audio devices:")
devs = sdl2.audio.get_audio_device_names(False)
for dev in devs:
    print(dev)

audio_device = r"CABLE-B Input (VB-Audio Cable B)"
'''

# Initialize pygame mixer globally
pygame.mixer.init(devicename=audio_device)
pygame.mixer.music.set_volume(0.5)  # Set volume to 50%

# Initialize the LanguageTool instance
tool = language_tool_python.LanguageTool('en-US')

# Flag to indicate whether audio is currently playing
is_playing = False
last_message = None
last_user = None

def spell_check_message(message):
    """Remove non-alphabetical characters while preserving punctuation and spaces."""
    # Keep letters (\p{L}), punctuation, and spaces
    cleaned_message = re.sub(r'[^\p{L}\d\s\p{P}]', '', message, flags=re.UNICODE)
    message = cleaned_message.strip()

    """Collapse repeated characters."""
    # Replace sequences of the same character (3 or more) with a single character
    message = re.sub(r'(.)\1{2,}', r'\1', message)

    """RReplace some common abbreviations."""
    list_slang = {
        "gonna": "going to",
        "gotta": "got to",
        "wanna": "want to",
        "kinda": "kind of",
        "sorta": "sort of",
        "shoulda": "should have",
        "coulda": "could have",
        "woulda": "would have",
        "gotcha": "got you",
        "lemme": "let me",
        "gimme": "give me",
        "brb:": "be right back",
        "omg": "oh my god",
        "lol": "laughing out loud",
        "afk": "away from keyboard",
        "btw": "by the way",
        "hehe": "laughs",
        "hihi": "laughs",
        " rp": " role play",
        " sl": "Second Life",
        "ctf": "Capture the Flag",
    }
    for slang, replacement in list_slang.items():
        message = re.sub(rf'\b{slang}\b', replacement, message, flags=re.IGNORECASE)

    """Check and correct spelling in the message."""
    exceptions = {"Gor", "Kurrii", "Tal", "Gorean"}
    matches = tool.check(message)
    filtered_matches = [
        match for match in matches
        if not any(exception.lower() in match.context.lower() for exception in exceptions)
    ]
    corrected_message = language_tool_python.utils.correct(message, filtered_matches)

    # Ensure exception words are capitalized in the final result
    for exception in exceptions:
        corrected_message = re.sub( rf'\b{exception.lower()}\b', exception, corrected_message, flags=re.IGNORECASE )

    return corrected_message

async def speak_text(text):
    """Use Edge TTS to speak the given text."""
    global is_playing
    while is_playing:
        await asyncio.sleep(0.25)  # Wait until the current audio finishes

    is_playing = True  # Set the flag to indicate audio is playing

    # Create a temporary file for the audio
    output_file = "output.mp3"
    communicate = Communicate(text=text)
    await communicate.save(output_file)

    # Play the audio file
    pygame.mixer.music.load(output_file)
    pygame.mixer.music.play()

    # Wait for the audio to finish playing
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    pygame.mixer.music.unload()

    # Clean up and reset the flag
    is_playing = False

def monitor_log(log_file):
    print("Monitoring log file... Press Ctrl+C to stop.")
    global last_message, last_user

    # Start at the end of the file
    last_position = 0
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as file:
            file.seek(0, os.SEEK_END)
            last_position = file.tell()

    last_mod_time = os.path.getmtime(log_file)

    try:
        while True:
            current_mod_time = os.path.getmtime(log_file)
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
    log_file_path = r"D:\SecondLife\Logs\nadia_windlow\chat.txt"
    monitor_log(log_file_path)
