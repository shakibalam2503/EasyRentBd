
const db = require('../config/db');

exports.getOwnerDashboard = async (req, res) => {
    const owner_id = req.user.id;

    try {
        // Total Properties
        const [totalResult] = await db.query('SELECT COUNT(*) as totalProperties FROM properties WHERE owner_id = ?', [owner_id]);

        // Monthly Revenue (from occupied properties)
        const [revenueResult] = await db.query('SELECT SUM(monthly_rent) as monthlyRevenue FROM properties WHERE owner_id = ? AND status = \'occupied\'', [owner_id]);

        // Occupied Count
        const [occupiedResult] = await db.query('SELECT COUNT(*) as occupiedCount FROM properties WHERE owner_id = ? AND status = \'occupied\'', [owner_id]);

        // Vacant Count
        const [vacantResult] = await db.query('SELECT COUNT(*) as vacantCount FROM properties WHERE owner_id = ? AND status = \'vacant\'', [owner_id]);

        // Active Inquiries Count
        const [inquiriesResult] = await db.query('SELECT COUNT(*) as activeInquiries FROM inquiries WHERE property_id IN (SELECT id FROM properties WHERE owner_id = ?)', [owner_id]);

        res.status(200).json({
            totalProperties: totalResult[0].totalProperties || 0,
            monthlyRevenue: revenueResult[0].monthlyRevenue || 0,
            occupiedCount: occupiedResult[0].occupiedCount || 0,
            vacantCount: vacantResult[0].vacantCount || 0,
            activeInquiries: inquiriesResult[0].activeInquiries || 0,
        });

    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
};

exports.getTenantDashboard = async (req, res) => {
    const tenantId = req.user.id;

    try {
        // Quick Stats
        const [propertyStats] = await db.query(`
            SELECT 
                (SELECT COUNT(*) FROM properties WHERE status = 'vacant') as availableProperties,
                (SELECT COUNT(DISTINCT neighborhood) FROM properties WHERE status = 'vacant') as areasCovered;
        `);

        const [searchStats] = await db.query('SELECT COUNT(*) as savedSearches FROM search_history WHERE user_id = ?', [tenantId]);

        // For recommendations, we can get recently added properties for now
        const [recommendations] = await db.query('SELECT * FROM properties WHERE status = \'vacant\' ORDER BY created_at DESC LIMIT 4');

        // Recent activity can be derived from search_history for this user
        const [recentActivity] = await db.query('SELECT * FROM search_history WHERE user_id = ? ORDER BY created_at DESC LIMIT 3', [tenantId]);

        res.status(200).json({
            stats: {
                availableProperties: propertyStats[0].availableProperties || 0,
                areasCovered: propertyStats[0].areasCovered || 0,
                savedSearches: searchStats[0].savedSearches || 0,
                recommendations: recommendations.length || 0
            },
            recommendations: recommendations,
            recentActivity: recentActivity
        });

    } catch (error) {
        console.error('Error fetching tenant dashboard data:', error);
        res.status(500).json({ message: 'Server error' });
    }
};
