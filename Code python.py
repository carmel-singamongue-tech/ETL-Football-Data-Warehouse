
import pandas as pd
from pathlib import Path

# Récupérer le dossier où se trouve ce script
dossier = Path(__file__).parent

# Lecture des fichiers CSV
clubs = pd.read_csv(dossier / "clubs.csv", dtype=str)
stades = pd.read_csv(dossier / "stades.csv", dtype=str)
matchs = pd.read_csv(dossier / "matchs.csv")

# Affichage des données
print("=== CLUBS ===")
print(clubs)

print("\n=== STADES ===")
print(stades)

print("\n=== MATCHS ===")
print(matchs)

# Nombre de lignes
print("\nNombre de clubs :", len(clubs))
print("Nombre de stades :", len(stades))
print("Nombre de matchs :", len(matchs))

# ==================================================
# PARTIE C : PROCESSUS ETL AVEC PYTHON
# ÉTAPE 5 : CONTRÔLE DE LA QUALITÉ DES DONNÉES
# ==================================================

print("\n=== VALEURS MANQUANTES ===")
print("Clubs :")
print(clubs.isnull().sum())

print("\nStades :")
print(stades.isnull().sum())

print("\nMatchs :")
print(matchs.isnull().sum())

print("\n=== DOUBLONS ===")
print("Doublons clubs :", clubs.duplicated().sum())
print("Doublons stades :", stades.duplicated().sum())
print("Doublons matchs :", matchs.duplicated().sum())

print("\n=== VALEURS NEGATIVES ===")
print("Buts domicile :", (matchs["buts_dom"] < 0).sum())
print("Buts extérieur :", (matchs["buts_ext"] < 0).sum())
print("Spectateurs :", (matchs["spectateurs"] < 0).sum())
print("Recettes :", (matchs["recette_billetterie"] < 0).sum())


# ==================================================
# PARTIE C : PROCESSUS ETL
# C2 : VERIFICATION DES REFERENCES
# ==================================================

print("\n=== VERIFICATION DES REFERENCES ===")

# Vérification des clubs à domicile
clubs_domicile_invalides = matchs[
    ~matchs["club_domicile"].isin(clubs["code_club"])
]

# Vérification des clubs à l'extérieur
clubs_exterieur_invalides = matchs[
    ~matchs["club_exterieur"].isin(clubs["code_club"])
]

# Vérification des stades
stades_invalides = matchs[
    ~matchs["code_stade"].isin(stades["code_stade"])
]

print("Clubs domicile inconnus :", len(clubs_domicile_invalides))
print("Clubs extérieur inconnus :", len(clubs_exterieur_invalides))
print("Stades inconnus :", len(stades_invalides))

# Vérification des clubs identiques
clubs_identiques = matchs[
    matchs["club_domicile"] == matchs["club_exterieur"]
]

print("Matchs avec clubs identiques :", len(clubs_identiques))

print("\n=== FIN DU CONTROLE C2 ===")


# ==========================================================
# PARTIE C : PROCESSUS ETL AVEC PYTHON
# C3 : DECOMPOSITION DES SCORES ET CREATION DE DEUX
#      LIGNES DE FAITS PAR MATCH
# ==========================================================

lignes_faits = []

for _, match in matchs.iterrows():

    # Décomposition du score
    buts_dom = int(match["buts_dom"])
    buts_ext = int(match["buts_ext"])

    # Détermination du résultat
    if buts_dom > buts_ext:
        victoire_dom, nul_dom, defaite_dom = 1, 0, 0
        victoire_ext, nul_ext, defaite_ext = 0, 0, 1

    elif buts_dom < buts_ext:
        victoire_dom, nul_dom, defaite_dom = 0, 0, 1
        victoire_ext, nul_ext, defaite_ext = 1, 0, 0

    else:
        victoire_dom, nul_dom, defaite_dom = 0, 1, 0
        victoire_ext, nul_ext, defaite_ext = 0, 1, 0

    # Première ligne : club à domicile
    lignes_faits.append({
        "id_match": match["id_match"],
        "saison": match["saison"],
        "code_stade": match["code_stade"],
        "code_club": match["club_domicile"],
        "code_club_adverse": match["club_exterieur"],
        "role_club": "DOMICILE",
        "buts_marques": buts_dom,
        "buts_encaisses": buts_ext,
        "victoires": victoire_dom,
        "nuls": nul_dom,
        "defaites": defaite_dom,
        "spectateurs": int(match["spectateurs"]),
        "recette": int(match["recette_billetterie"])
    })

    # Deuxième ligne : club à l'extérieur
    lignes_faits.append({
        "id_match": match["id_match"],
        "saison": match["saison"],
        "code_stade": match["code_stade"],
        "code_club": match["club_exterieur"],
        "code_club_adverse": match["club_domicile"],
        "role_club": "EXTERIEUR",
        "buts_marques": buts_ext,
        "buts_encaisses": buts_dom,
        "victoires": victoire_ext,
        "nuls": nul_ext,
        "defaites": defaite_ext,
        "spectateurs": 0,
        "recette": 0
    })

# Création du DataFrame des faits
fait_match_df = pd.DataFrame(lignes_faits)

# Affichage des données transformées
print("\n=== TABLE DE FAITS TRANSFORMEE ===")
print(fait_match_df.to_string(index=False))

# Vérification du nombre de lignes
print("\nNombre de matchs :", len(matchs))
print("Nombre de lignes de faits :", len(fait_match_df))

# Vérification des totaux
print("Total spectateurs :", fait_match_df["spectateurs"].sum())
print("Total recettes :", fait_match_df["recette"].sum())

# Vérification des rôles
print("\nRépartition des rôles :")
print(fait_match_df["role_club"].value_counts())


# ==================================================
# PARTIE C : PROCESSUS ETL
# C4 : CHARGEMENT DES DONNEES DANS POSTGRESQL
# ETAPE 1 : CONNEXION A LA BASE DE DONNEES
# ==================================================


import psycopg2

# Paramètres de connexion à PostgreSQL
connexion = psycopg2.connect(
    host="localhost",
    port="5432",
    database="linafoot_sid",
    user="postgres",
    password="Carmelo60@"
)

# Vérification de la connexion
if connexion:
    print("\nConnexion à PostgreSQL réussie !")

# Fermeture de la connexion de test
connexion.close()
print("Connexion fermée.")
