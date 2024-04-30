import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

scraped_pages = set()  # Global set for all instances
file_name = "scraped_links.txt"

# Remove duplicates
def remove_duplicate_lines(file_name):
    # Read lines from the file
    with open(file_name, 'r') as file:
        lines = file.readlines()

    # Remove duplicates while preserving order
    unique_lines = list(dict.fromkeys(lines))

    # Write unique lines back to the file
    with open(file_name, 'w') as file:
        file.writelines(unique_lines)

async def scrape_movies(instance_number, start_page, url):
    start_url = f"{url}&page={start_page}"

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()

        while True:
            print(f"Instance {instance_number} is processing page {start_page}")
            if start_page not in scraped_pages:
                scraped_pages.add(start_page)
                print(scraped_pages)

                await page.goto(start_url)
                html_content = await page.content()
                soup = BeautifulSoup(html_content, "html.parser")

                movie_links = []
                movie_items = soup.find_all("div", class_="item")
                # Check if the list is empty
                if not movie_items:
                    print(f"No movie items found on page {start_page}")
                    break
                for item in movie_items:
                    link = item.find("a", class_="tooltipstered").get("href")
                    movie_links.append(link)
                    print(link)
                    # Save the link to a file
                    with open(file_name, "a") as f:
                        f.write("https://fbox.to" + link + "\n")

            else:
                # print(f"Instance {instance_number} found that page {start_page} has already been scraped")
                if scraped_pages:  # Check if the set is not empty
                    start_page = max(scraped_pages) + 1
                    start_url = f"{url}&page={start_page}"
                continue

        print(f"Instance {instance_number} is about to close the browser")
        await browser.close()

async def main():
    tasks = []
    num_instances = int(input("Threads: "))  # Adjust the number of instances as needed
    url = input("Enter a URL: ")
    # url = "https://fbox.to/filter?keyword=&type%5B%5D=tv&genre%5B%5D=215&genre%5B%5D=248&country%5B%5D=181851&country%5B%5D=181861&country%5B%5D=181847&country%5B%5D=8&country%5B%5D=2&year%5B%5D=2024&quality%5B%5D=HD&quality%5B%5D=HDRip&sort=recently_updated"
    for i in range(1, num_instances + 1):
        tasks.append(scrape_movies(i, i, url))

    await asyncio.gather(*tasks)
    remove_duplicate_lines(file_name)

# Run the asynchronous main function
asyncio.run(main())
