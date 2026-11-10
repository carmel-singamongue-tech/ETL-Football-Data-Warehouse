"""
LINAFOOT Analytics - Chaîne ETL
Sources : clubs.csv, stades.csv, matchs.csv
Cible : PostgreSQL / base linafoot_sid / schéma dw_football

Installation :
    pip install pandas sqlalchemy psycopg2-binary

Avant exécution, renseigner les paramètres PostgreSQL ci-dessous.
Placer ce fichier et les trois CSV dans le même dossier.
"""

from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# ---------------------------------------------------------------------
# 1. CONFIGURATION DE LA CONNEXION
# ---------------------------------------------------------------------
PGHOST = "localhost"
PGPORT = "5432"
PGDATABASE = "linafoot_sid"
PGUSER = "postgres"
PGPASSWORD = "Carmelo60@"  # Remplacer par votre mot de passe PostgreSQL

SCHEMA = "dw_football"
DOSSIER = Path(__file__).resolve().parent

F_CLUBS = DOSSIER / "clubs.csv"
F_STADES = DOSSIER / "stades.csv"
F_MATCHS = DOSSIER / "matchs.csv"
F_REJETS = DOSSIER / "rejets_etl.csv"

url = URL.create(
    "postgresql+psycopg2",
    username=PGUSER,
    password=PGPASSWORD,
    host=PGHOST,
    port=PGPORT,
    database=PGDATABASE,
)
engine = create_engine(url, future=True)


# ---------------------------------------------------------------------
# 2. EXTRACTION - C1
# ---------------------------------------------------------------------
def lire_sources():
    for fichier in (F_CLUBS, F_STADES, F_MATCHS):
        if not fichier.exists():
            raise FileNotFoundError(
                f"Fichier introuvable : {fichier.name}. "
                "Vérifiez que les trois CSV sont dans le dossier de etl.py."
            )

    clubs = pd.read_csv(F_CLUBS, dtype=str)
    stades = pd.read_csv(F_STADES, dtype=str)
    matchs = pd.read_csv(F_MATCHS, dtype=str)

    print("=== EXTRACTION TERMINÉE ===")
    print(f"Clubs : {len(clubs)} lignes")
    print(f"Stades : {len(stades)} lignes")
    print(f"Matchs : {len(matchs)} lignes")
    return clubs, stades, matchs


# ---------------------------------------------------------------------
# 3. NETTOYAGE ET VALIDATION - C2
# ---------------------------------------------------------------------
COLONNES_CLUBS = {"code_club", "nom_club"}
COLONNES_STADES = {"code_stade", "nom_stade"}
COLONNES_MATCHS = {
    "id_match", "saison", "club_domicile", "club_exterieur",
    "code_stade", "buts_dom", "buts_ext", "spectateurs",
    "recette_billetterie"
}


def nettoyer_referentiel(df, colonnes, nom):
    manquantes = colonnes - set(df.columns)
    if manquantes:
        raise ValueError(f"Colonnes absentes dans {nom} : {sorted(manquantes)}")

    df = df.copy()
    for col in colonnes:
        df[col] = df[col].astype("string").str.strip()

    if df[list(colonnes)].isna().any().any() or (df[list(colonnes)] == "").any().any():
        raise ValueError(f"Valeur obligatoire manquante dans {nom}.")

    doublons = df.duplicated(subset=list(colonnes), keep="first")
    if doublons.any():
        print(f"Attention : {int(doublons.sum())} doublon(s) exact(s) retiré(s) de {nom}.")
        df = df.loc[~doublons].copy()

    # Un code métier ne doit désigner qu'un seul libellé.
    if df.iloc[:, 0].duplicated().any():
        raise ValueError(f"Code métier dupliqué avec des libellés différents dans {nom}.")

    return df.reset_index(drop=True)


def nettoyer_et_valider(clubs, stades, matchs):
    clubs = nettoyer_referentiel(clubs, COLONNES_CLUBS, "clubs.csv")
    stades = nettoyer_referentiel(stades, COLONNES_STADES, "stades.csv")

    manquantes = COLONNES_MATCHS - set(matchs.columns)
    if manquantes:
        raise ValueError(f"Colonnes absentes dans matchs.csv : {sorted(manquantes)}")

    matchs = matchs.copy()
    for col in COLONNES_MATCHS:
        matchs[col] = matchs[col].astype("string").str.strip()

    rejets = []

    # Identifiants de match dupliqués : conserver la première occurrence.
    doublons = matchs["id_match"].duplicated(keep="first")
    for idx in matchs.index[doublons]:
        rejets.append({
            "ligne_source": int(idx) + 2,
            "id_match": matchs.at[idx, "id_match"],
            "motif_rejet": "Identifiant de match dupliqué"
        })
    matchs = matchs.loc[~doublons].copy()

    codes_clubs = set(clubs["code_club"])
    codes_stades = set(stades["code_stade"])
    lignes_valides = []

    colonnes_num = ["buts_dom", "buts_ext", "spectateurs", "recette_billetterie"]

    for idx, ligne in matchs.iterrows():
        motif = []

        obligatoires = [
            "id_match", "saison", "club_domicile",
            "club_exterieur", "code_stade"
        ]
        if any(pd.isna(ligne[c]) or str(ligne[c]).strip() == "" for c in obligatoires):
            motif.append("Valeur obligatoire manquante")

        valeurs = {}
        for col in colonnes_num:
            try:
                if pd.isna(ligne[col]) or str(ligne[col]).strip() == "":
                    raise ValueError
                valeurs[col] = int(ligne[col])
            except (ValueError, TypeError):
                motif.append(f"Valeur non entière ou manquante : {col}")

        if not motif:
            if any(valeurs[c] < 0 for c in colonnes_num):
                motif.append("Score, spectateurs ou recette négatif")

            if ligne["club_domicile"] not in codes_clubs:
                motif.append("Code du club à domicile inconnu")
            if ligne["club_exterieur"] not in codes_clubs:
                motif.append("Code du club extérieur inconnu")
            if ligne["club_domicile"] == ligne["club_exterieur"]:
                motif.append("Un club ne peut pas jouer contre lui-même")
            if ligne["code_stade"] not in codes_stades:
                motif.append("Code stade inconnu")

            saison = str(ligne["saison"])
            morceaux = saison.split("-")
            if (
                len(morceaux) != 2
                or not all(p.isdigit() and len(p) == 4 for p in morceaux)
                or int(morceaux[1]) != int(morceaux[0]) + 1
            ):
                motif.append("Libellé de saison invalide (format attendu AAAA-AAAA)")

        if motif:
            rejets.append({
                "ligne_source": int(idx) + 2,
                "id_match": ligne.get("id_match", ""),
                "motif_rejet": " ; ".join(motif)
            })
        
        else:
            for col, valeur in valeurs.items():
                ligne[col] = str(valeur)

            lignes_valides.append(ligne)


    matchs_valides = pd.DataFrame(lignes_valides, columns=matchs.columns).reset_index(drop=True)

    # Conserver les rejets dans un fichier pour assurer leur traçabilité.
    pd.DataFrame(
        rejets, columns=["ligne_source", "id_match", "motif_rejet"]
    ).to_csv(F_REJETS, index=False, encoding="utf-8-sig")

    print("\n=== CONTRÔLES QUALITÉ ===")
    print(f"Clubs conservés : {len(clubs)}")
    print(f"Stades conservés : {len(stades)}")
    print(f"Matchs valides : {len(matchs_valides)}")
    print(f"Rejets : {len(rejets)}")
    print(f"Fichier de traçabilité : {F_REJETS.name}")

    return clubs, stades, matchs_valides, rejets


# ---------------------------------------------------------------------
# 4. TRANSFORMATION - C3
# ---------------------------------------------------------------------
def construire_faits(matchs):
    faits = []

    for _, m in matchs.iterrows():
        saison_debut, saison_fin = map(int, str(m["saison"]).split("-"))

        # La ligne du club à domicile.
        if m["buts_dom"] > m["buts_ext"]:
            v_dom, n_dom, d_dom = 1, 0, 0
        elif m["buts_dom"] == m["buts_ext"]:
            v_dom, n_dom, d_dom = 0, 1, 0
        else:
            v_dom, n_dom, d_dom = 0, 0, 1

        faits.append({
            "id_match": m["id_match"],
            "code_club": m["club_domicile"],
            "code_club_adverse": m["club_exterieur"],
            "libelle_saison": m["saison"],
            "annee_debut": saison_debut,
            "annee_fin": saison_fin,
            "code_stade": m["code_stade"],
            "role_club": "DOMICILE",
            "buts_marques": int(m["buts_dom"]),
            "buts_encaisses": int(m["buts_ext"]),
            "victoires": v_dom,
            "nuls": n_dom,
            "defaites": d_dom,
            "spectateurs": int(m["spectateurs"]),
            "recette": int(m["recette_billetterie"]),
        })

        # La ligne du club à l'extérieur : scores et résultat inversés.
        if m["buts_ext"] > m["buts_dom"]:
            v_ext, n_ext, d_ext = 1, 0, 0
        elif m["buts_ext"] == m["buts_dom"]:
            v_ext, n_ext, d_ext = 0, 1, 0
        else:
            v_ext, n_ext, d_ext = 0, 0, 1

        faits.append({
            "id_match": m["id_match"],
            "code_club": m["club_exterieur"],
            "code_club_adverse": m["club_domicile"],
            "libelle_saison": m["saison"],
            "annee_debut": saison_debut,
            "annee_fin": saison_fin,
            "code_stade": m["code_stade"],
            "role_club": "EXTERIEUR",
            "buts_marques": int(m["buts_ext"]),
            "buts_encaisses": int(m["buts_dom"]),
            "victoires": v_ext,
            "nuls": n_ext,
            "defaites": d_ext,
            "spectateurs": 0,
            "recette": 0,
        })

    df_faits = pd.DataFrame(faits)
    print("\n=== TRANSFORMATION TERMINÉE ===")
    print(f"Nombre de lignes de faits produites : {len(df_faits)}")
    print(df_faits[[
        "id_match", "code_club", "role_club",
        "buts_marques", "buts_encaisses",
        "victoires", "nuls", "defaites",
        "spectateurs", "recette"
    ]].to_string(index=False))
    return df_faits


# ---------------------------------------------------------------------
# 5. CHARGEMENT - C4
# ---------------------------------------------------------------------
def charger_dans_postgresql(clubs, stades, matchs, df_faits):
    with engine.begin() as conn:
        # Charger les dimensions avant la table de faits.
        for _, c in clubs.iterrows():
            conn.execute(text("""
                INSERT INTO dw_football.dim_club (code_club, nom_club)
                VALUES (:code, :nom)
                ON CONFLICT (code_club)
                DO UPDATE SET nom_club = EXCLUDED.nom_club
            """), {"code": c["code_club"], "nom": c["nom_club"]})

        for _, s in stades.iterrows():
            conn.execute(text("""
                INSERT INTO dw_football.dim_stade (code_stade, nom_stade)
                VALUES (:code, :nom)
                ON CONFLICT (code_stade)
                DO UPDATE SET nom_stade = EXCLUDED.nom_stade
            """), {"code": s["code_stade"], "nom": s["nom_stade"]})

        saisons = (
            matchs[["saison"]].drop_duplicates().sort_values("saison")
        )
        for _, s in saisons.iterrows():
            debut, fin = map(int, s["saison"].split("-"))
            conn.execute(text("""
                INSERT INTO dw_football.dim_saison
                    (libelle_saison, annee_debut, annee_fin)
                VALUES (:libelle, :debut, :fin)
                ON CONFLICT (libelle_saison)
                DO UPDATE SET
                    annee_debut = EXCLUDED.annee_debut,
                    annee_fin = EXCLUDED.annee_fin
            """), {"libelle": s["saison"], "debut": debut, "fin": fin})

        # Récupérer les clés substituts des dimensions.
        clubs_keys = {
            r.code_club: r.club_key
            for r in conn.execute(text("""
                SELECT club_key, code_club FROM dw_football.dim_club
            """)).fetchall()
        }
        stades_keys = {
            r.code_stade: r.stade_key
            for r in conn.execute(text("""
                SELECT stade_key, code_stade FROM dw_football.dim_stade
            """)).fetchall()
        }
        saisons_keys = {
            r.libelle_saison: r.saison_key
            for r in conn.execute(text("""
                SELECT saison_key, libelle_saison FROM dw_football.dim_saison
            """)).fetchall()
        }

        # Supprimer les anciennes lignes des matchs présents dans ce lot,
        # puis réinsérer leurs faits : le chargement est répétable.
        ids = matchs["id_match"].tolist()
        if ids:
            conn.execute(text("""
                DELETE FROM dw_football.fait_match
                WHERE id_match = ANY(:ids)
            """), {"ids": ids})

        for _, f in df_faits.iterrows():
            conn.execute(text("""
                INSERT INTO dw_football.fait_match (
                    id_match, club_key, club_adverse_key,
                    saison_key, stade_key, role_club,
                    buts_marques, buts_encaisses,
                    victoires, nuls, defaites,
                    spectateurs, recette
                )
                VALUES (
                    :id_match, :club_key, :adverse_key,
                    :saison_key, :stade_key, :role,
                    :bm, :be, :v, :n, :d, :spectateurs, :recette
                )
            """), {
                "id_match": f["id_match"],
                "club_key": clubs_keys[f["code_club"]],
                "adverse_key": clubs_keys[f["code_club_adverse"]],
                "saison_key": saisons_keys[f["libelle_saison"]],
                "stade_key": stades_keys[f["code_stade"]],
                "role": f["role_club"],
                "bm": int(f["buts_marques"]),
                "be": int(f["buts_encaisses"]),
                "v": int(f["victoires"]),
                "n": int(f["nuls"]),
                "d": int(f["defaites"]),
                "spectateurs": int(f["spectateurs"]),
                "recette": int(f["recette"]),
            })

    print("\n=== CHARGEMENT TERMINÉ ===")
    with engine.connect() as conn:
        for table in ("dim_club", "dim_stade", "dim_saison", "fait_match"):
            nombre = conn.execute(text(
                f"SELECT COUNT(*) FROM dw_football.{table}"
            )).scalar_one()
            print(f"{table} : {nombre} lignes")


# ---------------------------------------------------------------------
# 6. EXÉCUTION GÉNÉRALE
# ---------------------------------------------------------------------
def main():
    clubs, stades, matchs = lire_sources()
    clubs, stades, matchs_valides, rejets = nettoyer_et_valider(
        clubs, stades, matchs
    )
    df_faits = construire_faits(matchs_valides)
    charger_dans_postgresql(clubs, stades, matchs_valides, df_faits)

    print("\nETL terminé avec succès.")
    if rejets:
        print(f"Consultez {F_REJETS.name} pour les lignes rejetées.")
    else:
        print("Aucun rejet : le fichier rejets_etl.csv est vide.")


if __name__ == "__main__":
    main()
