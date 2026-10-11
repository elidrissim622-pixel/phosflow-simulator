# PhosFlow Simulator - Supervision SCADA OCP

PhosFlow Simulator[cite: 1] est une application de bureau développée en Python permettant la simulation dynamique et la supervision SCADA d'un pipeline de transport de pulpe de phosphate. Ce logiciel a été conçu dans le cadre d'un projet de modélisation hydraulique pour le Groupe OCP (Station Tête, Khouribga).

L'outil modélise en temps réel la ligne piézométrique (HGL - Hydraulic Grade Line), simule la logique de contrôle-commande et permet de visualiser l'écoulement continu des lots (pulpe et eau) tout en détectant les anomalies physiques du pipeline.

## 🚀 Fonctionnalités Principales

* **Modélisation Hydraulique en Temps Réel :** Calcul dynamique et affichage de la ligne piézométrique (HGL) superposée au profil topographique du pipeline.
* **Simulation Multi-Fluides :** Gestion des injections d'eau, de pulpe (Slurry) avec calcul adaptatif de la densité, et suivi des lots (batches) le long des 187,25 km de la conduite.
* **Supervision SCADA & Télémétrie :** Interface interactive permettant d'ajuster les débits de pompe (m³/h), les pressions en tête et les appoints des stations intermédiaires (PMS).
* **Détection d'Anomalies :**
  * Détection automatique de *Slack Flow* (écoulement libre ou rupture de veine liquide).
  * Alertes de surpression en cas de dépassement de la MAOP (Maximum Allowable Operating Pressure).
  * Risque de cavitation (HGL minimum).
* **Mode Configuration de Scénarios :** Édition manuelle de la table des lots pour simuler des états initiaux spécifiques du pipeline.

## 🛠️ Technologies Utilisées

* **Langage :** Python 3.x
* **Interface Graphique :** PyQt5
* **Visualisation de Données :** Matplotlib
* **Calcul Numérique & Modélisation :** NumPy, SciPy (Interpolation Pchip)
* **Manipulation de Données :** Pandas

## 📋 Prérequis et Installation

1. **Cloner le dépôt :**
   ```bash
   git clone [https://github.com/elidrissim622-pixel/phosflow-simulator.git](https://github.com/elidrissim622-pixel/phosflow-simulator.git)
   cd phosflow-simulator