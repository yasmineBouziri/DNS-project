# Tâche 4 — DNSSEC et validation cryptographique

**Responsable :** Nour Bouchniba · **Dépend de :** Ilef (zone `lab.test`, BIND9), Malek (Unbound)
**Fournit à :** Malek (zone signée + ancre de confiance), Yasmine (mesures avec/sans validation)

Objectif : le Resolver ne se contente plus de renvoyer une IP, il **vérifie l'authenticité**
des données. Réponse valide → `NOERROR` + flag `AD`. Réponse falsifiée → `SERVFAIL`.

## Machines concernées (plan d'adressage 10.10.10.0/24)

| Machine | IP | Rôle DNSSEC |
|---|---|---|
| Primary DNS (BIND9) | 10.10.10.30 | Génère les clés, signe et sert `lab.test` |
| Secondary DNS (BIND9) | 10.10.10.31 | Reçoit la zone déjà signée par transfert |
| Resolver (Unbound) | 10.10.10.20 | Valide les signatures avec l'ancre de confiance |
| Client | 10.10.10.10 | Lance les tests |
| Attacker | 10.10.10.40 | IP utilisée pour la falsification simulée |

## Contenu

```text
dnssec/
├── configuration/
│   ├── zones/db.lab.test          zone de test (remplacée par celle d'Ilef)
│   ├── bind9/named.conf.dnssec    déclaration de la zone signée (Primary)
│   └── unbound/dnssec-lab.conf    validation + ancre de confiance (Resolver)
├── scripts/
│   ├── 01-generate-keys.sh        ZSK + KSK (ECDSAP256SHA256, algo 13)
│   ├── 02-sign-zone.sh            signature, dnssec-verify, export du DS
│   └── 03-tamper-zone.sh          scénario d'échec : break / restore
├── tests/test-dnssec.sh           valid / invalid, depuis le Client
└── captures/                      captures Wireshark (DNSKEY, RRSIG, AD, SERVFAIL)
```

## Procédure

**1. Primary (10.10.10.30)** — `sudo apt install bind9 bind9-utils`
```bash
sudo ./scripts/01-generate-keys.sh
sudo cp configuration/zones/db.lab.test /etc/bind/zones/   # ou la zone d'Ilef
sudo ./scripts/02-sign-zone.sh /etc/bind/zones/db.lab.test
# intégrer configuration/bind9/named.conf.dnssec dans /etc/bind/named.conf.local
sudo named-checkconf && sudo rndc reload lab.test
```
Après **toute** modification de la zone : relancer `02-sign-zone.sh` (le serial est incrémenté
automatiquement). Les signatures expirent au bout de 30 jours : re-signer avant la démo.

**2. Resolver (10.10.10.20)**
```bash
scp primary:/etc/bind/zones/lab.test.ds /tmp/ && sudo cp /tmp/lab.test.ds /etc/unbound/
sudo cp configuration/unbound/dnssec-lab.conf /etc/unbound/unbound.conf.d/
sudo unbound-checkconf && sudo systemctl restart unbound
```

**3. Client (10.10.10.10)**
```bash
./tests/test-dnssec.sh valid                       # NOERROR + AD + RRSIG
# sur le Primary : sudo ./scripts/03-tamper-zone.sh break
# sur le Resolver : sudo unbound-control flush_zone lab.test
./tests/test-dnssec.sh invalid                     # SERVFAIL ; avec +cd la fausse IP apparaît
# sur le Primary : sudo ./scripts/03-tamper-zone.sh restore  (+ flush sur le Resolver)
```

## Points d'attention

- **`local-zone: "test." nodefault`** est indispensable : Unbound bloque le TLD réservé `.test` par défaut.
- `lab.test` n'a pas de parent signé : la chaîne de confiance commence à l'ancre `lab.test.ds`
  (DS de la KSK). Si la KSK est régénérée, il faut recopier le DS sur le Resolver.
- Ne jamais mettre `lab.test` dans `domain-insecure` (cela désactiverait la validation).
- `03-tamper-zone.sh` ne change pas le serial : seul le Primary sert la version falsifiée.
  Si le stub-zone de Malek interroge aussi le Secondary, la réponse peut venir de ce dernier.
- Les fichiers `*.private` (clés privées) sont exclus par `.gitignore`.
- Si `root.key` manque au démarrage d'Unbound : `sudo unbound-anchor -a /var/lib/unbound/root.key`.

## Vérification

Scénario complet (signature → validation → falsification → SERVFAIL → restauration → validation)
testé dans un conteneur Ubuntu 24.04 (BIND 9.18, Unbound 1.19).

## Commandes utiles pour le rapport / Wireshark

```bash
dig @10.10.10.30 lab.test DNSKEY +dnssec +multiline    # clés 256 (ZSK) et 257 (KSK)
dig @10.10.10.20 www.lab.test +dnssec                   # flag ad + RRSIG
dig @10.10.10.20 www.lab.test +cd                       # sans validation (checking disabled)
sudo tcpdump -i enp0s8 -w captures/dnssec.pcap port 53  # capture à ouvrir dans Wireshark
```
