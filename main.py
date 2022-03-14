from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains

import random
import json
import time
import re
import os


def main() -> None:
    with open('config.json', 'r', encoding='utf-8') as file:
        config = json.load(file)

    options = webdriver.ChromeOptions()
    options.binary_location = config['binary_location']
    options.headless = config['headless_browser']

    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument(f'window-size={config["window_size"]}')
    options.add_argument(f'user-agent={config["user_agent"]}')

    with webdriver.Chrome(executable_path=config['executable_path'], options=options) as browser:
        browser.maximize_window()

        if check_cookies():
            print('Session valid, continue...')
            login_by_cookies(browser)
            save_cookies(browser)
        else:
            print('Session invalid, please login again')
            login_by_password(browser, input('Login: '), input('Password: '), config["short_delay"])
            save_cookies(browser)

        print('Start auto participation')
        start_auto_participation(browser, config["short_delay"], config["long_delay"], config["captcha_tries"])


def check_cookies() -> bool:
    if os.path.exists('cookies.json'):
        with open('cookies.json', 'r', encoding='utf-8') as file:
            cookie_user = json.load(file)[0]

            if cookie_user['expiry'] > time.time():
                return True

    return False


def login_by_cookies(driver) -> None:
    with open('cookies.json', 'r', encoding='utf-8') as file:
        cookies = json.load(file)

    driver.get('https://lolz.guru')
    for cookie in cookies:
        driver.add_cookie(cookie)

    driver.refresh()


def login_by_password(driver, login: str, password: str, short_delay: list) -> None:
    driver.get('https://lolz.guru/login/')
    WebDriverWait(driver, 10).until(lambda x: x.find_element(By.CSS_SELECTOR, '#ctrl_pageLogin_login'))

    driver.find_element(By.CSS_SELECTOR, '#ctrl_pageLogin_login').send_keys(login)
    time.sleep(random.randrange(*short_delay))
    driver.find_element(By.CSS_SELECTOR, '#ctrl_pageLogin_password').send_keys(password)
    time.sleep(random.randrange(*short_delay))
    driver.find_element(By.CSS_SELECTOR, '#ctrl_pageLogin_password').send_keys(Keys.ENTER)
    time.sleep(random.randrange(*short_delay))


def save_cookies(driver) -> None:
    driver.get('https://lolz.guru/')
    cookies = driver.get_cookies()

    cookies_for_save = []
    session_cookies = {
        'xf_user': None,
        'xf_session': None,
        'xf_logged_in': None
    }

    for cookie in cookies:
        if cookie['name'] in ('xf_user', 'xf_session', 'xf_logged_in'):
            if session_cookies[cookie['name']] is None:
                session_cookies[cookie['name']] = cookie

            elif cookie.get('expiry', 1) > session_cookies[cookie['name']].get('expiry', 0):
                session_cookies[cookie['name']] = cookie

    for key in session_cookies:
        cookies_for_save.append(session_cookies[key])

    with open('cookies.json', 'w', encoding='utf-8') as file:
        json.dump(cookies_for_save, file, indent=4)

    print('Session updated and saved')


def start_auto_participation(driver, short_delay: list, long_delay: list, captcha_tries: int) -> None:
    while True:
        new_draws_urls = get_new_draws(get_pages_contests(driver, short_delay))
        for draw_url in new_draws_urls:
            take_part(driver, short_delay, draw_url, captcha_tries)

        print('Участие принято во всех новых розыгрышах, ожидаю следующую итерацию')
        time.sleep(random.randrange(*long_delay))


def get_pages_contests(driver, short_delay: list) -> list:
    print('Начинаю парсить страницы розыгрышей')
    url_contests = 'https://lolz.guru/forums/contests/page-'
    pages_sources = []

    for i in range(1, 9999):
        last_page = url_contests + str(i - 1)
        new_page = url_contests + str(i)
        driver.get(new_page)

        if driver.current_url == last_page:
            break

        time.sleep(random.randrange(*short_delay))
        pages_sources.append(driver.page_source)

    return pages_sources


def get_new_draws(pages_sources: list) -> list:
    unread_threads = []
    unread_threads_urls = []

    for page_source in pages_sources:
        soup = BeautifulSoup(page_source, 'lxml')
        unread_threads.extend(soup.find_all('div', id=re.compile('thread'), class_='unread'))

    for unread_thread in unread_threads:
        if unread_thread.find_all('a')[-1].find('h3').find('i') is None:
            thread_id = unread_thread.get("id")[7:]
            unread_threads_urls.append('https://lolz.guru/threads/' + thread_id)

    print('Страницы спаршены на наличие новых розыгрышей')
    return unread_threads_urls


def take_part(driver, short_delay: list, draw_url: str, captcha_tries: int) -> None:
    if draw_url == 'refresh':
        driver.refresh()
        time.sleep(random.randrange(*short_delay))
        print('Получаю другую капчу, эту может не засчитать')
    else:
        driver.get(draw_url)
        time.sleep(random.randrange(*short_delay))
        print('Принимаю участие в розыгрыше:', draw_url)

    soup = BeautifulSoup(driver.page_source, 'lxml')
    captcha_block = soup.find('div', class_='captchaBlock')

    if captcha_block is None:
        error = soup.find('div', class_=re.compile('error'))
        if error is None:
            error = soup.find('span', class_='button contestIsFinished disabled')
            if error is None:
                error = soup.find('span', class_='LztContest--alreadyParticipating')
                if error is None:
                    print('Участие не принято: Неизвестная ошибка')
                else:
                    print('Участие уже было принято')
            else:
                print('Участие не принято:', error.text.strip())
        else:
            print('Участие не принято:', error.text.strip())
    else:
        save_captcha_images(driver, short_delay, get_captcha_src(captcha_block), captcha_block)
        answer_coord = get_answer_coord()

        if answer_coord <= 30:
            take_part(driver, short_delay, 'refresh', captcha_tries)

        solve_captcha(driver, short_delay, captcha_tries, answer_coord)


def get_captcha_src(captcha_block) -> list:
    template_src = captcha_block.find('img', style=re.compile('top:'))['src']
    list_captcha_img = captcha_block.find_all('img')
    list_captcha__src = []

    for captcha_img in list_captcha_img:
        list_captcha__src.append(captcha_img['src'])

    list_captcha__src.remove(template_src)
    list_captcha__src.append(template_src)

    return list_captcha__src


def save_captcha_images(driver, short_delay: list, list_captcha__src: list, captcha_block) -> None:
    search = driver.find_element(By.XPATH, '//*[@id="searchBar"]/fieldset/form/div[1]/input')
    search.send_keys(Keys.ENTER)
    time.sleep(random.randrange(*short_delay))
    driver.switch_to.window(driver.window_handles[1])

    driver.get(list_captcha__src[1])
    time.sleep(random.randrange(*short_delay))
    driver.save_screenshot("captcha/template.png")

    driver.get(list_captcha__src[0])
    time.sleep(random.randrange(*short_delay))
    driver.save_screenshot("captcha/image.png")

    driver.close()
    driver.switch_to.window(driver.window_handles[0])

    puzzle_offset = int(captcha_block.find('img', style=re.compile('top:'))['style'][5:-3])
    Image.open('captcha/template.png').crop((945, 466, 975, 496)).save('captcha/template.png')
    Image.open('captcha/image.png').crop((810, 381+puzzle_offset, 1110, 411+puzzle_offset)).save('captcha/image.png')

    template_rgb = Image.open("captcha/template.png").convert('RGBA')
    template_bi = Image.open("captcha/template.png").convert('L').point(lambda x: 255 if x >= 127 else 0, mode='1')

    rgb_pixels_data = list(template_rgb.getdata())
    bi_pixels_data = list(template_bi.convert('RGBA').getdata())

    for i, pixel in enumerate(bi_pixels_data):
        if pixel[:3] == (255, 255, 255):
            bi_pixels_data[i] = (0, 0, 0)
        elif pixel[:3] == (0, 0, 0):
            bi_pixels_data[i] = (255, 255, 255)

    for i, pixel in enumerate(rgb_pixels_data):
        if pixel[:3] == (230, 230, 230):
            bi_pixels_data[i] = (255, 255, 255, 0)

    template_rgb.putdata(bi_pixels_data)
    template_rgb.save("captcha/template.png")

    image_bi = Image.open("captcha/image.png").convert('L').point(lambda x: 255 if x >= 127 else 0, mode='1')
    bi_pixels_data = list(template_bi.convert('RGB').getdata())
    image_bi.putdata(bi_pixels_data)
    image_bi.save("captcha/image.png")


def solve_captcha(driver, short_delay: list, captcha_tries: int, answer_coord: int) -> None:
    if answer_coord <= 100:
        speed = random.randrange(3, 5)
    else:
        speed = random.randrange(5, 7)

    iterations = answer_coord // speed
    accuracy = answer_coord % speed - 1

    captcha_block = driver.find_element(By.CLASS_NAME, 'captchaBlock')
    slider = captcha_block.find_element(By.TAG_NAME, 'svg').find_element(By.XPATH, '..').find_element(By.XPATH, '..')

    action = ActionChains(driver)
    action.click_and_hold(slider)

    for i in range(iterations):
        action.move_by_offset(speed, 0)
    for i in range(accuracy):
        action.move_by_offset(1, 0)

    action.move_by_offset(random.randrange(-1, 2), -1)
    action.move_by_offset(1, 0)
    action.release()
    action.perform()

    captcha_tries = captcha_tries - 1
    time.sleep(random.randrange(*short_delay))
    driver.refresh()
    time.sleep(random.randrange(*short_delay))

    soup = BeautifulSoup(driver.page_source, 'lxml')
    captcha_block = soup.find('div', class_='captchaBlock')

    if captcha_block is None:
        error = soup.find('div', class_=re.compile('error'))
        if error is None:
            error = soup.find('span', class_='button contestIsFinished disabled')
            if error is None:
                error = soup.find('span', class_='LztContest--alreadyParticipating')
                if error is None:
                    print('Участие не принято: Неизвестная ошибка')
                else:
                    print('Успешно:', error.find('span').text.strip())
            else:
                print('Участие не принято:', error.text.strip())
        else:
            print('Участие не принято:', error.text.strip())

    elif captcha_tries != 0:
        print('Капча не решена, осталось попыток:', captcha_tries)
        save_captcha_images(driver, short_delay, get_captcha_src(captcha_block), captcha_block)

        answer_coord = get_answer_coord()
        if answer_coord <= 30:
            take_part(driver, short_delay, 'refresh', captcha_tries)

        solve_captcha(driver, short_delay, captcha_tries, answer_coord)
    else:
        print('Участие не принято: по неизвестной причине не получись решить капчу за заданное количество попыток.')


def get_answer_coord() -> int:
    template = cv.imread('captcha/template.png')
    image = cv.imread('captcha/image.png')

    return cv.minMaxLoc(cv.matchTemplate(image, template, cv.TM_CCORR_NORMED))[3][0]


if __name__ == '__main__':
    main()
    # TODO отловить редкие баги, если таковые есть / баг с баном на 15 минут при неверном решении (улучши решение)/
    #  реализованно, оттестить более масштабно протестировать безголовый режим на обноружение и баги / фичи добавить
    #  прокси, перезапуск скрипта / фичи подумать над добовлением фермы / маловероятно добавить проверку галочки на
    #  розыгрыше как дополнительную проверку участия кроме анриад / реализованно, оттестить к ошибкам добавить
    #  розыгрыш закончился, вы уже участвуете, возможно найти еще варианты ошибок / реализованно, оттестить текущая
    #  реализация идеи - 99% функционал / 80% фичи / 70% рефакторинг
