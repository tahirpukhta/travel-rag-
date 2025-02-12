-- Active: 1738385387191@@127.0.0.1@3306@travel_db
-- Create the travel database if it doesn't exist and use it
CREATE DATABASE IF NOT EXISTS travel_db;
USE travel_db;

-- Create the users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL
);

-- Create the hotels table with a foreign key linking to users
CREATE TABLE IF NOT EXISTS hotels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    description TEXT,
    amenities VARCHAR(200),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Create the FAQs table for AI retrieval
CREATE TABLE IF NOT EXISTS faqs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    embedding BLOB
);

-- Create the reviews table with columns matching the ORM model
CREATE TABLE IF NOT EXISTS reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    content TEXT NOT NULL,
    user_id INT NOT NULL,
    hotel_id INT NOT NULL,
    embedding BLOB,
    sentiment VARCHAR(20)
);

-- Add foreign key constraints for reviews
ALTER TABLE reviews
ADD CONSTRAINT fk_review_user
    FOREIGN KEY (user_id) REFERENCES users(id),
ADD CONSTRAINT fk_review_hotel
    FOREIGN KEY (hotel_id) REFERENCES hotels(id);

-- Add indexes for frequent joins
CREATE INDEX idx_reviews_user ON reviews(user_id);
CREATE INDEX idx_reviews_hotel ON reviews(hotel_id);

-- Optional: For text search fallback on reviews
CREATE FULLTEXT INDEX idx_review_content ON reviews(content);

