import os

os.system(
    "pyinstaller --noconfirm --onefile --windowed "
    "--name CryptixCore "
    "--icon=cryptix.ico "
    "--add-data \"cryptix.ico;.\" "
    "main.py"
)