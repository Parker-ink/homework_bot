from http import HTTPStatus
import json
import os
import requests
import logging
import time
import sys

import telegram

from dotenv import load_dotenv

from exceptions import ResponseNotOK
load_dotenv()

logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('STUDENT_TOKEN')
TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат.
    определяемый переменной окружения TELEGRAM_CHAT_ID.
    """
    logger.info('Пытаюсь отправить сообщение')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError:
        logger.error('Ошибка отправки сообщения')
    else:
        logger.info('Сообщение отправлено!')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as error:
        raise ResponseNotOK(f'Ошибка при запросе к API: {error}')
    if response.status_code != HTTPStatus.OK:
        status_code = response.status_code
        raise Exception(f'Ошибка {status_code}')
    try:
        return response.json()
    except json.JSONDecodeError:
        raise json.JSONDecodeError


def check_response(response):
    """Проверяет ответ API на корректность."""
    if response['homeworks'] == []:
        text = 'Получен пустой список работ'
        raise TypeError(text)
    elif 'homeworks' not in response:
        text = 'В полученном словаре отсутствует "homeworks"'
        raise ValueError(text)
    homeworks = response['homeworks']
    if homeworks[0] is None:
        text = 'Отсутсвует список работ'
        raise ValueError(text)
    elif not isinstance(homeworks[0], dict):
        text = f'Ошибка типа! {homeworks} не словарь'
        raise TypeError(text)
    else:
        return homeworks


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы.
    В качестве параметра функция получает только один элемент
    из списка домашних работ.
    """
    if 'status' not in homework:
        raise KeyError('Отсутствует "status" в ответе API')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует "homework_name" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError(f'Неизвестный статус домашки: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения.
    которые необходимы для работы программы.
    """
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют токены')
        sys.exit(1)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    start_message = 'Бот начал свою работу!'
    send_message(bot, start_message)
    current_timestamp = int(time.time())
    status_message = ''
    error_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                status = parse_status(homework)
                if homework['status'] == 'approved':
                    current_timestamp = int(time.time())
                if status != status_message:
                    send_message(bot, status)
                    status_message = status
                else:
                    info = f'Статус не изменился. Ждем еще {RETRY_TIME} сек.'
                    logger.debug(info)
        except Exception as error:
            logger.error(error)
            message = f'Сбой в работе программы: {error}'
            if message != error_message:
                send_message(bot, message)
                error_message = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
        handlers=[logging.StreamHandler()]
    )
    main()
