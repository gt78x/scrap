#! python3
import asyncio, queue, bs4
from playwright.async_api import async_playwright, Playwright
import re
import tracemalloc, time, argparse
tracemalloc.start()


class Video:
    def __init__(self, name, episode_number = None, link = None, m3u8 = None):
        self.name = name
        self.episode_number = episode_number
        self.link = link
        self.m3u8 = m3u8


    def PrintEpisode(self):
        print(f"{self.name}, {self.episode_number}, {self.m3u8}")

all_vidoes = []
# Sort URLS for scrapping
async def sort_urls(page, link):
    await page.goto(link)
    html_content = await page.content()
    await page.close()
    soup = bs4.BeautifulSoup(html_content, 'html.parser')
    nameElement = soup.select_one('.video-details > span.date')
    serie_name = nameElement.get_text(strip=True)
    clean_name = re.sub(r'[^\w\s]', '', serie_name) # Remove special characters from serie_name using regex
    print(serie_name)
    
    episodeElement = soup.select("ul.listing.items.lists > li.video-block")
    if episodeElement:
        print(f"Scrapping {len(episodeElement)} Episodes")
        for block in reversed(episodeElement):
            episode_link = block.find('a')['href'] # Get episode link
            # print(episode_link)

            # Get episode number
            episode_numberElement = block.find(class_='name')
            episode_number = ' '.join(episode_numberElement.get_text(strip=True).split()[-2:])
            # print(episode_number)

            all_vidoes.append(Video('-'.join(clean_name.split()), episode_number,'https://goone.pro' + episode_link))
    else:
        print('Failed to grab URLS')
        return False
    file_name = '-'.join(clean_name.split()) + '.txt'
    print(file_name)
    return file_name



# Sort lines when finished
def sort_lines(file_name):
    try:
        with open(file_name, 'r') as myfile:
            lines = myfile.readlines()

        # Filter out lines that include Episode init
        valid_lines = [line for line in lines if 'Episode' in line]

        sorted_lines = sorted(valid_lines, key=lambda line: (
            # Split on 'Episode' and space to get the episode number part
            line.split('Episode ')[1].split(' ')[0]
        ))

        # Convert to float if possible, else keep it as a string
        sorted_lines = sorted(
            valid_lines,
            key=lambda line: float(line.split('Episode ')[1].split(' ')[0]) if '.' 
            in line.split('Episode ')[1].split(' ')[0] else int(line.split('Episode ')[1].split(' ')[0])
        )

        with open(file_name, 'w') as myfile:
            myfile.writelines(sorted_lines)
    except Exception as e:
        print(f"Error occurred while sorting episodes: {e}")


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


# Incase data already exists, skip it - Returns True if exists
async def check_if_exist(file_name, video):

    try:
        with open(file_name, 'r') as myFile:
            lines = myFile.readlines()
            for line in lines:
                data = line.split()
                # Skipping that episode
                if video.name == data[0] and video.episode_number == f"{data[1]} {data[2]}":
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
async def handle_failed_videos(file_name, video, video_queue):
    
    is_on_file = await check_if_exist(file_name, video)
    is_on_queue = await check_if_exists_in_queue(video, video_queue)

    if not is_on_file and not is_on_queue:
        print(f'Handle_failed_video - Adding failed video to queue')
        await video_queue.put(video)



# Requests

m3u8_count = 0
async def track_request(request, video):
    global m3u8_count
    
    if request.url.endswith(".m3u8"):

        m3u8_count += 1

        if m3u8_count == 2:
            print(f'Assinging m3u8 to object - {video.name} {video.episode_number} ')
            video.m3u8 = request.url  # Assign m3u8 URL
            m3u8_count = 0


# Waiting for m3u8...
async def wait_for_request(file_name, page, video):
    while video.m3u8 == None:
        await asyncio.sleep(1)

    # Export Data to file
    extracted_data = [video.name, video.episode_number, video.m3u8]
    print(extracted_data)
    print(f'Opening file to write {file_name}')
    with open(file_name, mode='a', newline='') as myfile:
        myfile.write('   '.join(extracted_data))
        myfile.write('\n')
        print('Writing data to file')
        # sort_episodes(file_name)
    sort_lines(file_name)
    # await page.close()
    return True

# def hide_ads(page):
#     ads_to_hide = page.query_selector_all('.wrapp') 

#     for ad in ads_to_hide:
#         # Apply css, display: none;
#         page.evaluate('(element) => element.style.display = "none"', ad)


# async def bring_element_to_top(page):
#     # Replace '.jw-icon-display' with the correct CSS selector targeting the element you want to bring to the top
#     element_to_bring_to_top = await page.query_selector('.jw-icon-display')

#     if element_to_bring_to_top:
#         # Use page.evaluate() to modify the z-index of the element
#         await page.evaluate('(element) => { element.style.zIndex = "9999"; }', element_to_bring_to_top)



async def automation(file_name, page, video, video_queue = None , context = None):
    # print('Starting automation')
    link = video.link
    mute_clicked = False
        # Track m3u8 request
    page.on("request", lambda request: track_request(request, video))
    pause_click = False
    try:
        await page.goto(link)
        # pause_click = False
        requestResult = asyncio.create_task(wait_for_request(file_name, page, video))   

        # await asyncio.sleep(320)
        for i in range(10):
            if not video.m3u8 and not requestResult.done():
                await asyncio.sleep(1)

            # pauseButton = await page.query_selector('.jw-media.jw-reset')
            # time.sleep(160)
            # await page.click('body')
            await page.mouse.click(3, 300)
            await page.wait_for_timeout(500)
            # await page.mouse.click(1, 500)

            # await page.wait_for_timeout(1000)


            # try mute
            mute_element = await page.query_selector(f'[aria-label="Mute button"]')
            if mute_element and not mute_clicked:
                await mute_element.click()


            playButton = await page.query_selector('.play-video')
            if playButton and not pause_click:
                await playButton.click()
                await page.wait_for_timeout(3000)
                await playButton.click()
                pause_click = True


            if video.m3u8 != None:
                break
            
            
            # print(f"{video.episode_number} = {i}")
            
        if video.m3u8 == None:
        # await page.wait_for_timeout(3000)
            await handle_failed_videos(file_name, video, video_queue)
            # print(f"Exiting loop - calling handle_failed_video {video.episode_number}")

        await page.close()
        return True
    except Exception as e:
        try:
            await page.close()
        except:
            pass

        await handle_failed_videos(file_name, video, video_queue)
        print(e)
        return False




async def process_episodes(context, video_queue, file_name):
    while not video_queue.empty():
        video = await video_queue.get()
        page = await context.new_page()
        await automation(file_name, page, video, video_queue, context)
    remove_duplicate_lines(file_name)

prev_file_name = ''
async def main(link, numThreads = 1):
    async with async_playwright() as playwright:
        video_queue = asyncio.Queue()
        global all_vidoes
        browser = await playwright.firefox.launch()
        context = await browser.new_context()
        file_name = await sort_urls(await context.new_page(), link)
        # while prev_file_name == file_name:
        #     print('Waiting for new file name')
        #     await asyncio.sleep(2)
        # prev_file_name == file_name

        for video in all_vidoes:
            if not await check_if_exist(file_name, video):
                await video_queue.put(video)

        # Create tasks
        tasks = [process_episodes(context, video_queue, file_name) for _ in range(numThreads)]

        await asyncio.gather(*tasks)
        all_vidoes = []
        remove_duplicate_lines(file_name)
        await context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process links.')
    parser.add_argument('-f', '--file', help='Path to file containing links')

    args = parser.parse_args()

    if args.file:
        with open(args.file, 'r') as file:
            links = file.readlines()
            numThreads = int(input("Threads: "))
            for link in links:
                asyncio.run(main(link.strip(), numThreads))  # Strip newline characters and process each link
    else:

        try:
            link = input("Enter link: ")
            # link = 'https://goone.pro/videos/tearmoon-teikoku-monogatari-dantoudai-kara-hajimaru-hime-no-tensei-gyakuten-story-episode-2'
            numThreads = int(input("Threads: "))
        except Exception as e:
            print(e)
            exit(1)

        asyncio.run(main(link, numThreads))

    # asyncio.run(main())
