# LexConnect Testing Guide

This guide documents how to run, seed, and manually test the LexConnect platform after stabilization.

## Quick start

```bash
# Activate your virtual environment, then:
python manage.py migrate
python generate_lawyers.py --with-slots
python manage.py runserver
```

Open http://127.0.0.1:8000/

For full demo data (client account, booking normalization, demo accounts file):

```bash
python manage.py prepare_demo
```

---

## Demo credentials

| Role | Username / login | Password |
|------|------------------|----------|
| Client (demo) | `demo_client` | `client@123` |
| Any imported lawyer | email (e.g. `lawyer1@gmail.com`) or username (`lawyer1`) | `lawyer@123` |
| Admin | Django superuser you create | your password |

Lawyer list: http://127.0.0.1:8000/demo-accounts/ (requires `LEXCONNECT_SHOW_DEMO_ACCOUNTS=True`, default in DEBUG)

---

## Route map

### Public (landing & discovery)

| Route | Name | Purpose |
|-------|------|---------|
| `/` | home | Public landing, featured lawyers, categories |
| `/demo-accounts/` | demo_accounts | Demo credential reference |
| `/lawyers/<category_id>/` | lawyers_by_category | Lawyer search & filters by category |
| `/lawyer/profile/<lawyer_id>/` | lawyer_profile | Public lawyer profile |
| `/chatbot/` | chatbot | Lexora AI full page |
| `/ask-lexora/` | ask_lexora | Lexora API (POST, JSON) |
| `/register/` | register | Client sign up |
| `/login/` | login | Client login |
| `/lawyer/login/` | lawyer_login | Lawyer login |
| `/lawyer/register/` | lawyer_register | Lawyer registration (admin review) |

### Client workspace

| Route | Purpose |
|-------|---------|
| `/client/dashboard/` | Client home |
| `/client/bookings/` | Booking list, reschedule, cancel |
| `/client/chats/` | Paid consultation chats |
| `/consult/<lawyer_id>/` | Book a consultation slot |
| `/payment/<booking_id>/` | Demo payment step |
| `/chat/start/<lawyer_id>/` | Start booking-linked chat |
| `/notifications/` | Notifications |

### Lawyer workspace

| Route | Purpose |
|-------|---------|
| `/lawyer/dashboard/` | Lawyer home |
| `/lawyer/bookings/` | Assigned bookings |
| `/lawyer/availability/` | Publish weekly availability |
| `/lawyer/availability/add/` | POST: add availability window |
| `/lawyer/chats/` | Client chats |
| `/lawyer/toggle-status/` | Go online/offline |

### Platform admin (internal dashboard)

| Route | Purpose |
|-------|---------|
| `/admin/dashboard/` | Admin overview |
| `/admin/lawyers/` | Lawyer moderation |
| `/admin/clients/` | Client accounts |
| `/admin/bookings/` | All bookings |
| `/admin/payments/` | Payment review |
| `/admin/operations/audit/` | Operational events |

### Django admin (database tables)

| Route | Purpose |
|-------|---------|
| `/django-admin/` | Stock Django admin for raw model access |

---

## Recommended testing sequence

### 1. Seed & verify lawyers

1. Run `python generate_lawyers.py --with-slots`
2. Homepage should show **Featured Lawyers** (up to 6)
3. `/demo-accounts/` should list verified lawyers with password `lawyer@123`

### 2. Client booking flow

1. Log in as `demo_client` / `client@123` (or register a new client)
2. Browse a category → open a lawyer profile → **Book consultation**
3. Select an available slot → submit issue → continue to payment
4. Request demo payment verification; admin approves payment in `/admin/payments/`
5. Chat unlocks from client dashboard after payment success

### 3. Lawyer availability flow

1. Log in as `lawyer1@gmail.com` / `lawyer@123` in a **separate browser window** (avoids CSRF/session conflicts)
2. Open `/lawyer/availability/`
3. Add a weekday window (e.g. Monday 09:00–17:00, 30 min slots, Active checked)
4. As client (other window), open consult page — slots should appear within 21 days

### 4. Lexora AI

1. Open `/chatbot/` or use the floating Lexora widget
2. Ask: "I have a property dispute" → category + lawyer recommendations
3. Ask: "How do I book a consultation?" → platform guidance

### 5. Admin

1. Create superuser: `python manage.py createsuperuser`
2. Use `/admin/dashboard/` for platform operations
3. Use `/django-admin/` only when you need direct model editing

---

## Expected behaviors

- **Lawyer import**: 120 lawyers from CSV; 9 blank separator rows skipped; all visible to clients when verified
- **Booking slots**: Generated from weekly availability; past slots hidden; booked slots marked unavailable
- **CSRF**: Signing in as another role in the same browser invalidates old form tokens; refresh the page or use separate windows
- **Public vs app UI**: Home, discovery, Lexora use minimal public nav; dashboards use full role-based nav

---

## Known limitations

- Demo payments require admin approval before chat unlocks
- Lawyer registration still requires admin verification (CSV import bypasses this for demo lawyers only)
- Lexora uses local classification; Gemini enhancement requires `GEMINI_API_KEY` in `.env`
- Multi-role testing in one browser tab can cause CSRF errors (by design — use separate windows)

---

## Environment flags

| Variable | Default (DEBUG) | Purpose |
|----------|-----------------|--------|
| `LEXCONNECT_SHOW_DEMO_ACCOUNTS` | `True` | Show demo accounts page & nav link |
| `GEMINI_API_KEY` | empty | Optional Lexora Gemini enhancement |
| `DJANGO_DEBUG` | `True` | Debug mode |

Set `LEXCONNECT_SHOW_DEMO_ACCOUNTS=False` in production.
