import os

os.system(
    "pyinstaller --noconfirm --onefile --windowed "
    "--icon=cryptix.ico "
    "--add-data \"cryptix.ico;.\" "
    "main.py"
)