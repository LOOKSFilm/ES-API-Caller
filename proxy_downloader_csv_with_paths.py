# --------- INFO ---------
""" 
CSV beinhaltet bereits Namen zu Clips und Pfade zu Proxies. 
Pfade müssen nicht via API oder "resule_all_metadata_all_clips.csv" abgefragt werden.
 """

# --------- IMPORTS ---------
import os
import csv
import html
import paramiko
from pathlib import Path, PurePosixPath
from dotenv import load_dotenv
import subprocess
import re


# --------- INIT ---------
env_path = Path(__file__).parent / "cred.env"
load_dotenv(env_path)


# --------- CONFIG ---------
clip_list_path = Path(__file__).parent / "Maischberger Kollektion Proxy Pfad für API Call.csv"
download_path = Path(r"\\10.0.77.11\Ablage KI Proxy_1\(04) 2026-02-02_Protege\Lieferung 2 Maischberger")

proxy_server_base = PurePosixPath("/RAIDS/RAID_1/flow/files")
PLACEHOLDER_UUID = "5a2122e2-17b0-459c-9253-2ee3c60e105e"


# --------- FUNC ---------
def sanitize_filename(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name)


# --------- NETWORK MOUNT ---------
net_use = subprocess.run([
    "net", "use",
    str(download_path.drive),
    f"/user:{os.environ['FLOW_USER']}",
    os.environ["FLOW_PASSWORD"]
], capture_output=True, encoding="cp1252", errors="replace")

if net_use.returncode != 0:
    print(f"❌ Netzlaufwerk konnte nicht verbunden werden:")
    print(f"   {net_use.stderr}")
    exit(1)
else:
    print(f"✅ Netzlaufwerk verbunden: {download_path.drive}")


# --------- TEST ---------
test_file = download_path / "_connection_test.tmp"
try:
    download_path.mkdir(parents=True, exist_ok=True)
    test_file.write_text("test")
    test_file.unlink()
    print(f"✅ Zielpfad erreichbar: {download_path}")
except Exception as e:
    print(f"❌ Zielpfad nicht erreichbar: {download_path}")
    print(f"   Fehler: {e}")
    exit(1)


# --------- MAIN ---------
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(
        os.environ["SSH_HOST"],
        username=os.environ["SSH_USER"],
        password=os.environ["SSH_PASSWORD"]
    )
    
    sftp = ssh.open_sftp()
    
    all_titles = []
    placeholder_titles = []
    
    with open(clip_list_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for i, row in enumerate(reader, start=2):
            title = row.get("Neuer Dateiname", "").strip()
            proxy_path = row.get("proxy_path", "").strip()
            
            if not title:
                print(f"⚠️  Zeile {i}: Titel fehlt")
                continue
                
            if not proxy_path:
                print(f"⚠️  Zeile {i}: proxy_path fehlt - überspringe")
                continue

            all_titles.append(title)

            if PLACEHOLDER_UUID in proxy_path:
                placeholder_titles.append(title)
                print(f"⚠️  Zeile {i}: Platzhalter-UUID gefunden - überspringe")
                continue

            source = proxy_server_base / proxy_path
            dest_name = sanitize_filename(title) + source.suffix
            destination = download_path / dest_name

            try:
                sftp.get(source.as_posix(), str(destination))
                print(f"✅ Kopiert: {dest_name}")
            except Exception as e:
                print(f"❌ Fehler: {type(e).__name__}: {e}")
    
    sftp.close()
    
    # Abgleich mit Downloadordner
    print(f"\n🔍 Prüfe Downloadordner: {download_path}")
    existing_files = set()
    for file_path in download_path.iterdir():
        if file_path.is_file():
            # Entferne Dateiendung um Basisnamen zu bekommen
            base_name = file_path.stem
            existing_files.add(base_name)
    
    missing_titles = []
    for title in all_titles:
        sanitized = sanitize_filename(title)
        if sanitized not in existing_files:
            missing_titles.append(title)
    
    # Bericht erstellen
    print(f"\n📊 Zusammenfassung:")
    print(f"   Gesamt Titel in CSV: {len(all_titles)}")
    
    if placeholder_titles:
        print(f"   Titel mit Platzhalter-UUID: {len(placeholder_titles)}")
        for title in placeholder_titles:
            print(f"     - {title}")
    
    successfully_downloaded = len(all_titles) - len(missing_titles)
    print(f"   Erfolgreich heruntergeladen: {successfully_downloaded}")
    
    if missing_titles:
        print(f"   Fehlend/Nicht herunterladbar: {len(missing_titles)}")
        for title in missing_titles:
            status = "Platzhalter" if title in placeholder_titles else "Download fehlgeschlagen"
            print(f"     - {title} ({status})")
    else:
        print(f"✅ Alle {len(all_titles)} Titel wurden erfolgreich heruntergeladen!")
        
finally:
    ssh.close()


# --------- NETWORK DEMOUNT ---------
subprocess.run(
    ["net", "use", str(download_path.drive), "/delete"],
    capture_output=True, encoding="cp1252"
)
print(f"✅ Netzlaufwerk getrennt: {download_path.drive}")