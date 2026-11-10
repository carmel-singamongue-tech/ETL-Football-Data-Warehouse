-- ============================================================
-- LINAFOOT SID - analyses.sql
-- Requêtes analytiques de la partie D
-- Base : linafoot_sid | Schéma : dw_football
-- ============================================================

-- D1. Nombre de buts marqués par club et par saison
SELECT
    c.nom_club,
    s.libelle_saison,
    SUM(f.buts_marques) AS total_buts_marques
FROM dw_football.fait_match AS f
INNER JOIN dw_football.dim_club AS c
    ON f.club_key = c.club_key
INNER JOIN dw_football.dim_saison AS s
    ON f.saison_key = s.saison_key
GROUP BY
    c.nom_club,
    s.libelle_saison
ORDER BY
    s.libelle_saison,
    total_buts_marques DESC;


-- D2. Nombre total de victoires par club
SELECT
    c.nom_club,
    SUM(f.victoires) AS total_victoires
FROM dw_football.fait_match AS f
INNER JOIN dw_football.dim_club AS c
    ON f.club_key = c.club_key
GROUP BY
    c.nom_club
ORDER BY
    total_victoires DESC,
    c.nom_club;


-- D3. Nombre total de spectateurs par stade
SELECT
    st.nom_stade,
    SUM(f.spectateurs) AS total_spectateurs
FROM dw_football.fait_match AS f
INNER JOIN dw_football.dim_stade AS st
    ON f.stade_key = st.stade_key
GROUP BY
    st.nom_stade
ORDER BY
    total_spectateurs DESC;


-- D4. Recettes totales de billetterie par saison
SELECT
    s.libelle_saison,
    SUM(f.recette) AS recette_totale
FROM dw_football.fait_match AS f
INNER JOIN dw_football.dim_saison AS s
    ON f.saison_key = s.saison_key
GROUP BY
    s.libelle_saison
ORDER BY
    s.libelle_saison;


-- D5. Buts marqués, encaissés et différence de buts par club
SELECT
    c.nom_club,
    SUM(f.buts_marques) AS total_buts_marques,
    SUM(f.buts_encaisses) AS total_buts_encaisses,
    SUM(f.buts_marques) - SUM(f.buts_encaisses)
        AS difference_buts
FROM dw_football.fait_match AS f
INNER JOIN dw_football.dim_club AS c
    ON f.club_key = c.club_key
GROUP BY
    c.nom_club
ORDER BY
    difference_buts DESC,
    c.nom_club;


-- Contrôle facultatif : nombre de lignes dans chaque table
SELECT 'dim_club' AS table_name, COUNT(*) AS nombre_lignes
FROM dw_football.dim_club
UNION ALL
SELECT 'dim_stade', COUNT(*)
FROM dw_football.dim_stade
UNION ALL
SELECT 'dim_saison', COUNT(*)
FROM dw_football.dim_saison
UNION ALL
SELECT 'fait_match', COUNT(*)
FROM dw_football.fait_match;
