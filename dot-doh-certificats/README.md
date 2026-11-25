# DoT / DoH / Certificats

## Contenu
- pki/ : CA du labo (ca.crt) et dns.cnf
- unbound/dot-doh.conf : configuration du résolveur chiffré
- bench.sh : script de mesure
- mesures/ : resultants (temps, CPU)
- rapport/ : sorties des tests

## Mise en place
1. Installer unbound, kdig
2. Générer CA et certificat (voir pki/dns.cnf)
3. Copier unbound/dot-doh.conf dans /etc/unbound/unbound.conf.d/
4. sudo systemctl restart unbound

## Intégration
- Fournir ca.crt aux cliens
- Ajouter forward-zone vers le serveur autoritatif


