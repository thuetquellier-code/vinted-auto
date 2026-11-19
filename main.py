import os, json, sqlite3, uuid, pathlib, base64, traceback
from io import BytesIO
from PIL import Image
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from openai import OpenAI

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
MODELES = [m for m in [
    os.environ.get("GROQ_MODEL"),
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "qwen/qwen3.6-27b",
] if m]
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
Si une info n'est pas visible, mets null. Aucun texte en dehors du JSON."""

CHAMPS = ["titre", "description", "categorie", "marque", "taille", "couleur", "matiere", "etat", "prix_conseille"]
MAX_PHOTOS_IA = 3
TAILLE_MAX = 768

def reduire(chemin):
    img = Image.open(chemin).convert("RGB")
    img.thumbnail((TAILLE_MAX, TAILLE_MAX))
    tampon = BytesIO()
    img.save(tampon, format="JPEG", quality=75)
    return base64.b64encode(tampon.getvalue()).decode()

def analyser(chemins):
    contenu = [{"type": "text", "text": PROMPT}]
    for p in chemins[:MAX_PHOTOS_IA]:
        contenu.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + reduire(p)}})
    erreurs = []
    for modele in MODELES:
        try:
            rep = client.chat.completions.create(
                model=modele,
                messages=[{"role": "user", "content": contenu}],
                temperature=0.4,
            )
            texte = rep.choices[0].message.content
            texte = texte[texte.find("{"): texte.rfind("}") + 1]
            donnees = json.loads(texte)
            for c in CHAMPS:
                donnees.setdefault(c, None)
            donnees["modele_utilise"] = modele
            return donnees
        except Exception as e:
            erreurs.append(modele + " : " + str(e)[:300])
    raise RuntimeError(" | ".join(erreurs))

def envoyer_brouillon_vinted(donnees, chemins):
    raise NotImplementedError

def balise(t):
    return "<" + t + ">"

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def accueil():
    return (
        balise("h2") + "Nouvelle annonce" + balise("/h2")
        + balise("form action='/annonce' method='post' enctype='multipart/form-data'")
        + balise("input type='file' name='photos' multiple accept='image/*'")
        + balise("button") + "Generer" + balise("/button")
        + balise("/form")
    )

@app.post("/annonce")
async def creer(photos: list[UploadFile] = File(...)):
    try:
        aid = uuid.uuid4().hex[:8]
        chemins = []
        for i, f in enumerate(photos):
            p = DOSSIER / (aid + "_" + str(i).zfill(2) + ".jpg")
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
    except Exception as e:
        return JSONResponse({"erreur": str(e), "detail": traceback.format_exc()[-1500:]}, status_code=500)

@app.get("/annonces")
def lister():
    lignes = db.execute("SELECT id, donnees, statut FROM annonces").fetchall()
    return [{"id": i, "statut": s, **json.loads(d)} for i, d, s in lignes]
