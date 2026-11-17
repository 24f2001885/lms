# JSON API Examples

## Prerequisites
1. Seed demo data (`make demo-data`) and start the server (`flask --app app run --debug`).
2. Default demo password placeholder: `$DEMO_PASSWORD` (`Demo#12345`).

---

## 1. Sign in with curl
```bash
# Step 1: Fetch login CSRF token and store session cookie
LOGIN_CSRF=$(curl -s -c cookies.txt http://127.0.0.1:5000/login | grep -o 'name="csrf_token"[^>]*value="[^"]*"' | sed 's/.*value="\([^"]*\)".*/\1/')

# Step 2: Authenticate as demo student
curl -s -b cookies.txt -c cookies.txt -X POST http://127.0.0.1:5000/login \
  -d "csrf_token=${LOGIN_CSRF}&email=student01@demo.local&password=Demo%2312345"

# Step 3: Read API session and CSRF token
API_CSRF=$(curl -s -b cookies.txt http://127.0.0.1:5000/api/v1/session | python3 -c "import sys,json; print(json.load(sys.stdin)['csrf_token'])")
```

## 2. Browser Console (fetch)
```javascript
const { csrf_token } = await fetch('/api/v1/session', { credentials: 'same-origin' }).then(r => r.json());
const exams = await fetch('/api/v1/examinations', { credentials: 'same-origin' }).then(r => r.json());
const booked = await fetch('/api/v1/bookings', {
  method: 'POST',
  credentials: 'same-origin',
  headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf_token },
  body: JSON.stringify({ slot_id: 2 })
}).then(r => r.json());
```

## 3. Worked Examples by HTTP Verb

### GET List (`200 OK`)
```bash
curl -s -b cookies.txt "http://127.0.0.1:5000/api/v1/examinations?page=1&per_page=5"
# -> {"items": [...], "page": 1, "per_page": 5, "total": 2}
```

### POST Create Booking (`201 Created`)
```bash
curl -s -i -b cookies.txt -X POST http://127.0.0.1:5000/api/v1/bookings \
  -H "Content-Type: application/json" -H "X-CSRFToken: ${API_CSRF}" \
  -d '{"slot_id": 2}'
# -> HTTP/1.1 201 Created | Location: /api/v1/bookings/10
# -> {"id": 10, "slot_id": 2, "examination_id": 1, "status": "booked", "booked_at": "...Z"}
```

### PUT Update Slot (`200 OK` as `examiner1@demo.local`)
```bash
curl -s -b ex_cookies.txt -X PUT http://127.0.0.1:5000/api/v1/slots/2 \
  -H "Content-Type: application/json" -H "X-CSRFToken: ${EX_CSRF}" \
  -d '{"max_capacity": 5}'
# -> {"id": 2, "examination_id": 1, ..., "max_capacity": 5, "status": "available"}
```

### DELETE Cancel Booking (`200 OK`)
```bash
curl -s -b cookies.txt -X DELETE http://127.0.0.1:5000/api/v1/bookings/10 \
  -H "X-CSRFToken: ${API_CSRF}"
# -> {"id": 10, "status": "cancelled"}
```

## 4. Standard Error Responses
- **401 Unauthenticated**: `curl -s http://127.0.0.1:5000/api/v1/examinations` -> `{"error": {"code": "unauthenticated", "message": "..."}}`
- **403 Forbidden**: Student calling `GET /api/v1/examiners` -> `{"error": {"code": "forbidden", "message": "..."}}`
- **409 Conflict**: Student booking same examination twice -> `{"error": {"code": "duplicate_booking", "message": "..."}}`
- **422 Validation Error**: `POST /api/v1/bookings` with `{"slot_id": "abc"}` -> `{"error": {"code": "validation_error", "fields": {"slot_id": ["Must be a whole number."]}}}`
