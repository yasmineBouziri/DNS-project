# Protocole de capture

## Requêtes de test (identiques pour chaque mode)
1. www.lab.test      type A
2. mail.lab.test     type A
3. lab.test          type NS
4. lab.test          type DNSKEY
5. inexistant.lab.test  type A   (pour observer NXDOMAIN)

## Conditions
- Cache résolveur vidé avant chaque capture (cache froid)
- Interface de capture : <à compléter>
- Client : 10.0.0.10 | Résolveur : 10.0.0.20 | Autoritatif : 10.0.0.30

## Filtres Wireshark
- Clair / DNSSEC : `port 53`
- DoT : `port 853`
- DoH : `port 443`

## Nommage des fichiers
captures/01-clair.pcap
captures/02-dnssec.pcap
captures/03-dot.pcap
captures/04-doh.pcap