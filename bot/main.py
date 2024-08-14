from os import getenv
import sys
from datetime import timedelta, datetime
import random
import re
from telethon import functions
from telethon import TelegramClient, events, Button as button
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
import logging
from functools import wraps
from db import Session, Main

load_dotenv()
api_hash = getenv('api_hash')
api_id = getenv('api_id')
bot_token = getenv('bot_token')

client = TelegramClient('bot_session', api_id, api_hash).start(bot_token=bot_token)
scheduler = AsyncIOScheduler()

current_user_state = {}

character_images = {
    25: 'bot/imgs/25.gif',
    50: 'bot/imgs/50.gif',
    75: 'bot/imgs/75.gif',
    100: 'bot/imgs/100.gif',
}

monsters_images = [
                    'bot/imgs/monsters/1.png', 'bot/imgs/monsters/2.png', 'bot/imgs/monsters/3.png', 'bot/imgs/monsters/4.png', 'bot/imgs/monsters/5.png', 'bot/imgs/monsters/6.png', 'bot/imgs/monsters/7.png', 'bot/imgs/monsters/8.png', 'bot/imgs/monsters/9.png', 'bot/imgs/monsters/10.png', 'bot/imgs/monsters/11.png', 'bot/imgs/monsters/12.png', 'bot/imgs/monsters/13.png', 'bot/imgs/monsters/14.png', 'bot/imgs/monsters/15.png', 'bot/imgs/monsters/16.png', 'bot/imgs/monsters/17.png', 'bot/imgs/monsters/18.png', 'bot/imgs/monsters/19.png', 'bot/imgs/monsters/20.png', 'bot/imgs/monsters/21.gif'
]


log_filename = 'bot_logs.log'
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)


console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)


def log_function(func):
    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        user_id = event.sender_id
        user_name = (await event.get_sender()).first_name
        logger.info(f"[{user_name} ({user_id})] Розпочав виконання функції: {func.__name__}")

        try:
            result = await func(event, *args, **kwargs)
            logger.info(f"[{user_name} ({user_id})] Успішно завершив виконання функції: {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"[{user_name} ({user_id})] Помилка при виконанні функції: {func.__name__} - {e}")
            raise

    return wrapper



def update_character_image(progress):
    if progress < 50:
        return character_images[25]
    elif 50 <= progress < 66:
        return character_images[50]
    elif 66 <= progress < 100:
        return character_images[75]
    else:
        return character_images[100]

def calculate_progress(completed_tasks_count, total_tasks_count):
    if total_tasks_count == 0:
        return 0
    progress = (completed_tasks_count / total_tasks_count) * 100
    return round(progress, 2)

@client.on(events.NewMessage(pattern='/start'))
@log_function
async def start(event):
    global sender
    sender = await event.get_sender()
    first_name = sender.first_name
    enter_tasks = [
        [button.inline("Ввести теми", b'enter_tasks')],
        [button.inline("Видалити тему", b'delete')],
        [button.inline("Відмітити як виконані", b'completed_tasks')]
    ]
    start_hero = 'bot/imgs/start.png'
    await client.send_file(event.chat_id, start_hero, caption=f'Привіт, {first_name}! Зверху твій персонаж, якщо хочеш його прокращити та стати продуктивніше - заходь частіше!\nЦей бот створений для введення своїх тасків, їх відстежування, видалення.\nГоловна фішка цього бота - гейміфікфція щоб використання бота було цікавим та захоплюючим.\nby @big_pencil19 & @penoplastiz', buttons=enter_tasks)
    try:
        await client(functions.channels.ToggleAntiSpamRequest(
            channel=event.chat_id,
            enabled=True
        ))
        logger.info(f"Антиспам ввімкнен для бота {event.chat_id}")
    except Exception as e:
        logger.error(f"Не вдалося включити антиспам: {str(e)}")
    
    with Session() as session:
        user = session.query(Main).filter(Main.id == sender.id).first()
        if user:
            user.owner = first_name
        else:
            user = Main(id=sender.id, owner=first_name, tasks='', due_dates='', experience=0, progress=0)
            session.add(user)
        session.commit()

@client.on(events.CallbackQuery(pattern=b'enter_tasks'))
@log_function
async def enter_tasks(event):
    await event.respond("Введи свої теми і дедлайни у форматі 'тема - дедлайн(рррр/мм/дд)',\nТема не може містити спец символи по типу +=*\nрозділені ; ")
    current_user_state[event.sender_id] = 'waiting_for_tasks'

@client.on(events.CallbackQuery(pattern=b'delete'))
@log_function
async def delete_task(event):
    await event.respond("Введи назву теми для видалення: ")
    current_user_state[event.sender_id] = 'waiting_for_task_deletion'

@client.on(events.CallbackQuery(pattern=b'completed_tasks'))
@log_function
async def completed_tasks(event):
    await event.respond("Введи ті теми, які ти пройшов, розділені ; ")
    current_user_state[event.sender_id] = 'waiting_for_completed_tasks'

@client.on(events.NewMessage(pattern='/commands'))
@log_function
async def send_all_commands(event):
    await event.respond('''
/set_time - зазначити час нагадувань (чч:хх)
/my_tasks - всі задачі
/show_exp - показати ваш досвід
/difficulty - задати рівень складності(1-3)
/start - запуск
''')
    

@client.on(events.NewMessage(pattern='/my_tasks'))
@log_function
async def show_tasks(event):
    user_id = event.sender_id

    with Session() as session:
        user = session.query(Main).filter(Main.id == user_id).first()
        if user and user.tasks:
            tasks = user.tasks.split('; ')
            due_dates = user.due_dates.split('; ')

            valid_tasks_with_dates = []
            for task, due_date in zip(tasks, due_dates):
                try:
                    parsed_date = datetime.strptime(due_date, '%Y/%m/%d')
                    valid_tasks_with_dates.append((task, due_date))
                except ValueError:
                    continue


            tasks_with_dates_sorted = sorted(valid_tasks_with_dates, key=lambda x: datetime.strptime(x[1], '%Y/%m/%d'))

            task_list = '\n'.join([f'{task} - {due_date}' for task, due_date in tasks_with_dates_sorted])
            await event.respond(f'Ось ваші теми:\n{task_list}')
        else:
            await event.respond("У вас немає запланованих тем.")




@client.on(events.NewMessage(pattern='/set_time'))
@log_function
async def set_time(event):
    user_input = event.text.split()
    if len(user_input) == 2:
        time_parts = user_input[1].split(':')
        if len(time_parts) == 2 and time_parts[0].isdigit() and time_parts[1].isdigit():
            hours = int(time_parts[0])
            minutes = int(time_parts[1])


            hours = (hours - 3) % 24

            if 0 <= hours < 24 and 0 <= minutes < 60:
                user_id = event.sender_id
                reminder_time = f'{hours:02d}:{minutes:02d}'

                with Session() as session:
                    user = session.query(Main).filter(Main.id == user_id).first()
                    if user:
                        user.reminder_time = reminder_time
                        session.commit()

                job_id = f'reminder_{user_id}'
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)

                scheduler.add_job(
                    send_user_reminder,
                    CronTrigger(hour=hours, minute=minutes),
                    args=[user_id],
                    id=job_id
                )

                await event.respond(f'Час нагадування встановлено корректно')
            else:
                await event.respond("Некоректний час. Переконайтеся, що години від 0 до 23, а хвилини від 0 до 59")
        else:
            await event.respond("Введіть час у форматі ГГ:ХХ, наприклад /set_time 14:30")
    else:
        await event.respond("Введіть команду у форматі /set_time ГГ:ХХ, наприклад /set_time 14:30")



@client.on(events.NewMessage())
@log_function
async def handle_message(event):
    user_id = event.sender_id

    if user_id in current_user_state:
        state = current_user_state[user_id]

        if state == 'waiting_for_tasks':
            tasks_input = event.text
            new_tasks = []
            new_due_dates = []
            valid_input = True

            pattern = re.compile(r'^([\w\s]+)\s*-\s*(\d{4}/\d{2}/\d{2})$|^([\w\s]+)-(\d{4}/\d{2}/\d{2})$')

            for item in tasks_input.split(';'):
                item = item.strip()
                match = pattern.match(item)
                if match:
                    if match.group(1) and match.group(2):
                        task, due_date = match.group(1).strip(), match.group(2).strip()
                    elif match.group(3) and match.group(4):
                        task, due_date = match.group(3).strip(), match.group(4).strip()
                    else:
                        valid_input = False
                        await event.respond(f"Некорректний формат ввода для елемента: '{item}'")
                        return
                    new_tasks.append(task)
                    new_due_dates.append(due_date)
                else:
                    valid_input = False
                    await event.respond(f"Некорректний формат ввода для елемента: '{item}'")
                    return

            if valid_input:
                with Session() as session:
                    user = session.query(Main).filter(Main.id == user_id).first()
                    if user:
                        existing_tasks = user.tasks.split('; ') if user.tasks else []
                        existing_due_dates = user.due_dates.split('; ') if user.due_dates else []

                        all_tasks = existing_tasks + new_tasks
                        all_due_dates = existing_due_dates + new_due_dates

                        tasks_with_dates_sorted = sorted(zip(all_tasks, all_due_dates), key=lambda x: datetime.strptime(x[1], '%Y/%m/%d'))

                        sorted_tasks, sorted_due_dates = zip(*tasks_with_dates_sorted)

                        user.tasks = '; '.join(sorted_tasks)
                        user.due_dates = '; '.join(sorted_due_dates)
                        session.commit()

                del current_user_state[user_id]

                await event.respond(f'Список тем оновлено:\n' +
                                    '\n'.join([f'{task} - {due_date}' for task, due_date in zip(sorted_tasks, sorted_due_dates)]))






        elif state == 'waiting_for_task_deletion':
            task_to_remove = event.text.strip().casefold()

            with Session() as session:
                user = session.query(Main).filter(Main.id == user_id).first()
                if user:
                    existing_tasks = user.tasks.split('; ') if user.tasks else []
                    existing_due_dates = user.due_dates.split('; ') if user.due_dates else []

                    normalized_tasks = [task.casefold() for task in existing_tasks]

                    if task_to_remove in normalized_tasks:
                        index = normalized_tasks.index(task_to_remove)
                        original_task = existing_tasks[index]
                        existing_tasks.pop(index)
                        existing_due_dates.pop(index)
                        user.tasks = '; '.join(existing_tasks)
                        user.due_dates = '; '.join(existing_due_dates)
                        session.commit()
                        response = f'Тема "{original_task}" видалена.'
                    else:
                        response = f'Тема "{task_to_remove}" не знайдена.'
                else:
                    response = "Користувач не знайден."

            del current_user_state[user_id]

            await event.respond(response)
        elif state == 'waiting_for_completed_tasks':
            completed_tasks_input = event.text.strip()
            completed_tasks = [task.strip().lower() for task in completed_tasks_input.split(';')]

            with Session() as session:
                user = session.query(Main).filter(Main.id == user_id).first()
                if user:
                    existing_tasks = user.tasks.split('; ') if user.tasks else []
                    existing_due_dates = user.due_dates.split('; ') if user.due_dates else []


                    normalized_tasks = [task.lower() for task in existing_tasks]
                    

                    indices_to_remove = [normalized_tasks.index(task) for task in completed_tasks if task in normalized_tasks]

                    if indices_to_remove:
                        for index in sorted(indices_to_remove, reverse=True):
                            del existing_tasks[index]
                            del existing_due_dates[index]
                        user.tasks = '; '.join(existing_tasks)
                        user.due_dates = '; '.join(existing_due_dates)

                        user.experience += len(indices_to_remove) * 10

                        completed_tasks_count = len(completed_tasks)
                        total_tasks_count = len(existing_tasks) + completed_tasks_count

                        user.progress = calculate_progress(completed_tasks_count, total_tasks_count)

                        session.commit()

                        progress_percentage = user.progress
                        progress_message = f"Ви виконали {progress_percentage}% завдань."

                        await event.respond(
                            f'Теми {completed_tasks_input} відмічені як виконані. Ось оновлений список:\n' +
                            '\n'.join([f'{task} - {due_date}' for task, due_date in zip(existing_tasks, existing_due_dates)]) +
                            f'\n\n{progress_message}'
                        )

                        character_image_path = update_character_image(user.progress)
                        await client.send_file(user_id, character_image_path, caption="Ти вже непогано прокачався")

                    else:
                        await event.respond("Жодна з введених тем не знайдена в вашому списку.")
                else:
                    await event.respond("Користувач не знайден.")

            del current_user_state[user_id]

@client.on(events.NewMessage(pattern='/show_exp'))
async def show_experience(event):
    user_id = event.sender_id

    with Session() as session:
        user = session.query(Main).filter(Main.id == user_id).first()
        if user:
            enter_tasks = [
                [button.inline("Ввести теми", b'enter_tasks')],
                [button.inline("Видалити тему", b'delete')],
                [button.inline("Відмітити як виконані", b'completed_tasks')]
            ]
            await event.respond(f'Ваш поточний досвід: {user.experience} балів.', buttons = enter_tasks)
        else:
            await event.respond("Користувач не знайден.")

difficulty_levels = {1: 10, 2: 15, 3: 20}


@client.on(events.NewMessage(pattern='/difficulty'))
async def set_difficulty(event):
    user_id = event.sender_id
    user_input = event.text.split()

    if len(user_input) == 2 and user_input[1].isdigit():
        difficulty_level = int(user_input[1])

        if difficulty_level in [1, 2, 3]:
            current_user_state[user_id] = {'difficulty': difficulty_level}
            await event.respond(f'Рівень складності заданий на {difficulty_level}.')
        else:
            await event.respond("Рівень скоадності повинен бути 1 / 2 / 3.\n1 = -10exp\n2 = -15exp\n20 = -20exp")
    else:
        await event.respond("Введіть команду у форматі: /difficulty [1|2|3]")



async def send_user_reminder(user_id):
    now = datetime.now().date()
    previous_day = now - timedelta(days=1)

    with Session() as session:
        user = session.query(Main).filter(Main.id == user_id).first()
        if user:
            missed_tasks = []
            if user.due_dates:
                due_dates = user.due_dates.split('; ')
                tasks = user.tasks.split('; ')

                for due_date_str, task in zip(due_dates, tasks):
                    due_date = datetime.strptime(due_date_str, '%Y/%m/%d').date()
                    if due_date == previous_day:
                        missed_tasks.append(task)

            if missed_tasks:
                missed_tasks_list = '\n'.join(missed_tasks)
                
                user_difficulty = current_user_state.get(user_id, {}).get('difficulty', 1)
                exp_deduction = difficulty_levels.get(user_difficulty, 10)

                user.experience -= exp_deduction
                if user.experience < 0:
                    user.experience = 0
                    session.commit()
                    game_over_image = 'bot/imgs/game_over.jpg' 
                    await client.send_message(
                        user_id,
                        f'Ви пропустили тему за {previous_day}:\n{missed_tasks_list}\nМонстр це виявив та зняв у вас {exp_deduction} exp.\nТепер в тебе: {user.experience} exp.',
                        file=game_over_image
                    )
                else:
                    session.commit()
                    monster = random.choice(monsters_images)
                    await client.send_message(
                        user_id,
                        f'Ви пропустили тему за {previous_day}:\n{missed_tasks_list}\nМонстр це виявив та зняв у вас {exp_deduction} exp.\nТепер в тебе: {user.experience} exp.',
                        file=monster
                    )
            else:
                await client.send_message(
                    user_id,
                    "Не забудьте перевірити свої завдання!"
                )


scheduler.start()
client.run_until_disconnected()