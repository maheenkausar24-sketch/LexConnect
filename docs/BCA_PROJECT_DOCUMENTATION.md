# LEXCONNECT — BCA FINAL YEAR PROJECT DOCUMENTATION DATASET

> **Source of truth:** Implemented codebase at `LexConnect-main` (Django 6, Channels, Celery).  
> **Purpose:** Chapter-wise academic content for conversion into BCA project report.  
> **Placeholders:** Replace bracketed fields on title/certificate pages with institute details.

---

## TITLE PAGE DETAILS

| Field | Content |
|-------|---------|
| **Project Title** | LexConnect — Web-Based Legal Consultation and Lawyer Marketplace Platform |
| **Student Name** | [Your Name] |
| **Register Number** | [Register Number] |
| **Guide Name** | [Guide Name] |
| **College Name** | [College Name] |
| **Department** | Bachelor of Computer Applications (BCA) |
| **Academic Year** | [e.g., 2025–2026] |

---

## CERTIFICATE PAGE CONTENT

This is to certify that the project entitled **“LexConnect — Web-Based Legal Consultation and Lawyer Marketplace Platform”** submitted by **[Student Name]** (Register No: **[Register Number]**) in partial fulfillment of the requirements for the award of **Bachelor of Computer Applications (BCA)** is a record of bonafide work carried out under my supervision and guidance.

The matter embodied in this project has not been submitted earlier for the award of any degree/diploma to the best of my knowledge.

**Guide:** _________________________  
**Head of Department:** _________________________  
**Principal:** _________________________  
**Date:** _________________________  
**Place:** _________________________

---

## DECLARATION PAGE CONTENT

I, **[Student Name]**, Register Number **[Register Number]**, student of **[College Name]**, Department of Computer Applications, hereby declare that the project work titled **“LexConnect — Web-Based Legal Consultation and Lawyer Marketplace Platform”** submitted to **[University/Board Name]** is a record of original work done by me under the guidance of **[Guide Name]**.

This work has not been submitted elsewhere for any degree or diploma. All sources of information have been duly acknowledged.

**Place:** _________________________  
**Date:** _________________________  
**Signature of Student:** _________________________

---

## ACKNOWLEDGEMENT PAGE CONTENT

I express sincere gratitude to **[Guide Name]** for continuous guidance, technical direction, and encouragement throughout this project.

I thank **[Head of Department]** and the faculty of the Department of Computer Applications, **[College Name]**, for academic support and infrastructure.

I acknowledge open-source communities behind **Django**, **Channels**, **Celery**, and related libraries that made this implementation feasible.

Finally, I thank my family and peers for their motivation and feedback during development and testing.

---

## ABSTRACT

LexConnect is a full-stack web application that connects clients with verified lawyers for online legal consultations. The system addresses fragmentation in legal service discovery, unstructured appointment booking, and lack of integrated payment and communication channels in small-to-medium legal practices. Built on **Django 6.0.3** with **Django Channels 4.2** for WebSocket-based chat, the platform supports role-based access for **clients**, **lawyers**, and **platform administrators**.

Clients browse lawyers by legal category, book time-bounded consultation slots from lawyer-defined availability, submit demo payment verification requests, and communicate via booking-linked real-time chat after administrative payment approval. Lawyers manage availability, confirm or complete consultations, and respond through the same chat channel. Administrators verify lawyer credentials, moderate payments, audit operational events, and monitor system health.

The implementation uses **SQLite** (development) or **PostgreSQL** (production), optional **Redis** for channel layers and Celery, **session-based authentication** with CSRF protection, **Content Security Policy (CSP)** headers, rate limiting, idempotent payment state machines, and an embedded **Lexora** legal guidance module (keyword classification with optional **Google Gemini** enhancement). Automated tests in `main/tests.py` validate booking overlap rules, payment transitions, chat authorization, webhooks, and security controls.

**Problem addressed:** Difficulty finding verified lawyers, double-booking of slots, disconnected payment and chat workflows, and absence of audit trails in informal consultation arrangements.

**Technologies used:** Python, Django, Channels, Daphne, Celery, Redis, PostgreSQL/SQLite, HTML/CSS/JavaScript, Google Generative AI (optional).

**Objectives:** Role-separated marketplace, atomic booking creation, payment-gated chat, admin verification, AI-assisted legal triage, production-ready security baseline.

**Final outcome:** A deployable MVP demonstrating end-to-end consultation lifecycle from discovery → booking → payment approval → confirmed chat → completion → review.

---

## TABLE OF CONTENTS

1. **Chapter 1 — Introduction**  
   1.1 Introduction | 1.2 Problem Definition | 1.3 Objectives | 1.4 Scope | 1.5 Methodology  
2. **Chapter 2 — Project Justification**  
   2.1 Purpose | 2.2 Existing System | 2.3 Proposed System | 2.4 Advantages | 2.5 Comparison | Feasibility Study  
3. **Chapter 3 — Literature Survey**  
   3.1 Introduction | 3.2 Review | 3.3 Summary | 3.4 Research Gap | 3.5 Justification | References  
4. **Chapter 4 — Software Requirement Specification**  
   4.1–4.12 (Functional/Non-functional requirements)  
5. **Chapter 5 — System Design**  
   5.1 Introduction | 5.2 Architecture | 5.3 DFD | 5.4 Use Case | 5.5 Sequence | 5.6 Activity | 5.7 ER | 5.8 Class  
6. **Chapter 6 — System Implementation**  
   6.1–6.8 Modules, APIs, libraries, challenges  
7. **Chapter 7 — Testing and Results**  
   7.1–7.9 Test cases, outputs, limitations  
8. **Chapter 8 — Conclusion and Future Enhancements**  
9. **References** | **Bibliography**  
**Appendices:** Schema, folder structure, workflows, viva Q&A, checklists

---

## LIST OF FIGURES (Suggested)

| Fig. No. | Title | Chapter |
|----------|-------|---------|
| Fig. 1.1 | Methodology pipeline of LexConnect | Ch. 1 |
| Fig. 2.1 | Comparison of existing vs proposed system | Ch. 2 |
| Fig. 5.1 | Three-tier system architecture | Ch. 5 |
| Fig. 5.2 | DFD Level 0 — LexConnect context | Ch. 5 |
| Fig. 5.3 | DFD Level 1 — major processes | Ch. 5 |
| Fig. 5.4 | DFD Level 2 — booking & payment subprocess | Ch. 5 |
| Fig. 5.5 | Use case diagram (Client, Lawyer, Admin) | Ch. 5 |
| Fig. 5.6 | Sequence diagram — booking to chat unlock | Ch. 5 |
| Fig. 5.7 | Activity diagram — consultation lifecycle | Ch. 5 |
| Fig. 5.8 | Entity Relationship diagram | Ch. 5 |
| Fig. 5.9 | Class diagram — core domain models | Ch. 5 |
| Fig. 6.1 | Home page — lawyer discovery | Ch. 6 |
| Fig. 6.2 | Consultation booking form | Ch. 6 |
| Fig. 6.3 | Payment verification page | Ch. 6 |
| Fig. 6.4 | Admin payment approval | Ch. 6 |
| Fig. 6.5 | Real-time chat interface | Ch. 6 |
| Fig. 6.6 | Lexora AI chatbot widget | Ch. 6 |
| Fig. 6.7 | Custom admin dashboard | Ch. 6 |
| Fig. 7.1 | Test execution summary | Ch. 7 |

---

## LIST OF TABLES (Suggested)

| Table No. | Title | Chapter |
|-----------|-------|---------|
| Table 2.1 | Existing vs Proposed System comparison | Ch. 2 |
| Table 4.1 | Functional requirements | Ch. 4 |
| Table 4.2 | Non-functional requirements | Ch. 4 |
| Table 4.3 | Hardware requirements | Ch. 4 |
| Table 4.4 | Software requirements | Ch. 4 |
| Table 5.1 | Database entities summary | Ch. 5 |
| Table 6.1 | HTTP route summary by module | Ch. 6 |
| Table 6.2 | Major Python dependencies | Ch. 6 |
| Table 7.1–7.6 | Test case matrices | Ch. 7 |

---

# CHAPTER 1: INTRODUCTION

## 1.1 Introduction

The legal services sector traditionally relies on referrals, physical offices, and unstructured phone consultations. Clients face difficulty comparing lawyer expertise, verifying credentials, and securing confirmed appointment slots. Lawyers lack integrated tools for availability management, payment tracking, and secure client communication. Digital transformation in legal tech (LegalTech) has introduced marketplaces and consultation platforms, but many academic and SME-scale solutions remain fragmented across discovery, scheduling, payments, and messaging.

**LexConnect** is a web-based legal consultation marketplace developed as a BCA final-year project. It unifies lawyer discovery by category (Property, Family, Cyber, Criminal, Consumer, Corporate), slot-based booking with overlap prevention, demo/manual payment workflows suitable for academic demonstration, booking-linked real-time chat using WebSockets, in-app notifications, optional email reminders via Celery, and **Lexora** — an AI-assisted legal information module that classifies user queries and recommends verified lawyers without replacing professional legal advice.

The system’s importance lies in demonstrating enterprise patterns—finite state machines for bookings and payments, `select_for_update` locking, idempotent webhooks, audit logging, CSP/CSRF hardening, and role-based access control—in a domain relevant to Indian legal consultation contexts (default timezone `Asia/Kolkata`).

**Industry relevance:** Legal marketplaces (e.g., consultation platforms) increasingly require verified professionals, payment escrow, and secure messaging; LexConnect models these concerns at MVP scale.

## 1.2 Problem Definition

**Existing problems:**

1. **Discovery gap:** Clients cannot easily filter lawyers by category, city, fee, and online status.
2. **Scheduling conflicts:** Manual booking leads to double-booked slots and no atomic overlap checks.
3. **Payment–booking disconnect:** Payment success does not automatically confirm consultations; chat opens without payment gates in informal systems.
4. **Communication fragmentation:** Consultation chat occurs on external apps without audit linkage to bookings.
5. **Verification trust:** Unverified lawyer listings reduce platform credibility.
6. **Security weaknesses:** Missing CSRF/CSP, rate limits, and upload validation expose web forms and file uploads.

**Limitations in current informal/manual systems:**

- No centralized audit trail for payment or booking status changes.
- No idempotent payment provider integration.
- No role-separated admin operations distinct from Django superuser CRUD.

## 1.3 Objectives

**Main objectives:**

- Build a multi-role legal consultation platform (client, lawyer, admin).
- Implement slot-based booking with database-enforced uniqueness for active slots.
- Integrate payment state machine that confirms bookings upon successful payment.
- Enable booking-gated real-time chat with HTTP fallback polling.
- Provide Lexora AI for categorized legal guidance and lawyer recommendations.

**Technical goals:**

- Django service-layer architecture with atomic transactions.
- Channels WebSocket consumer with session authentication.
- Celery tasks for email, webhooks, reminders, and cleanup.
- Comprehensive automated tests (`LexConnectFlowTests`).

**Security goals:**

- Session cookies (HttpOnly, SameSite), CSRF on forms, CSP via custom middleware.
- Rate limiting on login, chat, payments, and webhooks.
- Protected media downloads for chat files and certificates.

**Functional goals:**

- Lawyer availability CRUD, booking lifecycle, reviews after completion, custom admin panel.

## 1.4 Scope of the Project

**Current scope:**

- Web application (server-rendered templates + JSON endpoints for chat/Lexora/health).
- Demo payment provider (`Demo Manual`, `Secure Demo`) with admin approval and signed webhooks.
- Single marketplace (no multi-tenant firms).
- English UI; Indian timezone default.

**Future scalability:**

- Live payment gateways (Razorpay, Stripe), video consultation (Jitsi/Zoom APIs), mobile apps, multi-language, case management UI for `ClientCase` models.

**Real-world usage:**

- Small law firms, college legal aid cells, demo LegalTech incubators.

## 1.5 Methodology

**Step-by-step project workflow:**

| Phase | Activity | Technologies |
|-------|----------|--------------|
| 1 | Requirements & literature study | SRS, comparative analysis |
| 2 | Database design (21+ domain tables) | Django ORM, ER modeling |
| 3 | Backend services (bookings, payments, chat) | Python, Django 6 |
| 4 | Frontend templates & static assets | HTML, CSS (`app.css`), JS (`chat.js`, `lexora.js`) |
| 5 | Real-time layer | Channels, Daphne, Redis (optional) |
| 6 | Async jobs | Celery, Redis broker |
| 7 | Security hardening | CSP middleware, rate limits, validators |
| 8 | Testing | `manage.py test` (58 tests) |
| 9 | Deployment prep | Docker Compose, health endpoints, management commands |

**Methodology diagram (Fig. 1.1) should show:**

```
[Requirements] → [Design: ER, DFD, UML] → [Implementation: Django main app]
      → [Testing] → [Deployment: Daphne + Redis + PostgreSQL]
```

Arrows labeled: Client Browser, WebSocket, Admin Panel, Celery Worker, Database.

---

# CHAPTER 2: PROJECT JUSTIFICATION

## 2.1 Purpose of the Project

To deliver an integrated, secure, and auditable platform where clients book verified lawyers, payments are tracked with state history, and consultation chat is unlocked only after confirmed payment—while providing AI-assisted triage (Lexora) for initial legal category routing.

## 2.2 Existing System

**Existing approaches:**

- Phone/email booking with manual calendars.
- Generic form builders without overlap constraints.
- Third-party chat apps (WhatsApp) without booking linkage.
- Static lawyer directories without verification workflow.

**Technologies commonly used:** Spreadsheets, WordPress directories, generic CRMs.

**Drawbacks:** No atomic slot locking, no payment FSM, no WebSocket chat tied to booking status, weak security on uploads and forms.

## 2.3 Proposed System

**Solution:** Monolithic Django application (`main` app) with:

- **Presentation:** Templates (`templates/`), static JS/CSS.
- **Business logic:** `main/services/*.py` (bookings, payments, chat, lexora, admin_panel).
- **Data:** `main/models.py` with migrations 0001–0013.
- **Real-time:** `ChatConsumer` on `ws/chat/<id>/`.
- **Async:** `main/tasks.py` + Celery beat schedule in `lexconnect/celery.py`.

**Architecture overview:** Three-tier — Browser → Django/ASGI (Daphne) → SQLite/PostgreSQL + optional Redis.

**Working principle:** Session-authenticated users interact via HTTP; chat uses WebSocket push with HTTP POST for sending messages; payments transition through validated states; admin approval reconciles booking to `CONFIRMED`.

## 2.4 Advantages of Proposed System

1. Unified lifecycle: discovery → book → pay → chat → complete → review.
2. Database-enforced slot uniqueness for active bookings.
3. Payment ledger and provider event idempotency.
4. Booking-gated chat (confirmed/completed + payment success).
5. Custom admin ops panel with confirmation tokens for sensitive actions.
6. Lexora local guidance works without API key; Gemini optional.
7. Production-oriented health checks and operational event logging.

## 2.5 Comparison Between Existing and Proposed System

| Criterion | Existing Manual System | LexConnect (Proposed) |
|-----------|------------------------|------------------------|
| Lawyer verification | Informal | `verification_status` + admin approve |
| Slot booking | Manual, error-prone | Generated slots + overlap checks + DB constraint |
| Payment tracking | Receipts/spreadsheets | `Payment` FSM + `PaymentStatusHistory` + ledger |
| Chat | External apps | Booking-linked WebSocket + protected files |
| Audit | None | `BookingStatusHistory`, `OperationalEvent`, audit logs |
| Security | Variable | CSRF, CSP, rate limits, MIME validation |
| AI assistance | None | Lexora keyword + optional Gemini |

### Feasibility Study

**Technical feasibility:** High — Django/Channels are mature; project implements working MVP with 58 automated tests.

**Economic feasibility:** Open-source stack; optional Gemini API cost only; deployable on low-cost VPS with SQLite for demos.

**Operational feasibility:** `prepare_demo` management command seeds demo data; `TESTING_GUIDE.md` documents flows; role-separated dashboards reduce training burden.

---

# CHAPTER 3: LITERATURE SURVEY

## 3.1 Introduction

Legal consultation platforms and LegalTech systems have been studied in contexts of access to justice, e-governance, and online dispute resolution. This chapter surveys analogous systems, enabling technologies, and research gaps motivating LexConnect.

## 3.2 Review of Existing Literature

**Similar systems (industry/research themes):**

- **Online legal marketplaces** — Lawyer discovery, ratings, and appointment booking (commercial platforms conceptually similar to Upwork/legal directories).
- **Tele-law initiatives** — Government and NGO projects for remote legal aid in developing countries.
- **Chatbot-based legal information** — Rule-based and LLM-based triage (not a substitute for counsel).

**Technologies in research and practice:**

- Web frameworks (Django, Rails) for rapid secure web development.
- WebSockets for real-time collaboration (Channels, Socket.io patterns).
- Finite state machines for order/payment workflows (e-commerce literature).
- OAuth/session security best practices (OWASP).

## 3.3 Summary of Literature

Prior work emphasizes either **information dissemination** (static content) or **communication** (chat) but rarely **atomic integration** of verified identity, slot scheduling, payment state, and gated messaging in one open academic codebase.

## 3.4 Research Gap

1. Lack of demonstrable **payment–booking reconciliation** in student LegalTech projects.
2. Insufficient **idempotent webhook** handling in demo payment flows.
3. Weak **role-based admin** separation from end-user flows.
4. Missing **CSP/CSRF** documentation in small marketplace projects.

## 3.5 Proposed Solution Justification

LexConnect fills the gap by implementing a **single transactional domain model** where `Payment.SUCCESS` triggers `confirm_booking_for_successful_payment()` (see `main/services/payments.py`), unlocking `Chat` eligibility per `booking_is_chat_eligible()` in `main/services/chat.py`, with automated tests proving the pipeline.

### References (IEEE-style, minimum 10)

1. Django Software Foundation, *Django Documentation*, https://docs.djangoproject.com/  
2. Django Channels, *Channels Documentation*, https://channels.readthedocs.io/  
3. OWASP Foundation, *OWASP Top Ten*, https://owasp.org/www-project-top-ten/  
4. OWASP, *Content Security Policy Cheat Sheet*, https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html  
5. Fielding, R. T., *Architectural Styles and the Design of Network-based Software Architectures* (REST), 2000.  
6. Celery Project, *Celery Documentation*, https://docs.celeryq.dev/  
7. PostgreSQL Global Development Group, *PostgreSQL Documentation*, https://www.postgresql.org/docs/  
8. Google AI, *Gemini API Documentation*, https://ai.google.dev/gemini-api/docs  
9. Redis Ltd., *Redis Documentation*, https://redis.io/docs/  
10. NIST, *Digital Identity Guidelines (SP 800-63)*, https://pages.nist.gov/800-63-3/  
11. India Code, *Information Technology Act, 2000* (legal informatics context), https://www.indiacode.nic.in/  

---

# CHAPTER 4: SOFTWARE REQUIREMENT SPECIFICATION (SRS)

## 4.1 Introduction

This SRS describes functional and non-functional requirements for LexConnect v1 (MVP), derived from implemented features in `main/` application.

## 4.2 Purpose

Define requirements for developers, testers, and evaluators of the BCA project submission.

## 4.3 Scope

Web-based marketplace for Indian-context legal consultations: clients, verified lawyers, platform admins. Excludes native mobile apps and live video in current UI (model supports `consultation_mode`).

## 4.4 Overall Description

Product perspective: single Django project `lexconnect` with app `main`. Users access via browser; lawyers/clients have dashboards; admins use `/admin/*` custom UI.

## 4.5 System Features

| ID | Feature | Implementation |
|----|---------|----------------|
| F1 | User registration (client/lawyer) | `views/auth.py`, `services/auth.py` |
| F2 | Email verification | `auth_security.py`, tokens |
| F3 | Login/logout (role redirect) | Session auth, `get_dashboard_route` |
| F4 | Lawyer browse/search | `pages.lawyers_by_category`, `LawyerSearchForm` |
| F5 | Lawyer profile & reviews | `lawyer_profile`, `Review` model |
| F6 | Availability management | `LawyerAvailability`, `add_schedule_slot` |
| F7 | Consultation booking | `create_booking_with_payment` |
| F8 | Payment demo flow | `payment_page`, `request_demo_payment_verification` |
| F9 | Admin payment approval | `admin_update_payment` → `mark_payment_success` |
| F10 | Booking status updates | `transition_booking_status` |
| F11 | Reschedule/cancel | `reschedule_booking`, `cancel_booking` |
| F12 | Real-time chat | `ChatConsumer`, `chat.js`, HTTP send/poll |
| F13 | Notifications | `Notification`, context processor |
| F14 | Lexora AI | `ask_lexora`, `lexora.js` |
| F15 | Custom admin panel | `admin_panel.py` views |
| F16 | Health checks | `/health/live/`, `/health/ready/` |
| F17 | Provider webhooks | `provider_webhook`, `payments.py` |
| F18 | Refunds (demo) | `process_refund` |
| F19 | Protected file download | `media.py` views |
| F20 | Booking reminders | Celery `send_booking_reminders_task` |

## 4.6 User Characteristics

| Role | Skills | Access |
|------|--------|--------|
| Client | Basic web literacy | Book, pay, chat, review |
| Lawyer | Professional user | Availability, bookings, chat |
| Admin | Technical/legal ops | Verification, payments, audit |

## 4.7 Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Server | 2 vCPU, 2 GB RAM | 4 vCPU, 8 GB RAM |
| Client | Modern browser device | Desktop/laptop |
| Storage | 10 GB | 50 GB SSD (media uploads) |

## 4.8 Software Requirements

| Software | Version (project) |
|----------|-------------------|
| Python | 3.10+ |
| Django | 6.0.3 |
| Channels | 4.2.0 |
| Daphne | 4.2.1 |
| Celery | 5.6.0 |
| Redis | 6.x (optional) |
| PostgreSQL | 14+ (production) or SQLite (dev) |
| Browser | Chrome/Firefox latest |

## 4.9 Functional Requirements

**FR-1:** System shall allow client registration and login.  
**FR-2:** System shall allow lawyer registration pending admin verification.  
**FR-3:** System shall generate bookable slots from lawyer availability rules.  
**FR-4:** System shall reject overlapping active bookings for same lawyer/datetime.  
**FR-5:** System shall create `Payment` in `pending` when booking is created.  
**FR-6:** System shall require admin confirmation token to change payment status in admin UI.  
**FR-7:** System shall set booking to `confirmed` when payment becomes `success`.  
**FR-8:** System shall allow chat only for confirmed/completed bookings with successful payment.  
**FR-9:** System shall broadcast new chat messages via Channels group `chat_{id}`.  
**FR-10:** System shall rate-limit login and chat endpoints.

## 4.10 Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | Response time &lt; 3s for typical pages on LAN |
| NFR-2 | Availability 99% (deployment dependent) |
| NFR-3 | Password hashing via Django PBKDF2 |
| NFR-4 | CSRF protection on state-changing forms |
| NFR-5 | CSP headers on all responses |
| NFR-6 | Upload size limits (10 MB request, 5 MB file memory) |
| NFR-7 | Audit events for security-sensitive actions |

## 4.11 Constraints

- Demo payment only (not production PCI without real gateway).
- WebSocket requires ASGI server (Daphne), not pure `runserver` for full chat in production.
- Gemini requires `GEMINI_API_KEY` for enhanced Lexora responses.

## 4.12 Assumptions

- Users have stable internet for WebSocket (HTTP fallback exists).
- Lawyers are pre-seeded or imported via CSV for demos.
- Single organization operates the platform (no multi-tenant isolation).

---

# CHAPTER 5: SYSTEM DESIGN

## 5.1 Introduction

System design translates SRS into architecture, data flows, and UML models aligned with `main/models.py` and service modules.

## 5.2 System Architecture

**Pattern:** Layered monolith with ASGI extension.

| Layer | Components |
|-------|------------|
| Presentation | Django templates, `static/main/js/chat.js`, `lexora.js` |
| Application | `main/views/*`, decorators, forms |
| Domain services | `main/services/*` |
| Infrastructure | ORM, Channels, Celery, cache |
| Data | SQLite/PostgreSQL, `media/`, Redis |

**Architecture diagram (Fig. 5.1):**  
Center: **Django Application (main)**. Left: **Client/Lawyer/Admin Browsers**. Right top: **PostgreSQL/SQLite**. Right middle: **Redis** (channel layer + Celery). Bottom: **Celery Worker/Beat**. Arrow from Browser → Daphne (ASGI) → HTTP/WebSocket handlers.

## 5.3 Data Flow Diagram (DFD)

### 5.3.1 DFD Level 0

**Entities:** Client, Lawyer, Administrator, Payment Provider (external).  
**Process:** LexConnect System (single bubble).  
**Flows:** Booking requests, payment events, messages, admin commands, notifications.

### 5.3.2 DFD Level 1

Processes: **P1 User Management**, **P2 Lawyer Discovery**, **P3 Booking & Scheduling**, **P4 Payment Processing**, **P5 Chat & Notifications**, **P6 Admin & Audit**, **P7 Lexora AI**.  
Data stores: **D1 Users/Profiles**, **D2 Lawyers/Categories**, **D3 Bookings**, **D4 Payments**, **D5 Chats/Messages**, **D6 Notifications/Events**.

### 5.3.3 DFD Level 2 (Booking & Payment)

Decompose **P3+P4:** Validate slot → Create booking → Create payment → Await verification → Admin/webhook success → Confirm booking → Create chat → Notify users.

## 5.4 Use Case Diagram

**Actors:** Client, Lawyer, Platform Admin, Payment Provider (external), Guest.

**Client use cases:** Register, Login, Browse lawyers, Book consultation, Pay, Chat, Review, Use Lexora.  
**Lawyer use cases:** Register, Manage availability, View bookings, Update status, Chat, Toggle online.  
**Admin use cases:** Verify lawyer, Update payment status, Cancel booking, View audit/health.  
**Guest:** Browse public pages, Ask Lexora (rate-limited).

## 5.5 Sequence Diagram

**Scenario: Payment approval unlocks chat**

1. Client → `payment_page`: POST awaiting verification  
2. Admin → `admin_update_payment`: POST success + confirmation token  
3. `mark_payment_success` → `transition_payment_status` → `confirm_booking_for_successful_payment`  
4. `ensure_chat_for_booking`  
5. Client → `chat_page`: GET  
6. Client → WebSocket: connect `ws/chat/{id}/`  
7. Client → `send_message`: POST → DB → `broadcast_chat_message` → WebSocket payload to group

## 5.6 Activity Diagram

Start → Login → Select lawyer → Choose slot → Submit booking → Payment page → Admin approves → Booking confirmed → Open chat → Exchange messages → Lawyer marks completed → Client submits review → End.

Decision nodes: Slot available? Payment success? Chat eligible?

## 5.7 Entity Relationship Diagram (ER Diagram)

**Core entities:** User, UserProfile, Lawyer, LawCategory, Booking, Payment, Chat, Message, Review, Notification.

**Relationships (cardinality):**

- User 1—1 UserProfile  
- User 1—0..1 Lawyer  
- LawCategory 1—* Lawyer  
- Booking *—1 Client (User), *—1 Lawyer  
- Booking 1—1 Payment  
- Booking 0..1 Chat, 0..1 Review  
- Chat 1—* Message  
- Payment 1—* PaymentStatusHistory, RefundRequest, PaymentLedgerEntry

See **Appendix A** for full table list (21 domain tables).

## 5.8 Class Diagram

**Django Model classes (main/models.py):** `TimestampedModel` (abstract), `LawCategory`, `UserProfile`, `Lawyer`, `LawyerAvailability`, `LawyerAvailabilityBreak`, `LawyerBlockedDate`, `Booking`, `Payment`, `PaymentStatusHistory`, `ProviderEvent`, `RefundRequest`, `RefundStatusHistory`, `PaymentLedgerEntry`, `Chat`, `Message`, `Review`, `Notification`, `OperationalEvent`, `BookingStatusHistory`, `ClientCase`, `LegalDocument`.

**Service classes (module-level functions):** `bookings.create_booking_with_payment`, `payments.transition_payment_status`, `chat.send_chat_message`, `lexora.ask_lexora`.

**Consumer:** `ChatConsumer(AsyncJsonWebsocketConsumer)`.

---

# CHAPTER 6: SYSTEM IMPLEMENTATION

## 6.1 Introduction

Implementation follows Django best practices: fat services, thin views, templates for UI, and JavaScript only where interactivity is required (chat, Lexora).

## 6.2 Development Environment

| Item | Detail |
|------|--------|
| OS | Windows 10/11 or Linux (Docker) |
| IDE | VS Code / Cursor / PyCharm |
| Runtime | Python venv (`env/`) |
| Server dev | `python manage.py runserver` |
| Server prod | Daphne via Docker Compose |
| DB dev | `db.sqlite3` |
| VCS | Git |

## 6.3 Module Implementation

### Module 1: Authentication & User Management

**Purpose:** Register/login users; assign roles; email verification.

**Workflow:** Form POST → `auth.register` / `authenticate` → `login()` → session cookie → redirect `get_dashboard_route`.

**Backend:** `main/services/auth.py`, `auth_security.py`, `views/auth.py`.

**Frontend:** `login.html`, `register.html`, `lawyer_login.html`, `lawyer_register.html`.

**Database:** `auth_user`, `main_userprofile`, `main_lawyer`.

**APIs:** `/login/`, `/register/`, `/lawyer/login/`, `/verify-email/<uid>/<token>/`.

**Code snippet (role routing):**

```python
# main/services/auth.py (conceptual)
def get_dashboard_route(user):
    if is_admin_user(user):
        return "admin_dashboard"
    if is_lawyer_user(user):
        return "lawyer_dashboard"
    if is_client_user(user):
        return "client_dashboard"
```

**Screenshots:** Login page, registration, email verification success.

---

### Module 2: Lawyer Discovery & Profiles

**Purpose:** Public browsing of verified lawyers.

**Workflow:** `visible_lawyers_queryset()` filters verified lawyers with user accounts → search form filters → paginated list → profile with reviews and consult button.

**Backend:** `services/lawyers.py`, `views/pages.py`.

**Frontend:** `home.html`, `lawyers.html`, `lawyer_profile.html`.

**APIs:** `/`, `/lawyers/<category_id>/`, `/lawyer/profile/<id>/`.

**Screenshot:** Home featured lawyers, category filter page, lawyer profile.

---

### Module 3: Availability & Slot Generation

**Purpose:** Lawyers define weekly availability; system generates discrete slots.

**Workflow:** Lawyer POST availability → `LawyerAvailability` saved → `generated_slots_for_date()` computes slots excluding breaks, blocked dates, past times, booked intervals.

**Backend:** `services/bookings.py` — `generated_slots_for_date`, `upcoming_available_slots`.

**Frontend:** `lawyer_availability.html`, `consult.html` slot picker.

**Database:** `main_lawyeravailability`, `main_lawyeravailabilitybreak`, `main_lawyerblockeddate`.

**Screenshot:** Lawyer availability form, consult page slot list.

---

### Module 4: Booking Creation

**Purpose:** Atomic booking + payment creation.

**Workflow:**

```python
# main/services/bookings.py — create_booking_with_payment (simplified)
with transaction.atomic():
    lawyer = lock_lawyer_for_booking(lawyer)
    slot = validate_booking_slot(lawyer, date, time)
    assert_no_booking_overlap(...)
    booking = Booking.objects.create(..., status=PENDING)
    Payment.objects.create(booking=booking, amount=...)
```

**APIs:** `POST /consult/<lawyer_id>/`.

**Screenshot:** Consultation form, booking success redirect.

---

### Module 5: Payments

**Purpose:** Payment FSM, admin approval, webhooks, refunds, ledger.

**Workflow:** Client requests verification → `AWAITING_VERIFICATION` → Admin `mark_payment_success` → `SUCCESS` → `confirm_booking_for_successful_payment` → `CONFIRMED`.

**Key function:** `confirm_booking_for_successful_payment` in `payments.py`.

**APIs:** `/payment/<booking_id>/`, `/admin/payments/<id>/status/`, `POST /payments/webhooks/<provider>/`.

**Screenshot:** Payment page, admin payments list, payment timeline.

---

### Module 6: Real-Time Chat

**Purpose:** Booking-linked messaging.

**Workflow:** HTTP POST saves message → `broadcast_chat_message` → group send → WebSocket clients receive JSON; fallback poll `GET /chat-room/<id>/messages/`.

**Backend:** `services/chat.py`, `consumers.py`, `utils.broadcast_chat_message`.

**Frontend:** `chat.html`, `static/main/js/chat.js` — WebSocket + `markOnline()` badge only.

**WebSocket:** `ws/chat/<chat_id>/` — ping/pong, no send over WS.

**Screenshot:** Chat room with Online badge, message bubbles.

---

### Module 7: Lexora AI

**Purpose:** Legal information triage (not legal advice).

**Workflow:** `POST /ask-lexora/` → keyword category → local guidance text → optional Gemini enhance → lawyer recommendations from DB.

**Backend:** `services/lexora.py`.

**Frontend:** `chatbot.html`, `includes/lexora_widget.html`, `lexora.js`.

**Screenshot:** Lexora widget on home, chatbot page with recommendations.

---

### Module 8: Admin Panel

**Purpose:** Operations without Django admin for daily tasks.

**Workflow:** `@admin_required` views → querysets in `admin_panel.py` → POST actions with `AdminActionConfirmationForm` tokens.

**Screenshot:** `admin_dashboard.html`, lawyer verification, payment update.

---

### Module 9: Notifications & Reminders

**Purpose:** In-app alerts and email reminders.

**Workflow:** `create_notification` on booking/chat events; Celery `send_booking_reminders_task` scans upcoming appointments.

**Screenshot:** Notifications page, nav badge.

---

### Module 10: Security & Operations

**Purpose:** CSP, rate limits, health, audit.

**Middleware:** `SecurityHeadersMiddleware`, `RequestLoggingMiddleware`, `PresenceMiddleware`.

**Screenshot:** Browser devtools showing CSP header; `/admin/operations/health/`.

## 6.4 API Implementation

See **Table 6.1** (Appendix). Authentication: session cookie; role decorators; webhook uses signature header `X-LexConnect-Signature` (provider module).

**Chat JSON examples:**

- `GET /chat-room/1/messages/?after=0` → `{"messages": [{id, text, sender_id, ...}]}`  
- `POST /chat-room/1/send/` → `{"message": {...}}`

## 6.5 Integration of Modules

Booking module invokes Payment on create; Payment success invokes Booking confirm + Chat create; Chat send invokes Notification; Admin payment update ties to Booking FSM.

## 6.6 Tools and Libraries Used

| Library | Purpose |
|---------|---------|
| Django 6 | Web framework, ORM, auth, admin |
| channels | WebSocket, channel layers |
| channels-redis | Redis channel layer |
| daphne | ASGI server |
| celery | Async tasks |
| psycopg | PostgreSQL driver |
| google-genai | Optional Lexora LLM |
| python-dotenv | Environment configuration |
| gunicorn | WSGI (optional) |

## 6.7 Challenges Faced

1. Payment success without booking confirmation (orphan state) — fixed via `confirm_booking_for_successful_payment`.
2. CSP blocking form POSTs — fixed `format_csp_source` in middleware.
3. Template variable `messages` shadowing Django flash messages — renamed to `chat_messages`.
4. WebSocket UI over-engineering — simplified to Online/Offline only.

## 6.8 Solutions Implemented

Documented in git history and `TESTING_GUIDE.md`; regression tests added for payment-booking-chat pipeline.

---

# CHAPTER 7: TESTING AND RESULTS

## 7.1 Introduction

Testing validates booking integrity, payment FSM, chat authorization, security controls, and operational commands using Django `TestCase` (`LexConnectFlowTests`).

## 7.2 Objectives of Testing

- Verify functional requirements FR-1–FR-10.  
- Ensure illegal state transitions raise `ValidationError`.  
- Confirm WebSocket rejects unauthorized users (close code 4403).  
- Validate rate limits return HTTP 429.

## 7.3 Types of Testing Performed

| Type | Application in LexConnect |
|------|---------------------------|
| Unit | Service functions (transitions, slot overlap) |
| Integration | HTTP views + DB + channels layer |
| System | End-to-end booking → pay → chat flows |
| Security | CSP, rate limit, upload validation, CSRF token on admin payment |
| Performance | Not load-tested; health endpoints for readiness |

## 7.4 Test Cases

### Table 7.1 — Booking

| TC ID | Scenario | Expected | Actual (impl.) | Status |
|-------|----------|----------|----------------|--------|
| BK-01 | Create booking | PENDING booking + PENDING payment | Pass | Pass |
| BK-02 | Overlapping slot | ValidationError | Pass | Pass |
| BK-03 | Adjacent slots | Allowed | Pass | Pass |
| BK-04 | Cancel releases slot | New booking allowed | Pass | Pass |

### Table 7.2 — Payment

| TC ID | Scenario | Expected | Actual | Status |
|-------|----------|----------|--------|--------|
| PY-01 | Admin approves payment | SUCCESS + CONFIRMED | Pass | Pass |
| PY-02 | Idempotent retry | Single history row | Pass | Pass |
| PY-03 | Invalid transition | ValidationError | Pass | Pass |
| PY-04 | Orphan SUCCESS payment re-approve | CONFIRMED | Pass | Pass |

### Table 7.3 — Chat

| TC ID | Scenario | Expected | Actual | Status |
|-------|----------|----------|--------|--------|
| CH-01 | Chat without payment | Denied redirect | Pass | Pass |
| CH-02 | Payment success | Chat created | Pass | Pass |
| CH-03 | WS non-participant | Close 4403 | Pass | Pass |
| CH-04 | Protected file outsider | 404/denied | Pass | Pass |

### Table 7.4 — Security

| TC ID | Scenario | Expected | Actual | Status |
|-------|----------|----------|--------|--------|
| SE-01 | CSP header present | object-src 'none' | Pass | Pass |
| SE-02 | Login rate limit | 429 after threshold | Pass | Pass |
| SE-03 | SVG upload rejected | Validation error | Pass | Pass |

### Table 7.5 — Lexora

| TC ID | Scenario | Expected | Actual | Status |
|-------|----------|----------|--------|--------|
| LX-01 | No API key | Local guidance + lawyers | Pass | Pass |
| LX-02 | Gemini failure | Safe fallback | Pass | Pass |

**Total automated tests:** 58 (`python manage.py test main.tests`).

## 7.5 Output Screens and Validation

| Screen | URL | Validation |
|--------|-----|------------|
| Home | `/` | Categories, lawyers load |
| Consult | `/consult/<id>/` | Slots from availability |
| Payment | `/payment/<id>/` | Status awaiting/success |
| Chat | `/chat-room/<id>/` | Messages send/receive |
| Admin payments | `/admin/payments/` | Status update with token |

## 7.6 Result Analysis

Core marketplace loop is stable under automated tests. Demo payment flow suitable for academic demonstration. WebSocket depends on Daphne/Redis in production.

## 7.7 Advantages of Developed System

Integrated workflow, auditability, security baseline, AI triage, test coverage.

## 7.8 Limitations

- Demo payments only.  
- No native mobile app.  
- Video consultation mode in model but not fully implemented in UI.  
- `ClientCase` UI not exposed.  
- Lexora is information-only, not legal advice.

## 7.9 Conclusion (Testing Chapter)

Testing confirms requirement satisfaction for MVP scope; manual browser validation recommended for WebSocket in Firefox/private mode.

---

# CHAPTER 8: CONCLUSION AND FUTURE ENHANCEMENTS

## 8.1 Conclusion

LexConnect successfully demonstrates a multi-role legal consultation marketplace with atomic booking, payment-gated chat, administrative oversight, and AI-assisted discovery. The service-layer architecture, state machines, and automated test suite provide a foundation for academic evaluation and future production hardening.

## 8.2 Future Enhancements

1. **Payment gateways:** Razorpay/Stripe integration with PCI-compliant flows.  
2. **Video calls:** WebRTC or embedded Zoom for `consultation_mode=video`.  
3. **Mobile apps:** Flutter/React Native consuming JSON APIs.  
4. **AI:** RAG over Indian bare acts; multilingual Lexora.  
5. **Cloud:** Kubernetes, S3 media, managed PostgreSQL.  
6. **Case management UI:** Expose `ClientCase` and `LegalDocument` to clients/lawyers.  
7. **Analytics:** Admin dashboards for booking conversion and lawyer utilization.

## 8.3 Final Summary

The project integrates web development, real-time systems, asynchronous processing, and security engineering into a cohesive LegalTech MVP aligned with BCA curriculum outcomes in software design, databases, web technologies, and project management.

---

# REFERENCES

(See Chapter 3 — References section; expand as per institution format.)

---

# BIBLIOGRAPHY

1. Django Documentation — https://docs.djangoproject.com/  
2. Django Channels — https://channels.readthedocs.io/  
3. Celery Documentation — https://docs.celeryq.dev/  
4. MDN Web Docs — WebSocket API — https://developer.mozilla.org/en-US/docs/Web/API/WebSocket  
5. OWASP Cheat Sheet Series — https://cheatsheetseries.owasp.org/  
6. PostgreSQL Tutorial — https://www.postgresql.org/docs/current/tutorial.html  
7. Redis Documentation — https://redis.io/docs/  
8. Google AI Gemini — https://ai.google.dev/  
9. Python Software Foundation — https://docs.python.org/3/  
10. Docker Documentation — https://docs.docker.com/  

---

# APPENDICES

## Appendix A — Database Schema Summary

21 domain tables in `main` app (see exploration report): `LawCategory`, `UserProfile`, `Lawyer`, `LawyerAvailability`, `LawyerAvailabilityBreak`, `LawyerBlockedDate`, `Booking`, `Payment`, `PaymentStatusHistory`, `ProviderEvent`, `RefundRequest`, `RefundStatusHistory`, `PaymentLedgerEntry`, `Chat`, `Message`, `Review`, `Notification`, `OperationalEvent`, `BookingStatusHistory`, `ClientCase`, `LegalDocument`.

Plus Django: `auth_user`, sessions, admin log tables.

## Appendix B — Folder Structure

```
LexConnect-main/
├── lexconnect/          # Project settings, urls, asgi, celery
├── main/                # Application code
│   ├── models.py
│   ├── views/
│   ├── services/
│   ├── consumers.py
│   ├── tests.py
│   └── management/commands/
├── templates/
├── static/main/
├── media/
├── docs/
└── requirements.txt
```

## Appendix C — Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3 |
| Framework | Django 6 |
| Real-time | Channels + Daphne |
| Task queue | Celery |
| Cache/Channels | Redis (optional) |
| DB | SQLite / PostgreSQL |
| Frontend | Django Templates, CSS, Vanilla JS |
| AI | google-genai (optional) |

## Appendix D — Security Features

- Session authentication with role decorators  
- CSRF middleware + custom failure view  
- CSP via `SecurityHeadersMiddleware`  
- Rate limiting (`main/rate_limit.py`)  
- File upload MIME/extension validation  
- Protected media views  
- `OperationalEvent` / audit logging  
- Webhook signature verification (`payment_providers.py`)  
- Admin action confirmation tokens  

## Appendix E — Authentication Workflow

1. User submits credentials → `authenticate()`.  
2. `login(request, user)` creates session.  
3. `UserProfile.role` determines client vs lawyer.  
4. `is_staff`/`is_superuser` → admin dashboard.  
5. `@client_required` / `@lawyer_required` / `@admin_required` guard views.  
6. WebSocket uses `AuthMiddlewareStack` — same session as HTTP.

## Appendix F — Admin Workflow

1. Login as staff → `/admin/dashboard/`.  
2. Verify lawyers → `/admin/lawyers/<id>/verify/`.  
3. Monitor bookings → force cancel if needed.  
4. Approve payments with confirmation token → booking confirms → chat unlocks.  
5. Review provider events and operational audit.

## Appendix G — Client Workflow

Register → Browse → Book slot → Payment verification request → Wait for admin → Chat → Complete → Review.

## Appendix H — Deployment Workflow

1. Set `DJANGO_SECRET_KEY`, `POSTGRES_*`, `REDIS_URL`.  
2. `python manage.py migrate`.  
3. `collectstatic`.  
4. Run Daphne: `daphne -b 0.0.0.0 -p 8000 lexconnect.asgi:application`.  
5. Celery worker + beat.  
6. Health check: `/health/ready/`.  
7. Docker: `docker-compose up` (see `docker-compose.yml`).

## Appendix I — Screenshot Capture Checklist

| # | Capture |
|---|---------|
| 1 | Home page (`/`) |
| 2 | Lawyers by category |
| 3 | Lawyer profile |
| 4 | Consult/booking form |
| 5 | Client bookings list |
| 6 | Payment page |
| 7 | Admin payments + success update |
| 8 | Chat room (Online badge) |
| 9 | Lawyer dashboard |
| 10 | Lawyer availability |
| 11 | Lexora widget / chatbot |
| 12 | Admin dashboard |
| 13 | Notifications |
| 14 | Health ready JSON |
| 15 | `python manage.py test` terminal output |

## Appendix J — Diagram Generation Checklist

- [ ] Context diagram (DFD 0)  
- [ ] DFD Level 1 & 2  
- [ ] Use case diagram (3 actors)  
- [ ] Sequence: payment → confirm → chat  
- [ ] Activity: consultation lifecycle  
- [ ] ER diagram (all main tables)  
- [ ] Class diagram (models + key services)  
- [ ] Deployment diagram (Docker services)  
- [ ] Architecture 3-tier  

## Appendix K — Viva Questions and Answers

**Q1: Why Django?**  
A: Rapid ORM development, built-in auth/admin, mature ecosystem; Channels adds WebSockets to same project.

**Q2: How is double booking prevented?**  
A: Application-level overlap checks in `assert_no_booking_overlap` plus partial unique constraint `unique_active_lawyer_booking_slot` on `(lawyer, date, time)` for pending/confirmed statuses.

**Q3: When does chat unlock?**  
A: When `booking.status` is `confirmed` or `completed` AND `payment.payment_status` is `success` (`booking_is_chat_eligible`).

**Q4: How are payments made idempotent?**  
A: `idempotency_key` on payments, unique provider events, `transition_payment_status` returns early if status unchanged but still reconciles booking.

**Q5: What is Lexora?**  
A: Rule-based legal information assistant with optional Gemini; includes disclaimer; not legal advice.

**Q6: Difference between `/admin/` and `/django-admin/`?**  
A: Custom ops UI for daily tasks vs Django model CRUD for developers.

**Q7: Why HTTP POST for chat messages if WebSocket exists?**  
A: Reliable file upload and form handling; WebSocket used for push delivery only.

**Q8: What happens if Redis is unavailable?**  
A: In-memory channel layer; Celery runs eager locally; single-server demo still works.

## Appendix L — Important Code Snippets

**Booking creation (atomic):**

```python
# main/services/bookings.py
with transaction.atomic():
    lawyer = lock_lawyer_for_booking(lawyer)
    slot = validate_booking_slot(lawyer, appointment_date, appointment_time)
    booking = Booking.objects.create(..., status=Booking.Status.PENDING)
    Payment.objects.create(booking=booking, amount=booking.price_snapshot or lawyer.fee)
```

**Chat eligibility:**

```python
# main/services/chat.py
def booking_is_chat_eligible(booking):
    payment = getattr(booking, "payment", None)
    return bool(
        booking.status in BOOKING_CHAT_STATUSES
        and payment is not None
        and payment.payment_status == Payment.PaymentStatus.SUCCESS
    )
```

**WebSocket consumer authorization:**

```python
# main/consumers.py
if not user.is_authenticated or not await self.user_can_access_chat(user.id, self.chat_id):
    await self.close(code=4403)
    return
```

## Appendix M — Module Dependencies

```
views → services → models
views → forms, decorators, rate_limit
payments → bookings (confirm on success)
chat → bookings, payments (eligibility)
bookings → lawyers, notifications
lexora → lawyers (recommendations)
admin_panel → bookings, payments, auth
tasks → payments, reminders, emails
consumers → models (chat access query)
```

## Appendix N — End-to-End Project Workflow

1. **Setup:** `pip install -r requirements.txt`, `migrate`, `generate_lawyers.py --with-slots`.  
2. **Client:** Register → book → request payment verification.  
3. **Admin:** Approve payment → booking confirmed.  
4. **Both:** Open `/chat/booking/<id>/` → real-time chat.  
5. **Lawyer:** Mark booking completed.  
6. **Client:** Submit review on profile.  
7. **Ops:** Monitor health, cleanup commands, Celery beat reminders.

---

## Suggested Page Distribution (Approximate)

| Chapter | Pages |
|---------|-------|
| Preliminary (Title–TOC) | 8–10 |
| Chapter 1 | 8–10 |
| Chapter 2 | 10–12 |
| Chapter 3 | 8–10 |
| Chapter 4 | 12–15 |
| Chapter 5 | 20–25 |
| Chapter 6 | 25–35 |
| Chapter 7 | 15–20 |
| Chapter 8 | 5–8 |
| References/Bibliography/Appendix | 10–15 |
| **Total** | **~120–150** |

## Suggested Figure Numbering

Figures 1.x (Ch1), 2.x (Ch2), 5.x (Ch5 design), 6.x (screenshots Ch6), 7.x (testing).

## Suggested Table Numbering

Tables 2.1, 4.1–4.4, 5.1, 6.1, 7.1–7.5.

## Suggested Appendix Contents

A: Schema | B: Folders | C: Stack | D: Security | E: Auth | F–H: Workflows | I: Screenshots | J: Diagrams | K: Viva | L: Code | M: Dependencies | N: E2E workflow

---

*Document generated from LexConnect implemented codebase. Update placeholders and institute formatting before submission.*
