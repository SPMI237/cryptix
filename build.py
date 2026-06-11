import os

os.system(
    "pyinstaller --noconfirm --onefile --windowed "
    "--name Cryptix "
    "--icon=cryptix.ico "
    "--add-data \"cryptix.ico;.\" "
    "main.py"
)