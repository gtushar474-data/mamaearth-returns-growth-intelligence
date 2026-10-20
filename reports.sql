USE mamaearth_db;

-- How much are we selling, and what is the average value per order?

SELECT
count(*) AS total_orders,
ROUND(SUM(o.quantity * p.price*(1- COALESCE(o.discount_pct ,0) / 100.0)),2) AS  revenue_after_discount,
ROUND(AVG(o.quantity * p.price*(1- COALESCE(o.discount_pct ,0) / 100.0)),2) AS average_order_value
from orders o 
join products p
on p.product_id = o.product_id ;

-- How many ratings are present, and how many are missing?

SELECT
count(*) AS total_order_rows,
count(rating) as available_ratings,
count(*) - count(rating) AS missing_ratings
from orders;

-- Which registered customers have no matching order?

SELECT
c.customer_id,
c.customer_name
from customers c 
left join orders o 
on c.customer_id = o.customer_id
WHERE o.order_id IS NULL;

-- Which cities have a return rate greater than 20%?

SELECT
c.city,
count(*)  AS total_orders,
SUM(CASE WHEN o.is_returned = 1 THEN 1 ELSE 0 END) AS returned_orders,
ROUND(100 * SUM(CASE WHEN o.is_returned = 1 THEN 1 ELSE 0 END) / count(*),2) AS return_rate_pct
FROM customers c 
join orders o 
on c.customer_id = o.customer_id
GROUP BY c.city
HAVING 
ROUND(100 * SUM(CASE WHEN o.is_returned = 1 THEN 1 ELSE 0 END) / count(*),2) > 15
ORDER BY return_rate_pct DESC;

-- Which customers have the highest calculated order value after discounts?

SELECT
c.customer_id,
c.customer_name,
ROUND(SUM(o.quantity * p.price * (1-COALESCE(o.discount_pct,0)/100.0)),2) AS total_spend
from customers c 
join orders o 
on c.customer_id = o.customer_id
join products p 
on p.product_id = o.product_id
GROUP BY c.customer_id, c.customer_name
ORDER BY total_spend DESC
LIMIT 5;

-- Which product categories contribute the most order value?

SELECT	
p.category,
ROUND(SUM(o.quantity * p.price * (1-COALESCE(o.discount_pct,0)/100.0)),2) AS revenue_after_discount
from orders o 
join products p 
on p.product_id = o.product_id
GROUP BY p.category
ORDER BY revenue_after_discount DESC
LIMIT 5;

-- How much revenue do orders generate?

SELECT
    COUNT(*) AS total_orders,

    ROUND(SUM(p.price * o.quantity), 2)
        AS revenue_before_discount,

    ROUND(SUM(
        p.price * o.quantity *
        (1 - COALESCE(o.discount_pct, 0) / 100.0)
    ), 2) AS revenue_after_discount,

    ROUND(SUM(
        CASE
            WHEN o.is_returned = 0 THEN
                p.price * o.quantity *
                (1 - COALESCE(o.discount_pct, 0) / 100.0)
            ELSE 0
        END
    ), 2) AS value_excluding_returns

FROM orders o
JOIN products p
    ON o.product_id = p.product_id;
    
-- How does the revenue picture change after discounts, returns, and data-quality issues?

SELECT
    COUNT(*) AS total_orders,

    ROUND(SUM(p.price * o.quantity), 2)
        AS gross_order_value,
ROUND(SUM(p.price * o.quantity * 1- COALESCE(o.discount_pct , 0)/ 100.0) , 2) AS value_after_discount,
ROUND(SUM(
         CASE WHEN o.is_returned = 1 THEN 
             p.price * o.quantity * 
             (1- COALESCE(o.discount_pct , 0)/ 100.0) 
             ELSE 0 END 
             ),2) AS returned_order_value,
 ROUND(SUM(
        CASE WHEN o.is_returned = 0 THEN
            p.price * o.quantity *
            (1 - COALESCE(o.discount_pct, 0) / 100.0)
        ELSE 0 END
    ), 2) AS value_excluding_returns,
    SUM(CASE WHEN o.discount_pct IS NULL
             THEN 1 ELSE 0 END) AS missing_discount_count,

    SUM(CASE WHEN o.rating IS NULL
             THEN 1 ELSE 0 END) AS missing_rating_count

FROM orders o
JOIN products p
    ON o.product_id = p.product_id;
    
-- Which cities and payment methods have higher return rates?

SELECT
c.city,
o.payment_method,
count(*) AS  total_orders,
SUM(CASE WHEN o.is_returned = 1 THEN 1 ELSE 0 END) AS  returned_orders,
ROUND(100 * SUM(CASE WHEN o.is_returned = 1 THEN 1 ELSE 0 END) / COUNT(*),2)AS return_rate_pct
FROM orders o 
JOIN customers c 
on o.customer_id = c.customer_id
group by 
c.city,
o.payment_method
ORDER BY return_rate_pct DESC;

SELECT
    UPPER(TRIM(payment_method)) AS payment_method_clean,
    COUNT(*) AS total_orders,

    SUM(CASE
        WHEN is_returned = 1 THEN 1
        ELSE 0
    END) AS returned_orders,

    ROUND(
        100.0 * SUM(CASE
            WHEN is_returned = 1 THEN 1
            ELSE 0
        END) / COUNT(*),
        2
    ) AS return_rate_pct

FROM orders
GROUP BY UPPER(TRIM(payment_method))
ORDER BY return_rate_pct DESC;

-- Are certain customer segments associated with more returns?

SELECT
c.city_tier,
COUNT(*)  AS total_orders,
SUM(CASE WHEN o.is_returned = 1 THEN 1 ELSE 0 END) AS returned_orders,
ROUND(100 * SUM(CASE WHEN o.is_returned = 1 THEN 1 ELSE 0 END) / COUNT(*) ,2)  AS return_rate_pct
FROM customers c 
JOIN orders o 
on c.customer_id = o.customer_id
GROUP BY 
c.city_tier
ORDER BY return_rate_pct DESC;

-- Return rate by customer acquisition source

SELECT
c.acquisition_source,
count(*) AS total_orders,
SUM(CASE WHEN o.is_returned = 1 THEN 1 ELSE 0 END) AS returned_orders,
ROUND(100 * SUM(CASE WHEN o.is_returned = 1 THEN 1 ELSE 0 END) / COUNT(*) ,2)  AS return_rate_pct
FROM orders o 
JOIN customers c 
on c.customer_id = o.customer_id
GROUP BY 
c.acquisition_source
ORDER BY return_rate_pct DESC;

-- What business actions should the operations and finance teams consider?

SELECT
    p.category,
    p.product_name,
    COUNT(*) AS total_orders,

    SUM(CASE
        WHEN o.is_returned = 1 THEN 1
        ELSE 0
    END) AS returned_orders,

    ROUND(
        100.0 * SUM(CASE
            WHEN o.is_returned = 1 THEN 1
            ELSE 0
        END) / COUNT(*),
        2
    ) AS return_rate_pct,

    ROUND(SUM(
        p.price * o.quantity *
        (1 - COALESCE(o.discount_pct, 0) / 100.0)
    ), 2) AS discounted_order_value

FROM orders o
JOIN products p
    ON o.product_id = p.product_id

GROUP BY p.category, p.product_name
HAVING COUNT(*) >= 3
ORDER BY return_rate_pct DESC;


SELECT
c.city,
 UPPER(TRIM(o.payment_method)) AS payment_method,
count(payment_method) AS total_count
from orders o 
JOIN customers c 
On c.customer_id = o.customer_id
group by c.city,
 UPPER(TRIM(o.payment_method));