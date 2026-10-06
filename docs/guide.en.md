# Memcard: five-minute setup

Start with the console jailbroken and the **ftpsrv payload loaded**.
Memcard copies your saves to your computer and keeps a version history.
It only reads files from the PS5. This guide does not explain how to jailbreak it.

[Português](guia.md) · [Back to the README](../README.en.md)

The five minutes are for setting up the service. The first backup may take
longer, depending on the number of saves and your network speed.

## 1. What you need

- PS5 on, already jailbroken, with **ftpsrv on port 2121**.
- PC on the same network, with free space for the saves.
- On Windows, the executable is enough. For the other path, install Git, Docker
  and Docker Compose on your computer.

Keep the PC on while you want automatic backups. Choose **Windows** or
**Docker** below. Both open the same interface in your browser.

## 2. Windows: download and open

1. Open the [releases page](https://github.com/bps2414/memcard/releases/latest).
   Download `memcard.exe` and `memcard.exe.sha256`. Keep both in a folder where
   you can write files. You do not need to install Python.
2. Open PowerShell in that folder and check the file:

   ```powershell
   (Get-FileHash .\memcard.exe -Algorithm SHA256).Hash.ToLower()
   Get-Content .\memcard.exe.sha256
   ```

   The first result must match the hash at the start of the second. If they
   differ, download the files again before opening the executable.
3. Double-click `memcard.exe`. It is not digitally signed. If you see
   **Windows protected your PC**, after checking the hash use
   **More info › Run anyway**.
4. A console window stays open and your browser shows **Cards** at
   `http://127.0.0.1:8765`. If the browser does not open, enter that address.
   Before the first backup, the page may say no profiles have been read yet.
5. Keep the console window open. Closing it stops the service.
   Opening the executable again while it is running only reopens the interface.

<!-- PRINT: Windows folder containing memcard.exe and its SHA-256 file, with no personal data -->
<!-- PRINT: current interface on the Cards tab before the first backup -->

Settings live in `config.toml`, created when you save in the interface. Backups
and the log live in `data/`. Everything stays next to the executable. Keep this
folder when updating. Windows updates are manual; see the
[README](../README.en.md#windows-without-docker).

## 3. Docker: prepare and start

Open a terminal with Git, Docker and Docker Compose available. Run the four
commands from the README:

```sh
git clone https://github.com/bps2414/memcard.git
cd memcard
cp config.example.toml config.toml
cp .env.example .env
```

You should have `config.toml` and `.env` inside the `memcard` folder.
In PowerShell, `cp` also copies files.

Open `config.toml`. In the `[ps5]` section, replace `host` with your PS5's IP
and check `ftp_port = 2121`. For example, for a PS5 at `192.168.0.50`:

```toml
[ps5]
host = "192.168.0.50"
ftp_port = 2121
subnet = "192.168.0.0/24"
```

Edit those existing lines; keep the other settings. `subnet` is the network
where Memcard searches for the console. Use the **PS5's** network, not Docker's
internal network. In Compose's default mode, called *bridge*, the container
may see an address on another network. Setting `subnet` avoids searching that
internal network. The example covers `192.168.0.x` addresses; adapt it to yours.

Save the file and start:

```sh
docker compose up -d
```

Wait for Docker to download the image and start the services. Open
`http://localhost:8765` on this PC, or `http://<computer-ip>:8765` on another
device on the same network. You should see the **Cards** tab.
If you set `WEB_PASSWORD` in `.env`, sign in with that password.

Backups live in `data/`, inside the project folder. The service keeps running
when you close the terminal. Compose includes automatic image updates;
details and changing the backup folder are in the [README](../README.en.md#installation).

<!-- PRINT: terminal with docker compose up -d completed and services started -->

## 4. Find the PS5

Open **Settings › Console**. Check **PS5 address** and **ftpsrv port**.
Use **Find now**. Once found, the page confirms the IP and port and updates
the fields. The search uses the address and network you entered, even before saving.

Automatic search is on by default. If the configured address does not respond,
Memcard tries to find the console and corrects the IP and port in `config.toml`.
An unsuccessful search is repeated every five minutes.

<!-- PRINT: Settings, Console section and PS5 found confirmation using example data -->

If it cannot find the console:

1. Check that the PS5 is on and **ftpsrv is still loaded on port 2121**.
   Try **Find now** again. You should see the address confirmation.
2. Check that PC and PS5 are on the same network. A guest network may prevent
   them from communicating. In **Network to search (advanced)**, enter the PS5's
   network, such as `192.168.0.0/24`. With Docker bridge, also check `subnet` in
   the file. Search again and click **Save settings** to keep that network.
3. Check that the firewall allows Memcard to reach the PS5 on your local network.
   If your PC uses a VPN, check that it allows local network access. Fix the
   block and try again.
4. If you know the IP, enter it, check the port and click **Save settings**.
   The page should confirm **Settings saved**. If it still cannot connect,
   continue to diagnostics in step 8.

With the network field empty, the search tries the configured address's range,
the PC's range and the common `192.168.1.x` and `192.168.0.x` ranges. Filling in
a network limits the search to that range. Reserving the PS5's IP on your router
helps keep it the same.

## 5. First backup

With the PS5 found, return to **Cards**. The first backup starts automatically
with the default settings. To start it manually, click **Back up now**.
If a backup is already running, wait for that round.

The page shows **Copying saves from the PS5…** during the backup. Then profile
cards and game blocks appear. Click a game, then a save. You should see at
least one stored version, with a date and an option to download it.

<!-- PRINT: Cards after the first backup and a save's history with a stored version -->

There is no fixed duration. Many saves, slow Wi-Fi or a game writing its save
may take longer. There is also an initial wait, 20 seconds by default, when
the console starts responding. Keep PC and PS5 on until it finishes.

Open **Log** and check the `backup [...]` summary: it lists new versions,
unchanged files, files waiting to settle and failures. To confirm the first
backup, check the stored versions and **0 falhas** (zero failures). If any saves
are waiting to settle, wait for the next round and check again.
A connected console alone does not confirm a backup.

## 6. Discord notifications

This step is optional. Use a server where you can create webhooks.
The webhook is the address Memcard uses to send messages to the channel.

1. In Discord, open **Server Settings › Integrations** and create a webhook.
   Choose the text channel and copy the URL. You should see the webhook linked
   to that channel. See also
   [Discord's official help](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks).
2. In Memcard, open **Settings › Discord notifications**. Paste the URL into
   **Webhook** and click **Save** next to it. The page confirms it was saved.
3. Click **Send test**. **Memcard test** should arrive in the chosen channel.
   If it does not, check the URL, the channel and the error message in the interface.

<!-- PRINT: Discord webhook linked to the chosen channel, with its URL hidden -->
<!-- PRINT: Settings with webhook configured and test message received in Discord -->

Do not share that URL. Memcard stores it in `data/secrets.json`.
During use, the session message is updated on every backup. These edits do not
send a notification for each save. Notification language is in **Settings › Language**;
if you change it, click **Save settings**.

## 7. How to tell it is working

Play and save your game. Keep PS5 and PC on. Then check that save's history
and **Log**: a change in content should appear as a new version. Unchanged
files are not copied again. While playing, versions close together may be
replaced by the latest one; by default, one is kept every ten minutes.

In **Log › Integrity**, click **Check now**. Wait for it to finish.
With stored versions, the result should report intact versions and no problems.
This checks the files on your PC, even when the PS5 is off.

<!-- PRINT: Log with completed backup, zero failures and integrity check without problems -->

When the PS5 turns off or enters rest mode, FTP stops responding. Memcard
shows the console as unreachable and keeps the existing backups. It cannot
read a save after the console leaves the network. Anything written after
the last reading waits until FTP responds again.

In Discord, the session summary arrives after the network outage grace period
(by default, three minutes after connection loss is detected). Once the PS5
returns with ftpsrv loaded, backups resume automatically. The service on your
PC must still be running.

## 8. If something goes wrong

Check the address in **Settings › Console**. With the PS5 on and ftpsrv loaded,
run diagnostics. On Windows, open PowerShell in the executable's folder:

```powershell
.\memcard.exe diag
```

With Docker, open a terminal in the project folder:

```sh
docker compose exec ps5-backup ps5backup diag
```

You should see a block starting with **Diagnóstico de compatibilidade (somente
leitura)** (read-only compatibility diagnostics). It tests reads at the
configured address without searching for another console or changing settings.
The last line says whether the required steps worked or what was missing.
Without saves, it cannot test reading a save. Command-line text stays in Portuguese.

<!-- PRINT: terminal with completed diagnostics using a fake PS5, with no personal data -->

Copy the whole block and open a
[compatibility issue](https://github.com/bps2414/memcard/issues/new?template=compat.yml).
Include the PS5 firmware, ftpsrv version, PC operating system and whether a
backup finished. Say what you did and what appeared. Diagnostics omit IPs and
profile/save names and IDs; do not add those details or your webhook URL.

Check the [compatibility table and diagnostics explanation](COMPATIBILITY.en.md).
Successful diagnostics confirm reads at that moment. Also check the stored
versions to confirm the backup.

## 9. Restore a save

Open the game and save in the interface. Choose a version in its history and
download it. You should receive the file on your computer. Memcard does not
send it to the PS5.

Read the [manual restoration test plan](restore.en.md) before importing through
Garlic SaveMgr. It still lists cases to test on a real console; the final guide
depends on those results. Keep the current state before any attempt.
Having a backup does not confirm that restoration has been tested.

<!-- PRINT: save history, selected version and download button -->
