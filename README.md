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

* Modern Infrastructure: Fully dockerized the application (Backend + PostgreSQL) using Docker Compose for seamless deployment.

* Advanced CLI Tooling: Moved maintenance tasks (like clearing expired reservations) into custom Django Management Commands.
---

## 🧱 Tech Stack

- **Backend:** Django (Python)
- **Database:** PostgreSQL
- **DevOps:** Docker, Docker Compose
- **Frontend:** HTML, Bootstrap 5
- **Auth:** Django built-in authentication
- **ORM:** Django ORM
- **Linter:** Ruff

---

## 🚀 Features & Business Logic


### User Experience
* Smart Event Browsing: Optimized listing of upcoming events with real-time ticket availability counting (database-level).

* Secure Reservation: Multi-ticket selection with a 15-minute window before seats are automatically released.

* Enhanced Shopping Cart: Dedicated view for inputting specific participant data (First Name, Last Name, PESEL) for each ticket.

* Order Management: Full order history for registered users, detailed order tracking, and a cancellation system that resets ticket availability.

* Responsive UI: Fully mobile-friendly interface built with Bootstrap 5.

### Technical Excellence (The "Under the Hood" Stuff)
* Service Layer Architecture: Business logic is entirely decoupled from Django views, ensuring high maintainability and testability.

* Database Optimization: Eliminated N+1 query problems using strategic annotate, select_related, and Count/Sum aggregations.

* Concurrency Protection: Implemented Row-Level Locking (select_for_update) to ensure no two users can reserve the same seat simultaneously.

* Data Integrity: Used Atomic Transactions to ensure that multi-step processes (like finalizing an order) either complete fully or roll back on error.

* Maintenance Automation: Custom Django Management Command (cleanup_reservations) to handle database cleanup, ready for Cron or Celery scheduling.

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
* [ ] Asynchronous Tasks: Integration with Redis & Celery for automated background reservation cleanup and email notifications.

* [ ] Data Security: Hashing/Encoding of sensitive participant data (PESEL) before database storage.

* [ ] Guest Checkout: Allowing users to reserve tickets without a mandatory account.

* [ ] Payment Integration: Mocking a payment gateway (e.g., Stripe/PayU integration).
## 👥 Authors

- [Maciej Trznadel](https://github.com/mtrznadel24) - Developer, Architect, Refactoring & DevOps
- [Patryk Blacha](https://github.com/PatrykBlacha) - Orginal project collabolator

### [Orignal Repository](https://github.com/PatrykBlacha/ticket-reservation-system)





