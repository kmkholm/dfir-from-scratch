"""Chapter 03 - Log forensics: from SSH brute force to a web shell."""

from __future__ import annotations

import datetime as dt
import random
from pathlib import Path
from urllib.parse import quote

from ..core import Chapter, Question

HOST = "web01"
STAFF = ["alice", "bob", "carol", "deploy", "omar", "nadia", "backup"]
WORDLIST = [
    "admin", "root", "test", "user", "oracle", "postgres", "ubuntu", "guest", "ftp", "pi",
    "support", "git", "jenkins", "minecraft", "hadoop", "www", "mysql", "dev", "info", "tomcat",
]
COMMANDS = ["id", "whoami", "uname -a", "cat /etc/passwd", "ls -la /var/www", "ps aux", "netstat -tlpn"]
PAGES = ["/", "/index.html", "/about", "/contact", "/products", "/products/42", "/blog/2026/spring-sale",
         "/assets/css/site.css", "/assets/js/app.js", "/assets/img/logo.png", "/login", "/cart", "/search?q=shoes"]
AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
]


def _doc_ip(rng: random.Random) -> str:
    # RFC 5737 documentation ranges only.
    return f"{rng.choice(['192.0.2', '198.51.100', '203.0.113'])}.{rng.randint(2, 250)}"


def _syslog_ts(t: dt.datetime) -> str:
    return f"{t.strftime('%b')} {t.day:>2} {t.strftime('%H:%M:%S')}"


def _clf_ts(t: dt.datetime) -> str:
    return t.strftime("%d/%b/%Y:%H:%M:%S +0000")


def generate(rng: random.Random, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    day = dt.datetime(2026, rng.randint(2, 10), rng.randint(1, 27))
    start = day + dt.timedelta(hours=rng.randint(0, 2))
    end = start + dt.timedelta(hours=6)

    attacker = _doc_ip(rng)
    decoy = _doc_ip(rng)
    while decoy.rsplit(".", 1)[0] == attacker.rsplit(".", 1)[0]:
        decoy = _doc_ip(rng)
    office = [f"10.0.4.{rng.randint(10, 60)}" for _ in range(4)]
    victim = rng.choice(["deploy", "backup", "omar"])

    auth = []   # (datetime, line)
    pid = rng.randint(1200, 3000)

    def sshd(t, msg):
        nonlocal pid
        pid += rng.randint(1, 9)
        auth.append((t, f"{_syslog_ts(t)} {HOST} sshd[{pid}]: {msg}"))

    # routine traffic
    t = start
    while t < end:
        t += dt.timedelta(minutes=rng.randint(3, 25), seconds=rng.randint(0, 59))
        r = rng.random()
        if r < 0.45:
            u = rng.choice(STAFF[:3] + ["nadia"])
            ip = rng.choice(office)
            sshd(t, f"Accepted publickey for {u} from {ip} port {rng.randint(40000, 65000)} ssh2: ED25519 SHA256:{rng.getrandbits(64):016x}")
            auth.append((t, f"{_syslog_ts(t)} {HOST} sshd[{pid}]: pam_unix(sshd:session): session opened for user {u}(uid={rng.randint(1000, 1010)}) by (uid=0)"))
        elif r < 0.75:
            auth.append((t, f"{_syslog_ts(t)} {HOST} CRON[{rng.randint(3000, 9000)}]: pam_unix(cron:session): session opened for user root(uid=0) by (uid=0)"))
        else:
            auth.append((t, f"{_syslog_ts(t)} {HOST} sudo:    {rng.choice(STAFF[:3])} : TTY=pts/0 ; PWD=/home ; USER=root ; COMMAND=/usr/bin/systemctl status nginx"))

    # decoy: a handful of failures, never succeeds
    t = start + dt.timedelta(minutes=rng.randint(20, 80))
    for _ in range(rng.randint(3, 6)):
        t += dt.timedelta(seconds=rng.randint(2, 9))
        sshd(t, f"Failed password for invalid user {rng.choice(WORDLIST)} from {decoy} port {rng.randint(40000, 65000)} ssh2")

    # the real attack
    t = start + dt.timedelta(minutes=rng.randint(100, 160), seconds=rng.randint(0, 59))
    tried = set()
    fails = 0
    for _ in range(rng.randint(35, 80)):
        t += dt.timedelta(seconds=rng.randint(1, 4))
        u = rng.choice(WORDLIST)
        tried.add(u)
        sshd(t, f"Failed password for invalid user {u} from {attacker} port {rng.randint(40000, 65000)} ssh2")
        fails += 1
    for _ in range(rng.randint(4, 10)):
        t += dt.timedelta(seconds=rng.randint(1, 4))
        tried.add(victim)
        sshd(t, f"Failed password for {victim} from {attacker} port {rng.randint(40000, 65000)} ssh2")
        fails += 1
    t += dt.timedelta(seconds=rng.randint(2, 5))
    success_t = t
    sshd(t, f"Accepted password for {victim} from {attacker} port {rng.randint(40000, 65000)} ssh2")
    auth.append((t, f"{_syslog_ts(t)} {HOST} sshd[{pid}]: pam_unix(sshd:session): session opened for user {victim}(uid=1004) by (uid=0)"))

    # web access log
    web = []
    t = start
    while t < end:
        t += dt.timedelta(seconds=rng.randint(5, 70))
        ip = _doc_ip(rng) if rng.random() < 0.8 else rng.choice(office)
        if ip == attacker:
            continue
        page = rng.choice(PAGES)
        status = 200 if rng.random() < 0.93 else rng.choice([301, 304, 404])
        web.append((t, f'{ip} - - [{_clf_ts(t)}] "GET {page} HTTP/1.1" {status} {rng.randint(300, 48000)} "-" "{rng.choice(AGENTS)}"'))

    shell = f"/assets/img/{rng.choice(['thumb', 'cache', 'logo2', 'favicon', 'sprite'])}_{rng.getrandbits(16):04x}.php"
    cmds = rng.sample(COMMANDS, rng.randint(3, 5))
    t = success_t + dt.timedelta(minutes=rng.randint(4, 15))
    # a 404 probe first, then the shell is used
    web.append((t, f'{attacker} - - [{_clf_ts(t)}] "GET {shell.replace(".php", ".bak")} HTTP/1.1" 404 162 "-" "curl/8.5.0"'))
    for c in cmds:
        t += dt.timedelta(seconds=rng.randint(8, 50))
        web.append((t, f'{attacker} - - [{_clf_ts(t)}] "GET {shell}?c={quote(c)} HTTP/1.1" 200 {rng.randint(40, 4000)} "-" "curl/8.5.0"'))

    auth.sort(key=lambda x: x[0])
    web.sort(key=lambda x: x[0])
    (out / "auth.log").write_text("\n".join(l for _, l in auth) + "\n", encoding="utf-8", newline="\n")
    (out / "access.log").write_text("\n".join(l for _, l in web) + "\n", encoding="utf-8", newline="\n")

    return {
        "attacker_ip": attacker,
        "failed_attempts": fails,
        "usernames_tried": len(tried),
        "compromised_user": victim,
        "login_time": success_t.strftime("%H:%M:%S"),
        "webshell_path": shell,
        "first_command": cmds[0],
    }


CHAPTER = Chapter(
    id="03",
    slug="logs",
    title="Reading the logs: SSH brute force to web shell",
    summary="Rebuild an intrusion timeline from auth.log and an Apache access log.",
    brief=(
        "The web server web01 started sending spam overnight. The admin pulled two logs before\n"
        "rebuilding the box: /var/log/auth.log and the web server's access.log (all times UTC).\n"
        "Find how the attacker got in and what they did once inside."
    ),
    questions=[
        Question("attacker_ip", "Which IP address broke in over SSH?"),
        Question("failed_attempts", "How many failed password attempts did that IP make before it got in?", "int"),
        Question("usernames_tried", "How many distinct usernames did it try?", "int"),
        Question("compromised_user", "Which account was compromised?"),
        Question("login_time", "At what time (HH:MM:SS) did the successful login happen?", "text"),
        Question("webshell_path", "What is the path of the web shell (without the query string)?", "text"),
        Question("first_command", "What was the first command run through the web shell? (decoded)", "text"),
    ],
    hints=[
        "Start with `grep 'Failed password' auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn`. "
        "More than one IP fails - only one of them ever succeeds.",
        "'invalid user X' means the account does not exist; it is still a username the attacker tried. "
        "The real account name appears without the word 'invalid'.",
        "In access.log, follow the attacker's IP. Web shells usually take the command in a query parameter; "
        "it is URL-encoded (%20 is a space). Python: urllib.parse.unquote().",
    ],
    generate=generate,
    tags=["linux logs", "ssh", "apache", "timeline"],
)
