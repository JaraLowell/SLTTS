# SL TTS your Chat to Speech using Microsoft Edge TTS

Provides a tool to grab the Second Life chat log and turns it to Edge TTS Voice near live unless it a realy realy big chat line, then can take a second or two.
By Jaralowell

- Watch Chat in a easy UI
- Have an internal webpage where chat shows on, for OBS
- Hear what people say, almost live
- Multiple voice options for Machinema
- Turn Second Life Abbreviation to real words

## Build in Python v3.10.10
![Language](https://img.shields.io/badge/language-Python-blue.svg)

Libraries to Install via pip if using Python
```
pip install customtkinter pygame edge-tts regex aiohttp emoji
```

Or use the Released executable made for Windows 64bit platform.

Executables made with pyinstaller might some times returns a false positive by an antivirus program. Make sure to have for that an folder thats ignored by sush and disable while unpacking or downloading.

## Configure and Setup

The config.ini:
to reflect where your chat.log file is located.
```
[Settings]
log_file_path = D:\SecondLife\Logs\SLAvatar_Name\chat.txt
edge_tts_llm = en-US-EmmaMultilingualNeural
ignore_list = zcs, gm
obs_chat_filtered = True
```
* log_file_path
  - The location of your Second Life Log File
* edge_tts_llm
  - The voice to use to speak.
    options are: Female en-US-AvaMultilingualNeural or en-US-EmmaMultilingualNeural
                 Male   en-US-AndrewMultilingualNeural or en-US-BrianMultilingualNeural
    It is higly adviced to use a Multilingual voice in seccond life. As if a user writes somting that the llm detects as a language it cant speak. it wont say noting at all
* enable_spelling_check
  - Enable (True) or Disbale (False) Spell(grammer) checking. Might not always have the results we want.
* ignore_list
  - List of names that should not be spoken. Huds, or objects in world. Or namme the object in world
  - Suports also Starts with, for example Talking Object v1, one could put in this line Talking Object*
* obs_chat_filtered
  - Pass the original chat to obs or the adjusrted one (True or False)

Second Life Viewer Settings:

* Check where your logs are
  - You can find this in preferences under Network & Files, then the Directories tab. Conversation logs location.
* Check you log local chat
  - You can find this in preferences under Privacy, then Logs & Transcripts. Make sure the Save nearby chat transcript is turned on and you have Log and transcripts enabled.
* Legacy names vs Display names. The program amuses legacy names or if both n in passes the one that readable and can be spoken by TTS. If you only log Display names, some text lies might not be spoken due the name being gibberish and unspeakable.
  - So under preferences and then General make sure you have both Username and view display Names both on.

Optional the slangreplce.json
```
{
    "afk": "away from keyboard"
}
```
An list of Abbreviation you seek to replace, each line ends with a , except the last one.

Additionally one can make a name2voice.json file in the programs folder
```
{
    "Avatar Name (as how it is logged)": "Edge Voice to Use"
}
```
a List of names you want to assign a Edge Voice to, each line ends with a , except the last one.
