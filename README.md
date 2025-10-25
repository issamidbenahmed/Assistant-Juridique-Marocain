# Assistant Juridique Marocain 🇲🇦

Un assistant juridique intelligent basé sur l'IA pour la législation marocaine, utilisant la technologie RAG (Retrieval-Augmented Generation) pour fournir des réponses précises et contextualisées aux questions juridiques.

## 🌟 Fonctionnalités

### 🤖 Intelligence Artificielle Avancée
- **RAG Pipeline**: Recherche et génération augmentée pour des réponses précises
- **LLM Local**: Utilise Ollama avec Llama2 pour la génération de texte
- **Embeddings**: Vectorisation avec nomic-embed-text pour la recherche sémantique
- **Validation**: Validation optionnelle des réponses avec Gemini API

### 💬 Interface Utilisateur
- **Chat Intuitif**: Interface de conversation moderne et responsive
- **Citations Sources**: Chaque réponse inclut les références juridiques
- **Historique**: Sauvegarde et recherche dans l'historique des conversations
- **Multiplateforme**: Compatible desktop, tablette et mobile

### 📚 Base de Données Juridique
- **Textes Officiels**: Support pour les lois, codes et instructions marocaines
- **Recherche Vectorielle**: ChromaDB pour une recherche sémantique avancée
- **Métadonnées Riches**: Articles, chapitres, sections et références complètes
- **Mise à Jour**: Système de rechargement des données en temps réel

### 🔧 Administration
- **API REST**: Endpoints complets pour la gestion des données
- **Monitoring**: Surveillance de la santé des services
- **Logs**: Journalisation complète pour le débogage
- **Backup**: Sauvegarde et restauration de la base de données

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Frontend       │    │  Backend API    │    │  RAG Pipeline   │
│  (Angular)      │◄──►│  (FastAPI)      │◄──►│                 │
└─────────────────┘    └─────────────────┘    │  ┌─────────────┐│
                                              │  │ Embedding   ││
┌─────────────────┐    ┌─────────────────┐    │  │ Service     ││
│  ChromaDB       │    │  Ollama         │    │  └─────────────┘│
│  (Vector DB)    │◄──►│  (LLM + Embed)  │◄──►│  ┌─────────────┐│
└─────────────────┘    └─────────────────┘    │  │ LLM Service ││
                                              │  └─────────────┘│
┌─────────────────┐    ┌─────────────────┐    │  ┌─────────────┐│
│  History        │    │  Gemini API     │    │  │ Data Service││
│  (JSON)         │    │  (Optional)     │◄──►│  └─────────────┘│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Installation Rapide

### Prérequis
- **Docker** et **Docker Compose** (version 3.8+)
- **Git**
- **8GB RAM minimum** (16GB recommandé)
- **10GB d'espace disque** pour les modèles IA

### Installation Manuelle

1. **Cloner le repository**
```bash
git clone https://github.com/votre-username/assistant-juridique-marocain.git
cd assistant-juridique-marocain
```

2. **Configurer l'environnement**
```bash
# Copier le fichier d'exemple
cp .env.example .env

# Éditer la configuration si nécessaire
nano .env
```

3. **Lancer les services**
```bash
# Développement
docker-compose up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

4. **Installer les modèles IA**
```bash
# Attendre que Ollama soit démarré, puis
docker-compose exec ollama ollama pull llama2:latest
docker-compose exec ollama ollama pull nomic-embed-text:latest
```

## 📊 Accès aux Services

| Service | URL | Description |
|---------|-----|-------------|
| **Application Web** | http://localhost:4200 | Interface utilisateur principale |
| **API Backend** | http://localhost:8000 | API REST |
| **Documentation API** | http://localhost:8000/docs | Swagger UI |
| **Ollama** | http://localhost:11434 | Service IA local |
| **Prometheus** | http://localhost:9090 | Monitoring (prod) |
| **Grafana** | http://localhost:3000 | Dashboards (prod) |

## 📁 Structure du Projet

```
assistant-juridique-marocain/
├── 📁 backend/                 # API FastAPI
│   ├── 📁 app/
│   │   ├── 📁 api/             # Endpoints REST
│   │   ├── 📁 services/        # Services métier
│   │   ├── 📁 models/          # Modèles Pydantic
│   │   ├── 📁 utils/           # Utilitaires
│   │   └── 📁 core/            # Configuration
│   ├── 📁 tests/               # Tests unitaires
│   ├── 📄 requirements.txt     # Dépendances Python
│   └── 📄 Dockerfile          # Image Docker backend
├── 📁 frontend/                # Application Angular
│   ├── 📁 src/
│   │   ├── 📁 app/
│   │   │   ├── 📁 components/  # Composants UI
│   │   │   ├── 📁 services/    # Services Angular
│   │   │   └── 📁 models/      # Modèles TypeScript
│   │   └── 📁 environments/    # Configuration
│   ├── 📄 package.json        # Dépendances Node.js
│   └── 📄 Dockerfile          # Image Docker frontend
├── 📁 data/                   # Données juridiques (CSV)
├── 📁 nginx/                  # Configuration proxy
├── 📁 monitoring/             # Configuration monitoring
├── 📄 docker-compose.yml      # Orchestration développement
├── 📄 docker-compose.prod.yml # Orchestration production
```

## 📚 Utilisation

### 1. Ajouter des Données Juridiques

Placez vos fichiers CSV dans le dossier `./data/` avec la structure suivante:

```csv
document_name,article,chapter,section,pages,content
"Loi n° 17-95","Article 2","TITRE PREMIER","Section I","[5]","La société anonyme est constituée..."
```

### 2. Indexer les Documents

```bash
# Via l'API
curl -X POST http://localhost:8000/api/v1/reload-data \
  -H "Content-Type: application/json" \
  -d '{"reset_collection": true}'

# Ou via l'interface web (section Admin)
```

### 3. Poser des Questions

Accédez à http://localhost:4200 et posez vos questions:

- "Qu'est-ce qu'une société anonyme selon la loi marocaine ?"
- "Quel est le capital minimum pour créer une SARL ?"
- "Quelles sont les conditions de licenciement ?"

### 4. Explorer l'Historique

Consultez l'onglet "Historique" pour:
- Rechercher dans vos conversations passées
- Exporter l'historique en JSON
- Supprimer des conversations spécifiques

## 🔧 Configuration Avancée

### Variables d'Environnement

```bash
# API Configuration
API_V1_STR=/api/v1
PROJECT_NAME=Assistant Juridique Marocain

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2:latest
EMBEDDING_MODEL=nomic-embed-text:latest

# ChromaDB Configuration
CHROMA_DB_PATH=./chroma_db
CHROMA_COLLECTION_NAME=legal_documents

# Performance Settings
MAX_SOURCES=3
SIMILARITY_THRESHOLD=0.002

# Gemini API (optionnel)
GEMINI_API_KEY=your_api_key_here
USE_GEMINI_VALIDATION=false
```

### Personnalisation des Modèles

```bash
# Utiliser un autre modèle LLM
docker-compose exec ollama ollama pull mistral:latest
# Puis modifier OLLAMA_MODEL=mistral:latest dans .env

# Utiliser un autre modèle d'embedding
docker-compose exec ollama ollama pull all-minilm:latest
# Puis modifier EMBEDDING_MODEL=all-minilm:latest dans .env
```

### Tests unitaires 

déja testés et vérifiés

## 📊 Monitoring et Logs

### Logs en Temps Réel

```bash
# Tous les services
docker-compose logs -f

# Service spécifique
docker-compose logs -f backend
docker-compose logs -f ollama
```

### Métriques de Performance

```bash
# Santé des services
curl http://localhost:8000/health

# Statistiques de la collection
curl http://localhost:8000/api/v1/collection/stats

# Informations sur l'API
curl http://localhost:8000/info
```

### Développement
- CORS configuré pour localhost
- Validation des entrées avec Pydantic
- Logs détaillés pour le débogage


## 🚨 Dépannage

### Problèmes Courants

#### Ollama ne démarre pas
```bash
# Vérifier les logs
docker-compose logs ollama

# Redémarrer le service
docker-compose restart ollama

# Vérifier l'espace disque (modèles volumineux)
df -h
```

#### Erreur de connexion ChromaDB
```bash
# Réinitialiser la base de données
docker-compose down -v
docker-compose up -d

# Ou supprimer uniquement le volume ChromaDB
docker volume rm assistant-juridique-marocain_chroma_data
```

#### Frontend ne se charge pas
```bash
# Vérifier la construction
docker-compose logs frontend

# Reconstruire l'image
docker-compose build --no-cache frontend
```

### Commandes de Diagnostic

```bash
# Vérifier l'état des conteneurs
docker-compose ps

# Vérifier l'utilisation des ressources
docker stats

# Tester la connectivité API
curl -f http://localhost:8000/health

# Tester Ollama
curl -f http://localhost:11434/api/tags
```

## 🤝 Contribution

Nous accueillons les contributions ! Voici comment participer:

### 1. Fork et Clone
```bash
git clone https://github.com/votre-username/assistant-juridique-marocain.git
cd assistant-juridique-marocain
```

### 2. Créer une Branche
```bash
git checkout -b feature/nouvelle-fonctionnalite
```

### 3. Développer
- Suivez les conventions de code existantes
- Ajoutez des tests pour les nouvelles fonctionnalités
- Documentez les changements importants

### 4. Tester
```bash
# Backend
cd backend && python -m pytest

# Frontend
cd frontend && npm test
```

### 5. Soumettre
```bash
git add .
git commit -m "feat: ajouter nouvelle fonctionnalité"
git push origin feature/nouvelle-fonctionnalite
```

Puis créez une Pull Request sur GitHub.

### Guidelines de Contribution

- **Issues**: Utilisez les templates fournis
- **Code Style**: Suivez PEP 8 (Python) et Angular Style Guide (TypeScript)
- **Commits**: Utilisez les [Conventional Commits](https://conventionalcommits.org/)
- **Tests**: Maintenez une couverture de code > 80%


**Assistant Juridique Marocain** - Démocratiser l'accès à l'information juridique grâce à l'IA 🚀
