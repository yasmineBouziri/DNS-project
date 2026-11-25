# DNS Sécurisé et Résilient

Projet GL3 Réseaux — Projet 10 : du DNS classique vers DNSSEC et DoT/DoH en laboratoire.

## Objectifs

- **Déploiement initial :** infrastructure DNS classique avec serveurs autoritaires (Primary/Secondary) et résolveur local.
- **Amélioration :** DNSSEC pour l'authenticité des données, puis chiffrement de la résolution avec DNS-over-TLS et DNS-over-HTTPS.
- **Travail expérimental :** comparer sécurité, coût en ressources et temps de résolution selon les configurations.

## Outils

BIND9, Unbound, Stubby, Nginx/Caddy, Prometheus, Wireshark, dig/kdig.

## Plan d'adressage (3 zones + routeur Linux, domaine de test `lab.test`)

Conformément au cahier des charges, le laboratoire comporte **trois zones réseau reliées par un routeur Linux**. Les derniers chiffres des adresses sont ceux prévus au départ ; seul le 3e nombre change selon la zone.

| Machine | Zone | Adresse IP | Rôle |
|---|---|---|---|
| Routeur | toutes | 10.10.10.1 / 10.10.20.1 / 10.10.30.1 | Relie les 3 zones (IP forwarding activé) |
| Client | zone-clients | 10.10.10.10 | Envoie les requêtes DNS |
| Resolver | zone-clients | 10.10.10.20 | Résolution DNS avec Unbound |
| Attacker | zone-clients | 10.10.10.40 | Tests de sécurité isolés (démarré à la demande) |
| Primary DNS | zone-dns | 10.10.20.30 | Serveur BIND9 principal |
| Secondary DNS | zone-dns | 10.10.20.31 | Serveur BIND9 secondaire |
| Supervision | zone-supervision | 10.10.30.50 | Prometheus et outils de surveillance |

Réseaux : zone-clients `10.10.10.0/24`, zone-dns `10.10.20.0/24`, zone-supervision `10.10.30.0/24`.

```text
 zone-clients (10.10.10.0/24)    zone-dns (10.10.20.0/24)    zone-supervision (10.10.30.0/24)
   client .10                      primary .30                 supervision .50
   resolver .20                    secondary .31
   attacker .40
         \                              |                           /
          \_____________ ROUTEUR (.1 dans chaque zone) ____________/
```

Deux machines d'une même zone se parlent directement. Pour passer d'une zone à une autre, tout le trafic traverse le routeur (c'est aussi là que l'on pourra capturer le trafic et injecter pannes et latence).

## Organisation du dépôt

```text
Vagrantfile       laboratoire : VM, réseaux, routes (à la racine)
network/          plan d'adressage, schéma réseau
dns/bind9/        serveurs autoritaires
dns/unbound/      résolveur
dnssec/           signature des zones et validation
encrypted_dns/    DoT et DoH
monitoring/       Prometheus, métriques
machine_learning/ détection d'anomalies
ai_agent/         agent IA
wireshark/        captures et analyses
tests/            scénarios de test communs (dont test-network.sh)
documentation/    rapport
```

## Workflow Git

- `main` contient uniquement le travail intégré et testé.
- Chaque membre travaille sur sa propre branche (ex. `tache4-dnssec-validation`) dans son dossier.
- Fusion dans `main` par pull request, après test par la personne qui dépend du résultat.
- Ne jamais commiter de clés privées, certificats privés ou mots de passe.

## Indicateurs d'évaluation

Temps de résolution, disponibilité, taux d'échec, surcharge CPU, taille des échanges, comportement en cas de panne.

---

## Mise en place de l'environnement

Le laboratoire est décrit dans le fichier `Vagrantfile` : **Vagrant** crée les machines virtuelles, les réseaux, les adresses IP et les routes à partir de ce seul fichier. **Il ne faut pas installer Ubuntu à la main.** Tout le monde obtient ainsi exactement le même laboratoire.

### 1. Prérequis

- **Oracle VirtualBox** 7.x
- **Vagrant 2.4.9 ou plus récent** (version nécessaire pour VirtualBox 7.2)
- **Git** (sous Windows, installer Git pour Windows : il fournit **Git Bash**, à utiliser pour toutes les commandes ci-dessous)
- Un PC avec 8 Go de RAM minimum (16 Go recommandés), 25 Go de disque libre et la virtualisation activée dans le BIOS.

Les 6 VM utilisent environ 4,6 Go de RAM ; l'attacker ajoute 0,5 Go. Testé avec VirtualBox 7.2.6 et Vagrant 2.4.9 sous Windows.

### 2. Télécharger l'image Ubuntu (une seule fois, à faire avant la fin 2026)

Vagrant copie un modèle Ubuntu préinstallé (un *box*) pour créer chaque VM. Il se télécharge une fois, puis reste sur votre PC :

```bash
vagrant box add bento/ubuntu-24.04 --provider virtualbox --architecture amd64
vagrant box list
```

Le téléchargement fait environ 1 Go. **Faites-le maintenant :** HashiCorp ferme Vagrant Cloud (le site qui héberge ces images) fin 2026. Une fois le box sur votre PC, plus aucun téléchargement n'est nécessaire. Si quelqu'un n'arrive pas à le télécharger, il peut recopier le dossier `~/.vagrant.d/boxes` d'un coéquipier.

### 3. Démarrer le laboratoire

```bash
git clone <adresse-du-dépôt>
cd <dossier-du-dépôt>
vagrant validate        # doit afficher : Vagrantfile validated successfully.
```

Démarrez **seulement les VM dont vous avez besoin** (le `router` est toujours nécessaire, sans lui les zones ne communiquent pas) :

| Votre tâche | Commande |
|---|---|
| BIND9 (serveurs autoritaires) | `vagrant up router primary secondary` |
| Unbound, DNSSEC, DoT/DoH | `vagrant up router client resolver primary secondary` |
| Prometheus | `vagrant up router supervision resolver primary secondary` |
| ML / agent IA | commencer avec des données simulées sur votre PC |
| Tests de sécurité | ajouter `vagrant up attacker` |
| Tout le laboratoire (sauf attacker) | `vagrant up` |

Chaque VM met quelques minutes à démarrer la première fois. Attendez la ligne `Machine booted and ready!` : ne faites pas Ctrl+C pendant l'attente. L'avertissement `You assigned a static IP ending in ".1"` est normal (le routeur utilise des adresses en .1).

### 4. Vérifier

```bash
vagrant status                  # les VM démarrées doivent être "running"
bash tests/test-network.sh      # à lancer quand les 6 VM tournent
```

Le script teste 11 chemins réseau et vérifie le TTL : **64** dans une même zone, **63** quand le paquet traverse le routeur. Résultat attendu : `Result: 11 passed, 0 failed`.

### 5. Commandes utiles

| Commande | Effet |
|---|---|
| `vagrant status` | État des VM |
| `vagrant ssh <vm>` | Ouvre un terminal dans la VM (`exit` pour sortir) |
| `vagrant halt` | Éteint les VM (rien n'est perdu) |
| `vagrant up <vm>` | Démarre (ou crée) une VM |
| `vagrant provision <vm>` | Rejoue les scripts automatiques d'une VM |
| `vagrant destroy -f <vm>` | **Supprime** la VM (pas vos fichiers du dépôt), puis `vagrant up <vm>` la recrée à neuf |

Noms des VM : `router`, `client`, `resolver`, `primary`, `secondary`, `supervision`, `attacker`.

### 6. Ce qui est déjà automatisé

- Création des 6 VM (+ attacker optionnelle) avec RAM, CPU et adresses IP fixes.
- Trois réseaux isolés (zone-clients, zone-dns, zone-supervision), reliés uniquement par le routeur.
- Routeur : IP forwarding activé de façon persistante (`/etc/sysctl.d/99-lab-router.conf`).
- Routes inter-zones réappliquées **à chaque démarrage** de chaque VM (provisioner `run: "always"`) : client, resolver et attacker passent par `10.10.10.1`, primary et secondary par `10.10.20.1`, supervision par `10.10.30.1`.
- Script de test réseau : `tests/test-network.sh`.

Prévu ensuite : installation des outils communs et synchronisation de l'horloge sur toutes les VM, points de sauvegarde (snapshots), scripts de pannes et de charge, captures de trafic.

### 7. Règles

- **Ne changez pas les adresses IP ni les noms des VM** : vos configurations (BIND, Unbound, Prometheus...) en dépendent.
- **Ne modifiez pas le `Vagrantfile` sans prévenir** la personne en charge de l'environnement : un seul fichier partagé crée vite des conflits. Pour automatiser votre partie (installer BIND9, Unbound...), mettez vos scripts dans votre dossier et demandez qu'ils soient branchés dans le bloc de votre VM.
- **Tout doit être dans des scripts versionnés.** Une VM est jetable : si elle est cassée, `vagrant destroy -f <vm>` puis `vagrant up <vm>`. Ce que vous avez installé à la main dedans sera perdu.
- Après un `git pull` qui change l'IP ou le réseau d'une VM, recréez-la (`vagrant destroy -f <vm>` puis `vagrant up <vm>`) : Vagrant ne peut pas modifier le réseau d'une VM existante.
- Ne jamais commiter de clés ni de mots de passe (`.vagrant/`, `*.key` et `*.private` sont déjà ignorés par Git).

### 8. Dépannage

| Problème | Solution |
|---|---|
| `vagrant: command not found` | Fermer et rouvrir Git Bash ; redémarrer le PC après l'installation de Vagrant |
| Bloqué sur `Waiting for machine to boot` plus de 5 à 10 min | Ouvrir la VM dans VirtualBox pour voir son écran, puis `vagrant halt -f <vm>` et `vagrant up <vm>` |
| `Guest communication could not be established` ou `Connection reset` | Même procédure ; si cela persiste : `vagrant destroy -f <vm>` puis `vagrant up <vm>` |
| `syntax error` dans le Vagrantfile | Ne pas deviner : `git checkout Vagrantfile` restaure la version du dépôt (efface vos modifications locales) |
| Un test réseau échoue | `vagrant ssh <vm> -c "ip route"` pour voir les routes, puis `vagrant provision <vm>` pour les réappliquer |
| Le box est introuvable au téléchargement | Demander le dossier `~/.vagrant.d/boxes` à un coéquipier (voir l'étape 2) |
| Chemin du projet avec espaces ou accents | Déplacer le dépôt dans un chemin simple, par exemple `C:\Users\<nom>\DNS-project` |