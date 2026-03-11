![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Django](https://img.shields.io/badge/django-%23092e20.svg?style=for-the-badge&logo=django&logoColor=white)
![Celery](https://img.shields.io/badge/celery-%2337814A.svg?style=for-the-badge&logo=celery&logoColor=white)
![Poetry](https://img.shields.io/badge/Poetry-%233B82F6.svg?style=for-the-badge&logo=poetry&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/github%20actions-%232088FF.svg?style=for-the-badge&logo=githubactions&logoColor=white)
![Nginx](https://img.shields.io/badge/nginx-%23009639.svg?style=for-the-badge&logo=nginx&logoColor=white)


# Ticket Reservation System
A robust, web-based ticket reservation system built with Django and PostgreSQL. Originally developed as a university database project, recently refactored and expanded independently to implement professional architectural patterns and modern DevOps practices.

> ⚠️ Note: System is using Stripe in test mode. No real funds are moved.

---

## 🌐 Live Demo
#### **Website:** [https://tickets.mtrznadel.me](https://tickets.mtrznadel.me)  

### Test Credentials:
* **User (Client):** `demo_user` / `Password123!`
* **Staff (Scanner):** `staff_user` / `Password123!`

### Payment Testing:
The system is integrated with Stripe in **Test Mode**. To complete a successful transaction and receive a ticket PDF, use the following test card details:
* **Card Number:** `4242 4242 4242 4242`
* **Expiry/CVC:** Any future date and any 3 digits.

> 💡 **Note:** The database may be reset periodically to maintain a clean demo environment.
> 
---

### Project Background & Evolution
This project originated as a 2-person university assignment for a Database Systems course. I decided to refactor the code to transform it from a simple academic task into a professional-grade application.

---

### Key Refactoring Milestones:
* Architectural Overhaul: Introduced a Service Layer to decouple business logic from views, adhering to the Separation of Concerns principle.

* Performance Optimization: Eliminated N+1 query problems by strategically using select_related, prefetch_related, and database annotate.

* Concurrency Control: Implemented Database Row-Level Locking (select_for_update) to prevent race conditions during ticket reservations.

* Modern Infrastructure: Fully dockerized the application (Django, PostgreSQL, Worker, Beat, Redis) using Docker Compose for seamless deployment.

* Asynchronous Task Processing: Integrated Celery to offload heavy I/O operations (PDF generation) from the main request-response cycle, significantly reducing server response time.

* Automated Lifecycle Management: Implemented Celery Beat to orchestrate periodic tasks, replacing manual cleanup with a reliable, scheduled system.

* Payment Integration: Used Stripe API (Test Mode) for payment processing. Implemented Webhooks to handle asynchronous order confirmation.

* Testing: Developed a comprehensive test suite using Pytest, covering critical business paths

* CI/CD Integration: Established a fully automated pipeline using GitHub Actions, handling linting, testing, and production deployment.

* Production-Grade Deployment: Configured a secure Nginx reverse proxy with SSL termination and Gunicorn process management on a DigitalOcean Droplet.

---

## Tech Stack

- **Backend:** Django (Python), Celery (Background tasks), Gunicorn
- **Infrastructure:** PostgreSQL, Redis
- **DevOps & CI/CD:** Docker, Docker Compose, GitHub Actions, Nginx
- **Frontend:** HTML, Bootstrap 5, QR Code Generation (External API)
- **Tooling:** Ruff, Poetry, Pytest
- **Security:** AES-256 Encryption (Fernet), SSL (Let's Encrypt)
- **Payment Gateway:** Stripe

---

## Features & Business Logic


### User Experience
* **Smart Event Browsing:** Optimized listing of upcoming events with real-time ticket availability counting (database-level).

* **Secure Reservation:** Multi-ticket selection with a 15-minute window before seats are automatically released.

* **Enhanced Shopping Cart:** Dedicated view for inputting specific participant data (First Name, Last Name, PESEL) for each ticket.

* **Order Management:** Full order history for registered users, detailed order tracking, and a cancellation system that resets ticket availability.

* **Responsive UI:** Fully mobile-friendly interface built with Bootstrap 5.

### Technical Excellence 
* **Service Layer Architecture:** Business logic is entirely decoupled from Django views, ensuring high maintainability and testability.

* **Database Optimization:** Eliminated N+1 query problems using strategic annotate, select_related, and Count/Sum aggregations.

* **Database Indexing Strategy:** Optimized query performance by implementing database indexes on frequently filtered fields (e.g., start_datetime).

* **Concurrency Protection:** Implemented Row-Level Locking (select_for_update) to ensure no two users can reserve the same seat simultaneously.

* **Data Integrity:** Used Atomic Transactions to ensure that multistep processes (like finalizing an order) either complete fully or roll back on error.

* **Secure Checkout Flow:** Integrated Stripe API with custom success/cancel redirection logic and session metadata handling.

* **Asynchronous Order Fulfillment:** Implemented Stripe Webhooks to listen for `checkout.session.completed` events. This ensures that tickets are only marked as "Sold" and generated (PDF) after a verified payment confirmation from the provider.

### Asynchronous Operations

* **Non-blocking PDF Generation:** Tickets are generated in the background. Users can continue browsing while a distributed worker handles the PDF creation and QR code embedding.

* **Instant QR Visualization:** Integrated dynamic QR code rendering in the user dashboard for seamless mobile check-ins without downloading files.

### Automation & Maintenance

* **Automated Reservation Cleanup:** A background scheduler (Celery Beat) monitors the database every minute to release expired 15-minute seat reservations, ensuring maximum ticket availability.

* **Reliable Task Execution:** Used transaction.on_commit to ensure background tasks are only queued after successful database commits, preventing race conditions.

### Security & Data Privacy

* **Sensitive Data Encryption:** Implemented application-level encryption for personal identifiers (PESEL) using `django-encrypted-model-fields` (AES-256 via Fernet). Even with full database access, sensitive data remains unreadable without the unique `FIELD_ENCRYPTION_KEY`.
* **Secure Environment Management:** Decoupled sensitive credentials (DB passwords, Encryption keys, Stripe secrets) from the codebase using Docker environment variables and `.env` files.

### Staff & Management Tools

* **Real-time Ticket Verification:** Dedicated dashboard for event staff to scan and validate tickets.
* **Anti-Fraud System:** Automatic status updates to "Scanned" upon verification to prevent double-entry or ticket reuse.
* **Mass Data Generation:** Administrative tools to generate thousands of tickets across multiple sectors/rows in seconds using optimized database operations.

---

## 🛠️ DevOps & CI/CD

### Automated Pipeline (GitHub Actions)
* **Continuous Integration:** Every Pull Request triggers an automated suite of **Pytest** units and **Ruff** linting/formatting checks.
* **Continuous Deployment:** Successful merges to the `main` branch trigger an automated deployment to the production server via SSH, ensuring zero manual intervention.

### Production Environment
* **Web Server:** **Nginx** acts as a reverse proxy, managing static files and SSL/TLS encryption (Let's Encrypt).
* **Application Server:** **Gunicorn** serves as the WSGI HTTP Server, optimized for concurrent request handling.
* **Environment Safety:** Strict separation of configuration and secrets using `.env` files and Docker environment variables.

---

## Installation & Running
The easiest way to run the project is using Docker:

1. Clone the repository:
```bash
git clone https://github.com/mtrznadel24/ticket-reservation-system.git
cd ticket-reservation-system
```
2. Set up environment variables: Create a .env file based on .env.example.
3. Run with Docker Compose:
```bash
docker-compose up --build
```
4. Run migrations:
```bash
docker compose exec backend python manage.py migrate
```
The app will be available at http://localhost:8000.

## Authors

- [Maciej Trznadel](https://github.com/mtrznadel24) - Developer, Architect, Refactoring & DevOps
- [Patryk Blacha](https://github.com/PatrykBlacha) - Orginal project collabolator

### [Orignal Repository](https://github.com/PatrykBlacha/ticket-reservation-system)





