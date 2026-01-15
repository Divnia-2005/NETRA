-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Jan 14, 2026 at 09:14 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.0.30

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `netra`
--

-- --------------------------------------------------------

--
-- Table structure for table `alerts`
--

CREATE TABLE `alerts` (
  `id` int(11) NOT NULL,
  `severity` enum('Critical','Warning','Info') NOT NULL,
  `source` varchar(100) NOT NULL,
  `message` text NOT NULL,
  `status` enum('Unresolved','Investigating','Resolved') DEFAULT 'Unresolved',
  `created_at` datetime DEFAULT current_timestamp(),
  `assigned_officer_id` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `alerts`
--

INSERT INTO `alerts` (`id`, `severity`, `source`, `message`, `status`, `created_at`, `assigned_officer_id`) VALUES
(1, 'Critical', 'Camera-01', 'Unauthorized access detected', 'Resolved', '2026-01-07 23:51:16', NULL),
(2, 'Warning', 'Server', 'High CPU usage', 'Resolved', '2026-01-07 23:51:16', NULL),
(3, 'Info', 'Backup System', 'Backup completed successfully', 'Resolved', '2026-01-07 23:51:16', NULL);

-- --------------------------------------------------------

--
-- Table structure for table `messages`
--

CREATE TABLE `messages` (
  `id` int(11) NOT NULL,
  `sender_id` int(11) NOT NULL,
  `receiver_id` int(11) DEFAULT NULL,
  `content` text NOT NULL,
  `timestamp` datetime DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `messages`
--

INSERT INTO `messages` (`id`, `sender_id`, `receiver_id`, `content`, `timestamp`) VALUES
(11, 73, 93, 'Hello Officer 93, this is Admin.', '2026-01-13 10:30:29'),
(12, 93, 73, 'Acknowledged Admin 73.', '2026-01-13 10:30:29'),
(13, 17, NULL, 'hellooo officers', '2026-01-13 10:33:44'),
(14, 97, 98, 'Hello B (98) from A (97)', '2026-01-13 10:47:15'),
(15, 98, 97, 'Hello A (97), this is B.', '2026-01-13 10:47:15'),
(16, 1, 17, 'rfbwiehf', '2026-01-13 10:49:20'),
(17, 1, 65, 'hello mr  albin', '2026-01-13 10:49:41'),
(18, 73, NULL, 'Notification Test', '2026-01-13 11:49:01'),
(19, 1, 17, 'system alert is not working!!!', '2026-01-13 12:03:39'),
(20, 17, 65, 'dei', '2026-01-13 12:08:58'),
(21, 1, 17, 'sus found', '2026-01-13 12:27:00');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `google_id` varchar(255) DEFAULT NULL,
  `name` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `role` varchar(50) DEFAULT 'officer',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `password` varchar(255) DEFAULT NULL,
  `reset_otp` varchar(6) DEFAULT NULL,
  `otp_expiry` datetime DEFAULT NULL,
  `status` enum('pending','approved','rejected','blocked') DEFAULT 'pending'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`id`, `google_id`, `name`, `email`, `role`, `created_at`, `password`, `reset_otp`, `otp_expiry`, `status`) VALUES
(1, 'manual_google_id_001', 'DIVINIA MARIO ANTONY', 'diviniamarioantony2028@mca.ajce.in', 'officer', '2025-12-23 05:57:06', 'divinia123', NULL, NULL, 'approved'),
(16, NULL, 'ardra', 'ardrasnair2028@mca.ajce.in', 'officer', '2026-01-07 06:44:09', '123456789', NULL, NULL, 'approved'),
(17, NULL, 'aleena shibu', 'aleenashibu2028@mca.ajce.in', 'admin', '2026-01-07 08:03:02', 'divinia123', NULL, NULL, 'approved'),
(51, NULL, 'Test Officer', 'testofficer@netra.com', 'officer', '2026-01-13 00:59:46', '123456', NULL, NULL, 'approved'),
(53, NULL, 'don shaji', 'donshaji2028@mca.ajce.in', 'officer', '2026-01-13 01:13:56', 'donshaji123', NULL, NULL, 'blocked'),
(62, NULL, 'Verify Pending', 'verify_pending@netra.com', 'officer', '2026-01-13 03:20:49', 'password123', NULL, NULL, 'approved'),
(65, NULL, 'albin thomas', 'albinthomas2028@mca.ajce.in', 'officer', '2026-01-13 03:23:42', 'albinthomas123', NULL, NULL, 'approved'),
(73, NULL, 'Admin', 'admin@netra.com', 'admin', '2026-01-13 04:32:11', 'admin123', NULL, NULL, 'approved'),
(74, NULL, 'Unblock Test', 'unblock_test@netra.com', 'officer', '2026-01-13 04:32:35', 'password123', NULL, NULL, 'approved'),
(93, NULL, 'Msg Test', 'msg_test@netra.com', 'officer', '2026-01-13 05:00:29', 'password123', NULL, NULL, 'approved'),
(97, NULL, 'Officer A', 'p2p_a@netra.com', 'officer', '2026-01-13 05:17:14', 'a_pass', NULL, NULL, 'approved'),
(98, NULL, 'Officer B', 'p2p_b@netra.com', 'officer', '2026-01-13 05:17:14', 'b_pass', NULL, NULL, 'approved'),
(107, NULL, 'ashin tom ', 'ashintommathew2028@mca.ajce.in', 'officer', '2026-01-13 10:23:08', 'ashin123', NULL, NULL, 'approved'),
(109, NULL, 'anupriya', 'anupriyaa2028@mca.ajce.in', 'officer', '2026-01-13 10:44:59', 'anupriya123', NULL, NULL, 'approved');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `alerts`
--
ALTER TABLE `alerts`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fk_assigned_officer` (`assigned_officer_id`);

--
-- Indexes for table `messages`
--
ALTER TABLE `messages`
  ADD PRIMARY KEY (`id`),
  ADD KEY `sender_id` (`sender_id`),
  ADD KEY `receiver_id` (`receiver_id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `email` (`email`),
  ADD UNIQUE KEY `google_id` (`google_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `alerts`
--
ALTER TABLE `alerts`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

--
-- AUTO_INCREMENT for table `messages`
--
ALTER TABLE `messages`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=22;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=117;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `alerts`
--
ALTER TABLE `alerts`
  ADD CONSTRAINT `fk_assigned_officer` FOREIGN KEY (`assigned_officer_id`) REFERENCES `users` (`id`);

--
-- Constraints for table `messages`
--
ALTER TABLE `messages`
  ADD CONSTRAINT `messages_ibfk_1` FOREIGN KEY (`sender_id`) REFERENCES `users` (`id`),
  ADD CONSTRAINT `messages_ibfk_2` FOREIGN KEY (`receiver_id`) REFERENCES `users` (`id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
