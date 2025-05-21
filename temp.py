import pandas as pd

df = pd.read_csv("products/products.csv")
df['Category'] = "Mobile"
df["Description"] = "Very Good Mobile"
print(df.head())
print(df.info())

# Using correct column names from your data
print(df[['Model Name', 'Brand']].drop_duplicates())

# Create a sub-dataframe with unique brand, model name, and specs
unique_products = df.drop_duplicates(subset=['Brand', 'Model Name'])

# Select only relevant columns based on your data
specs_columns = ['Brand', 'Model Name', 'Specs (RAM/ROM/Display/etc)', 
                'Product Image URL', 'Description', 'Warranty', 'EMI Options'] 
unique_specs_df = unique_products[specs_columns]

print("\nUnique Products with Specs:")
unique_specs_df.dropna(inplace=True)
print(unique_specs_df)
unique_specs_df.to_csv("products/unique_products.csv", index=False)
# unique_products = unique_products['Brand', 'Model Name', 'Specs (RAM/ROM/Display/etc)','Description']
# print(unique_specs_df.info())