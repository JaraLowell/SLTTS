# SLTTS
Grab the second life chat log and turns it to Edge TTS Voice near live unless it a realy realy big chat line, then can take a second or two.
By Jaralowell

# Build in Python v3.10.10
![Language](https://img.shields.io/badge/language-Python-blue.svg)

Make sure to pip install the needed libraries:
* edge-tts 
* language_tool_python (if you wish to use the grammer/spell check library)
* asyncio
* regex
* pygame
* aiohttp (if you wish to use the OBS (html web output) version)
* PyQt5 
* emoji

Then edit line 180, to reflect where your chat.log file is located.
* log_file_path = r"D:\SecondLife\Logs\sl_resident\chat.txt"
To reflect where your log is

Setting up your viewer:
* In Preferences under Privacy, find Logs and Transcripts. There Enable save nearby chat trasnscripts. And make sure it set to Log and transcripts.
* Under General enable Usernames, and View Display names. And make sure to disable Lecgacy names instead of usernames.
* Now under Network & Files, in the Directory tab. You can see where the Conversation logs are stored.
