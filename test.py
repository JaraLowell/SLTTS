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

tmp = "ᴄʜʀɪs".lower()

print(f"unicodedata : {ascii_name(tmp)}")
toprnt = ""
for char in tmp:
  print(f"{char} = {unicodedata.name(char)}")
