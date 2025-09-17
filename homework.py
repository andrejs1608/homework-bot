import logging
import os
import time

import requests
from dotenv import load_dotenv
from telebot import TeleBot


load_dotenv()

PRACTICUM_TOKEN = os.getenv('practicum_token')
TELEGRAM_TOKEN = os.getenv('telegram_token')
TELEGRAM_CHAT_ID = os.getenv('chat_id')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности токенов"""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = []
    for token_name, token_value in tokens.items():
        if not token_value:
            missing_tokens.append(token_name)
            logger.error(f'Отсутствует обязательный токен: {token_name}')

    if missing_tokens:
        logger.error(
            f'Отсутствуют обязательные токены: {", ".join(missing_tokens)}'
        )
        raise ValueError('Доступны не все обязательные токены')


def send_message(bot, message):
    """Отправка сообщений в Telegram"""
    logger.debug('Отправка сообщения')
    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message
    )
    logger.debug('Сообщение отправлено')


def get_api_answer(timestamp):
    """Получение ответа API"""
    logger.debug(f'Отправка запроса {ENDPOINT}, время {timestamp}')
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        response.raise_for_status()
    except requests.RequestException as error:
        logger.error(f'Ошибка при запросе к основному API: {error}')
        raise
    try:
        response_data = response.json()
    except ValueError as error:
        logger.error(f'Ошибка парсинга JSON ответа: {error}')
        raise
    logger.debug('Ответ от API получен')
    return response_data


def check_response(response):
    """Проверка ответа API на соответствие документации"""
    logger.debug('Начало проверки ответа API.')
    if not isinstance(response, dict):
        raise TypeError(
            f'Не верный тип данных: {type(response)}'
        )
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homeworks" в ответе API.')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'Не верный формат данных с ключом "homeworks": {type(homeworks)}.'
        )
    logger.debug('Завершение проверки ответа API.')


def parse_status(homework):
    """Извлечение статуса домашней работы"""
    logger.debug('Начало извлечения статуса домашней работы.')
    if not isinstance(homework, dict):
        raise TypeError(f'Не верный формат homework: {type(homework)}')
    if 'status' not in homework:
        raise KeyError('Отсутствует обязательное поле: status')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует обязательное поле: homework_name')
    homework_status = homework['status']
    homework_name = homework['homework_name']
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус домашней работы: {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    message = f'Статус проверки {homework_name} изменился: {verdict}'
    logger.debug('Статус домашней работы успешно извлечен')
    return message


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    latest_homework_status = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks', [])
            latest_homework = homeworks[0]
            current_status = parse_status(latest_homework)
            if current_status != latest_homework_status:
                send_message(bot, current_status)
                latest_homework_status = current_status
                logger.info('Сообщение о новом статусе отправлено.')
            else:
                logger.info('Статус домашней работы не изменился')
            timestamp = response.get('current_date', int(time.time()))
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_error_message:
                try:
                    send_message(bot, message)
                    last_error_message = message
                except Exception as send_error:
                    logger.error(f'Не удалось отправить сообщение об ошибке: {send_error}')
        logger.debug(f'Ожидание {RETRY_PERIOD} секунд перед следующей проверкой')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
