import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiException

from exceptions import MissingTokenError, InvalidResponseError


load_dotenv()

PRACTICUM_TOKEN = os.getenv('practicum_token')
TELEGRAM_TOKEN = os.getenv('telegram_token')
TELEGRAM_CHAT_ID = os.getenv('chat_id')

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
    """Проверка доступности токенов."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = [
        token_name for token_name, token_value in tokens.items()
        if not token_value
    ]
    if missing_tokens:
        logger.critical(
            f'Отсутствуют обязательный токен: {", ".join(missing_tokens)}'
        )
        raise MissingTokenError('Доступны не все обязательные токены')


def send_message(bot, message):
    """Отправка сообщений в Telegram."""
    logger.debug('Отправка сообщения')
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.debug('Сообщение отправлено')
        return True
    except (ApiException, requests.RequestException) as error:
        logger.error(f'Ошибка при отправке сообщения в Telegram: {error}')
        return False


def get_api_answer(timestamp):
    """Получение ответа API."""
    logger.debug(f'Отправка запроса {ENDPOINT}, время {timestamp}')
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка соединения с API: {error}')
    response_status = response.status_code
    if response_status == HTTPStatus.OK:
        logger.debug('Ответ от API получен')
        response_data = response.json()
        # Тесты требуют возвращать словарь, я без понятия, зачем он тут
        return response_data
    raise InvalidResponseError(f'Невалидный ответ: {response_status}')


def check_response(response):
    """Проверка ответа API."""
    logger.debug('Начало проверки ответа API.')
    if not isinstance(response, dict):
        raise TypeError(
            f'Неверный тип данных: {type(response)}'
        )
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homeworks" в ответе API.')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'Неверный формат данных с ключом "homeworks": {type(homeworks)}.'
        )
    logger.debug('Завершение проверки ответа API.')
    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
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
        raise ValueError(
            f'Неизвестный статус домашней работы: {homework_status}'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    logger.debug('Статус домашней работы успешно извлечен')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                latest_homework = homeworks[0]
                current_status = parse_status(latest_homework)

                if send_message(bot, current_status):
                    timestamp = response.get('current_date', int(time.time()))
                    logger.info('Сообщение успешно отправлено')
                else:
                    logger.error('Не удалось отправить сообщение')
            else:
                logger.debug('Нет новых домашних работ для проверки')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_error_message:
                logger.error(f'Обнаружена новая ошибка: {message}')
                last_error_message = message
        finally:
            logger.debug(
                f'Ожидание {RETRY_PERIOD} секунд перед следующей проверкой'
            )
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    stream_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    stream_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(stream_handler)

    main()


# FAILED tests/test_bot.py::TestHomework::test_get_api_answers - AssertionError: Проверьте, что функция `get_api_answer` возвращает словарь.
# assert False
#  +  where False = isinstance(<HTTPStatus.OK: 200>, dict)
# FAILED tests/test_bot.py::TestHomework::test_main_check_response_is_called - AssertionError: Убедитесь, что для проверки ответа API домашки бот использует функцию `check_response`.
# assert []
# FAILED tests/test_bot.py::TestHomework::test_main_send_message_with_new_status - AssertionError: Убедитесь, что при изменении статуса домашней работы бот отправляет в Telegram сообщение с вердиктом из переменной `HOMEWORK_VERDICTS`.
# assert []