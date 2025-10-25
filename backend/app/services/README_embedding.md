# Embedding Service Documentation

## Overview

The `EmbeddingService` provides text vectorization capabilities using Ollama's embedding models. It's designed for the Assistant Juridique Marocain to convert legal text into vector representations for similarity search and retrieval.

## Features

- **Single and Batch Embedding**: Generate embeddings for individual texts or process multiple texts concurrently
- **Automatic Retry Logic**: Built-in retry mechanism for handling temporary failures
- **Health Monitoring**: Comprehensive health checks for service and model availability
- **Model Management**: Switch between different embedding models dynamically
- **Performance Optimization**: Configurable concurrency limits and connection pooling
- **Error Handling**: Detailed error reporting and logging

## Configuration

The service uses the following configuration options from `settings`:

```python
OLLAMA_BASE_URL = "http://localhost:11434"      # Ollama server URL
EMBEDDING_MODEL = "nomic-embed-text"            # Default embedding model
OLLAMA_TIMEOUT = 30.0                           # Request timeout in seconds
OLLAMA_MAX_RETRIES = 3                          # Maximum retry attempts
OLLAMA_RETRY_DELAY = 1.0                        # Delay between retries
EMBEDDING_MAX_CONCURRENT = 5                    # Max concurrent requests
```

## Usage Examples

### Basic Usage

```python
from app.services.embedding_service import EmbeddingService

# Initialize the service
service = EmbeddingService()

# Generate embedding for a single text
embedding = await service.embed_text("Qu'est-ce qu'une société anonyme?")
print(f"Embedding dimension: {len(embedding)}")

# Generate embeddings for multiple texts
texts = ["Article 1", "Article 2", "Article 3"]
embeddings = await service.embed_batch(texts)
print(f"Generated {len(embeddings)} embeddings")

# Clean up
await service.close()
```

### Health Monitoring

```python
# Check service health
health = await service.check_health()
if health["healthy"]:
    print(f"Service is healthy, model dimension: {health['model_info']['embedding_dimension']}")
else:
    print(f"Service unhealthy: {health['error']}")
```

### Model Management

```python
# Get available models
models = await service.get_available_models()
for model in models:
    print(f"Available model: {model['name']}")

# Switch to a different model
await service.switch_model("all-minilm")
```

## Error Handling

The service raises `EmbeddingServiceError` for various failure scenarios:

- **Connection Errors**: When Ollama server is unreachable
- **Model Errors**: When the specified model is not available
- **Validation Errors**: When input text is empty or invalid
- **API Errors**: When Ollama returns error responses

## Performance Considerations

- **Batch Processing**: Use `embed_batch()` for multiple texts to leverage concurrency
- **Concurrency Limits**: Adjust `EMBEDDING_MAX_CONCURRENT` based on your Ollama server capacity
- **Connection Pooling**: The service maintains persistent HTTP connections for efficiency
- **Retry Logic**: Automatic retries handle temporary network issues

## Testing

Run the connection test script to verify your setup:

```bash
cd backend
python test_ollama_connection.py
```

This will test:
- Service configuration
- Ollama connectivity
- Model availability
- Single and batch embedding generation

## Requirements

- Ollama server running locally or remotely
- Embedding model installed (e.g., `ollama pull nomic-embed-text`)
- Python dependencies: `httpx`, `asyncio`

## Troubleshooting

### Common Issues

1. **Connection Refused**: Ensure Ollama is running (`ollama serve`)
2. **Model Not Found**: Install the model (`ollama pull nomic-embed-text`)
3. **Timeout Errors**: Increase `OLLAMA_TIMEOUT` for large texts
4. **Memory Issues**: Reduce `EMBEDDING_MAX_CONCURRENT` for resource-constrained environments

### Logging

The service logs important events at different levels:
- `INFO`: Successful operations and performance metrics
- `WARNING`: Non-critical issues like model availability
- `ERROR`: Failures and exceptions
- `DEBUG`: Detailed timing and dimension information