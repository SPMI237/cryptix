# build.py

import os

os.system(
    "pyinstaller --noconfirm --onefile --windowed "
    "--name CryptixCore "
    "--icon=cryptix.ico "
    "--add-data \"cryptix.ico;.\" "
    "--add-data \"audio;audio\" "
    "main.py"
)
