# Ecommerce_FL_Backend

Collections = 
1. products -
    - productId (string)
    - variants (dict)
    - images (list)
    - category (string)
    - brand (string)
    - price (float)
    - discount (float)
    - stock (int)
    - description (string)
    - specs (dict)

2. users -
    - userID (string)
    - orders (orderId)
    - wishlists (list)
    - carts (list)
    - email (string)
    - phone number (string)
    - address (string)
    - pincode (int)
    - firstName (string)
    - lastName (string)
    - type (admin, user, delivery.)

3. orders -
    - orderId (string)
    - userId (string)
    - productId (string)
    - totalPrice (float)
    - status (string)
    - shippingAddress (string)
    - paymentMethod (string)
    - orderDate (Date)
    - deliveryDate (Date)
    - trackingNumber (int)

4. reviews - 
    - reviewId (string)
    - userId (string)
    - productId (string)
    - rating (int)
    - comment (string)
    - reviewDate (Date)

5. banners
    - bannerId (string)
    - link (string)
    - position (int)