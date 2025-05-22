from selenium import webdriver
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json

driver = webdriver.Chrome()
driver.get("https://www.cashify.in/sell-old-mobile-phone/brands")

time.sleep(2)
brands_div = driver.find_element(
    By.XPATH, '//*[@id="__csh"]/main/div/div[3]/div[1]/div/div/div[3]/div/div'
)

brands = []
all_phones = {}

brand_div = brands_div.find_elements(By.TAG_NAME, "div")
for brand in brand_div:
    try:
        link = brand.find_element(By.TAG_NAME, "a")
        brand_name = brand.find_element(By.CSS_SELECTOR, "span.caption").text
        brand_url = link.get_attribute("href")
        brands.append({brand_name: brand_url})
        print(f"Found brand: {brand_name} - {brand_url}")
    except Exception as e:
        print(f"Error processing brand: {e}")

for brand_info in brands:
    for brand_name, brand_url in brand_info.items():
        print(f"Processing brand: {brand_name}")
        try:
            driver.get(brand_url)
            time.sleep(2)
            
            wait = WebDriverWait(driver, 10)
            phones_grid = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, 'div.grid'
            )))
            
            phone_divs = phones_grid.find_elements(By.CSS_SELECTOR, "div.basis-full a")
            
            brand_phones = []
            for phone_div in phone_divs:
                try:
                    phone_url = phone_div.get_attribute("href")
                    phone_title = phone_div.get_attribute("title").replace("Sell Old ", "")
                    
                    img_tag = phone_div.find_element(By.TAG_NAME, "img")
                    img_url = img_tag.get_attribute("src")
                    
                    phone_name = phone_div.find_element(By.CSS_SELECTOR, "span.caption").text
                    
                    brand_phones.append({
                        "name": phone_name,
                        "title": phone_title,
                        "url": phone_url,
                        "image": img_url
                    })
                    
                    print(f"  - Found phone: {phone_name}")
                except Exception as e:
                    print(f"  - Error processing phone: {e}")
            
            all_phones[brand_name] = brand_phones
            
        except Exception as e:
            print(f"Error processing brand {brand_name}: {e}")

with open("phone_data.json", "w", encoding="utf-8") as f:
    json.dump(all_phones, f, ensure_ascii=False, indent=2)

print(f"Scraping complete. Scraped {len(brands)} brands and saved data to phone_data.json")

driver.quit()