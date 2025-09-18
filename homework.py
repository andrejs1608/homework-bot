import logging
import os
import requests
import time

from http import HTTPStatus
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
    """Проверка доступности токенов."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = []
    for token_name, token_value in tokens.items():
        if not token_value:
            missing_tokens.append(token_name)
            logger.critical(f'Отсутствует обязательный токен: {token_name}')

    if missing_tokens:
        logger.critical(
            f'Отсутствуют обязательные токены: {", ".join(missing_tokens)}'
        )
        raise ValueError('Доступны не все обязательные токены')


def send_message(bot, message):
    """Отправка сообщений в Telegram."""
    logger.debug('Отправка сообщения')
    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message
    )
    logger.debug('Сообщение отправлено')


def get_api_answer(timestamp):
    """Получение ответа API."""
    logger.debug(f'Отправка запроса {ENDPOINT}, время {timestamp}')
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        response_status = response.status_code
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка при запросе к API: {error}')
    response_data = response.json()
    if response_status != HTTPStatus.OK:
        raise ValueError(f'Ошибка парсинга JSON ответа: {error}')
    logger.debug('Ответ от API получен')
    return response_data


def check_response(response):
    """Проверка ответа API на соответствие документации."""
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
    latest_homework_status = ''
    last_error_message = ''
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
                    logger.error(
                        f'Не удалось отправить сообщение: {send_error}'
                    )
        logger.debug(
            f'Ожидание {RETRY_PERIOD} секунд перед следующей проверкой'
        )
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()


#  +  where False = <built-in method startswith of str object at 0x7f106308b0f0>('Изменился статус проверки работы "Homework test"')
#  +    where <built-in method startswith of str object at 0x7f106308b0f0> = 'Статус проверки Homework test изменился: Работа проверена: ревьюеру всё понравилось. Ура!'.startswith
# FAILED tests/test_bot.py::TestHomework::test_main_without_env_vars_raise_exception - AssertionError: Убедитесь, что при отсутствии обязательных переменных окружения событие логируется с уровнем `CRITICAL`.
# ========================= 4 failed, 21 passed in 0.26s ======