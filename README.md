# Ecommerce_FL_Backend

Collections = 
1. products -
    - productId
    - variants
    - images
    - category
    - brand
    - price
    - discount
    - stock
    - description
    - specs (dict)

2. users -
    - userID
    - orders (orderId)
    - wishlists 
    - carts
    - email
    - phone number
    - address
    - firstName
    - lastName
    - type (admin, user, delivery.)

3. orders -
    - orderId
    - userId
    - productId
    - totalPrice
    - status
    - shippingAddress
    - paymentMethod
    - orderDate
    - deliveryDate
    - trackingNumber

4. reviews - 
    - reviewId
    - userId
    - productId
    - rating
    - comment
    - reviewDate

5. banners
    - bannerId
    - link
    - position