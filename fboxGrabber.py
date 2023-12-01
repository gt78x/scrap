import asyncio, bs4, traceback, queue
from playwright.async_api import async_playwright, Playwright
import time

class Episode:
    def __init__(self,show_name,  season,episode_number, episode_link,m3u8 = 'unknown'):
        self.show_name = show_name
        self.season = season
        self.episode_number = episode_number
        self.episode_link = episode_link
        self.m3u8 = m3u8

    def PrintEpisode(self):
        print(f"{self.show_name}, {self.season}, {self.episode_number}, {self.m3u8}")

all_episodes = []
file_name = ''

# Sort lines when finished
def sort_episodes(file_name):
    try:
        with open(file_name, 'r') as myfile:
            lines = myfile.readlines()

        # Filter out lines that don't contain 'Season' pattern
        valid_lines = [line for line in lines if 'Season' in line]

        sorted_lines = sorted(valid_lines, key=lambda line: (
            int(line.split('Season ')[1].split(' ')[0]),
            int(line.split('Episode ')[1].split(' ')[0])
        ))

        with open(file_name, 'w') as myfile:
            myfile.writelines(sorted_lines)
    except Exception as e:
        print(f"Error occurred while sorting episodes: {e}")

# Sort episodes URLS before scrapping
async def getUrls(playwright: Playwright, link):
    global file_name
    firefox = playwright.firefox
    browser = await firefox.launch()
    page = await browser.new_page()
    await page.goto(link)
    html_content = await page.content()
    await page.close()

    SOUP = bs4.BeautifulSoup(html_content, 'html.parser')
    show_name = SOUP.find('h1', class_='name').text
    try:
        print(f'Serie: {show_name}')
        soupCount = SOUP.select('#episodes ul.episodes')
        print(f'Scrapping {len(soupCount)} seasons')

        if soupCount:
            for season in soupCount:
                season_number = season['data-season'] # Current season number
                episodes = season.find_all('li')

                # Get links for current episodes
                for episode in episodes:
                    episode_number = episode.find('span', class_='num').text.strip(':')
                    episode_link = episode.find('a')['href']
                    # print(f"Season: {season_number} Episode Link: {episode_link}")
                    all_episodes.append(Episode('-'.join(show_name.split()),'Season ' + str(season_number),episode_number , "https://fbox.to" + episode_link))
        file_name = '-'.join(show_name.split())  + '.txt'
        return file_name
    
    except AttributeError: # Movie

        try:
            print(f'Movie: {show_name}')

        except:
            pass


# Incase data already exists, skip it
def check_if_exist(file_name, episode):
    try:
        with open(file_name, 'r') as myFile:
            lines = myFile.readlines()
            for line in lines:
                data = line.split()
                # Skipping that episode
                if episode.show_name == data[0] and episode.season == f"{data[1]} {data[2]}" and episode.episode_number == f"{data[3]} {data[4]}":
                    # print(f"Skipping")
                    return True
        return False
    except Exception as e:
        return False
    
# Automation
async def run(page, episode, Movie = False):

    my_request = []
    m3u8_count = 0
    link = episode.episode_link
    # found_request = asyncio.Event()
    # file_name = '-'.join(episode.show_name.split())  + '.txt'
    
    async def track_request(request):
        nonlocal m3u8_count
        if request.url.endswith(".m3u8"):
            m3u8_count += 1
            if m3u8_count == 2:
                episode.m3u8 = request.url  # Assign m3u8 URL
                # print('Assinging m3u8 to object')

    # Waiting for m3u8...
    async def wait_for_request():
        while episode.m3u8 == 'unknown':
            await asyncio.sleep(1)
        await page.close() # Close browser

        # Export Data to file
        extracted_data = [episode.show_name, episode.season, episode.episode_number, episode.m3u8]
        print(extracted_data)
        with open(file_name, mode='a', newline='') as myfile:
            myfile.write('   '.join(extracted_data))
            myfile.write('\n')
            print('Writing data to file')
            sort_episodes(file_name)

    # Automation
    try:
        await page.goto(link)
        await page.mouse.click(400,400) # Ad click
        await page.wait_for_timeout(1000)
        await page.mouse.click(500,500) # Ad click
        await page.wait_for_timeout(1000)

        playButton = await page.query_selector('.btn-watchnow') or await page.query_selector('.bi-play-circle-fill')
        if playButton:
            await playButton.click()
        else:
            await page.mouse.click(500,500)  # Ad click
            await page.wait_for_timeout(2000)
            playButton = await page.query_selector('.bi-play-circle-fill')
            if playButton:
                await playButton.click()

        pauseButton = await page.query_selector('.jw-video.jw-reset')
        if pauseButton:
            await pauseButton.click()

        page.on("request", track_request)
        asyncio.create_task(wait_for_request())

    except Exception as e:
        await page.close()
        print(e)

# link = "https://fbox.to/tv/masterchef-usa-179jp/1-1"
# link = 'https://fbox.to/tv/the-couple-next-door-4wj1k/1-1'
try:
    link = input('fbox.to URL: ')
    numThreads = int(input('Threads: '))
except Exception as exc:
    print(exc)

tasks = []
async def process_episodes(context, episode_queue):
    while not episode_queue.empty():
        episode = await episode_queue.get()
        await run(await context.new_page(), episode)
    await asyncio.sleep(15)
        
# Main function to orchestrate the process of fetching and processing episodes
async def main():
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        context = await browser.new_context()
        episode_queue = asyncio.Queue()
        file_name = await getUrls(playwright, link) # Get and sort URLS

        for episode in all_episodes:
            if not check_if_exist(file_name, episode):
                await episode_queue.put(episode)

        # Assign Tasks to process episodes concurrently
        tasks = [process_episodes(context, episode_queue) for _ in range(numThreads)]
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            print(e)
        finally:
            await context.close()
            print('Finished..')
            sort_episodes(file_name)


if __name__ == "__main__":
    asyncio.run(main())



