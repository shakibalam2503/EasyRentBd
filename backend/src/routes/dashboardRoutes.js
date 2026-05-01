
const express = require('express');
const router = express.Router();
const dashboardController = require('../controllers/dashboardController');
const { protect, isOwner } = require('../middleware/authMiddleware');

// Owner dashboard route
router.get('/owner', protect, isOwner, dashboardController.getOwnerDashboard);

router.get('/tenant', protect, dashboardController.getTenantDashboard);

module.exports = router;
