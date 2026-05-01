
const express = require('express');
const router = express.Router();
const propertyController = require('../controllers/propertyController');
const { protect } = require('../middleware/authMiddleware');
const upload = require('../middleware/uploadMiddleware');

// Protected specific routes (must be before /:id)
router.get('/owner', protect, propertyController.getOwnerProperties);

// Public routes
router.get('/', propertyController.getAllProperties);
router.get('/:id', propertyController.getPropertyById);

// Price statistics for chatbot
router.get('/price-stats', async (req, res) => {
    try {
        const db = require('../config/db');
        const [stats] = await db.query(
            `SELECT 
                AVG(monthly_rent) as avg_rent,
                MIN(monthly_rent) as min_rent,
                MAX(monthly_rent) as max_rent,
                COUNT(*) as total_properties
             FROM properties 
             WHERE status = 'vacant' AND monthly_rent > 0`
        );
        
        const avgRent = Math.round(stats[0].avg_rent || 0);
        const minRent = stats[0].min_rent || 0;
        const maxRent = stats[0].max_rent || 0;
        const totalProperties = stats[0].total_properties || 0;
        
        res.json({
            success: true,
            avg_rent: avgRent,
            min_rent: minRent,
            max_rent: maxRent,
            total_properties: totalProperties,
            budget_ranges: {
                budget: `${minRent.toLocaleString()} - 20,000 BDT`,
                mid_range: `20,000 - 50,000 BDT`,
                premium: `50,000+ BDT`
            }
        });
        
    } catch (error) {
        console.error('Error getting price statistics:', error);
        res.status(500).json({
            success: false,
            message: 'Failed to get price statistics'
        });
    }
});

// Property recommendations for chatbot
router.post('/recommendations', async (req, res) => {
    try {
        const preferences = req.body;
        const db = require('../config/db');
        
        // Use the existing search logic with some modifications for recommendations
        let query = `
            SELECT p.*, u.name as owner_name, u.phone as owner_phone,
            (SELECT i.image_url FROM property_images i WHERE i.property_id = p.id AND i.is_cover = true LIMIT 1) as cover_image
            FROM properties p 
            JOIN users u ON p.owner_id = u.id 
            WHERE p.status = 'vacant'
        `;
        const queryParams = [];
        
        // Apply preferences as filters
        if (preferences.location) {
            query += ' AND (p.thana LIKE ? OR p.neighborhood LIKE ? OR p.full_address LIKE ?)';
            const locationPattern = `%${preferences.location}%`;
            queryParams.push(locationPattern, locationPattern, locationPattern);
        }
        
        if (preferences.property_type) {
            query += ' AND p.property_type = ?';
            queryParams.push(preferences.property_type);
        }
        
        if (preferences.bedrooms) {
            query += ' AND p.bedrooms = ?';
            queryParams.push(preferences.bedrooms);
        }
        
        if (preferences.max_price) {
            query += ' AND p.monthly_rent <= ?';
            queryParams.push(preferences.max_price);
        }
        
        // Order by recent and popular properties
        query += ' ORDER BY p.created_at DESC, p.monthly_rent ASC LIMIT 10';
        
        const [properties] = await db.query(query, queryParams);
        
        res.json({
            success: true,
            properties: properties,
            preferences: preferences
        });
        
    } catch (error) {
        console.error('Error getting recommendations:', error);
        res.status(500).json({
            success: false,
            message: 'Failed to get property recommendations'
        });
    }
});

// Protected routes for property owners
router.post('/', protect, propertyController.createProperty);
router.put('/:id', protect, propertyController.updateProperty);
router.delete('/:id', protect, propertyController.deleteProperty);
router.post('/:id/images', protect, (req, res) => {
    upload(req, res, (err) => {
        if (err) {
            return res.status(400).json({ message: err });
        }
        propertyController.uploadImages(req, res);
    });
});

module.exports = router;
