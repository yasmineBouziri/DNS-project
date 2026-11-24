#!/usr/bin/env python3
"""Agent IA DNS : reçoit les alertes ML, propose des actions,
n'applique qu'après validation humaine."""
import argparse
import ipaddress
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import validate, ValidationError

BASE = Path(__file__).resolve().parent.parent
SCHEMA_PATH = BASE / "schemas" / "alerte.schema.json"
INBOX = BASE / "alertes"
DONE = INBOX / "traitees"
INVALID = INBOX / "invalides"
JOURNAL = BASE / "journal" / "actions.jsonl"

# Machines de l'infra : l'agent ne doit JAMAIS les bloquer
PROTECTED_IPS = {"10.10.10.20", "10.10.10.30", "10.10.10.31", "10.10.10.50"}

RATE_LIMIT_QPS = 50


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(entry):
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    entry["logged_at"] = now()
    with JOURNAL.open("a", encoding="utf-8-sig") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------- 1. Lecture et validation ----------
def load_alert(path, schema):
    with path.open(encoding="utf-8-sig") as f:
        alert = json.load(f)
    validate(alert, schema)
    ipaddress.ip_address(alert["source_ip"])  # lève ValueError si IP invalide
    return alert


# ---------- 2. Génération des actions ----------
def build_command(action, ip):
    """Commandes à exécuter sur la VM résolveur (iptables)."""
    if action == "block_ip":
        return f"iptables -I INPUT -s {ip} -j DROP"
    if action == "rate_limit":
        return (
            f"iptables -I INPUT -s {ip} -p udp --dport 53 "
            f"-m hashlimit --hashlimit-above {RATE_LIMIT_QPS}/sec "
            f"--hashlimit-mode srcip --hashlimit-name dnsrl -j DROP"
        )
    return None


def propose_actions(alert):
    ip = alert["source_ip"]
    atype = alert["anomaly_type"]
    sev = alert["severity"]
    actions = []

    def add(action, why):
        actions.append({
            "action": action,
            "target_ip": ip,
            "command": build_command(action, ip),
            "justification": why,
        })

    if atype == "flood":
        add("rate_limit", f"Flood détecté (score {alert['score']}) : limiter à {RATE_LIMIT_QPS} req/s.")
        if sev in ("high", "critical"):
            add("block_ip", "Gravité élevée : blocage complet de la source.")
    elif atype == "tunneling":
        add("block_ip", "Tunneling DNS (exfiltration probable) : blocage de la source.")
        add("notify_only", "Analyser les domaines TXT suspects avant de lever le blocage.")
    elif atype == "nxdomain_burst":
        add("rate_limit", "Rafale de NXDOMAIN : limiter le débit de la source.")
    elif atype == "amplification":
        add("rate_limit", "Tentative d'amplification : limiter la source.")
    else:
        add("notify_only", "Type inconnu : aucune action automatique, analyse manuelle.")

    # Garde-fou : jamais d'action coercitive sur l'infra elle-même
    if ip in PROTECTED_IPS:
        for a in actions:
            if a["action"] != "notify_only":
                a["action"] = "notify_only"
                a["command"] = None
                a["justification"] = "IP protégée (infra) : action coercitive refusée."
    return actions


# ---------- 3. Validation humaine ----------
def ask_human(alert, action):
    print("\n" + "-" * 60)
    print(f"Alerte {alert['alert_id']} | {alert['anomaly_type']} | "
          f"gravité {alert['severity']} | score {alert['score']}")
    print(f"Action proposée : {action['action']} sur {action['target_ip']}")
    print(f"Pourquoi        : {action['justification']}")
    if action["command"]:
        print(f"Commande        : {action['command']}")
    while True:
        rep = input("Valider cette action ? [o]ui / [n]on : ").strip().lower()
        if rep in ("o", "oui"):
            return True
        if rep in ("n", "non"):
            return False


# ---------- 4. Application ----------
def apply_action(action, real):
    if action["action"] == "notify_only" or not action["command"]:
        return "notified"
    if not real:
        return "dry-run (non exécuté)"
    # Étape 4 : exécution réelle sur la VM résolveur
    raise NotImplementedError("Exécution réelle : prévue à l'étape 4")


# ---------- Boucle principale ----------
def process(path, schema, real):
    try:
        alert = load_alert(path, schema)
    except (ValidationError, ValueError, json.JSONDecodeError) as e:
        print(f"[!] {path.name} invalide : {e}")
        log({"event": "alert_invalid", "file": path.name, "error": str(e)[:200]})
        INVALID.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), INVALID / path.name)
        return

    log({"event": "alert_received", "alert_id": alert["alert_id"]})
    for action in propose_actions(alert):
        approved = ask_human(alert, action)
        if approved:
            result = apply_action(action, real)
            print(f"-> Appliquée : {result}")
        else:
            result = "refused"
            print("-> Refusée, aucune action appliquée.")
        log({"event": "decision", "alert_id": alert["alert_id"],
             "action": action["action"], "target_ip": action["target_ip"],
             "approved": approved, "result": result})

    DONE.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), DONE / path.name)


def main():
    p = argparse.ArgumentParser(description="Agent IA DNS")
    p.add_argument("--once", action="store_true", help="traiter les alertes présentes puis quitter")
    p.add_argument("--real", action="store_true", help="exécuter réellement les commandes (étape 4)")
    args = p.parse_args()

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    INBOX.mkdir(parents=True, exist_ok=True)
    print(f"Agent démarré (mode {'RÉEL' if args.real else 'dry-run'}). Surveillance de {INBOX}")

    while True:
        for f in sorted(INBOX.glob("*.json")):
            process(f, schema, args.real)
        if args.once:
            break
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAgent arrêté.")