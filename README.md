# AZRION – Production-Ready E-Commerce Platform

AZRION is a full-featured, production-style e-commerce web application built using Django and PostgreSQL.  
The project demonstrates real-world backend architecture, secure authentication flows, payment integration, and a comprehensive admin management system.

---

## 🚀 Live Demo

https://azrion.shop  
(If deployed)

---

## 📌 Project Overview

AZRION is designed to simulate a real-world scalable e-commerce system with structured backend logic, modular architecture, and secure production practices.

This project focuses on:

- Clean authentication workflows
- Secure payment processing
- Structured admin controls
- Inventory & order lifecycle management
- Referral & wallet logic implementation

---

## 👤 User-Side Features

- OTP-Based Signup & Login
- Google OAuth Authentication
- Password Reset via OTP Verification
- Product Browsing & Filtering
- Product Variants (Size / Stock handling)
- Cart & Wishlist System
- Coupon Application
- Razorpay Payment Integration
- Payment Verification & Retry Handling
- Wallet & Referral System
- Order History
- Invoice Download
- Product Reviews & Ratings
- User Profile & Address Management

---

## 🛠 Admin-Side Features

- Dashboard with Sales Overview
- User Management (Block / Unblock)
- Product & Variant Management
- Inventory Stock Control
- Category & Offer Management
- Coupon Creation & Control
- Order Status Workflow Management
- Return Request Verification
- Wallet Monitoring
- Sales Report Generation & Download

---

## 🧠 Tech Stack

### Backend
- Python
- Django 5.x
- PostgreSQL
- Razorpay API
- Google OAuth (social-auth)

### Frontend
- HTML5
- CSS3
- JavaScript
- Tailwind CSS

---

## 🔐 Security Practices

- Environment-based secret management (.env)
- DEBUG = False in production
- CSRF Protection Enabled
- Secure authentication flows
- Sensitive keys removed from version control
- OAuth credentials rotated after exposure

---

## ⚙️ Installation & Setup

Clone the repository:

```bash
git clone https://github.com/banna652/AZRION.git
cd AZRION
```

Create virtual environment:

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in root directory:

```
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

GOOGLE_OAUTH_KEY=your_google_client_id
GOOGLE_OAUTH_SECRET=your_google_client_secret

RAZORPAY_KEY_ID=your_razorpay_key
RAZORPAY_KEY_SECRET=your_razorpay_secret

EMAIL_HOST_USER=your_email
EMAIL_HOST_PASSWORD=your_email_password
```

Apply migrations:

```bash
python manage.py migrate
```

Run server:

```bash
python manage.py runserver
```

---

## 📂 Project Architecture Highlights

- Modular Django app separation (User & Admin logic)
- Custom authentication workflow
- Secure OTP verification logic
- Structured URL routing
- Payment verification backend logic
- Environment-driven configuration
- PostgreSQL relational schema design

---

## 📈 Future Enhancements

- REST API version
- Docker deployment
- CI/CD pipeline
- Performance optimization
- Caching layer (Redis)
- Production deployment automation

---

## 🎯 Purpose of This Project

This project was built to demonstrate strong backend development capability, real-world authentication flows, payment integrations, and scalable admin architecture using Django and PostgreSQL.

---

## 👨‍💻 Developer

Muhammad Hasanul Banna  
Full Stack Developer (Django + PostgreSQL)

GitHub: https://github.com/banna652  
LinkedIn: https://www.linkedin.com/in/muhammad-hasanul-banna/

---

⭐ If you find this project useful, feel free to star the repository.