# DNS Sécurisé et Résilient

Projet GL3 Réseaux — Projet 10 : du DNS classique vers DNSSEC et DoT/DoH en laboratoire.

## Objectifs

- **Déploiement initial :** infrastructure DNS classique avec serveurs autoritaires (Primary/Secondary) et résolveur local.
- **Amélioration :** DNSSEC pour l'authenticité des données, puis chiffrement de la résolution avec DNS-over-TLS et DNS-over-HTTPS.
- **Travail expérimental :** comparer sécurité, coût en ressources et temps de résolution selon les configurations.

## Outils

BIND9, Unbound, Stubby, Nginx/Caddy, Prometheus, Wireshark, dig/kdig.

## Plan d'adressage (10.10.10.0/24, domaine de test `lab.test`)

| Machine | Adresse IP | Rôle |
|---|---|---|
| Client | 10.10.10.10 | Envoie les requêtes DNS |
| Resolver | 10.10.10.20 | Résolution DNS avec Unbound |
| Primary DNS | 10.10.10.30 | Serveur BIND9 principal |
| Secondary DNS | 10.10.10.31 | Serveur BIND9 secondaire |
| Attacker | 10.10.10.40 | Tests de sécurité isolés |
| Supervision | 10.10.10.50 | Prometheus et outils de surveillance |

## Organisation du dépôt

```text
network/          plan d'adressage, schéma réseau
dns/bind9/        serveurs autoritaires
dns/unbound/      résolveur
dnssec/           signature des zones et validation
encrypted_dns/    DoT et DoH
monitoring/       Prometheus, métriques
machine_learning/ détection d'anomalies
ai_agent/         agent IA
wireshark/        captures et analyses
tests/            scénarios de test communs
documentation/    rapport
```

## Workflow Git

- `main` contient uniquement le travail intégré et testé.
- Chaque membre travaille sur sa propre branche (ex. `tache4-dnssec-validation`) dans son dossier.
- Fusion dans `main` par pull request, après test par la personne qui dépend du résultat.
- Ne jamais commiter de clés privées, certificats privés ou mots de passe.

## Indicateurs d'évaluation

Temps de résolution, disponibilité, taux d'échec, surcharge CPU, taille des échanges, comportement en cas de panne.
