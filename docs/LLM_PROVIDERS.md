# LLM Provider Architecture

Paper Reproducibility Checker now supports multiple LLM providers through a pluggable abstraction layer.

## Supported Providers

### Anthropic Claude (Default)
```bash
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
export ANTHROPIC_MODEL=claude-opus-4-1  # Optional, default: claude-opus-4-1
```

### Ollama (Local)
```bash
export LLM_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434  # Optional, default: http://localhost:11434
export OLLAMA_MODEL=llama2  # Optional, default: llama2
```

**Note:** Requires Ollama running locally. Download from [ollama.ai](https://ollama.ai)

## Architecture

### Provider Interface

All providers implement `LLMProvider`:

```python
class LLMProvider:
    def complete(messages, system, max_tokens, temperature) -> str:
        """Get text completion"""
        pass
    
    def stream(messages, system, max_tokens, temperature) -> Generator[str]:
        """Stream text completion"""
        pass
    
    def get_name() -> str:
        """Provider name (e.g., 'anthropic', 'ollama')"""
        pass
    
    def get_model() -> str:
        """Current model name"""
        pass
```

### Factory Pattern

```python
from llm import get_provider

# Instantiates provider based on LLM_PROVIDER env var
provider = get_provider()

# Use same interface everywhere
response = provider.complete(
    messages=[{"role": "user", "content": "..."}],
    system="You are...",
    max_tokens=2000
)
```

## How to Add a New Provider

1. **Create provider file** in `llm/` directory:
   ```python
   # llm/my_provider.py
   from llm.provider import LLMProvider
   
   class MyProvider(LLMProvider):
       def __init__(self, model=None, api_key=None):
           # Initialize client
           pass
       
       def complete(self, messages, system=None, max_tokens=2048, temperature=0.7):
           # Call API and return response
           return response_text
       
       def stream(self, messages, system=None, max_tokens=2048, temperature=0.7):
           # Stream response chunks
           yield chunk
       
       def get_name(self):
           return "my_provider"
       
       def get_model(self):
           return self.model
   ```

2. **Register in factory** (`llm/factory.py`):
   ```python
   elif provider_name == "my_provider":
       return MyProvider()
   ```

3. **Update environment configuration** docs

4. **Test** with:
   ```bash
   export LLM_PROVIDER=my_provider
   docker-compose restart app
   # Run tests: pytest tests/
   ```

## Implementation Details

### Streaming Support

Both providers support streaming responses:

```python
# Anthropic: Uses native streaming API
for chunk in provider.stream(messages=...):
    print(chunk, end="", flush=True)

# Ollama: Uses OpenAI-compatible streaming
for chunk in provider.stream(messages=...):
    print(chunk, end="", flush=True)
```

### Error Handling

Providers raise exceptions on failures (no fallback):

```python
try:
    response = provider.complete(messages=...)
except Exception as e:
    app.logger.error(f"LLM provider failed: {e}")
    # Application handles error (return to user, retry, etc.)
```

### Response Format

Providers always return plain text (JSON parsing handled by app):

```python
response = provider.complete(messages=[
    {"role": "user", "content": "Return JSON: {...}"}
])

# App parses JSON from response
result = json.loads(response)
```

## Configuration Reference

| Variable | Provider | Required | Default | Description |
|----------|----------|----------|---------|-------------|
| `LLM_PROVIDER` | All | No | `anthropic` | Provider name |
| `ANTHROPIC_API_KEY` | Anthropic | ✅ Yes | - | API key (`sk-ant-...`) |
| `ANTHROPIC_MODEL` | Anthropic | No | `claude-opus-4-1` | Model name |
| `OLLAMA_BASE_URL` | Ollama | No | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | Ollama | No | `llama2` | Model name |

## Performance Comparison

### Anthropic Claude
- **Speed:** Fast (API latency 2-5s)
- **Cost:** ~$0.001/1K tokens (Haiku) to $0.03/1K tokens (Opus)
- **Capability:** Excellent for complex reasoning
- **Requires:** API key (cloud)

### Ollama (Local)
- **Speed:** Variable (depends on model size and hardware)
- **Cost:** Free (runs locally)
- **Capability:** Good for simple tasks (depends on model)
- **Requires:** Local setup, 4GB+ RAM

## Switching Providers

### From Anthropic to Ollama

```bash
# Stop current deployment
docker-compose down

# Edit .env
echo "LLM_PROVIDER=ollama" >> .env
echo "OLLAMA_BASE_URL=http://localhost:11434" >> .env

# Start Ollama locally (separate terminal)
ollama serve

# Pull a model
ollama pull llama2

# Restart app (will use Ollama now)
docker-compose up -d
```

### From Ollama to Anthropic

```bash
# Stop and remove .env changes
docker-compose down

# Reset to defaults or set explicitly
export ANTHROPIC_API_KEY=sk-ant-...
export LLM_PROVIDER=anthropic

# Restart
docker-compose up -d
```

## Troubleshooting

### "Unknown LLM provider: ..."
Check `LLM_PROVIDER` env var is set to valid value (anthropic|ollama)

### Anthropic: "ANTHROPIC_API_KEY environment variable is not set"
Set `ANTHROPIC_API_KEY` env var before starting app

### Ollama: "Cannot connect to Ollama at ..."
- Verify Ollama is running: `ollama serve` in separate terminal
- Verify `OLLAMA_BASE_URL` points to correct Ollama server
- Check network connectivity (if remote server)

### Ollama: "Model not found"
Pull the model first:
```bash
ollama pull llama2
# Or another model:
ollama pull mistral
ollama pull neural-chat
```

## Future Providers

Ready to add:
- OpenAI (GPT-4, GPT-3.5)
- Cohere
- Hugging Face Inference API
- AWS Bedrock
- Azure OpenAI

Just create new provider class following the interface.

## Testing

All tests pass with any provider:

```bash
# Test with Anthropic (default)
docker-compose exec app pytest tests/ -v

# Test with Ollama (set env var first)
# In .env or docker-compose.yml:
LLM_PROVIDER=ollama
docker-compose restart app
docker-compose exec app pytest tests/ -v
```

Tests don't require real API calls—they mock LLM responses—so any provider works.

---

See [ARCHITECTURE.md](./ARCHITECTURE.md) for system-wide design overview.
