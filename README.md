# Happ Decrypt API

Public API that decrypts `happ://` subscription links and forwards results to your Telegram channel.

## API Usage

### `POST /decrypt`

```json
{
  "link": "happ://crypt/your-encrypted-link"
}
```

**Response:**
```json
{
  "success": true,
  "original_link": "happ://crypt/...",
  "decrypted_url": "https://...",
  "telegram_sent": true
}
```

### Example (curl)

```bash
curl -X POST https://YOUR-URL.onrender.com/decrypt \
  -H "Content-Type: application/json" \
  -d '{"link": "happ://crypt/your-link-here"}'
```

### Other Endpoints

- `GET /` — API info
- `GET /health` — Health check
- `GET /docs` — Interactive Swagger UI (test your API in browser)
