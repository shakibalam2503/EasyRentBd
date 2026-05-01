
const db = require('../config/db');
const locationService = require('../services/locationService');

// Create a new property
exports.createProperty = async (req, res) => {
    const owner_id = req.user.id;
    const {
        propertyTitle, propertyDescription, propertyType, listingType, bedrooms, 
        bathrooms, squareFeet, monthlyRent, securityDeposit, availableFrom, 
        petsAllowed, furnished, fullAddress, neighborhood, city, amenities,
        latitude, longitude
    } = req.body;

    try {
        let locationData = null;
        let finalLatitude = latitude;
        let finalLongitude = longitude;
        let thana = null;
        let district = null;
        let postalCode = null;
        let googlePlaceId = null;

        // If coordinates are provided, use reverse geocoding to get address details
        if (latitude && longitude) {
            const reverseResult = await locationService.reverseGeocode(parseFloat(latitude), parseFloat(longitude));
            if (reverseResult.success) {
                locationData = reverseResult.data;
                thana = locationData.thana || locationData.neighborhood;
                district = locationData.district || locationData.city;
                postalCode = locationData.postal_code;
                googlePlaceId = locationData.place_id;
                
                console.log('🏠 Location extracted from coordinates:', {
                    neighborhood: locationData.neighborhood,
                    thana: locationData.thana,
                    district: locationData.district,
                    userFriendlyAddress: locationData.address
                });
            }
        } 
        // If no coordinates but address is provided, geocode it
        else if (fullAddress) {
            const geocodeResult = await locationService.geocodeAddress(fullAddress);
            if (geocodeResult.success) {
                locationData = geocodeResult.data;
                finalLatitude = locationData.latitude;
                finalLongitude = locationData.longitude;
                thana = locationData.thana || locationData.neighborhood;
                district = locationData.district || locationData.city;
                postalCode = locationData.postal_code;
                googlePlaceId = locationData.place_id;
                
                console.log('🏠 Geocoded from address:', {
                    neighborhood: locationData.neighborhood,
                    thana: locationData.thana,
                    district: locationData.district
                });
            }
        }

        const [result] = await db.query(
            `INSERT INTO properties (owner_id, title, description, property_type, listing_type, bedrooms, bathrooms, square_feet, monthly_rent, security_deposit, available_from, pets_allowed, furnished, full_address, neighborhood, city, thana, district, postal_code, latitude, longitude, google_place_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')`,
            [owner_id, propertyTitle, propertyDescription, propertyType, listingType, bedrooms, bathrooms, squareFeet, monthlyRent, securityDeposit, availableFrom, petsAllowed, furnished, fullAddress, neighborhood, city, thana, district, postalCode, finalLatitude, finalLongitude, googlePlaceId]
        );

        const propertyId = result.insertId;

        // Handle amenities
        if (amenities && amenities.length > 0) {
            // First, make sure all provided amenities exist in the database
            const insertPromises = amenities.map(amenity => 
                db.query('INSERT IGNORE INTO amenities (name) VALUES (?)', [amenity])
            );
            await Promise.all(insertPromises);

            // The frontend sends amenity names/keys. We need to get their actual IDs from the database.
            const [amenityRows] = await db.query('SELECT id, name FROM amenities WHERE name IN (?)', [amenities]);
            
            if (amenityRows.length > 0) {
                const amenityValues = amenityRows.map(amenity => [propertyId, amenity.id]);
                await db.query('INSERT IGNORE INTO property_amenities (property_id, amenity_id) VALUES ?', [amenityValues]);
            }
        }

        res.status(201).json({ 
            message: 'Property created successfully', 
            propertyId,
            locationData: locationData
        });

    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
};

// Get all properties for a specific owner
exports.getOwnerProperties = async (req, res) => {
    const owner_id = req.user.id;
    try {
        let query = 'SELECT p.*, u.name as owner_name, (SELECT i.image_url FROM property_images i WHERE i.property_id = p.id AND i.is_cover = true LIMIT 1) as cover_image FROM properties p JOIN users u ON p.owner_id = u.id WHERE p.owner_id = ?';
        const queryParams = [owner_id];

        const conditions = [];

        if (req.query.search) {
            conditions.push('(p.title LIKE ? OR p.full_address LIKE ?)');
            const searchPattern = `%${req.query.search}%`;
            queryParams.push(searchPattern, searchPattern);
        }

        if (req.query.status && req.query.status !== 'all') {
            conditions.push('p.status = ?');
            queryParams.push(req.query.status);
        }

        if (req.query.type && req.query.type !== 'all') {
            conditions.push('p.property_type = ?');
            queryParams.push(req.query.type);
        }

        if (conditions.length > 0) {
            query += ' AND ' + conditions.join(' AND ');
        }

        const [properties] = await db.query(query, queryParams);
        res.status(200).json(properties);

    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
};

// Get all properties with filtering
exports.getAllProperties = async (req, res) => {
    try {
        console.log('Request query:', req.query);
        console.log('User info:', req.user ? {id: req.user.id, role: req.user.role} : 'No user');
        
        // Simple logic: if owner=true, get owner's properties directly
        if (req.query.owner === 'true' && req.user && req.user.id) {
            let query = `SELECT p.*, u.name as owner_name, 
                        (SELECT i.image_url FROM property_images i WHERE i.property_id = p.id AND i.is_cover = true LIMIT 1) as cover_image 
                        FROM properties p 
                        JOIN users u ON p.owner_id = u.id 
                        WHERE p.owner_id = ?`;
            const queryParams = [req.user.id];
            
            // Add optional filters
            if (req.query.status && req.query.status !== 'all' && req.query.status !== '') {
                query += ' AND p.status = ?';
                queryParams.push(req.query.status);
            }
            
            if (req.query.type && req.query.type !== 'all') {
                query += ' AND p.property_type = ?';
                queryParams.push(req.query.type);
            }
            
            query += ' ORDER BY p.created_at DESC';
            
            console.log('Owner query:', query);
            console.log('Query params:', queryParams);
            
            const [properties] = await db.query(query, queryParams);
            console.log(`Found ${properties.length} properties for owner`);
            return res.status(200).json(properties);
        }

        // Regular public property search
        let query = 'SELECT p.*, u.name as owner_name, (SELECT i.image_url FROM property_images i WHERE i.property_id = p.id AND i.is_cover = true LIMIT 1) as cover_image FROM properties p JOIN users u ON p.owner_id = u.id';
        const queryParams = [];
        const conditions = ['p.status = ?'];
        queryParams.push('vacant');

        if (req.query.location) {
            conditions.push('(p.full_address LIKE ? OR p.city LIKE ? OR p.thana LIKE ? OR p.neighborhood LIKE ? OR p.district LIKE ? OR p.title LIKE ?)');
            const locationPattern = `%${req.query.location}%`;
            queryParams.push(locationPattern, locationPattern, locationPattern, locationPattern, locationPattern, locationPattern);
        }

        if (req.query.propertyType && req.query.propertyType !== 'all') {
            conditions.push('p.property_type = ?');
            queryParams.push(req.query.propertyType);
        }

        if (conditions.length > 0) {
            query += ' WHERE ' + conditions.join(' AND ');
        }

        console.log('Public query:', query);
        console.log('Query params:', queryParams);

        const [properties] = await db.query(query, queryParams);
        console.log(`Found ${properties.length} public properties`);
        res.status(200).json(properties);

    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
};

// Get a single property by ID
exports.getPropertyById = async (req, res) => {
    const { id } = req.params;
    try {
        const [properties] = await db.query('SELECT p.*, u.name as owner_name, u.email as owner_email FROM properties p JOIN users u ON p.owner_id = u.id WHERE p.id = ?', [id]);

        if (properties.length === 0) {
            return res.status(404).json({ message: 'Property not found' });
        }

        const property = properties[0];

        const [images] = await db.query('SELECT image_url, is_cover FROM property_images WHERE property_id = ?', [id]);
        const [amenities] = await db.query('SELECT a.name FROM amenities a JOIN property_amenities pa ON a.id = pa.amenity_id WHERE pa.property_id = ?', [id]);

        property.images = images;
        property.amenities = amenities.map(a => a.name);

        res.status(200).json(property);

    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
};

// Update a property
exports.updateProperty = async (req, res) => {
    const { id } = req.params;
    const owner_id = req.user.id;
    const {
        propertyTitle, propertyDescription, propertyType, listingType, bedrooms, 
        bathrooms, squareFeet, monthlyRent, securityDeposit, availableFrom, 
        petsAllowed, furnished, fullAddress, neighborhood, city, amenities, status,
        latitude, longitude
    } = req.body;

    try {
        // Verify the user owns the property
        const [properties] = await db.query('SELECT owner_id FROM properties WHERE id = ?', [id]);
        if (properties.length === 0 || properties[0].owner_id !== owner_id) {
            return res.status(403).json({ message: 'You are not authorized to update this property.' });
        }

        let locationData = null;
        let finalLatitude = latitude;
        let finalLongitude = longitude;
        let thana = null;
        let district = null;
        let postalCode = null;
        let googlePlaceId = null;

        // If coordinates are provided, use reverse geocoding to get address details
        if (latitude && longitude) {
            const reverseResult = await locationService.reverseGeocode(parseFloat(latitude), parseFloat(longitude));
            if (reverseResult.success) {
                locationData = reverseResult.data;
                thana = locationData.thana;
                district = locationData.district;
                postalCode = locationData.postal_code;
                googlePlaceId = locationData.place_id;
            }
        } 
        // If no coordinates but address is provided, geocode it
        else if (fullAddress) {
            const geocodeResult = await locationService.geocodeAddress(fullAddress);
            if (geocodeResult.success) {
                locationData = geocodeResult.data;
                finalLatitude = locationData.latitude;
                finalLongitude = locationData.longitude;
                thana = locationData.thana;
                district = locationData.district;
                postalCode = locationData.postal_code;
                googlePlaceId = locationData.place_id;
            }
        }

        // Update property details
        await db.query(
            `UPDATE properties SET 
                title = ?, description = ?, property_type = ?, listing_type = ?, bedrooms = ?, 
                bathrooms = ?, square_feet = ?, monthly_rent = ?, security_deposit = ?, available_from = ?, 
                pets_allowed = ?, furnished = ?, full_address = ?, neighborhood = ?, city = ?, 
                thana = ?, district = ?, postal_code = ?, latitude = ?, longitude = ?, google_place_id = ?, status = ?
            WHERE id = ?`,
            [propertyTitle, propertyDescription, propertyType, listingType, bedrooms, bathrooms, squareFeet, monthlyRent, securityDeposit, availableFrom, petsAllowed, furnished, fullAddress, neighborhood, city, thana, district, postalCode, finalLatitude, finalLongitude, googlePlaceId, status, id]
        );

        // Handle amenities update (simple version: delete all and re-add)
        await db.query('DELETE FROM property_amenities WHERE property_id = ?', [id]);
        if (amenities && amenities.length > 0) {
            const insertPromises = amenities.map(amenity => 
                db.query('INSERT IGNORE INTO amenities (name) VALUES (?)', [amenity])
            );
            await Promise.all(insertPromises);

            const [amenityRows] = await db.query('SELECT id, name FROM amenities WHERE name IN (?)', [amenities]);
            if (amenityRows.length > 0) {
                const amenityValues = amenityRows.map(amenity => [id, amenity.id]);
                await db.query('INSERT IGNORE INTO property_amenities (property_id, amenity_id) VALUES ?', [amenityValues]);
            }
        }

        res.status(200).json({ 
            message: `Property ${id} updated successfully`,
            locationData: locationData
        });

    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
};

// Delete a property
exports.deleteProperty = async (req, res) => {
    const { id } = req.params;
    const owner_id = req.user.id;
    try {
        // Verify the user owns the property before deleting
        const [properties] = await db.query('SELECT owner_id FROM properties WHERE id = ?', [id]);
        if (properties.length === 0 || properties[0].owner_id !== owner_id) {
            return res.status(403).json({ message: 'You are not authorized to delete this property.' });
        }

        await db.query('DELETE FROM properties WHERE id = ?', [id]);
        res.status(200).json({ message: 'Property deleted successfully' });

    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
};

// Upload images for a property
exports.uploadImages = async (req, res) => {
    const { id } = req.params; // property id
    const owner_id = req.user.id;

    try {
        // Verify the user owns the property
        const [properties] = await db.query('SELECT owner_id FROM properties WHERE id = ?', [id]);
        if (properties.length === 0 || properties[0].owner_id !== owner_id) {
            return res.status(403).json({ message: 'You are not authorized to upload images to this property.' });
        }

        if (req.files) {
            const images = req.files.map(file => {
                // We need to store a web-accessible URL
                const imageUrl = `/uploads/${file.filename}`;
                return [id, imageUrl];
            });

            if (images.length > 0) {
                await db.query('INSERT INTO property_images (property_id, image_url) VALUES ?', [images]);
            }

            // Set the first uploaded image as the cover image
            const [existingCover] = await db.query('SELECT id FROM property_images WHERE property_id = ? AND is_cover = true', [id]);
            if (existingCover.length === 0) {
                const [firstImage] = await db.query('SELECT id FROM property_images WHERE property_id = ? ORDER BY id ASC LIMIT 1', [id]);
                if(firstImage.length > 0){
                    await db.query('UPDATE property_images SET is_cover = true WHERE id = ?', [firstImage[0].id]);
                }
            }

            res.status(200).json({ message: 'Images uploaded successfully', files: req.files });
        } else {
            res.status(400).json({ message: 'No files were uploaded.' });
        }
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
};
