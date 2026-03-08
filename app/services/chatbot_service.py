"""
DataBot — Service de chatbot intelligent pour DataPrep Pro.
Base de connaissances couvrant le pipeline, la tarification,
les contraintes, et les cas d'usage.
"""

import re
from datetime import datetime

# ================================================================
# BASE DE CONNAISSANCES
# ================================================================

KNOWLEDGE_BASE = [
    # ─── ÉTAPE 0 : AUDIT INITIAL / EDA ───
    {
        "keywords": ["audit", "eda", "exploration", "analyse exploratoire", "étape 0", "section 0", "types", "cardinalité", "initial"],
        "question_patterns": ["qu'est-ce que l'audit", "à quoi sert l'audit", "comment fonctionne l'eda", "étape 0"],
        "answer": (
            "🔍 **Étape 0 — Audit Initial (EDA)**\n\n"
            "L'audit initial est la première étape du pipeline. Il effectue :\n\n"
            "• **Correction des types** : Détecte et convertit les colonnes mal typées (ex: '100' stocké en texte → float64)\n"
            "• **Analyse de cardinalité** : Identifie les colonnes à haute cardinalité (identifiants uniques comme PID, numéros de série) et les supprime automatiquement car elles n'apportent pas d'information au modèle ML\n"
            "• **Statistiques descriptives** : mean, median, std, min, max, distribution\n"
            "• **Détection des types** : numérique, catégoriel (nominal/ordinal), texte libre, date\n\n"
            "📌 **Règle d'or** : Toujours faire l'EDA AVANT de choisir une méthode d'imputation ou de scaling.\n\n"
            "💡 **Exemple** : Si une colonne 'ST_NUM' contient '100', '104', 'nan' — elle sera convertie de Utf8 vers float64."
        )
    },
    {
        "keywords": ["type", "correction type", "utf8", "float64", "int64", "conversion", "dtype"],
        "question_patterns": ["correction des types", "comment corriger les types", "pourquoi convertir"],
        "answer": (
            "🔧 **Correction des Types (Étape 0.1)**\n\n"
            "Le système détecte automatiquement les colonnes mal typées et les corrige :\n\n"
            "• `Utf8 → float64` : Colonnes numériques stockées en texte (ex: '100.5')\n"
            "• `Utf8 → int64` : Colonnes entières stockées en texte (ex: '42')\n"
            "• Les valeurs non convertibles sont remplacées par `null`\n\n"
            "⚙️ **Fonction** : `_infer_and_cast_types()` dans `data_processing_service.py`\n\n"
            "📌 Cette étape est cruciale car les algorithmes ML ne fonctionnent qu'avec des données numériques."
        )
    },
    {
        "keywords": ["cardinalité", "haute cardinalité", "identifiant", "pid", "suppression colonne", "unique"],
        "question_patterns": ["haute cardinalité", "pourquoi supprimer", "colonne identifiant"],
        "answer": (
            "🗑️ **Suppression Haute Cardinalité (Étape C.1)**\n\n"
            "Une colonne à **haute cardinalité** a trop de valeurs uniques par rapport au nombre de lignes.\n\n"
            "• **Seuil** : Si le ratio `valeurs_uniques / total_lignes > 0.95`, la colonne est considérée comme un identifiant\n"
            "• **Exemples** : PID, numéro de série, ID client, numéro de facture\n"
            "• **Pourquoi supprimer** : Ces colonnes n'apportent aucune information prédictive au modèle ML. Les encoder créerait un nombre explosif de colonnes (OHE) ou un ordonnancement artificiel (Label Encoding)\n\n"
            "📌 Le journal indique `C.1: Colonne 'PID' supprimée (identifiant ou haute cardinalité)`"
        )
    },

    # ─── ÉTAPE A : VALEURS MANQUANTES ───
    {
        "keywords": ["valeur manquante", "missing", "nan", "null", "imputation", "étape a", "section a", "mcar", "mar", "mnar"],
        "question_patterns": ["valeurs manquantes", "comment traiter", "imputation", "mcar mar mnar", "étape a"],
        "answer": (
            "🩹 **Étape A — Traitement des Valeurs Manquantes**\n\n"
            "Le système analyse le **mécanisme de manquance** pour choisir la meilleure stratégie :\n\n"
            "| Mécanisme | Signification | Stratégie |\n"
            "|-----------|--------------|----------|\n"
            "| **MCAR** | Manquant Complètement Au Hasard | Mean/Median/Mode (simple) |\n"
            "| **MAR** | Manquant selon d'autres variables | KNNImputer ou IterativeImputer |\n"
            "| **MNAR** | Manquant selon sa propre valeur | Indicateur binaire + imputation |\n\n"
            "📊 **Seuils** :\n"
            "• < 5% manquant → Imputation simple (mean/median)\n"
            "• 5-30% → KNNImputer (si MAR) ou IterativeImputer\n"
            "• > 50% → Suppression de la colonne\n\n"
            "⚠️ **Mode Invité** : Limité à mean/median/mode. KNNImputer et IterativeImputer nécessitent un compte Starter."
        )
    },
    {
        "keywords": ["mean", "median", "mode", "moyenne", "médiane", "imputation simple"],
        "question_patterns": ["imputation simple", "mean median mode", "quand utiliser mean"],
        "answer": (
            "📐 **Imputation Simple (Mean/Median/Mode)**\n\n"
            "• **Mean (Moyenne)** : Pour les colonnes numériques sans outliers. Calcule la moyenne et remplace les NaN.\n"
            "• **Median (Médiane)** : Recommandée si des outliers existent. Plus robuste que la moyenne.\n"
            "• **Mode** : Pour les colonnes catégorielles. Utilise la valeur la plus fréquente.\n\n"
            "🔧 **Fonction** : `MissingValueHandler(strategy='auto')` choisit automatiquement.\n\n"
            "✅ Disponible pour tous les tiers (Invité, Starter, Enterprise)."
        )
    },
    {
        "keywords": ["knn", "knnimputer", "k plus proches", "voisins"],
        "question_patterns": ["knnimputer", "imputation knn", "comment fonctionne knn"],
        "answer": (
            "🤖 **KNNImputer (K-Nearest Neighbors)**\n\n"
            "Impute les valeurs manquantes en utilisant les K voisins les plus proches :\n\n"
            "1. Trouve les K lignes les plus similaires (distance euclidienne)\n"
            "2. Calcule la moyenne pondérée des valeurs des voisins\n"
            "3. Remplace la valeur manquante par cette moyenne\n\n"
            "📌 **Quand l'utiliser** : Données MAR (le manquant dépend d'autres colonnes)\n"
            "⚙️ **Paramètre** : `n_neighbors=5` par défaut\n\n"
            "🔒 **Accès** : Starter, Pro, Enterprise (bloqué en mode Invité)"
        )
    },
    {
        "keywords": ["iterative", "iterativeimputer", "mice", "imputation itérative"],
        "question_patterns": ["iterativeimputer", "imputation itérative", "mice"],
        "answer": (
            "🔄 **IterativeImputer (MICE)**\n\n"
            "Imputation multivariée itérative :\n\n"
            "1. Modélise chaque colonne manquante comme une fonction des autres colonnes\n"
            "2. Utilise un régresseur (BayesianRidge par défaut) pour prédire les valeurs\n"
            "3. Itère jusqu'à convergence (max 10 itérations)\n\n"
            "📌 **Quand l'utiliser** : Données MAR complexes avec relations multivariées\n"
            "⚙️ **Avantage** : Plus précis que KNN pour les relations non-linéaires\n\n"
            "🔒 **Accès** : Starter, Pro, Enterprise (bloqué en mode Invité)"
        )
    },

    # ─── ÉTAPE B : VALEURS ABERRANTES (OUTLIERS) ───
    {
        "keywords": ["outlier", "aberrante", "valeur aberrante", "étape b", "section b", "iqr", "zscore", "z-score"],
        "question_patterns": ["valeurs aberrantes", "outliers", "comment traiter les outliers", "étape b"],
        "answer": (
            "📊 **Étape B — Traitement des Valeurs Aberrantes**\n\n"
            "Deux approches :\n\n"
            "**Méthodes univariées** (par colonne) :\n"
            "• **IQR** : Valeurs hors [Q1-1.5×IQR, Q3+1.5×IQR] → clampées aux bornes\n"
            "• **Z-score** : Valeurs avec |z| > 3 → clampées\n\n"
            "**Méthodes multivariées** (inter-colonnes) :\n"
            "• **LOF** (Local Outlier Factor) : Détecte les anomalies par densité locale\n"
            "• **Isolation Forest** : Isole les anomalies par partitionnement aléatoire\n"
            "• **Elliptic Envelope** : Ajuste une enveloppe elliptique (distribution gaussienne)\n\n"
            "⚠️ **Mode Invité** : Seuls IQR et Z-score sont disponibles. LOF, Isolation Forest et Elliptic Envelope nécessitent un compte Starter."
        )
    },
    {
        "keywords": ["lof", "local outlier factor", "densité locale"],
        "question_patterns": ["lof", "local outlier factor", "comment fonctionne lof"],
        "answer": (
            "🔎 **LOF (Local Outlier Factor)**\n\n"
            "Détecte les outliers en comparant la densité locale d'un point à celle de ses voisins :\n\n"
            "1. Calcule la distance de chaque point à ses K plus proches voisins\n"
            "2. Estime la densité locale de chaque point\n"
            "3. Compare : si la densité d'un point est significativement plus faible que celle de ses voisins → outlier\n\n"
            "📌 **Avantage** : Détecte les outliers dans des clusters de densités différentes\n"
            "⚙️ **Paramètres** : `n_neighbors=20`, `contamination=0.1`\n\n"
            "🔒 **Accès** : Starter, Pro, Enterprise"
        )
    },
    {
        "keywords": ["isolation forest", "isolement"],
        "question_patterns": ["isolation forest", "comment fonctionne isolation forest"],
        "answer": (
            "🌲 **Isolation Forest**\n\n"
            "Isole les anomalies par partitionnement aléatoire :\n\n"
            "1. Construit des arbres en choisissant aléatoirement une feature et un seuil\n"
            "2. Les anomalies sont isolées en peu de partitions (score d'anomalie élevé)\n"
            "3. Les points normaux nécessitent beaucoup plus de partitions\n\n"
            "📌 **Avantage** : Très efficace sur les grandes dimensions, sans hypothèse de distribution\n"
            "⚙️ **Paramètre** : `contamination='auto'`\n\n"
            "🔒 **Accès** : Starter, Pro, Enterprise"
        )
    },

    # ─── ÉTAPE C : FEATURE ENGINEERING ───
    {
        "keywords": ["feature engineering", "encodage", "encoding", "étape c", "section c", "ohe", "ordinal", "label", "one hot"],
        "question_patterns": ["feature engineering", "encodage", "comment encoder", "étape c"],
        "answer": (
            "🔧 **Étape C — Feature Engineering & Encodage**\n\n"
            "Transforme les colonnes catégorielles en valeurs numériques :\n\n"
            "| Méthode | Description | Quand |\n"
            "|---------|------------|-------|\n"
            "| **OHE** | One-Hot Encoding → colonnes binaires | Nominal, faible cardinalité (≤10) |\n"
            "| **Ordinal** | Encode l'ordre (1,2,3...) | Variables ordinales (taille: S<M<L) |\n"
            "| **Label** | Encode en entiers arbitraires | Classification uniquement |\n"
            "| **Target** | Encode par la moyenne de la cible | Haute cardinalité + supervision |\n"
            "| **Frequency** | Encode par la fréquence | Haute cardinalité, non-supervisé |\n\n"
            "✅ **Mode Invité** : OHE, Ordinal, Label\n"
            "✅ **Starter** : + Target, Frequency"
        )
    },

    # ─── ÉTAPE D : NLP ───
    {
        "keywords": ["nlp", "texte", "text", "tfidf", "tf-idf", "word2vec", "bert", "camembert", "étape d", "section d", "embedding"],
        "question_patterns": ["nlp", "traitement texte", "tfidf", "word2vec", "bert", "étape d"],
        "answer": (
            "📝 **Étape D — NLP (Traitement du Langage Naturel)**\n\n"
            "Transforme les colonnes texte libre en vecteurs numériques :\n\n"
            "| Méthode | Description | Dimensions |\n"
            "|---------|------------|------------|\n"
            "| **TF-IDF** | Fréquence pondérée des termes | ~100 features |\n"
            "| **Word2Vec** | Embeddings par mot (contexte local) | 300 dim |\n"
            "| **BERT/CamemBERT** | Embeddings contextuels (transformer) | 768 dim |\n\n"
            "⚙️ **Classe** : `TextEmbedder(mode='tfidf')` dans `data_processing_service.py`\n\n"
            "🔒 **Accès** :\n"
            "• Invité : ❌ Aucun NLP\n"
            "• Starter : Tout (TF-IDF, Word2Vec, BERT)\n"
            "• Enterprise : Tout (TF-IDF, Word2Vec, BERT)"
        )
    },

    # ─── ÉTAPE E : SÉPARATION TRAIN/TEST ───
    {
        "keywords": ["split", "séparation", "train", "test", "train_test_split", "étape e", "section e"],
        "question_patterns": ["séparation", "train test split", "comment séparer", "étape e"],
        "answer": (
            "✂️ **Étape E — Séparation Train/Test**\n\n"
            "Divise le dataset en deux parties :\n\n"
            "• **Train (80%)** : Utilisé pour entraîner le modèle\n"
            "• **Test (20%)** : Utilisé pour évaluer les performances\n\n"
            "📌 **Règle d'or** : Le scaling et l'encodage sont fit sur le train UNIQUEMENT, puis appliqués au test pour éviter le data leakage.\n\n"
            "⚙️ **Fonction** : `train_test_split(test_size=0.2, random_state=42, stratify=y)`\n"
            "La stratification préserve les proportions de classes dans les deux sets."
        )
    },

    # ─── ÉTAPE F : SCALING ───
    {
        "keywords": ["scaling", "normalisation", "standardisation", "scaler", "standard", "minmax", "étape f", "section f"],
        "question_patterns": ["scaling", "normalisation", "standardisation", "comment scaler", "étape f"],
        "answer": (
            "📏 **Étape F — Scaling (Mise à l'Échelle)**\n\n"
            "| Méthode | Formule | Quand |\n"
            "|---------|---------|-------|\n"
            "| **StandardScaler** | (x - μ) / σ | Algorithmes basés sur la distance (KNN, SVM) |\n"
            "| **MinMaxScaler** | (x - min) / (max - min) | Réseaux de neurones, [0,1] requis |\n\n"
            "📌 **Ordre** : Encoder les catégorielles AVANT le scaling.\n"
            "📌 **F.2** : Les catégorielles encodées (OHE, Label) sont aussi mises à l'échelle avec MinMaxScaler pour uniformiser.\n\n"
            "⚙️ Le choix est automatique selon l'algorithme sélectionné :\n"
            "• Famille Distance (KNN, SVM) → StandardScaler activé\n"
            "• Auto → StandardScaler par défaut"
        )
    },

    # ─── ÉTAPE G : SMOTE ───
    {
        "keywords": ["smote", "rééquilibrage", "balancement", "oversampling", "suréchantillonnage", "étape g", "section g", "déséquilibre", "classes"],
        "question_patterns": ["smote", "rééquilibrage", "classes déséquilibrées", "étape g"],
        "answer": (
            "⚖️ **Étape G — SMOTE (Rééquilibrage des Classes)**\n\n"
            "SMOTE (Synthetic Minority Over-sampling Technique) génère des exemples synthétiques pour la classe minoritaire :\n\n"
            "1. Sélectionne un exemple de la classe minoritaire\n"
            "2. Trouve ses K plus proches voisins (même classe)\n"
            "3. Crée un nouveau point entre l'exemple et un voisin aléatoire\n\n"
            "📌 **Quand** : Ratio de déséquilibre > 1:3\n"
            "⚠️ **Important** : SMOTE s'applique UNIQUEMENT sur le train set (après le split)\n\n"
            "🔒 **Accès** : Starter, Pro, Enterprise (bloqué en mode Invité)"
        )
    },

    # ─── ÉTAPE H : DASHBOARD ───
    {
        "keywords": ["dashboard", "visualisation", "graphique", "chart", "étape h", "section h", "corrélation", "distribution", "scatter"],
        "question_patterns": ["dashboard", "visualisations", "graphiques", "étape h"],
        "answer": (
            "📊 **Étape H — Dashboard & Visualisations**\n\n"
            "Après le prétraitement, le dashboard affiche :\n\n"
            "• **Types & Qualité** : Répartition des types de colonnes, score de qualité\n"
            "• **Corrélation** : Matrice de corrélation (Pearson) entre variables numériques\n"
            "• **Distribution** : Histogrammes par colonne\n"
            "• **Catégories** : Diagrammes à barres pour les catégorielles\n"
            "• **Scatter Plot** : Nuage de points entre 2 variables\n"
            "• **Funnel Chart** : Visualisation en entonnoir\n"
            "• **Waterfall** : Impact des transformations sur les données\n"
            "• **Gauge** : Score global de qualité des données\n\n"
            "🔒 Certains visuels avancés (scatter, corrélation heatmap, funnel) sont bloqués en mode Invité."
        )
    },

    # ─── EXPORT ───
    {
        "keywords": ["export", "télécharger", "csv", "excel", "json", "xml", "pkl", "pickle", "format"],
        "question_patterns": ["export", "télécharger", "quel format", "comment exporter"],
        "answer": (
            "💾 **Export des Données**\n\n"
            "| Format | Description | Accès |\n"
            "|--------|------------|-------|\n"
            "| **CSV** | Comma-Separated Values | Tous (filigrane pour Invité) |\n"
            "| **Excel** | Fichier .xlsx | Starter+ |\n"
            "| **JSON** | JavaScript Object Notation | Starter+ |\n"
            "| **XML** | eXtensible Markup Language | Starter+ |\n"
            "| **PKL** | Pipeline sérialisé (pickle) | Starter+ |\n\n"
            "⚠️ **Mode Invité** : Export CSV uniquement avec un filigrane 'DataPrep Pro - Guest Export'."
        )
    },

    # ─── TARIFICATION ───
    {
        "keywords": ["tarif", "prix", "plan", "abonnement", "coût", "gratuit", "pricing", "tier", "forfait"],
        "question_patterns": ["tarifs", "prix", "combien coûte", "quel plan", "plans disponibles"],
        "answer": (
            "💰 **Plans & Tarification**\n\n"
            "| | Invité | Starter | Pro | Enterprise |\n"
            "|--|--------|---------|-----|------------|\n"
            "| **Prix** | Gratuit | Gratuit | 29€/mois | Sur mesure |\n"
            "| **Fichier max** | 5 MB | 50 MB | Illimité | Illimité |\n"
            "| **Lignes** | 1 000 | 100 000 | Illimité | Illimité |\n"
            "| **Colonnes** | 20 | 100 | Illimité | Illimité |\n"
            "| **Session** | 30 min | Illimitée | Illimitée | Illimitée |\n"
            "| **Export** | CSV seul | CSV/XLS/JSON/XML/PKL | + PKL |\n"
            "| **NLP** | ❌ | Tout | Tout |\n"
            "| **Support** | — | Prioritaire | Dédié 24/7 |\n\n"
            "💡 Le plan **Starter** est gratuit et offre toutes les fonctionnalités avancées. Inscrivez-vous en 30 secondes !"
        )
    },
    {
        "keywords": ["invité", "guest", "mode invité", "sans compte", "limite invité"],
        "question_patterns": ["mode invité", "limitations invité", "que peut faire un invité"],
        "answer": (
            "👤 **Mode Invité**\n\n"
            "Le mode invité permet de tester DataPrep Pro sans inscription :\n\n"
            "✅ **Autorisé** :\n"
            "• Fichiers jusqu'à 5 MB\n"
            "• Max 1 000 lignes / 20 colonnes\n"
            "• Audit initial + EDA de base\n"
            "• Imputation simple (mean, median, mode)\n"
            "• Encodage basique (OHE, Ordinal, Label)\n"
            "• Export CSV (avec filigrane)\n\n"
            "❌ **Bloqué** :\n"
            "• KNNImputer, IterativeImputer\n"
            "• LOF, Isolation Forest\n"
            "• NLP (TF-IDF, Word2Vec, BERT)\n"
            "• SMOTE, Réseaux de neurones\n"
            "• Sauvegarde d'historique\n\n"
            "⏰ Session limitée à **30 minutes**. Données effacées à la fermeture."
        )
    },
    {
        "keywords": ["starter", "compte gratuit", "inscription"],
        "question_patterns": ["plan starter", "avantages starter", "pourquoi starter"],
        "answer": (
            "⚡ **Plan Starter (Gratuit)**\n\n"
            "Créez un compte gratuit pour débloquer :\n\n"
            "• Fichiers jusqu'à **50 MB** (10x plus)\n"
            "• Jusqu'à **100 000 lignes** et **100 colonnes**\n"
            "• **5 fichiers** simultanés\n"
            "• **KNNImputer** et **IterativeImputer**\n"
            "• **LOF**, **Isolation Forest**, **Elliptic Envelope**\n"
            "• **Tout le NLP** : TF-IDF, Word2Vec, BERT\n"
            "• **SMOTE** pour le rééquilibrage\n"
            "• Export **CSV, Excel, JSON, XML, PKL**\n"
            "• **Données Illimitées** (taille, lignes, colonnes)\n"
            "• **Historique** des sessions sauvegardé\n"
            "• Session **illimitée** (pas de timer)\n\n"
            "💡 Inscription en 30 secondes, aucune carte bancaire requise."
        )
    },
        {
        "keywords": ["enterprise", "entreprise", "sur mesure", "déploiement", "on-premise", "api dédiée", "sla", "formation"],
        "question_patterns": ["plan enterprise", "enterprise", "sur mesure", "déploiement sur site", "contacter"],
        "answer": (
            "🏢 **Plan Enterprise (Sur Mesure)**\n\n"
            "Solution dédiée pour les grandes organisations :\n\n"
            "• **Déploiement sur site** (On-premise) pour la souveraineté des données\n"
            "• **API dédiée** pour l'intégration dans vos workflows existants\n"
            "• **SLA garanti** à 99.9% de disponibilité\n"
            "• **Formation d'équipe** personnalisée\n"
            "• **Intégrations personnalisées** (Spark, Hadoop, Airflow, etc.)\n"
            "• **Support 24/7 dédié** avec un gestionnaire de compte\n\n"
            "📧 Pour discuter de vos besoins : **sales@dataprep.pro**\n"
            "📞 Ou contactez-nous via le formulaire de contact sur la page Tarifs.\n\n"
            "💡 Nous proposons des POC (Proof of Concept) gratuits de 30 jours."
        )
    },

    # ─── CONTRAINTES ───
    {
        "keywords": ["contrainte", "limite", "restriction", "rate limit", "taux", "opération"],
        "question_patterns": ["contraintes", "quelles limites", "restrictions"],
        "answer": (
            "🚧 **Contraintes de l'Application**\n\n"
            "| Contrainte | Invité | Starter | Pro/Enterprise |\n"
            "|-----------|--------|---------|----------------|\n"
            "| Taille fichier | 5 MB | Illimité | Illimité |\n"
            "| Lignes | 1 000 | Illimité | Illimité |\n"
            "| Colonnes | 20 | Illimité | Illimité |\n"
            "| Fichiers simultanés | 1 | Illimité | Illimité |\n"
            "| Opérations/heure | 3 | Illimité | Illimité |\n"
            "| Session | 30 min | Illimitée | Illimitée |\n\n"
            "📌 Les contraintes sont vérifiées côté serveur (impossible à contourner côté client)."
        )
    },

    # ─── PIPELINE COMPLET ───
    {
        "keywords": ["pipeline", "processus", "étapes", "workflow", "autopilot", "auto-pilot", "automatique"],
        "question_patterns": ["pipeline complet", "toutes les étapes", "autopilot", "processus complet"],
        "answer": (
            "🔄 **Pipeline Complet (Auto-Pilot)**\n\n"
            "Le pipeline s'exécute dans cet ordre :\n\n"
            "1. **0 — Audit Initial** : Correction types + suppression haute cardinalité\n"
            "2. **A — Imputation** : Traitement des valeurs manquantes (MCAR/MAR/MNAR)\n"
            "3. **B — Outliers** : Détection et traitement des valeurs aberrantes\n"
            "4. **C — Engineering** : Encodage des catégorielles (OHE/Ordinal/Label)\n"
            "5. **D — NLP** : Transformation du texte libre en embeddings\n"
            "6. **E — Split** : Séparation Train/Test (80/20)\n"
            "7. **F — Scaling** : Mise à l'échelle (StandardScaler/MinMaxScaler)\n"
            "8. **G — SMOTE** : Rééquilibrage des classes (si nécessaire)\n"
            "9. **H — Dashboard** : Visualisations et rapport de qualité\n\n"
            "📌 Le mode Auto-Pilot exécute automatiquement toutes les étapes selon l'objectif (classification/régression) et l'algorithme choisi."
        )
    },

    # ─── USE CASES ───
    {
        "keywords": ["use case", "cas d'usage", "exemple", "comment traiter", "quelle méthode", "recommandation"],
        "question_patterns": ["comment traiter", "quelle méthode utiliser", "recommandation pour"],
        "answer": (
            "💡 **Cas d'Usage Courants**\n\n"
            "**🏠 Données immobilières** (ex: property data) :\n"
            "→ Objectif: classification, Algo: auto\n"
            "→ Suppression PID/numéros uniques, imputation MCAR, scaling StandardScaler\n\n"
            "**💳 Détection de fraude** :\n"
            "→ Objectif: classification, déséquilibre fort → SMOTE\n"
            "→ Outliers: Isolation Forest, Scaling: StandardScaler\n\n"
            "**📊 Prédiction de prix** :\n"
            "→ Objectif: régression, Algo: random_forest\n"
            "→ Imputation: KNNImputer, Outliers: IQR, pas de SMOTE\n\n"
            "**📝 Analyse de texte** :\n"
            "→ NLP: TF-IDF (rapide) ou BERT (précis)\n"
            "→ Disponible pour les membres Starter et Enterprise"
        )
    },

    # ─── ALGORITHMES ───
    {
        "keywords": ["algorithme", "knn", "svm", "random forest", "xgboost", "regression", "classification", "famille distance", "famille arbre"],
        "question_patterns": ["quel algorithme", "algorithmes supportés", "famille d'algorithmes"],
        "answer": (
            "🤖 **Algorithmes Supportés**\n\n"
            "**Famille Distance** (scaling requis) :\n"
            "• KNN (K-Nearest Neighbors)\n"
            "• SVM (Support Vector Machine)\n\n"
            "**Famille Arbre** (pas de scaling requis) :\n"
            "• Decision Tree\n"
            "• Random Forest\n"
            "• Gradient Boosting / XGBoost\n\n"
            "**Régression** :\n"
            "• Linear Regression / Ridge / Lasso\n\n"
            "📌 Le mode **Auto** sélectionne automatiquement le meilleur pipeline selon l'objectif et les données."
        )
    },

    # ─── AIDE GÉNÉRALE ───
    {
        "keywords": ["aide", "help", "comment", "démarrer", "commencer", "utiliser"],
        "question_patterns": ["aide", "comment commencer", "comment utiliser", "démarrer"],
        "answer": (
            "🚀 **Comment Démarrer avec DataPrep Pro**\n\n"
            "1. **Importer** : Uploadez un fichier CSV ou Excel\n"
            "2. **Analyser** : Consultez l'aperçu de vos données\n"
            "3. **Configurer** : Choisissez l'objectif (classification/régression) et l'algorithme\n"
            "4. **Lancer** : Cliquez sur 'Auto-Pilot' pour le prétraitement automatique\n"
            "5. **Exporter** : Téléchargez vos données prétraitées\n\n"
            "💡 Le mode Auto-Pilot analyse intelligemment vos données et applique les bonnes transformations automatiquement.\n\n"
            "Besoin d'aide sur une étape précise ? Demandez-moi !"
        )
    },
    {
        "keywords": ["bonjour", "salut", "hello", "hi", "hey", "coucou", "bonsoir"],
        "question_patterns": ["bonjour", "salut", "hello"],
        "answer": (
            "👋 Bonjour ! Je suis **DataBot**, l'assistant intelligent de DataPrep Pro.\n\n"
            "Je peux vous aider avec :\n"
            "• 📊 Le **pipeline de prétraitement**\n"
            "• 💰 Les **plans et tarifs** (Invité, Starter, Enterprise)\n"
            "• 🔧 Les **méthodes et algorithmes** (imputation, outliers, NLP, scaling...)\n"
            "• 💡 Des **conseils** pour traiter vos données\n\n"
            "Posez-moi votre question ! 😊"
        )
    },
    {
        "keywords": ["merci", "thank", "parfait", "super", "génial", "excellent"],
        "question_patterns": ["merci", "thanks"],
        "answer": (
            "😊 Avec plaisir ! N'hésitez pas si vous avez d'autres questions.\n\n"
            "💡 Astuce : Vous pouvez me demander des détails sur n'importe quelle étape du pipeline, "
            "les méthodes disponibles, ou les différences entre les plans."
        )
    },
]

# Réponse par défaut
DEFAULT_ANSWER = (
    "🤔 Je n'ai pas trouvé de réponse précise à votre question.\n\n"
    "Essayez de me poser une question sur :\n"
    "• Une **étape du pipeline** (audit, imputation, outliers, encodage, NLP, scaling, SMOTE)\n"
    "• Les **plans et tarifs** (Invité, Starter, Enterprise)\n"
    "• Les **contraintes** de l'application\n"
    "• Un **cas d'usage** spécifique\n\n"
    "💡 Exemples : « Comment traiter les valeurs manquantes ? », « Qu'est-ce que LOF ? », « Quels sont les plans ? »"
)


# ================================================================
# MOTEUR DE RECHERCHE
# ================================================================

def _normalize(text: str) -> str:
    """Normalise le texte pour la comparaison."""
    text = text.lower().strip()
    # Remplacer les accents courants
    replacements = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'ù': 'u', 'û': 'u', 'ü': 'u',
        'î': 'i', 'ï': 'i',
        'ô': 'o', 'ö': 'o',
        'ç': 'c',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def find_answer(question: str) -> str:
    """Trouve la meilleure réponse pour une question donnée."""
    normalized = _normalize(question)
    
    best_score = 0
    best_answer = DEFAULT_ANSWER
    
    for entry in KNOWLEDGE_BASE:
        score = 0
        
        # Score par mots-clés
        for kw in entry["keywords"]:
            kw_norm = _normalize(kw)
            if kw_norm in normalized:
                # Bonus si le mot-clé est long (plus spécifique)
                score += 2 + len(kw_norm.split())
        
        # Score par patterns de question
        for pattern in entry.get("question_patterns", []):
            pattern_norm = _normalize(pattern)
            if pattern_norm in normalized:
                score += 5  # Patterns sont plus pertinents
        
        if score > best_score:
            best_score = score
            best_answer = entry["answer"]
    
    return best_answer
