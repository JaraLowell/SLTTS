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
import unicodedata

from aiohttp import web
from datetime import datetime
import html

# Initialize pygame mixer globally
pygame.mixer.init()
pygame.mixer.music.set_volume(0.75)  # Set volume to 50%

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
    message = re.sub(r'[^\p{L}\d\s\p{P}+\-*/=<>^|~]', '', message, flags=re.UNICODE)  # Remove unsupported characters
    message = re.sub(r'\s+', ' ', message).strip()  # Replace multiple spaces with a single space

    # Simplify Second Life map URLs
    message = re.sub(r'http://maps\.secondlife\.com/secondlife/([^/]+)/\d+/\d+/\d+', lambda match: match.group(1).replace('%20', ' '), message)

    # Replace Second Life agent or group links with "Second Life Link"
    message = re.sub(r'secondlife:///app/(agent|group)/[0-9a-fA-F\-]+/about', lambda m: f"{m.group(1).capitalize()} Link", message)

    # Simplify general URLs to their domain
    message = re.sub(r'(https?://(?:www\.)?([^/\s]+)[^\s]*)', r'\2 link', message)

    # Collapse repeated characters (3 or more)
    message = re.sub(r'(.)\1{2,}', r'\1', message)

    # Replace hyphen with "minus" or space based on context
    message = re.sub(r'(?<=\d)-(?=\d|\=)', ' minus ', message)
    message = re.sub(r'(?<=\w)-(?=\w)', ' ', message)

    # Replace common abbreviations v3.2 slang replacements
    slang_replacements = {
        "gonna": "going to", "gotta": "got to", "wanna": "want to", "kinda": "kind of",
        "sorta": "sort of", "shoulda": "should have", "coulda": "could have", "tough": "though",
        "woulda": "would have", "gotcha": "got you", "lemme": "let me", "gimme": "give me",
        "brb": "be right back", "omg": "oh my god", "lol": "laughing out loud", "sec": "second",
        "thx": "thanks", "ty": "thank you", "np": "no problem", "idk": "I don't know",
        "afk": "away from keyboard", "btw": "by the way", "hehe": "laughs", "hihi": "laughs",
        "rp": "role play", "sl": "Second Life", "ctf": "capture the flag", "kurrii": "kurr-rie",
        "ooc": "out of character", "ic": "in character", "tal": "Tal.", "gor": "Gor",
        "wb": "welcome back", "omw": "on my way", " :3": " kitty face", "rl": "real life",
        "imo": "in my opinion", "imho": "in my humble opinion", "smh": "shaking my head"
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

    if len(message) > 4:
        message = message[0].upper() + message[1:]

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
            # await Communicate(text = text2say, voice='en-US-EmmaMultilingualNeural', rate = '+8%', pitch = '+0Hz').save(output_file)
            await Communicate(text = text2say, voice='en-IE-EmilyNeural', rate = '+12%', pitch = '-4Hz').save(output_file)
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
    print(f"Client connected to SSE from {request.remote}")
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
    finally:
        try:
            await response.write_eof()
        except ConnectionResetError:
            pass

    # Close the response stream
    return response

async def chat_page_handler(request):
    """Serve the chat page with SSE integration."""
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
                max-width: 45%; /* Optional: Limit the width of the box to 80% of the container */
                word-wrap: break-word; /* Ensure long words or URLs wrap to the next line */
                text-shadow: -1px -1px 0 #00000080, 1px -1px 0 #00000080, -1px 1px 0 #00000080, 1px 1px 0 #00000080, 1px 1px 1px #000000, 0 0 1em #000000, 0 0 0.2em #000000;
                transition: transform 0.5s ease, opacity 0.5s ease;
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
    return web.Response(text=html_content, content_type='text/html')

async def start_server():
    """Start the internal web server."""
    app = web.Application()
    app.router.add_get('/', chat_page_handler)  # Serve the chat page
    app.router.add_get('/sse', sse_handler)  # Serve the SSE endpoint
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    print("Server started at http://localhost:8080 Use this URL in OBS via a browser source.")

# Modify the monitor_log function to call update_chat
async def monitor_log(log_file):
    print("Monitoring log file... Press Ctrl+C to stop.")
    await speak_text("Starting up! Monitoring log file...")
    global last_message, last_user, IgnoreList, last_chat, OBSChatFiltered

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
                            try:
                                if line.startswith("[20"):
                                    isemote = False
                                    isrepat = False
                                    # Get the timestamp and the rest of the line
                                    timestamp, rest = line.split(']', 1)
                                    speaker_part, message = rest.split(':', 1)
                                    speaker_part = speaker_part.strip()
                                    message = message.strip()
                                    messageorg = message
                                    first_name = None
                                    # IgnoreList
                                    if speaker_part in name_cache:
                                        first_name = name_cache[speaker_part]
                                    elif speaker_part.lower() not in IgnoreList:
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
                                    else:
                                        last_user = None
                                        print(f"[{time.strftime('%H:%M:%S', time.localtime())}] IGNORED! {speaker_part}: {message}")
                                elif last_user != None:
                                    message = line.strip()
                                    message = spell_check_message(message)
                                    if last_message != message and message:
                                        last_message = message
                                        print(f"           {message}")
                                        await update_chat(last_user + ' ' + message)
                                        await speak_text(message)
                                else:
                                    print(f"[{time.strftime('%H:%M:%S', time.localtime())}] IGNORED No Timestamp!: {line.strip()}")
                            except ValueError:
                                print(f"[{time.strftime('%H:%M:%S', time.localtime())}] ERROR! Could not parse line: {line.strip()}")
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Stopped monitoring.")

if __name__ == "__main__":
    # The location of your Second Life Log File
    log_file_path = r"D:\SecondLife\Logs\nadia_windlow\chat.txt"
    # Enable or Disbale Spell(grammer) checking. MMight not always have the results we want.
    Enable_Spelling_Check = False
    # List of names that should not be spoken. Huds, or objects in world. Or namme the object in world like object' so there a non ascii character at the end
    IgnoreList = ["zcs", "gm", "murr", "dina", "mama-allpa (f) v3.71"]
    # Pass the original chat to obs or the adjusrted one
    OBSChatFiltered = True

    if Enable_Spelling_Check:
        import language_tool_python
        tool = language_tool_python.LanguageTool('en-US')

    loop = asyncio.get_event_loop()
    try:
        # Start the server and monitor log tasks
        loop.create_task(start_server())
        loop.run_until_complete(monitor_log(log_file_path))
    except KeyboardInterrupt:
        print("KeyboardInterrupt received. Shutting down...")
    finally:
        # Cancel all running tasks and close the loop
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        loop.close()
        print("Event loop closed.")
