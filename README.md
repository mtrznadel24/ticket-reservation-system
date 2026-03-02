![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Django](https://img.shields.io/badge/django-%23092e20.svg?style=for-the-badge&logo=django&logoColor=white)
![Celery](https://img.shields.io/badge/celery-%2337814A.svg?style=for-the-badge&logo=celery&logoColor=white)
![Poetry](https://img.shields.io/badge/Poetry-%233B82F6.svg?style=for-the-badge&logo=poetry&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)

# 🎟️ Ticket Reservation System
A robust, web-based ticket reservation system built with Django and PostgreSQL. Originally developed as a university database project, recently refactored and expanded independently to implement professional architectural patterns and modern DevOps practices.

> ⚠️ Note: The payment system is **not implemented**. Tickets can be reserved and marked as sold, but no real payment gateway is integrated.

---

## 📖 Project Background & Evolution
This project originated as a 2-person university assignment for a Database Systems course. I decided to refactor the code to transform it from a simple academic task into a professional-grade application.

### Key Refactoring Milestones:
* Architectural Overhaul: Introduced a Service Layer to decouple business logic from views, adhering to the Separation of Concerns principle.

* Performance Optimization: Eliminated N+1 query problems by strategically using select_related, prefetch_related, and database annotate.

* Concurrency Control: Implemented Database Row-Level Locking (select_for_update) to prevent race conditions during ticket reservations.

* Modern Infrastructure: Fully dockerized the application (Django, PostgreSQL, Worker, Beat, Redis) using Docker Compose for seamless deployment.

* Asynchronous Task Processing: Integrated Celery to offload heavy I/O operations (PDF generation) from the main request-response cycle, significantly reducing server response time.

* Automated Lifecycle Management: Implemented Celery Beat to orchestrate periodic tasks, replacing manual cleanup with a reliable, scheduled system.

*

---

## 🧱 Tech Stack

- **Backend:** Django (Python), Celery (Background tasks)
- **Infrastructure:** PostgreSQL, Redis
- **DevOps:** Docker, Docker Compose
- **Frontend:** HTML, Bootstrap 5, QR Code Generation (External API)
- **Auth:** Django built-in authentication
- **ORM:** Django ORM
- **Tooling:** Ruff, Poetry

---

## 🚀 Features & Business Logic


### User Experience
* Smart Event Browsing: Optimized listing of upcoming events with real-time ticket availability counting (database-level).

* Secure Reservation: Multi-ticket selection with a 15-minute window before seats are automatically released.

* Enhanced Shopping Cart: Dedicated view for inputting specific participant data (First Name, Last Name, PESEL) for each ticket.

* Order Management: Full order history for registered users, detailed order tracking, and a cancellation system that resets ticket availability.

* Responsive UI: Fully mobile-friendly interface built with Bootstrap 5.

### Technical Excellence 
* Service Layer Architecture: Business logic is entirely decoupled from Django views, ensuring high maintainability and testability.

* Database Optimization: Eliminated N+1 query problems using strategic annotate, select_related, and Count/Sum aggregations.

* Concurrency Protection: Implemented Row-Level Locking (select_for_update) to ensure no two users can reserve the same seat simultaneously.

* Data Integrity: Used Atomic Transactions to ensure that multi-step processes (like finalizing an order) either complete fully or roll back on error.

* Maintenance Automation: Custom Django Management Command (cleanup_reservations) to handle database cleanup, ready for Cron or Celery scheduling.

### Asynchronous Operations

* Non-blocking PDF Generation: Tickets are generated in the background. Users can continue browsing while a distributed worker handles the PDF creation and QR code embedding.

* Instant QR Visualization: Integrated dynamic QR code rendering in the user dashboard for seamless mobile check-ins without downloading files.

### Automation & Maintenance

* Automated Reservation Cleanup: A background scheduler (Celery Beat) monitors the database every minute to release expired 15-minute seat reservations, ensuring maximum ticket availability.

* Reliable Task Execution: Used transaction.on_commit to ensure background tasks are only queued after successful database commits, preventing race conditions.

---

## 🛠️ Installation & Running
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

## 🗺️ Roadmap (Future Enhancements)
* [ ] Data Security: Hashing/Encoding of sensitive participant data (PESEL) before database storage.

* [ ] Payment Integration: Mocking a payment gateway (e.g., Stripe/PayU integration).

## 👥 Authors

- [Maciej Trznadel](https://github.com/mtrznadel24) - Developer, Architect, Refactoring & DevOps
- [Patryk Blacha](https://github.com/PatrykBlacha) - Orginal project collabolator

### [Orignal Repository](https://github.com/PatrykBlacha/ticket-reservation-system)





