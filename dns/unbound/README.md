# Attention — Configuration Unbound (Tâche 3)

Dans `dns/unbound/lab.conf`, la directive suivante est actuellement présente :

```conf
domain-insecure: "lab.test."
```

**Cette directive est temporaire !**

Elle désactive la validation DNSSEC pour la zone `lab.test`. Elle a été ajoutée pendant la tâche 3 pour permettre au resolver Unbound de résoudre correctement les noms.

### À faire dans la tâche 4 (DNSSEC)

- Supprimer `domain-insecure: "lab.test."`.
- Configurer correctement la validation DNSSEC dans Unbound.

**Ne pas oublier de retirer cette directive avant de considérer l'intégration DNSSEC terminée.**
