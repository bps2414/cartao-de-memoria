# Compatibility

[Português](COMPATIBILIDADE.md)

Only one combination has been verified on a real console. A successful diagnostic
shows that the required reads responded at that moment; also confirm that a
backup completes and versions appear before reporting that it works.

| Firmware | FTP server | Server version | Result | Notes | Reported by | Date |
|---|---|---|---|---|---|---|
| 13.42 | ftpsrv | 0.21.1 | Works | Combination used in the project's initial tests. | Initial project report | Not recorded |

## How to report

Turn on the PS5, load its FTP server and check the console configured in Memcard.
Diagnostics connect only to the configured address; they do not search for other
consoles, change config, or write or delete anything on the PS5.

With Docker:

```sh
docker compose exec ps5-backup ps5backup diag
```

On Windows, inside the executable's folder:

```powershell
.\memcard.exe diag
```

From source, with `PS5BACKUP_CONFIG` set as described in the README:

```sh
python -c "import sys; sys.path.insert(0, 'app'); import ps5backup; sys.exit(ps5backup.main())" diag
```

Copy the entire block and open a [compatibility issue](https://github.com/bps2414/memcard/issues/new?template=compat.yml).
Include firmware, server and version; say whether a real backup completed and
describe any failures. Do not add IPs, profile names/IDs or save names to the report.

The report includes Memcard, OS and Python versions, FTP banner, SYST and FEAT,
MLSD behavior and `type`, `size` and `modify` facts, profile counts, optional
metadata and the size/time of a RETR of the smallest save file found.
Banner and replies are summarized: FTP codes, `ftpsrv` identification/version,
system identifiers and known capabilities are retained; free text is omitted so
arbitrary replies or errors cannot reveal private data. No profile name/ID, IP or
save name is displayed. Title IDs may be included in your report if relevant.

Exit code **0**: connection, login, navigation, MLSD with valid facts and reading
a save worked. **1**: an essential step failed or could not be checked; the last
line says what is missing. With no saves, RETR cannot be checked. A size mismatch
also returns 1 (the save may change during the test). Missing `/user/appmeta` or
a readable `savedata.db` does not prevent copying saves and is reported as optional
metadata. Refusals of SYST/FEAT are recorded and do not prevent backup either.
There is no `LIST` fallback for servers without MLSD.

`GET /api/diag` returns `{"text": "..."}` and requires the same login as other routes.
It uses `X-Lang` (`pt-BR`/`en`) when provided, otherwise the language configured in
`[notify] language`; the CLI always uses Portuguese. The interface has no button yet.
