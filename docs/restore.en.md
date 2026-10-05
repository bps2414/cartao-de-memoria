# Restoring PS5 saves: test checklist and draft guide

[Português](restaurar.md) · **English**

Memcard never writes to the PS5. Restoration is a manual action performed by the
owner through [Garlic SaveMgr](https://git.etawen.dev/earthonion/garlic-savemgr),
at `http://<ps5-ip>:8082`, on the **Import** tab. This flow has not yet been tested
end to end on a real console. This document does not certify that restoration
works, even on the original console.

## Part 1 — checklist for the owner to run

Use a disposable PS5 save on the original console. Run one case at a time,
with the game closed when backing up, exporting, importing or deleting. Do not
modify files over FTP: use it only to inspect and download. Writes in this
checklist are performed manually by the owner in Garlic or the PS5 screens.

### What the Garlic source shows

Source reviewed on 2026-10-05: Garlic v1.13, commit
[`c1409a1aea9d4c15461f6e36950a64298b66bfe8`](https://git.etawen.dev/earthonion/garlic-savemgr/commit/c1409a1aea9d4c15461f6e36950a64298b66bfe8).
References: `src/ui.html` (user selector, Import tab, `importEncrypted`,
`importDrop`, `doImportFinish`) and `src/main.c` (routes below).

- `/api/users` lists each profile's local ID and name; it does not report the
  account ID. The selector starts with the first profile returned: check the target.
- Import accepts a decrypted folder or an encrypted image. For the `sdimg_...`
  image downloaded from Memcard, use **Browse File** or drag the file in.
  Do not use **Browse Folder** or upload multiple saves together.
- `POST /api/import_encrypted?uid=...` receives and mounts a temporary copy of
  the image, reads `sce_sys/param.sfo`, checks whether the save exists at the
  destination and compares the save's account ID with the profile's. In the
  normal path it returns `save_aid`, `user_aid`, `match` and `exists`. `match` is
  only true if the profile's ID is nonzero and matches; a resign offer alone
  does not prove that the accounts differ.
- The UI asks for confirmation if `exists` is true. If `match` is false, it
  shows both IDs and offers **Yes, Resign**. Accepting proceeds to finish the
  import; it does not call `/api/resign`.
- `GET /api/import_check?uid=...` checks whether an already mounted save exists
  at the destination. The UI uses it for the decrypted folder flow; in the
  encrypted flow the check already comes from `/api/import_encrypted`.
- `GET /api/import_finish?uid=...` reads the local account ID; if it is nonzero,
  it rewrites the account ID and local user ID in the PS5 `param.sfo`. It unmounts
  the image, copies it to `savedata_prospero/<TITLE_ID>/sdimg_<dir_name>` and tries
  to update/create the save database entry. Error and warning paths exist;
  a success screen is not a substitute for opening the game to check progress.
- `POST /api/resign` belongs to the Resign tab: it receives an image and a supplied
  account ID, modifies the copy and makes the file available for download. There
  is no need to use this tab for the resign offered during Import.
- Garlic may rewrite and re-encrypt the image even for the same profile.
  SHA-256 equality after import and the corresponding `sdimg_sce_bu_` behavior:
  **to confirm during testing**. The finish route handles the main image; it
  does not document synchronization of the `sce_bu_` copy.

If a warning about a zeroed `param.sfo`, regeneration or **Import Anyway** appears,
record it and cancel: this variation is **to confirm during testing**, outside
the three normal cases below. Do not force the import to complete this checklist.

### Preparation and two safety copies

- [ ] Record the environment and choose a game with a disposable save.
- [ ] Identify the old version by known progress and distinguish it from the
  current save. If there are not two versions yet, keep one, advance in the
  game, close it and back up again. Pin both before continuing.
- [ ] Close the game and wait for any backup/export to finish.
- [ ] In Memcard, run **Back up now**, wait for completion and check for errors.
  Pin the current version and the chosen old one.
- [ ] Download both into separate computer folders, preserving their names.
  If the game needs multiple saves, record and keep the set; this test should
  use a save whose progress can be checked without mixing slots.
- [ ] In Garlic, check the profile, game and save and use **Download Encrypted**
  to export the same current save as a second safety copy. Keep it in a separate
  folder, check that the download finished and record its filename (Garlic may
  prepend the TITLE_ID). Keep other required game files as well. Do not rely
  solely on a copy stored on the PS5 itself.
- [ ] Record presence, size, timestamp and, if possible, SHA-256 of the matching
  `sdimg_sce_bu_<dir_name>` file, reading over FTP or through Memcard. If missing,
  write “absent”; do not create, delete or rename this file.
- [ ] Check that the original profile and, for case C, `Y2jb` and the game are
  included in Memcard backups. Record and later revert selection changes.
- [ ] Before each case, repeat **Back up now**, pin/download the previous state
  and export it through Garlic. If unchanged, identify the copies already kept.

<!-- PRINT: old and current save versions in Memcard, with dates and pins -->
<!-- PRINT: profile and save selected in Garlic before Download Encrypted -->
<!-- PRINT: safety files downloaded to the computer, with names and sizes -->

| Field | Fill in |
|---|---|
| Date, test owner | ____________________ |
| PS5 firmware | ____________________ |
| Installed Garlic version (and source/commit, if known) | ____________________ |
| Memcard and ftpsrv versions | ____________________ |
| Game, game version and TITLE_ID | ____________________ |
| Original profile, local ID (UID) | ____________________ |
| Main save (`sdimg_...`) and other required files | ____________________ |
| Old version: date/time, SHA-256, expected progress | ____________________ |
| Current safety version: date/time, SHA-256, progress | ____________________ |
| Local folders: old / current / Garlic export | ____________________ |
| `sdimg_sce_bu_...` copy: path, presence, size, timestamp, SHA-256 | ____________________ |
| Memcard selections changed for the test | ____________________ |

### Case A — same profile, overwrite the current save

- [ ] Confirm the current save on the console and both safety copies from preparation.
- [ ] With the game closed, download the chosen old version from Memcard.
- [ ] Open Garlic, explicitly select the original profile and the **Import**
  tab. Upload only the chosen image using **Browse File**.
- [ ] Record the overwrite confirmation and accept only if the displayed game
  and save are the chosen ones. Record whether resign was offered; record the
  displayed IDs and your choice, without assuming account equality.
- [ ] Record the final screen, including warnings, and run the common checks.

<!-- PRINT: case A, target profile and overwrite confirmation -->
<!-- PRINT: case A, resign offer if displayed and Garlic final screen -->

Previous state/copies for undoing: ____________________

Confirmations, account IDs, choice and Garlic result: ____________________

Common checks result: ____________________

**If it goes wrong:** close the game. In the same profile, import the current
image pinned/downloaded before the case, or the encrypted Garlic export kept
on the computer. Check the destination and confirmations and check the game
again. Do not delete Memcard versions. If recovery also fails, keep the messages
and screenshots and stop the remaining cases; do not edit the database or `sce_bu_`.

Recovery attempted, file used and recovered progress: ____________________

### Case B — same profile, save deleted beforehand

- [ ] Confirm or recover the reference state after A. Repeat the safety copies
  from preparation before deleting anything.
- [ ] With the game closed, manually delete only the disposable save in the
  original profile using the PS5. Record the screen and what deletion removed;
  the exact selection available on this firmware is **to confirm during testing**.
  Do not delete over FTP.
- [ ] Do not open the game to create another save. Observe whether the main
  image and `sdimg_sce_bu_` disappeared; record anything left over.
- [ ] In Garlic, select the original profile, **Import**, and upload the same
  old version. Record whether overwrite was requested even after deletion,
  whether resign was offered, visible IDs and the final screen. Run the common checks.

<!-- PRINT: case B, disposable save selected for manual deletion on the PS5 -->
<!-- PRINT: case B, absence or remaining files before importing -->
<!-- PRINT: case B, unexpected confirmation if any and Garlic final screen -->

Previous state/copies for undoing: ____________________

Deletion and remaining files: ____________________

Confirmations, account IDs, choice and Garlic result: ____________________

Common checks result: ____________________

**If it goes wrong:** do not start a new game to replace the save. With the game
closed, import the image from before deletion or the Garlic export into the
original profile and check progress. If recovery fails, stop the test and keep
files and messages. Do not manipulate the database or `sce_bu_`.

Recovery attempted, file used and recovered progress: ____________________

### Case C — profile `Y2jb`

`Y2jb` is the only other profile on this console and nobody plays on it. Whether
it has another account is **to confirm during testing**; a different profile
name and UID do not prove that the account ID differs.

- [ ] With the game closed, record the UID of `Y2jb` and whether it already has
  a save for the game. If so, back up, pin/download and export it before overwriting.
  If not, record “absent” as its previous state.
- [ ] In Garlic, explicitly select **Y2jb**, **Import**, and upload the old
  version from the original profile. Confirm overwrite only if it is the
  disposable destination save you have just protected.
- [ ] If resign is offered, capture both IDs and accept **Yes, Resign**. If not,
  record that and the account IDs Garlic reports for the save/original profile
  and for `Y2jb`. Do not invent an ID or switch to the Resign tab.
- [ ] If the IDs are not visible, open the browser developer tools, Network tab,
  before uploading and record `save_aid`, `user_aid` and `match` from the
  `/api/import_encrypted` response in cases A and C. Do not run routes manually.
  `/api/users` provides UIDs, not account IDs. If the response omits these fields,
  write “not displayed; to confirm during testing”.
- [ ] Record the final screen and warnings. Sign into **Y2jb on the PS5 itself**
  to open the game and run the common checks. Also check that this import did
  not change the original profile's save.

<!-- PRINT: case C, Y2jb selected in Garlic before uploading -->
<!-- PRINT: case C, resign offer with IDs or browser import_encrypted response -->
<!-- PRINT: case C, final screen and game opened by profile Y2jb -->

| Field | Fill in |
|---|---|
| Original UID / Y2jb UID | ____________________ |
| Previous Y2jb state and copies for undoing | ____________________ |
| Case A: `save_aid` / `user_aid` / `match` | ____________________ |
| Case C: `save_aid` / `user_aid` / `match` | ____________________ |
| Resign offered? Choice? Accounts different, same or inconclusive? | ____________________ |
| Garlic result / common checks / original save preserved | ____________________ |

**If it goes wrong:** close the game in `Y2jb`. If there was a save beforehand,
restore the protected `Y2jb` copy or its Garlic export in that same profile and
check it. If there was none, manually delete only the test save created in
`Y2jb` through the PS5 screens and record the result. Do not delete the profile
or touch the original save. If the destination is uncertain, stop and keep evidence.

Recovery/removal attempted and final Y2jb state: ____________________

### Common checks — fill in one record for each case

- [ ] Before opening the game, after import finishes, run **Back up now** and
  record the resulting file, history and SHA-256. Pin any version created.
  This measurement helps separate Garlic rewriting from later game writes.
- [ ] Open the game in the target profile and confirm by its progress that it
  is the chosen version (slot, chapter, time, item or another known sign).
  Record corrupt-save warnings, wrong profile or different progress.
- [ ] Close the game, run **Back up now**, wait for completion and record whether
  Memcard counted the file as unchanged or created a new version. If the daemon
  copied it before the button, record that version's timestamp/trigger.
- [ ] Compare the SHA-256 stored after import with the old image uploaded and
  with the last backup before this case. A new version means a difference from
  the last content stored for that profile/file; returning to an old save can
  create a version even if its SHA matches the old one. For the first `Y2jb`
  save, with no previous backup, expect a first copy, not cross-profile
  deduplication. “Unchanged” in the summary alone does not prove SHA equality.
- [ ] Record `sdimg_sce_bu_` before import, after import with the game still
  closed and after opening/closing the game: absent, created, kept, changed or
  removed. Record size, timestamp and available SHA-256. Do not treat it as a
  valid recovery copy without testing. SHA changes alone do not prove lost progress.
- [ ] Record any undo attempt and the final state. Proceed to the next case
  only when the state is understood and protected.

<!-- PRINT: each case, progress loaded in the game under the target profile -->
<!-- PRINT: each case, Memcard Log and history after Back up now -->
<!-- PRINT: each case, main image and sce_bu_ before and after, without FTP writes -->

| Field — copy for A, B and C | Fill in |
|---|---|
| Case / profile / import time | ____________________ |
| Garlic: success, warning, error and complete message | ____________________ |
| Before opening the game: Back up now, timestamp/trigger, result, version, SHA-256 | ____________________ |
| Expected / observed progress / game warnings | ____________________ |
| After closing the game: Back up now, timestamp/trigger, result, version, SHA-256 | ____________________ |
| SHA after import equals uploaded image? Equals last destination backup? | ____________________ |
| `sce_bu_` before / after import / after playing: presence, size, timestamp, SHA-256 | ____________________ |
| Other affected files / saved screenshots and logs | ____________________ |
| Undo needed? Result / final state | ____________________ |
| Verdict: passed, failed or inconclusive; reason | ____________________ |

When finished, keep copies and evidence, revert temporary Memcard selections
and record which cases passed for this game, firmware and Garlic combination.
Keep uncertainties as **to confirm during testing**. Do not extrapolate results
to another console, another game, PS4 or every firmware version.

### PS4 saves — outside this test

PS4 saves consist of two files: the image and the `.bin` key. Memcard stores
these as separate versions; restoration requires the **pair from the same point
in time**, not two independently selected recent versions. This checklist does not test PS4.

## Part 2 — outline of the final user guide

**Guide still in preparation. TO FILL IN AFTER TESTING:** validated cases,
Garlic/firmware/game versions, limitations and real screenshots.

### 1. Keep the current state

Close the game. In Memcard, run **Back up now**, check completion and pin the
current versions of all involved saves. Download these versions to the computer.
Also export the same current saves through Garlic using **Download Encrypted**
and keep them separately. This prepares an attempt to return to the previous state.

<!-- PRINT: final guide, pinned current version and Garlic safety export -->

### 2. Choose and download the version

In the source profile's Memcard card, open the game, save and its history.
Choose a version by its date and the progress you want to recover; download
the `sdimg_...` image without editing its contents. Keep each version in its own folder.

**TO FILL IN AFTER TESTING:** how to identify the main save and files that must
be restored together for the tested game; how to handle `sce_bu_`.

<!-- PRINT: final guide, chosen history version and downloaded file -->

### 3. Import manually through Garlic

Open `http://<ps5-ip>:8082`, check the target profile in the selector and go to
**Import**. Use **Browse File** or drag in one image at a time. Check the identified
game/save before accepting overwrite. If resign is offered, check the IDs and
target profile before deciding. Keep the final screen and warnings. Garlic
performs restoration; Memcard remains read-only.

**TO FILL IN AFTER TESTING:** proven results for the same profile, a deleted save
and `Y2jb`; when to accept resign, including equal, zero or missing IDs; how to
handle errors. There is still no validated procedure for zeroed-SFO warnings.

<!-- PRINT: final guide, target profile, Import, confirmation and result -->

### 4. Check the game and Memcard

Open the game under the target profile and check progress. Close it and run
**Back up now**. Check the history; rewriting/re-encryption by Garlic or the
game itself may change SHA-256 even when progress is correct.

**TO FILL IN AFTER TESTING:** actual SHA-256 and `sce_bu_` results, observed
messages and criteria for considering the restoration successful.

<!-- PRINT: final guide, restored progress and history after checking -->

### 5. Return to the previous state if necessary

Close the game and keep the safety copies. Use the protected previous image
or the Garlic export under the correct profile, then check the game again.

**TO FILL IN AFTER TESTING:** recovery procedure actually exercised for each
case, including returning `Y2jb` to a state with no save. Having a safety file
does not guarantee that recovery has already been validated.

The PS4 image/`.bin` pair note above also applies to the final guide; PS4 and
restoration on another console remain outside this checklist's validation.
