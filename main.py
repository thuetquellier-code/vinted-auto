import os, json, sqlite3, uuid, pathlib
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODELE = "gemini-2.5-flash"
DOSSIER = pathlib.Path("photos"); DOSSIER.mkdir(exist_ok=True)

db = sqlite3.connect("annonces.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS annonces (id TEXT PRIMARY KEY, photos TEXT, donnees TEXT, statut TEXT)")

PROMPT = """Tu es une experte de la vente sur Vinted.
Analyse les photos de cet article et renvoie UNIQUEMENT un JSON avec :
titre, description, categorie, marque, taille, couleur, matiere, etat, prix_conseille.
Titre : type + marque + detail distinctif + couleur + taille, 60 caracteres max.
Description : etat, matiere, coupe, mesures si visibles, 3 mots-cles de recherche, ton chaleureux.
etat parmi : Neuf avec etiquette, Neuf sans etiquette, Tres bon etat, Bon etat, Satisfaisant.
prix_conseille en euros, realiste pour la seconde main.
Si une info n'est pas visible, mets null."""

CHAMPS = ["titre", "description", "categorie", "marque", "taille", "couleur", "matiere", "etat", "prix_conseille"]

def analyser(chemins):
    parties = [types.Part.from_bytes(data=p.read_bytes(), mime_type="image/jpeg") for p in chemins]
    rep = client.models.generate_content(
        model=MODELE,
        contents=parties + [PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    donnees = json.loads(rep.text)
    for c in CHAMPS:
        donnees.setdefault(c, None)
    return donnees

def envoyer_brouillon_vinted(donnees, chemins):
    # A brancher sur l'API Vinted que tu auras trouvee.
    # Les photos sont deja dans l'ordre d'envoi (chemins).
    raise NotImplementedError

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def accueil():
    return """<h2>Nouvelle annonce</h2>
    <form action='/annonce' method='post' enctype='multipart/form-data'>
    <input type='file' name='photos' multiple accept='image/*'>
    <button>Generer</button></form>"""

@app.post("/annonce")
async def creer(photos: list[UploadFile] = File(...)):
    aid = uuid.uuid4().hex[:8]
    chemins = []
    for i, f in enumerate(photos):  # i garde l'ordre d'envoi
        p = DOSSIER / f"{aid}_{i:02d}.jpg"
        p.write_bytes(await f.read())
        chemins.append(p)
    donnees = analyser(chemins)
    statut = "genere"
    try:
        envoyer_brouillon_vinted(donnees, chemins)
        statut = "brouillon_vinted"
    except NotImplementedError:
        pass
    db.execute("INSERT INTO annonces VALUES (?,?,?,?)",
               (aid, json.dumps([str(c) for c in chemins]), json.dumps(donnees, ensure_ascii=False), statut))
    db.commit()
    return {"id": aid, "statut": statut, **donnees}

@app.get("/annonces")
def lister():
    lignes = db.execute("SELECT id, donnees, statut FROM annonces").fetchall()
    return [{"id": i, "statut": s, **json.loads(d)} for i, d, s in lignes]
