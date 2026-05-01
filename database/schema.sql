CREATE DATABASE propertymanagement;
USE propertymanagement;
CREATE TABLE `users` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `name` VARCHAR(255) NOT NULL,
  `email` VARCHAR(255) NOT NULL UNIQUE,
  `password` VARCHAR(255) NOT NULL,
  `role` ENUM('tenant', 'owner', 'admin') NOT NULL,
  `phone` VARCHAR(20),
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE `properties` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `owner_id` INT NOT NULL,
  `title` VARCHAR(255) NOT NULL,
  `description` TEXT,
  `property_type` VARCHAR(50),
  `listing_type` ENUM('rent', 'sale') NOT NULL,
  `bedrooms` INT,
  `bathrooms` DECIMAL(3,1),
  `square_feet` INT,
  `monthly_rent` INT,
  `security_deposit` INT,
  `available_from` DATE,
  `pets_allowed` BOOLEAN DEFAULT false,
  `furnished` BOOLEAN DEFAULT false,
  `full_address` VARCHAR(255),
  `neighborhood` VARCHAR(100),
  `city` VARCHAR(100),
  `thana` VARCHAR(100),
  `district` VARCHAR(100),
  `postal_code` VARCHAR(20),
  `latitude` DECIMAL(10, 8),
  `longitude` DECIMAL(11, 8),
  `google_place_id` VARCHAR(255),
  `status` ENUM('occupied', 'vacant', 'maintenance', 'draft') DEFAULT 'draft',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `last_updated` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (`owner_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  INDEX `idx_location` (`latitude`, `longitude`),
  INDEX `idx_thana` (`thana`),
  INDEX `idx_district` (`district`),
  INDEX `idx_status` (`status`),
  INDEX `idx_property_type` (`property_type`),
  INDEX `idx_listing_type` (`listing_type`)
);

CREATE TABLE `property_images` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `property_id` INT NOT NULL,
  `image_url` VARCHAR(255) NOT NULL,
  `is_cover` BOOLEAN DEFAULT false,
  FOREIGN KEY (`property_id`) REFERENCES `properties`(`id`) ON DELETE CASCADE
);

CREATE TABLE `amenities` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `name` VARCHAR(100) NOT NULL UNIQUE
);

-- Seed initial amenities
INSERT INTO `amenities` (`name`) VALUES 
('WiFi'), ('Parking'), ('Air Conditioning'), ('TV/Cable'), 
('Kitchen'), ('Laundry'), ('Balcony'), ('Security'), 
('Furnished'), ('Gym/Fitness'), ('Swimming Pool'), ('Elevator')
ON DUPLICATE KEY UPDATE `name`=`name`;

CREATE TABLE `property_amenities` (
  `property_id` INT NOT NULL,
  `amenity_id` INT NOT NULL,
  PRIMARY KEY (`property_id`, `amenity_id`),
  FOREIGN KEY (`property_id`) REFERENCES `properties`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`amenity_id`) REFERENCES `amenities`(`id`) ON DELETE CASCADE
);

CREATE TABLE `inquiries` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `property_id` INT NOT NULL,
  `tenant_id` INT NOT NULL,
  `message` TEXT,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`property_id`) REFERENCES `properties`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`tenant_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
);

CREATE TABLE `tenancies` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `property_id` INT NOT NULL,
  `tenant_id` INT NOT NULL,
  `start_date` DATE NOT NULL,
  `end_date` DATE,
  `rent_amount` INT,
  `status` ENUM('active', 'ended') DEFAULT 'active',
  FOREIGN KEY (`property_id`) REFERENCES `properties`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`tenant_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
);

-- Chatbot sessions for conversation tracking
CREATE TABLE `chatbot_sessions` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `user_id` INT,
  `session_token` VARCHAR(255) NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `last_activity` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `status` ENUM('active', 'ended') DEFAULT 'active',
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE SET NULL
);

-- Chatbot conversations for message history
CREATE TABLE `chatbot_conversations` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `session_id` INT NOT NULL,
  `message_type` ENUM('user', 'bot') NOT NULL,
  `message_text` TEXT NOT NULL,
  `intent` VARCHAR(100),
  `entities` JSON,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`session_id`) REFERENCES `chatbot_sessions`(`id`) ON DELETE CASCADE
);

-- Search history for analytics and learning
CREATE TABLE `search_history` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `user_id` INT,
  `session_id` INT,
  `search_query` TEXT NOT NULL,
  `search_location` VARCHAR(255),
  `search_criteria` JSON,
  `results_count` INT DEFAULT 0,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
  FOREIGN KEY (`session_id`) REFERENCES `chatbot_sessions`(`id`) ON DELETE SET NULL
);

-- Location data cache for geocoding results
CREATE TABLE `location_data` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `address` VARCHAR(500) NOT NULL,
  `formatted_address` VARCHAR(500),
  `latitude` DECIMAL(10, 8) NOT NULL,
  `longitude` DECIMAL(11, 8) NOT NULL,
  `thana` VARCHAR(100),
  `district` VARCHAR(100),
  `division` VARCHAR(100),
  `postal_code` VARCHAR(20),
  `place_id` VARCHAR(255),
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `unique_address` (`address`),
  INDEX `idx_coordinates` (`latitude`, `longitude`),
  INDEX `idx_thana` (`thana`),
  INDEX `idx_district` (`district`)
);

-- Landmarks and points of interest
CREATE TABLE `landmarks` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `name` VARCHAR(255) NOT NULL,
  `category` VARCHAR(100),
  `latitude` DECIMAL(10, 8) NOT NULL,
  `longitude` DECIMAL(11, 8) NOT NULL,
  `thana` VARCHAR(100),
  `district` VARCHAR(100),
  `place_id` VARCHAR(255),
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX `idx_name` (`name`),
  INDEX `idx_category` (`category`),
  INDEX `idx_coordinates` (`latitude`, `longitude`)
);


