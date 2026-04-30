# PROJECT: Network Monitor (Windows)

## OBJECTIF
Monitoring réseau local avec ping + HTTP + historique + alertes

---

## ARCHITECTURE

/app
  /core
    monitor.py        # logique sondes
    scanner.py        # scan réseau
    alerts.py         # email
    scheduler.py      # boucle principale

  /db
    database.py
    models.py

  /web
    app.py            # Flask
    routes.py
    templates/
    static/

  /utils
    logger.py
    config.py

/service
  windows_service.py

/main.py

---

## BASE DE DONNÉES

Tables :

- probes
- groups
- probe_results
- settings

---

## LOGIQUE

- scheduler lance les sondes
- monitor exécute ping/http
- résultats stockés en DB
- alert si seuil atteint

---

## PERFORMANCE

- threading léger
- pas de blocage
- queue pour les checks

---

## SCAN RÉSEAU

- ARP table
- ping range /24
- récupération hostname

---

## EMAIL

- SMTP SSL
- file d’envoi
- retry en cas d’échec

---

## FRONT

- Chart.js
- AJAX pour refresh
- UI simple et rapide

---

## SERVICE WINDOWS

- boucle principale
- restart automatique
- logs

---

## BUILD

pyinstaller --onefile main.py

---

## PRIORITÉS

1. stabilité
2. simplicité
3. performance
4. extensibilité