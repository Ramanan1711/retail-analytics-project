IF NOT EXISTS (
    SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.df_orders') AND type in (N'U')
)
BEGIN
    CREATE TABLE dbo.df_orders
    (
        order_id INT PRIMARY KEY,
        order_date DATE,
        ship_mode VARCHAR(30),
        segment VARCHAR(30),
        country VARCHAR(50),
        city VARCHAR(50),
        state VARCHAR(50),
        postal_code VARCHAR(20),
        region VARCHAR(20),
        category VARCHAR(30),
        sub_category VARCHAR(30),
        product_id VARCHAR(50),
        quantity INT,
        discount FLOAT,
        sale_price FLOAT,
        profit FLOAT
    );
END;
GO
