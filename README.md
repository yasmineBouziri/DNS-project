# DNS chiffré : DoT et DoH avec Unbound

Cette partie du projet met en place un résolveur récursif **Unbound** qui accepte, en plus du DNS classique, le **DNS over TLS (DoT, port 853)** et le **DNS over HTTPS (DoH, port 443)**, avec une PKI interne pour les certificats.

## Paramètres

| Élément | Valeur |
|---|---|
| Nom du résolveur | `resolver.lab.test` |
| Adresse du résolveur | `10.10.10.20` (et `127.0.0.1` en local) |
| Réseau autorisé | `10.10.10.0/24` |
| Zone interne transmise | `lab.test` vers `10.10.20.30` et `10.10.20.31` |
| Ports | 53 (classique), 853 (DoT), 443 (DoH, chemin `/dns-query`) |

## Contenu du dossier

| Chemin | Rôle |
|---|---|
| `pki/ca.crt` | certificat de l'autorité interne (à distribuer aux clients) |
| `pki/dns.cnf` | configuration du certificat serveur (SAN : nom, IP, 127.0.0.1) |
| `pki/dns.crt` | certificat du serveur |
| `unbound/dot-doh.conf` | copie de la configuration Unbound utilisée |
| `bench.sh` | mesure du temps de résolution (classique, DoT, DoH) |
| `cpu.sh` | mesure de la charge CPU d'Unbound par protocole |
| `mesures/` | résultats : `temps.csv`, `resume.md`, `cpu.txt`, `cpu_ms.csv` |
| `rapport/` | sorties des tests : `test_classique.txt`, `test_dot.txt`, `test_doh.txt`, `test_sans_ca.txt` |
| `captures/` | captures d'écran et de trafic (les `.pcap` ne sont pas versionnés) |

Les clés privées (`*.key`), `*.csr`, `*.srl` et `*.pcap` ne sont **jamais** versionnés (voir `.gitignore`).

## Installation

1. Générer ou récupérer la CA et le certificat serveur dans `pki/`.
2. Copier `dns.crt`, `dns.key` et `ca.crt` dans `/etc/unbound/certs/` (propriétaire `root:unbound`, clé en `640`, dossier en `750`).
3. Copier `unbound/dot-doh.conf` dans `/etc/unbound/unbound.conf.d/`.
4. Vérifier puis démarrer :

```bash
sudo unbound-checkconf
sudo systemctl restart unbound
sudo ss -tulpn | grep unbound
```

5. Installer la CA sur les clients (`/usr/local/share/ca-certificates/lab-ca.crt` puis `sudo update-ca-certificates`).

## Tests de fonctionnement

```bash
CA=pki/ca.crt
dig  @127.0.0.1 example.com
kdig @127.0.0.1 +tls   +tls-ca=$CA +tls-hostname=resolver.lab.test example.com
kdig @127.0.0.1 +https=/dns-query +tls-ca=$CA +tls-hostname=resolver.lab.test example.com
kdig @127.0.0.1 +tls   +tls-hostname=resolver.lab.test example.com   # sans CA : doit échouer
```

Le dernier test montre que le certificat n'est accepté que par les clients qui font confiance à la CA interne.

## Mesures de performance

```bash
./bench.sh example.com 50     # temps de résolution -> mesures/temps.csv, mesures/resume.md
./cpu.sh   example.com 200    # charge CPU d'Unbound -> mesures/cpu.txt, mesures/cpu_ms.csv
```

Méthode : une requête de chauffe remplit le cache d'Unbound, puis chaque protocole est interrogé N fois avec le même client (`kdig`). Chaque requête ouvre une nouvelle connexion, donc le coût de la négociation TLS est inclus pour DoT et DoH. La réponse vient du cache : la mesure isole le surcoût du transport, pas la résolution récursive.

Résultats : voir `mesures/resume.md` (temps) et `mesures/cpu.txt` (CPU).

## Preuve du chiffrement

Capture avec `tshark` sur `lo`, puis relecture :

```bash
tshark -r captures/dns_clair.pcap -Y dns     # DNS classique : nom de domaine lisible
tshark -r captures/dns_dot.pcap   -Y dns     # DoT : aucune ligne DNS (trafic TLS)
tshark -r captures/dns_doh.pcap   -Y dns     # DoH : aucune ligne DNS (trafic TLS)
```

## Limites

- `domain-insecure: "lab.test"` désactive la validation DNSSEC pour la zone interne : à retirer quand DNSSEC sera actif sur `lab.test`.
- Les tests de `lab.test` ne fonctionnent qu'une fois la VM reliée au serveur Primary.
- La CA est interne : les clients doivent installer `ca.crt` pour valider le certificat.
