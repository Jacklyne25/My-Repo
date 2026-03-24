# DSAMS - Full System Report

## 1. Executive Summary
The Digital Student Attendance Monitoring System (DSAMS) is a comprehensive academic management platform designed to streamline scheduling, user administration, and attendance tracking. It leverages a hybrid monitoring approach to bridge digital efficiency with formal paper-based verification.

---

## 2. Module Functionality

### 2.1 User Management
- **Role-Based Access Control (RBAC)**: Support for System Admin, Faculty Admin, HOD, Lecturer, Coordinator, and Student.
- **Account Activation**: HOD-mediated activation for pending nominations with enforced password resets on first login.
- **Institutional Identity**: Integration of Staff IDs and Registration Numbers for secure identification.

### 2.2 Scheduling Module
- **7-Step Workflow**: Guided process for HODs to define academic years, semesters, and parameters.
- **Auto-Generation**: Greedy algorithm for conflict-free timetable generation based on room capacity and lecturer availability.
- **Visual Grid**: Interactive Monday-Friday (8:00 AM - 5:00 PM) timetable display tailored to each user role.

### 2.3 Attendance Monitoring (Hybrid)
- **Digital Recording**: Direct attendance capture by Class Coordinators via the mobile-friendly web interface.
- **Document-Based Verification**: Support for uploading scanned, signed paper attendance sheets.
- **Weekly Activity**: Grouped monitoring of the standard two lecture sessions per week per course.

### 2.4 Lecture Monitoring
- **Real-Time Tracking**: Monitoring of session status (Scheduled, Conducted, Missed, Approved).
- **Compliance Alerts**: Automated triggers notifying HODs of missed lectures or unsubmitted attendance records.

### 2.5 Communication Module
- **Role-Targeted Announcements**: Granular messaging (e.g., Lecturer to specific course students).
- **System Notifications**: Automated alerts for timetable publication, rescheduling, and report generation.
- **Notification Inbox**: Global notification bell with unread tracking.

---

## 3. Requirements

### 3.1 Functional Requirements
- **FR1**: System must support bulk import of academic data (Users, Rooms, Courses) via CSV/Excel.
- **FR2**: System must detect and prevent scheduling conflicts (Room double-booking, Lecturer overlap).
- **FR3**: System must allow Lecturers to verify and batch-approve weekly attendance.
- **FR4**: System must provide automated compliance reporting for HODs.

### 3.2 Non-Functional Requirements
- **Security**: SHA-256 password hashing, session-based authentication, and brute-force protection (ratelimiting).
- **Scalability**: Designed to support department-wide scaling with future-ready email/SMS hooks.
- **Aesthetics**: Premium Glassmorphism UI with responsive design for mobile and desktop.
- **Auditability**: Systematic logging of administrative actions via `AuditLog`.

---

## 4. Technology Stack
- **Backend Framework**: Python 3.12 / Django 4.2 (LTS)
- **Frontend**: HTML5, CSS3 (Vanilla), JavaScript (ES6+)
- **Database**: 
    - *Development*: SQLite3
    - *Production*: MySQL 8.0+
- **Key Libraries**:
    - `Pandas` / `OpenPyXL`: Excel template processing and data imports.
    - `ReportLab`: Generated PDF reporting.
    - `Pillow`: Image processing for uploaded attendance sheets.
    - `Factory Boy` / `Pytest`: Robust automated verification suite.

---

## 5. System Requirements

### 5.1 Server-Side
- **Operating System**: Linux (Ubuntu 22.04 LTS recommended) or Windows Server.
- **Environment**: Python 3.10+, pip, virtualenv.
- **Web Server**: Nginx with Gunicorn (Production).

### 5.2 Client-Side
- **Web Browser**: Latest version of Chrome, Firefox, Edge, or Safari.
- **Resolution**: Min-width 320px (Mobile-Responsive).

---

## 6. Development & Verification
- **Test Coverage**: Dedicated test suites for Notifications ([tests_notifications.py](file:///c:/Users/jackie/Desktop/DSAMS/core/tests_notifications.py)) and Hybrid Attendance ([tests_hybrid.py](file:///c:/Users/jackie/Desktop/DSAMS/attendance/tests_hybrid.py)).
- **Standardization**: Adherence to PEP 8 coding standards and Django best practices.
