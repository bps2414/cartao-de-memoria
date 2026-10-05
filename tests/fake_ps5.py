"""FTP de teste, somente leitura, com arquivos em memória e o MLSD do ftpsrv."""
import argparse
import datetime as dt
import json
import posixpath
import socket
import socketserver
import sqlite3
import threading
from contextlib import closing

UID = "1a2b3c4d"
OTHER_UID = "5e6f7081"
TITLE = "PPSA00001"
SAVE_PATH = f"/user/home/{UID}/savedata_prospero/{TITLE}/sdimg_slot"
OTHER_SAVE_PATH = f"/user/home/{OTHER_UID}/savedata_prospero/{TITLE}/sdimg_slot"
DB_PATH = f"/system_data/savedata_prospero/{UID}/db/user/savedata.db"
SAVE_LABEL = "A aventura de João"


def savedata_database(rows):
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE savedata (title_id TEXT, dir_name TEXT, main_title TEXT, sub_title TEXT, detail TEXT)")
        db.executemany("INSERT INTO savedata VALUES (?, ?, ?, ?, ?)", rows)
        db.commit()
        return db.serialize()


def example_tree():
    """Dois perfis, um jogo e os bancos que dão nome aos saves."""
    files = {
        SAVE_PATH: b"save original do primeiro perfil",
        OTHER_SAVE_PATH: b"save original do segundo perfil",
        f"/user/appmeta/{TITLE}/param.json": json.dumps({
            "contentVersion": "01.000.000", "localizedParameters": {
                "defaultLanguage": "pt-BR", "pt-BR": {"titleName": "Jogo de exemplo"}}}).encode("utf-8"),
    }
    for uid, name in ((UID, "João"), (OTHER_UID, "Maria")):
        files[f"/user/home/{uid}/username.dat"] = name.encode("utf-8") + b"\0"
        files[f"/system_data/savedata_prospero/{uid}/db/user/savedata.db"] = savedata_database([
            (TITLE, "slot", SAVE_LABEL, "Capítulo 2", "Antes do chefe")])
    return files


class FTPHandler(socketserver.StreamRequestHandler):
    def setup(self):
        super().setup()
        self.cwd = "/"
        self.passive = None

    def reply(self, text):
        self.wfile.write((text + "\r\n").encode("utf-8"))
        self.wfile.flush()

    def path(self, name):
        return posixpath.normpath(posixpath.join(self.cwd, name))

    def close_passive(self):
        if self.passive is not None:
            self.passive.close()
            self.passive = None

    def transfer(self, data):
        if self.passive is None:
            self.reply("425 Use PASV first")
            return
        self.reply("150 Opening data connection")
        try:
            conn, _ = self.passive.accept()
            with conn:
                conn.sendall(data)
        finally:
            self.close_passive()
        self.reply("226 Transfer complete")

    def handle(self):
        try:
            self.session()
        except ConnectionError:
            pass  # sondagens de porta fecham a conexão sem QUIT

    def session(self):
        fake = self.server.fake
        self.reply("220 Fake PS5 FTP")
        while line := self.rfile.readline():
            command, _, arg = line.decode("utf-8").rstrip("\r\n").partition(" ")
            command = command.upper()
            with fake.guard:
                fake.commands.append((command, arg))
            if command == "USER":
                self.reply("331 Password required")
            elif command == "PASS":
                self.reply("230 Logged in")
            elif command == "SYST":
                self.reply("215 UNIX Type: L8")
            elif command == "FEAT":
                self.reply("211-Features\r\n MLST type*;size*;modify*;\r\n211 End")
            elif command == "PWD":
                self.reply(f'257 "{self.cwd}"')
            elif command == "CWD":
                path = self.path(arg)
                if fake.is_dir(path):
                    self.cwd = path
                    self.reply("250 Directory changed")
                else:
                    self.reply("550 Directory not found")
            elif command == "TYPE":
                self.reply("200 Type set")
            elif command == "PASV":
                self.close_passive()
                self.passive = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.passive.bind(("127.0.0.1", 0))
                self.passive.listen(1)
                self.passive.settimeout(5)
                port = self.passive.getsockname()[1]
                self.reply(f"227 Entering Passive Mode (127,0,0,1,{port // 256},{port % 256})")
            elif command == "MLSD":
                path = self.path(arg) if arg and fake.respect_mlsd_argument else self.cwd
                if fake.is_dir(path):
                    self.transfer(fake.listing(path))
                else:
                    self.reply("550 Directory not found")
            elif command == "RETR":
                with fake.guard:
                    data = fake.files.get(self.path(arg))
                if data is None:
                    self.reply("550 File not found")
                else:
                    self.transfer(data)
            elif command == "QUIT":
                self.reply("221 Goodbye")
                return
            else:
                self.reply("502 Command not supported")

    def finish(self):
        self.close_passive()
        super().finish()


class FTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class FakePS5:
    def __init__(self, files=None, respect_mlsd_argument=False, port=0):
        self.files, self.modified, self.commands = {}, {}, []
        self.guard = threading.Lock()
        self.clock = 0
        self.respect_mlsd_argument = respect_mlsd_argument
        for path, data in (example_tree() if files is None else files).items():
            self.set_file(path, data)
        self.server = FTPServer(("127.0.0.1", port), FTPHandler)
        self.server.fake = self
        self.host, self.port = self.server.server_address
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)

    def set_file(self, path, data):
        """Altera o console de mentira entre rodadas, sem comando de escrita FTP."""
        with self.guard:
            path = posixpath.normpath("/" + path.lstrip("/"))
            self.clock += 1
            self.files[path] = bytes(data)
            self.modified[path] = (dt.datetime(2026, 1, 1) + dt.timedelta(seconds=self.clock)).strftime("%Y%m%d%H%M%S")

    def is_dir(self, path):
        prefix = path.rstrip("/") + "/"
        with self.guard:
            return path == "/" or any(name.startswith(prefix) for name in self.files)

    def listing(self, path):
        prefix, children = path.rstrip("/") + "/", {}
        with self.guard:
            for name, data in self.files.items():
                if not name.startswith(prefix):
                    continue
                child, _, rest = name[len(prefix):].partition("/")
                children[child] = ("dir" if rest else "file", 0 if rest else len(data), self.modified[name])
        return "".join(f"type={kind};size={size};modify={modify}; {name}\r\n"
                       for name, (kind, size, modify) in sorted(children.items())).encode("utf-8")

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--respect-mlsd-argument", action="store_true")
    args = parser.parse_args()
    with FakePS5(port=args.port, respect_mlsd_argument=args.respect_mlsd_argument) as fake:
        print(f"FTP de teste em {fake.host}:{fake.port}", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
