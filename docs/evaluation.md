# Évaluation du modèle

*Généré automatiquement par `python -m goutte.train` le 2026-11-26T08:52:12+00:00.*

- Région : **Bretagne** (4 stations SYNOP)
- Cible : jour de pluie = cumul ≥ 1.0 mm sur la journée UTC
- Période de test (jamais vue à l'apprentissage) : 2024-01-01 → 2026-01-14
- Taux de jours de pluie sur le test : 35.1%
- Modèle retenu : **random_forest**

## Résultats

|                              |   roc_auc |   brier |   accuracy |   precision |   rappel |     f1 |   duree_entrainement_s |
|:-----------------------------|----------:|--------:|-----------:|------------:|---------:|-------:|-----------------------:|
| reference_climatologie       |    0.5936 |  0.2242 |     0.6454 |      0.4906 |   0.2421 | 0.3242 |                        |
| reference_persistance        |    0.6508 |  0.3124 |     0.6876 |      0.5587 |   0.5272 | 0.5425 |                        |
| regression_logistique        |    0.7738 |  0.1837 |     0.7236 |      0.6562 |   0.4482 | 0.5326 |                   0.03 |
| random_forest                |    0.7771 |  0.1793 |     0.7272 |      0.6369 |   0.52   | 0.5726 |                   0.51 |
| gradient_boosting            |    0.7645 |  0.185  |     0.724  |      0.6305 |   0.5179 | 0.5687 |                   0.49 |
| climatologie_ml (date seule) |    0.6032 |  0.2219 |     0.6523 |      0.5116 |   0.2256 | 0.3132 |                        |

- **ROC AUC** : capacité à classer un jour pluvieux au-dessus d'un jour sec (0,5 = hasard, 1 = parfait).
- **Brier** : erreur quadratique sur la probabilité (plus bas = mieux calibré).
- **Précision / rappel / F1** : calculés au seuil de décision de 50 %.

## Variables les plus importantes

| Variable | Importance |
|---|---|
| pluie_mm_j1 | 0.192 |
| pmer_moy_j1 | 0.187 |
| pmer_var_j1 | 0.1531 |
| pmer_moy_j2 | 0.1019 |
| doy_cos | 0.0793 |
| pluie_mm_j2 | 0.0615 |
| vent_moy_j1 | 0.043 |
| t_moy_j1 | 0.0358 |
| nebulosite_moy_j1 | 0.0305 |
| ecart_rosee_j1 | 0.0265 |
