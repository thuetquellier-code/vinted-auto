import os, time, sqlite3, threading, random
from datetime import datetime
from zoneinfo import ZoneInfo

MESSAGE_JOUR = "Bonjour, je passe au point relais cet après-midi, je pourrais y déposer celui-ci. Bonne journée."
MESSAGE_SOIR = "Bonsoir, je passe au point relais demain matin si vous voulez le prendre rapidement."
INTERVALLE = 600
MAX_PAR_HEURE = 60

def message_du_moment():
    heure = datetime.now(ZoneInfo("Europe/Paris")).hour
    return MESSAGE_JOUR if 8 <= heure < 18 else MESSAGE_SOIR

db = sqlite3.connect("favoris.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS envoyes (utilisateur TEXT, article TEXT, date REAL, PRIMARY KEY (utilisateur, article))")

def recuperer_favoris():
    raise NotImplementedError

def envoyer_message(utilisateur, article, texte):
    raise NotImplementedError

def deja_envoye(u, a):
    return db.execute("SELECT 1 FROM envoyes WHERE utilisateur=? AND article=?", (u, a)).fetchone() is not None

def envoyes_derniere_heure():
    return db.execute("SELECT COUNT(*) FROM envoyes WHERE date > ?", (time.time() - 3600,)).fetchone()[0]

def tour():
    for fav in recuperer_favoris():
        u, a = str(fav["utilisateur"]), str(fav["article"])
        if deja_envoye(u, a):
            continue
        if envoyes_derniere_heure() >= MAX_PAR_HEURE:
            break
        envoyer_message(u, a, message_du_moment())
        db.execute("INSERT INTO envoyes VALUES (?,?,?)", (u, a, time.time()))
        db.commit()
        time.sleep(random.randint(20, 60))

def boucle():
    while True:
        try:
            tour()
        except NotImplementedError:
            pass
        except Exception as e:
            print("Erreur favoris :", e)
        time.sleep(INTERVALLE)

def demarrer():
    threading.Thread(target=boucle, daemon=True).start()
