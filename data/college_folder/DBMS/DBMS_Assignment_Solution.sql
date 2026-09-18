-- ==========================================================
-- JARVIS Autonomous Solutions Engine
-- Course: DBMS (Database Management Systems)
-- Task: Assignment 1 - Relational Schema, Normalization & SQL Queries
-- Generated: 2026-09-19 01:33:22
-- ==========================================================

-- Q1: Relational Schema Definition
CREATE TABLE Students (
    student_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    email VARCHAR(100) UNIQUE
);

CREATE TABLE Courses (
    course_id VARCHAR(10) PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    credits INT CHECK (credits > 0)
);

CREATE TABLE Enrollments (
    enrollment_id INT PRIMARY KEY,
    student_id INT REFERENCES Students(student_id),
    course_id VARCHAR(10) REFERENCES Courses(course_id),
    grade CHAR(2),
    enrollment_date DATE
);

-- Q2: 3NF & BCNF Normalization Proof
-- Functional Dependencies:
-- student_id -> name, department, email
-- course_id -> title, credits
-- (student_id, course_id) -> grade, enrollment_date
-- All non-key attributes are fully functionally dependent on candidate keys.
-- Schema satisfies Boyce-Codd Normal Form (BCNF).

-- Q3: Complex Query Formulation
SELECT s.name, c.title, e.grade
FROM Students s
JOIN Enrollments e ON s.student_id = e.student_id
JOIN Courses c ON e.course_id = c.course_id
WHERE e.grade = 'A'
ORDER BY s.name ASC;

-- Completed by JARVIS Autonomous Computer-Use Agent.
