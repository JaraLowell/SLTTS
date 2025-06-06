import unicodedata
import regex as re
from unidecode import unidecode

def ascii_name(name):
    # Remove all non-letter characters except spaces (\d\s- to allow hyphenated names and numbers)
    name = re.sub(r'[^\p{L}\s]', '', name)
    # Transliterate to ASCII
    name = unidecode(name, errors='ignore', replace_str='')
    # Remove extra spaces and capitalize each word
    name = name.strip().title()
    return name

tmp = "Tʜᴇ Cᴏɪɴ Gɪʀʟ¿".lower()

print(f"unicodedata : {unidecode(tmp, errors='ignore', replace_str='').title()}")
toprnt = ""

script_names = set()
for char in tmp:
    try:
        script_name = unicodedata.name(char)
    except ValueError:
        script_name = "Unknown" # Handle characters without a name
        continue

    # as a test removing "WITH" in script_name or 
    if "SMALL CAPITAL" in script_name:
        # Seriously ! ŦorestŞheŨrt is Latin ... but with stroke F, cedilla S and tilde U
        script_name = script_name.split()[0] + ' Extended'
    elif "DIGIT" in script_name:
        # We do want to keep numbers as LATIN, or thay get aded as DIGIT
        script_name = 'LATIN'
    else:
        script_name = script_name.split()[0]

    if script_name not in script_names:
        script_names.add(script_name)

    print(f"{char} = {script_name} ({unicodedata.name(char)})")

print(f"Script names: {', '.join(sorted(script_names))}")
# print(f"{char} = {unicodedata.name(char)}")
