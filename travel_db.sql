CREATE DATABASE IF NOT EXISTS travel_db; -- create db if it doesnt exist
USE travel_db; -- use newly created db

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL --changed from 'password'.
);

CREATE TABLE hotels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL, -- FK referencing the owner of the hotel.
    name VARCHAR(100) NOT NULL,
    location VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    description TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)-- establish a FK relationship to the users table.       
);

CREATE TABLE faqs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    embedding BLOB -- vector representation for AI-based retrieval(RAG)
);

CREATE TABLE reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding BLOB -- vector representation for AI-based retrieval(RAG)
);
