#! python3
import asyncio, queue, bs4
from playwright.async_api import async_playwright, Playwright
import re
import tracemalloc, time, argparse
tracemalloc.start()

class Video:
    def __init__(self, name, season = None, episode_number = None, link = None, m3u8 = None, isMovie = False, isEpisode = False):
        self.name = name
        self.season = season
        self.episode_number = episode_number
        self.link = link
        self.m3u8 = m3u8
        self.isMovie = isMovie
        self.isEpisode = isEpisode

    def PrintEpisode(self):
        print(f"{self.name}, {self.season}, {self.episode_number}, {self.m3u8}")

    def PrintMovie(self):
         print(f"{self.name} {self.m3u8}")

all_videos = []
file_name = ''


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


# Sort lines when finished
def sort_lines(file_name):
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


# Sort episodes URLS for scrapping
def sort_urls(html_content):
    try:
        global file_name
        soup = bs4.BeautifulSoup(html_content, 'html.parser')
        show_name = soup.find('h1', class_='name').text
        print(f'Serie: {show_name}')
        soupCount = soup.select('#episodes ul.episodes')
        print(f'Scrapping {len(soupCount)} seasons')

        if soupCount:
            for season in soupCount:
                season_number = season['data-season']  # Current season number
                episodes = season.find_all('li')

                # Get links for current episodes
                for episode in episodes:
                    episode_number = episode.find('span', class_='num').text.strip(':')
                    episode_link = episode.find('a')['href']
                    # print(f"Season: {season_number} Episode Link: {episode_link}")
                    all_videos.append(Video('-'.join(show_name.split()), 'Season ' + str(season_number), episode_number,
                                            "https://fbox.to" + episode_link, isEpisode=True))
        
        # Remove special characters from show_name using regex
        show_name = re.sub(r'[^\w\s]', '', show_name)
        file_name = '-'.join(show_name.split()) + '.txt'
        return file_name
    except Exception as e:
        print(f"sort_urls failed: {e}")

m3u8_count = 0
async def track_request(request, video):
    global m3u8_count
    
    if request.url.endswith(".m3u8"):
        m3u8_count += 1

        if m3u8_count == 2:
            video.m3u8 = request.url  # Assign m3u8 URL
            m3u8_count = 0

# Waiting for m3u8...
async def wait_for_request(page, video):
    global file_name
    while video.m3u8 == None:
        await asyncio.sleep(1)
    # Export Data to file
    if not video.isMovie:
        extracted_data = [video.name, video.season, video.episode_number, video.m3u8]
    else:
        extracted_data = [video.name, video.m3u8]
    print(extracted_data)
    print(f'Writing data to file: {file_name}')
    with open(file_name, mode='a', newline='') as myfile:
        myfile.write('   '.join(extracted_data))
        myfile.write('\n')
        # sort_episodes(file_name)
    sort_lines(file_name) if video.isEpisode else None
    # await page.close()
    return True


# Incase data already exists, skip it - Returns True if exists
async def check_if_exist(file_name, video):

    try:
        with open(file_name, 'r') as myFile:
            lines = myFile.readlines()
            for line in lines:
                data = line.split()
                # Skipping that episode
                if video.isEpisode:
                    if video.name == data[0] and video.season == f"{data[1]} {data[2]}" and video.episode_number == f"{data[3]} {data[4]}":
                        return True
                elif video.isMovie:
                    if video.name == data[0]:
                        return True
        return False
    except Exception as e:
        return False
    
# Simulated check function for video existence in the queue
async def check_if_exists_in_queue(video, video_queue):
    queue_copy = asyncio.Queue()

    while not video_queue.empty():
        item = await video_queue.get()
        queue_copy.put_nowait(item)
        if item == video:
            while not queue_copy.empty():
                video_queue.put_nowait(queue_copy.get_nowait())
            return True

    while not queue_copy.empty():
        video_queue.put_nowait(queue_copy.get_nowait())
    return False

# # Failed queues
failed_video_queue = asyncio.Queue()
async def handle_failed_videos(file_name, video, video_queue):
    global failed_video_queue
    
    is_on_file = await check_if_exist(file_name, video)
    is_on_queue = await check_if_exists_in_queue(video, video_queue)

    if not is_on_file and not is_on_queue:
        print('Handle_failed_video - Adding failed video to queue')
        await video_queue.put(video)

# Automation
async def automation(page, video, video_queue = None, file_name = None, context = None):
    link = video.link
        
        # Track m3u8 request
    page.on("request", lambda request: track_request(request, video))
    
    try:
        await page.goto(link)
        pause_click = False
        requestResult = asyncio.create_task(wait_for_request(page, video))   

        for i in range(10):
            if not video.m3u8 and not requestResult.done():
                await asyncio.sleep(1)

            pauseButton = await page.query_selector('.jw-media.jw-reset')
            # time.sleep(160)
            # await page.click('body')
            await page.mouse.click(1, 100)
            await page.wait_for_timeout(500)
            await page.mouse.click(1, 500)

            # await page.wait_for_timeout(1000)

            playButton = await page.query_selector('.btn-watchnow') or await page.query_selector('.bi-play-circle-fill')
            if playButton:
                await playButton.click()
            
            if video.m3u8 != None:
                break
            
            if pauseButton and not pause_click:
                await pauseButton.click()
                break
            
            
        if video.m3u8 == None:
        # await page.wait_for_timeout(3000)
            await handle_failed_videos(file_name, video, video_queue)

        await page.close()
        return True
    except Exception as e:
        try:
            await page.close()
        except:
            pass
        print(f'Automation failed at {video.season} {video.episode_number}')
        await handle_failed_videos(file_name, video, video_queue)
        print(e)
        return False


# Check if a movie or TV serie
async def isMovie(context, link):
    global file_name
    page = await context.new_page()
    await page.goto(link)
    html_content =  await page.content()

    soup = bs4.BeautifulSoup(html_content, 'html.parser')
    soupElem = soup.find(id='episodes')['class']

    try:
        if soupElem[0] == 'movie':
            file_name = 'MyMovies.txt'
            movie_name = soup.find('h1', class_='name').text
            movie_name = re.sub(r'[^\w\s]', '', movie_name)
            movie_name = '-'.join(movie_name.split())

            new_video = Video(movie_name,link=link, isMovie=True)
            if not await check_if_exist(file_name, new_video):
                await automation(page, new_video)
            # await page.wait_for_timeout(30000)
            return file_name, page

        else:
            sort_urls(html_content)
            await page.wait_for_timeout(3000)
            await page.close()
            return file_name, None
    except Exception as e:
        print(f'isMovie failed: {e}')

# tv
# link = 'https://fbox.to/tv/bookie-k9k94'
# link = 'https://fbox.to/tv/squid-game-the-challenge-r3l5y'
# link = 'https://fbox.to/tv/doctor-who-nkw7j/1-1'
# link = 'https://fbox.to/tv/bering-sea-gold-j2572/1-1'
# movie
# link = 'https://fbox.to/movie/good-burger-2-m320v'



tasks = []
async def process_episodes(context, video_queue, file_name):
    global all_videos
    global failed_video_queue
    while not video_queue.empty():
        video = await video_queue.get()
        result = await automation(await context.new_page(), video, video_queue, file_name)
    all_vidoes = []
    remove_duplicate_lines(file_name)

        
async def main(link, numThreads = 1):
    async with async_playwright() as playwright:
        global all_videos
        browser = await playwright.firefox.launch()
        context = await browser.new_context()
        video_queue = asyncio.Queue()
        file_name, moviePage = await isMovie(context, link)
        try:
            if moviePage:
                await moviePage.wait_for_timeout(5000)
            else:
                for video in all_videos:
                    if not await check_if_exist(file_name, video):
                        await video_queue.put(video)

                # Create tasks
                tasks = [process_episodes(context, video_queue, file_name) for _ in range(numThreads)]

                await asyncio.gather(*tasks)
                all_vidoes = []

                remove_duplicate_lines(file_name)
                await context.close()
                print("Finished...")
                
        except Exception as e:
            print(e)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process links.')
    parser.add_argument('-f', '--file', help='Path to file containing links')

    args = parser.parse_args()

    if args.file:
        with open(args.file, 'r') as file:
            links = file.readlines()
            numThreads = int(input("Threads: "))
            for link in links:
                file_name = None
                all_videos = []
                asyncio.run(main(link.strip(), numThreads))  # Strip newline characters and process each link
    else:

        try:
            link = input("Enter link: ")
            numThreads = int(input("Threads: "))
        except Exception as e:
            print(e)
            exit(1)

        asyncio.run(main(link, numThreads))
