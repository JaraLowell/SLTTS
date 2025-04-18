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

Then config.ini, to reflect where your chat.log file is located.
* log_file_path = r"D:\SecondLife\Logs\sl_resident\chat.txt"
  - To reflect where your log is

Setting up your viewer:
* Check where your logs are
  - You can find this in preferences under Network & Files, then the Directories tab. Conversation logs location.
* Check you log local chat
  - You can find this in preferences under Privacy, then Logs & Transcripts. Make sure the Save nearby chat transcript is turned on and you have Log and transcripts enabled.
* Legacy names vs Display names. The program amuses legacy names or if both n in passes the one that readable and can be spoken by TTS. If you only log Display names, some text lies might not be spoken due the name being gibberish and unspeakable.
  - So under preferences and then General make sure you have both Username and view display Names both on.
