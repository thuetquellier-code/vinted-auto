import os, time, sqlite3, threading, random

MESSAGE = os.environ.get("MESSAGE_FAVORI", "Bonjour ! Merci pour le favori, n'hesite pas si tu as une question :)")
INTERVALLE = 600
MAX_PAR_HEURE = 60

db = sqlite3.connect("favoris.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS envoyes (utilisateur TEXT, article TEXT, date REAL, PRIMARY KEY (utilisateur, article))")

def recuperer_favoris():
    # A brancher sur ton API Vinted : renvoie [{"utilisateur": "id", "article": "id"}, ...]
    raise NotImplementedError

def envoyer_message(utilisateur, article, texte):
    # A brancher sur ton API Vinted.
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
        envoyer_message(u, a, MESSAGE)
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
